"""Offline batch ingestion into a quarantined legal research corpus.

This module does not fetch sources, validate legal force, or publish to the demo API.
All imported content is UNVERIFIED and stored in immutable source snapshots.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from .ingest import normalize_persian

DATASET_TYPE = "LEGAL_RESEARCH_BATCH_V1"
KIND = frozenset({
    "constitution", "law", "regulation", "bylaw", "resolution", "circular",
    "directive", "judicial_decision", "advisory_opinion", "other",
})
UNIT_KIND = frozenset({"article", "note", "paragraph", "section", "ruling", "other"})
RELATION_KIND = frozenset({"amends", "repeals", "implements", "interprets", "relates_to"})
DATE_FIELDS = frozenset({"approval", "publication", "effective", "expiry"})
MAX_BYTES_PER_FILE = 25 * 1024 * 1024
MAX_FILES = 5000
MAX_DOCS_PER_FILE = 1000
MAX_UNITS_PER_DOCUMENT = 20000

SCHEMA = """
CREATE TABLE IF NOT EXISTS corpus_instruments (
    id TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS corpus_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id TEXT NOT NULL REFERENCES corpus_instruments(id),
    content_sha256 TEXT NOT NULL,
    source_file_sha256 TEXT NOT NULL,
    source_file_name TEXT NOT NULL,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    issuing_authority TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_reference TEXT,
    dates_json TEXT NOT NULL,
    relations_json TEXT NOT NULL,
    original_document_json TEXT NOT NULL,
    review_state TEXT NOT NULL DEFAULT 'UNVERIFIED' CHECK(review_state='UNVERIFIED'),
    imported_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(instrument_id, content_sha256)
);
CREATE INDEX IF NOT EXISTS idx_corpus_snapshots ON corpus_snapshots(instrument_id,id DESC);
CREATE TABLE IF NOT EXISTS corpus_units (
    snapshot_id INTEGER NOT NULL REFERENCES corpus_snapshots(id),
    unit_key TEXT NOT NULL,
    unit_type TEXT NOT NULL,
    heading TEXT,
    raw_text TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    PRIMARY KEY(snapshot_id,unit_key)
);
CREATE TABLE IF NOT EXISTS corpus_import_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    result TEXT NOT NULL CHECK(result IN ('ok','failed')),
    added_snapshots INTEGER NOT NULL DEFAULT 0,
    existing_snapshots INTEGER NOT NULL DEFAULT 0,
    added_units INTEGER NOT NULL DEFAULT 0,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_corpus_runs ON corpus_import_runs(id DESC);
"""


def initialize_corpus(db: sqlite3.Connection) -> None:
    db.executescript(SCHEMA)
    db.commit()


def _required_string(value: object, field: str, *, max_length: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f"Invalid or missing {field}")
    return value.strip()


def _url(value: object, field: str) -> str:
    value = _required_string(value, field, max_length=2048)
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"Invalid source URL in {field}")
    return value


def _dates(value: object) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict) or set(value) - DATE_FIELDS:
        raise ValueError("Invalid dates fields")
    for name, date in value.items():
        if not isinstance(date, dict) or set(date) != {"calendar", "value"}:
            raise ValueError(f"Date {name} needs calendar and value")
        calendar = date["calendar"]
        if calendar not in {"jalali", "gregorian"}:
            raise ValueError(f"Unsupported calendar for {name}")
        text = date["value"]
        if not isinstance(text, str) or not re.fullmatch(r"\d{4}[-/]\d{2}[-/]\d{2}", text):
            raise ValueError(f"Invalid date string in {name}")
        y, m, d = map(int, re.split("[-/]", text))
        if not (100 <= y <= 2500 and 1 <= m <= 12 and 1 <= d <= 31):
            raise ValueError(f"Invalid date components in {name}")
        if calendar == "jalali":
            if m > 6 and d > 30 or m == 12 and d > 30:
                raise ValueError(f"Invalid Jalali month/day in {name}")
        else:
            from datetime import date as civil_date
            try:
                civil_date(y, m, d)
            except ValueError as exc:
                raise ValueError(f"Invalid Gregorian date in {name}") from exc
    return value


def validate_batch(payload: object) -> list[dict]:
    """Validate the *whole file* before any document is inserted."""
    if not isinstance(payload, dict) or payload.get("dataset_type") != DATASET_TYPE:
        raise ValueError(f"Expected dataset_type={DATASET_TYPE}")
    documents = payload.get("documents")
    if not isinstance(documents, list) or not 1 <= len(documents) <= MAX_DOCS_PER_FILE:
        raise ValueError("Expected 1 to 1000 documents")
    seen_doc_ids: set[str] = set()
    for doc in documents:
        if not isinstance(doc, dict):
            raise ValueError("Document must be an object")
        ident = _required_string(doc.get("id"), "document id", max_length=128)
        if not re.fullmatch(r"[a-z0-9][a-z0-9._:-]*", ident):
            raise ValueError("Document ID should be a stable lowercase machine key")
        if ident in seen_doc_ids:
            raise ValueError(f"Duplicate document ID in file: {ident}")
        seen_doc_ids.add(ident)
        _required_string(doc.get("title"), "document title")
        if doc.get("kind") not in KIND:
            raise ValueError(f"Invalid legal instrument kind: {doc.get('kind')!r}")
        _required_string(doc.get("issuing_authority"), "issuing_authority")
        _required_string(doc.get("source_name"), "source_name")
        _url(doc.get("source_url"), "source_url")
        if doc.get("source_reference") is not None:
            _required_string(doc["source_reference"], "source_reference")
        _dates(doc.get("dates"))
        if doc.get("review_state", "UNVERIFIED") != "UNVERIFIED":
            raise ValueError("Unverified corpus imports may not declare official verification")
        links = doc.get("relations", [])
        if not isinstance(links, list):
            raise ValueError("Relations must be a list")
        for rel in links:
            if not isinstance(rel, dict) or rel.get("type") not in RELATION_KIND:
                raise ValueError("Invalid legal relation type")
            _required_string(rel.get("target_id"), "relation target_id", max_length=128)
        units = doc.get("units")
        if not isinstance(units, list) or not 1 <= len(units) <= MAX_UNITS_PER_DOCUMENT:
            raise ValueError("Expected 1 to 20000 legal units per document")
        seen_unit_keys: set[str] = set()
        for unit in units:
            if not isinstance(unit, dict):
                raise ValueError("Unit must be an object")
            key = _required_string(unit.get("key"), "unit key", max_length=128)
            if key in seen_unit_keys:
                raise ValueError(f"Duplicate unit key in document {ident}: {key}")
            seen_unit_keys.add(key)
            if unit.get("type", "article") not in UNIT_KIND:
                raise ValueError(f"Invalid unit type at {key}")
            _required_string(unit.get("text"), f"unit {key} text", max_length=200000)
            if unit.get("heading") is not None:
                _required_string(unit["heading"], f"unit {key} heading")
    return documents


def _canonical_sha(doc: dict) -> str:
    compact = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(compact.encode("utf-8")).hexdigest()


def import_directory(db: sqlite3.Connection, root: str, *, dry_run: bool = False) -> dict:
    """Batch-import local JSON files; each file is atomic, errors are reported.

    No official-source claims are made. Caller MUST use an isolated research DB.
    """
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError("Input directory does not exist")
    files = sorted(p for p in root_path.rglob("*.json") if p.is_file())
    if not files:
        raise ValueError("No JSON files found")
    if len(files) > MAX_FILES:
        raise ValueError("Too many JSON files; split into batches")
    initialize_corpus(db)
    report: dict = {
        "confidence": "UNVERIFIED", "publicly_published": False,
        "dry_run": dry_run, "files_checked": len(files), "files_ok": 0,
        "new_snapshots": 0, "unchanged_snapshots": 0, "new_units": 0,
        "errors": [],
    }
    for path in files:
        filename = path.relative_to(root_path).as_posix()
        file_sha = "unknown"
        try:
            if path.is_symlink() or path.stat().st_size > MAX_BYTES_PER_FILE:
                raise ValueError("Symlink or file exceeding 25 MiB is not allowed")
            raw = path.read_bytes()
            file_sha = hashlib.sha256(raw).hexdigest()
            try:
                payload = json.loads(raw.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("Invalid UTF-8 JSON") from exc
            docs = validate_batch(payload)
            plans = []
            for doc in docs:
                doc_sha = _canonical_sha(doc)
                existing = db.execute(
                    "SELECT id FROM corpus_snapshots WHERE instrument_id=? AND content_sha256=?",
                    (doc["id"], doc_sha)
                ).fetchone()
                plans.append((doc, doc_sha, existing is not None))
            added = sum(not exists for _, _, exists in plans)
            same = sum(exists for _, _, exists in plans)
            units = sum(len(doc["units"]) for doc, _, exists in plans if not exists)
            if not dry_run:
                with db:
                    for doc, doc_sha, exists in plans:
                        if exists:
                            continue
                        db.execute("INSERT OR IGNORE INTO corpus_instruments(id) VALUES (?)", (doc["id"],))
                        cur = db.execute(
                            "INSERT INTO corpus_snapshots(instrument_id,content_sha256,source_file_sha256,"
                            "source_file_name,title,kind,issuing_authority,source_name,source_url,"
                            "source_reference,dates_json,relations_json,original_document_json) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (doc["id"], doc_sha, file_sha, filename, doc["title"], doc["kind"],
                             doc["issuing_authority"], doc["source_name"], doc["source_url"],
                             doc.get("source_reference"), json.dumps(doc.get("dates", {}), ensure_ascii=False),
                             json.dumps(doc.get("relations", []), ensure_ascii=False),
                             json.dumps(doc, ensure_ascii=False))
                        )
                        db.executemany(
                            "INSERT INTO corpus_units(snapshot_id,unit_key,unit_type,heading,raw_text,content_sha256) "
                            "VALUES (?,?,?,?,?,?)",
                            [(cur.lastrowid, item["key"], item.get("type", "article"),
                              item.get("heading"), item["text"],
                              hashlib.sha256(item["text"].encode("utf-8")).hexdigest())
                             for item in doc["units"]]
                        )
                    db.execute(
                        "INSERT INTO corpus_import_runs(file_name,file_sha256,result,"
                        "added_snapshots,existing_snapshots,added_units) VALUES (?,?,'ok',?,?,?)",
                        (filename, file_sha, added, same, units)
                    )
            report["files_ok"] += 1
            report["new_snapshots"] += added
            report["unchanged_snapshots"] += same
            report["new_units"] += units
        except (ValueError, OSError, sqlite3.DatabaseError, TypeError) as exc:
            report["errors"].append({"file": filename, "reason": str(exc)})
            if not dry_run:
                with db:
                    db.execute(
                        "INSERT INTO corpus_import_runs(file_name,file_sha256,result) VALUES (?,?,'failed')",
                        (filename, file_sha),
                    )
    return report


def corpus_stats(db: sqlite3.Connection) -> dict:
    initialize_corpus(db)
    total = db.execute("SELECT COUNT(*) FROM corpus_instruments").fetchone()[0]
    snapshots = db.execute("SELECT COUNT(*) FROM corpus_snapshots").fetchone()[0]
    units = db.execute("SELECT COUNT(*) FROM corpus_units u JOIN corpus_snapshots s ON s.id=u.snapshot_id "
                       "WHERE s.id=(SELECT MAX(id) FROM corpus_snapshots WHERE instrument_id=s.instrument_id)").fetchone()[0]
    kinds = db.execute("SELECT s.kind,COUNT(*) AS documents FROM corpus_snapshots s "
                       "WHERE s.id=(SELECT MAX(id) FROM corpus_snapshots WHERE instrument_id=s.instrument_id) "
                       "GROUP BY s.kind ORDER BY s.kind").fetchall()
    return {"confidence": "UNVERIFIED", "publicly_published": False,
            "instruments": total, "snapshots": snapshots, "latest_units": units,
            "by_kind": [dict(row) for row in kinds]}


def corpus_search(db: sqlite3.Connection, phrase: str, *, limit: int = 20) -> dict:
    """Developer-only scan, not yet a full-text index for a national corpus."""
    term = normalize_persian(phrase).casefold()
    if not 2 <= len(term) <= 120 or not 1 <= limit <= 100:
        raise ValueError("Phrase must be 2–120 chars and limit 1–100")
    initialize_corpus(db)
    rows = db.execute(
        "SELECT s.instrument_id,s.id AS snapshot_id,s.title,s.kind,s.source_url,"
        "u.unit_key,u.unit_type,u.raw_text FROM corpus_snapshots s "
        "JOIN corpus_units u ON u.snapshot_id=s.id "
        "WHERE s.id=(SELECT MAX(id) FROM corpus_snapshots WHERE instrument_id=s.instrument_id)"
    )
    matches = []
    for row in rows:
        if (term not in normalize_persian(row["raw_text"]).casefold()
                and term not in normalize_persian(row["title"]).casefold()
                and term != normalize_persian(row["unit_key"]).casefold()):
            continue
        matches.append({"id": row["instrument_id"], "title": row["title"],
                        "kind": row["kind"], "unit_key": row["unit_key"],
                        "unit_type": row["unit_type"], "snippet": row["raw_text"][:180],
                        "snapshot_id": row["snapshot_id"], "source_url": row["source_url"]})
    return {"confidence": "UNVERIFIED", "publicly_published": False,
            "query": phrase, "total": len(matches), "results": matches[:limit]}
