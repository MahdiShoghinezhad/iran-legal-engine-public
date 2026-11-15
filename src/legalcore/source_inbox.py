"""Offline intake of owner-supplied source files with provenance and change alerts.

No network requests. Source URLs are claims, not verification. File-byte changes
are NOT automatically classified as legal amendments or published into the API.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import sqlite3
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from .evidence import attach_evidence, initialize_evidence
from .source_registry import get_source, initialize_source_registry, associate_evidence

DATASET_TYPE = "LEGAL_SOURCE_INBOX_V1"
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_RECORDS = 500
MAX_DIFF_BYTES = 256 * 1024
SCHEMA = """
CREATE TABLE IF NOT EXISTS source_inbox_observations (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 source_id TEXT NOT NULL REFERENCES legal_source_registry(id),
 instrument_id TEXT NOT NULL REFERENCES corpus_instruments(id),
 source_reference TEXT NOT NULL,
 observed_url TEXT NOT NULL,
 evidence_id INTEGER NOT NULL REFERENCES corpus_source_evidence(id),
 observed_sha256 TEXT NOT NULL,
 change_state TEXT NOT NULL CHECK(change_state IN ('FIRST_SEEN','UNCHANGED','CHANGED_BYTES')),
 created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_source_inbox_doc
 ON source_inbox_observations(source_id,instrument_id,source_reference,id DESC);
"""


def initialize_inbox(db: sqlite3.Connection) -> None:
    initialize_evidence(db)
    initialize_source_registry(db)
    db.executescript(SCHEMA)
    db.commit()


def _safe_file(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not 1 <= len(value) <= 240 or "\\" in value:
        raise ValueError("local_file must be a relative POSIX-style path")
    rel = PurePosixPath(value)
    if rel.is_absolute() or any(part in {".", "..", ""} for part in rel.parts):
        raise ValueError("local_file must stay inside the selected inbox")
    # Reject symlinks (including directory components), even if they point inside.
    candidate = root.joinpath(*rel.parts)
    for parent in [candidate, *list(candidate.parents)]:
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise ValueError("Symlinks are not permitted in the local inbox")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError("Local file escapes the selected inbox")
    if not candidate.is_file():
        raise ValueError("Local evidence file not found")
    return candidate


def _valid_row(row: object) -> dict:
    if not isinstance(row, dict):
        raise ValueError("Every inbox record must be an object")
    required = ("source_id", "instrument_id", "source_reference", "local_file", "observed_url")
    for key in required:
        value = row.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > (2048 if key == "observed_url" else 240):
            raise ValueError(f"Missing or invalid {key}")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", row["source_id"]):
        raise ValueError("Invalid source_id")
    parsed = urlsplit(row["observed_url"])
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.port is not None or parsed.fragment):
        raise ValueError("observed_url must be HTTPS without credentials, port or fragment")
    if row.get("snapshot_id") is not None and (type(row["snapshot_id"]) is not int or row["snapshot_id"] < 1):
        raise ValueError("snapshot_id must be a positive integer")
    return row


def load_inbox(path: str) -> tuple[Path, list[dict]]:
    manifest = Path(path).resolve()
    if not manifest.is_file() or manifest.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("Inbox manifest missing or too large")
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid inbox JSON") from exc
    if not isinstance(payload, dict) or payload.get("dataset_type") != DATASET_TYPE:
        raise ValueError(f"Expected dataset_type={DATASET_TYPE}")
    rows = payload.get("records")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_RECORDS:
        raise ValueError("Inbox must contain 1–500 records")
    keys = set()
    for row in rows:
        _valid_row(row)
        key = (row["source_id"], row["instrument_id"], row["source_reference"])
        if key in keys:
            raise ValueError("Duplicate source/instrument/reference tuple in one inbox manifest")
        keys.add(key)
    return manifest.parent, rows


def _source_matches(db: sqlite3.Connection, row: dict) -> None:
    source = get_source(db, row["source_id"])
    observed_host = urlsplit(row["observed_url"]).hostname
    if observed_host is None or observed_host.lower().removeprefix("www.") != source["site_host"].removeprefix("www."):
        raise ValueError("Observed URL hostname differs from registered source")
    args = (row["instrument_id"],)
    if row.get("snapshot_id") is not None:
        match = db.execute("SELECT id FROM corpus_snapshots WHERE instrument_id=? AND id=?",
                           (*args, row["snapshot_id"])).fetchone()
    else:
        match = db.execute("SELECT id FROM corpus_snapshots WHERE instrument_id=? ORDER BY id DESC LIMIT 1",
                           args).fetchone()
    if match is None:
        raise ValueError("Import the research corpus instrument before attaching its original source")


def _previous(db: sqlite3.Connection, row: dict):
    return db.execute(
        "SELECT observed_sha256,evidence_id,id FROM source_inbox_observations "
        "WHERE source_id=? AND instrument_id=? AND source_reference=? ORDER BY id DESC LIMIT 1",
        (row["source_id"], row["instrument_id"], row["source_reference"])
    ).fetchone()


def import_inbox(db: sqlite3.Connection, path: str, *, dry_run: bool = False,
                 evidence_root: str = "storage/source-evidence") -> dict:
    """One-shot intake with preflight of every record. No URL is fetched.

    A failure during copying may leave some previously imported receipts; retrying
    is safe because the underlying evidence vault is content-addressed.
    """
    root, records = load_inbox(path)
    initialize_inbox(db)
    prepared = []
    # Preflight ALL records before any new evidence file is written.
    for row in records:
        _source_matches(db, row)
        file = _safe_file(root, row["local_file"])
        data = file.read_bytes()
        if not data or len(data) > 25 * 1024 * 1024:
            raise ValueError("Evidence file size must be between 1 byte and 25 MiB")
        sha = hashlib.sha256(data).hexdigest()
        # Existing evidence helper performs its own content validation upon copy.
        prev = _previous(db, row)
        state = "FIRST_SEEN" if prev is None else ("UNCHANGED" if prev["observed_sha256"] == sha else "CHANGED_BYTES")
        prepared.append((row, str(file), sha, state))
    output = {"dry_run": dry_run, "network_requests": 0, "legal_authenticity_verified": False,
              "publicly_published": False, "records": []}
    for row, file, sha, state in prepared:
        if not dry_run:
            receipt = attach_evidence(
                db, row["instrument_id"], file, row["observed_url"],
                source_reference=row["source_reference"], snapshot_id=row.get("snapshot_id"),
                evidence_root=evidence_root,
            )
            associate_evidence(db, row["source_id"], receipt["evidence_id"])
            with db:
                db.execute(
                    "INSERT INTO source_inbox_observations(source_id,instrument_id,source_reference,"
                    "observed_url,evidence_id,observed_sha256,change_state) VALUES(?,?,?,?,?,?,?)",
                    (row["source_id"], row["instrument_id"], row["source_reference"],
                     row["observed_url"], receipt["evidence_id"], sha, state)
                )
        output["records"].append({
            "source_id": row["source_id"], "instrument_id": row["instrument_id"],
            "source_reference": row["source_reference"], "sha256": sha,
            "change_state": state, "review_required": state == "CHANGED_BYTES",
        })
    output["total"] = len(output["records"])
    return output


def inbox_history(db: sqlite3.Connection, source_id: str, instrument_id: str,
                  source_reference: str, limit: int = 20) -> dict:
    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100")
    initialize_inbox(db)
    rows = db.execute(
        "SELECT id,source_id,instrument_id,source_reference,observed_url,evidence_id,"
        "observed_sha256,change_state,created_at FROM source_inbox_observations "
        "WHERE source_id=? AND instrument_id=? AND source_reference=? "
        "ORDER BY id DESC LIMIT ?", (source_id, instrument_id, source_reference, limit)
    ).fetchall()
    return {"records": [dict(row) for row in rows], "count": len(rows),
            "source_identity_verified": False, "legal_authenticity_verified": False}


def inbox_diff(db: sqlite3.Connection, source_id: str, instrument_id: str,
              source_reference: str, *, evidence_root: str = "storage/source-evidence") -> dict:
    """Compare the latest captured bytes to most recent *different* captured bytes.

    Only text-like files are diffed; PDF bytes need dedicated authorized parsing.
    """
    initialize_inbox(db)
    rows = db.execute(
        "SELECT i.id,i.observed_sha256,e.relative_path FROM source_inbox_observations i "
        "JOIN corpus_source_evidence e ON e.id=i.evidence_id "
        "WHERE i.source_id=? AND i.instrument_id=? AND i.source_reference=? "
        "ORDER BY i.id DESC", (source_id, instrument_id, source_reference)
    ).fetchall()
    if not rows:
        raise ValueError("No source observations for this document")
    newest = rows[0]
    previous = next((x for x in rows[1:] if x["observed_sha256"] != newest["observed_sha256"]), None)
    result = {"source_id": source_id, "instrument_id": instrument_id,
              "source_reference": source_reference, "current_sha256": newest["observed_sha256"],
              "previous_sha256": previous["observed_sha256"] if previous else None,
              "file_bytes_changed": previous is not None,
              "legal_amendment_verified": False,
              "unified_diff": None, "diff_note": "No earlier different source capture"}
    if previous is None:
        return result
    root = Path(evidence_root).resolve()
    def read_text(row):
        rel = Path(row["relative_path"])
        if rel.is_absolute() or ".." in rel.parts or rel.suffix.lower() not in {".txt", ".json", ".xml", ".html", ".htm"}:
            return None
        p = root / rel
        if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_DIFF_BYTES:
            return None
        data = p.read_bytes()
        if hashlib.sha256(data).hexdigest() != row["observed_sha256"]:
            return None
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None
    before, after = read_text(previous), read_text(newest)
    if before is not None and after is not None:
        diff = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                            fromfile="previous captured file", tofile="latest captured file"))
        result["unified_diff"] = diff[:12000]
        result["diff_note"] = "Text-only byte snapshot comparison; not a verified legal amendment"
    else:
        result["diff_note"] = "No text diff (binary, damaged, absent, or oversized local source file)"
    return result
