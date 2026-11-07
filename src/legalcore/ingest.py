"""Propose changes, never publish legal text on ingestion alone."""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
from pathlib import Path


def normalize_persian(text: str) -> str:
    replacements = str.maketrans({"ي": "ی", "ك": "ک", "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9"})
    return re.sub(r"\s+", " ", text.translate(replacements)).strip()


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalize_persian(text).encode("utf-8")).hexdigest()


def load_manifest(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_manifest(payload)


def validate_manifest(payload: dict) -> dict:
    """Validate parsed source data without a second disk read."""
    if not isinstance(payload, dict) or not isinstance(payload.get("documents"), list):
        raise ValueError("Manifest must have a 'documents' array")
    seen = set()
    for doc in payload["documents"]:
        if not isinstance(doc, dict):
            raise ValueError("Each document must be an object")
        for field in ("id", "title", "kind", "source_name", "source_url"):
            if not isinstance(doc.get(field), str) or not doc[field].strip():
                raise ValueError(f"Document missing nonempty {field}")
        if not doc["source_url"].startswith(("https://", "http://")):
            raise ValueError("A source URL must be HTTP(S)")
        if not isinstance(doc.get("articles"), list):
            raise ValueError("Document 'articles' must be an array")
        for article in doc["articles"]:
            key = str(article.get("number", "")).strip()
            body = article.get("text")
            if not key or not isinstance(body, str) or not body.strip():
                raise ValueError("Article must contain number and nonempty text")
            identity = (doc["id"], key)
            if identity in seen:
                raise ValueError(f"Duplicate article in manifest: {identity}")
            seen.add(identity)
    return payload


def ingest_manifest(conn: sqlite3.Connection, payload: dict, *, dry_run: bool = False) -> dict:
    """Return counts. Only a separate explicit approval makes text publicly visible."""
    result = {"proposed": 0, "unchanged": 0, "already_pending": 0, "dry_run": dry_run}
    for doc in payload["documents"]:
        if not dry_run:
            conn.execute(
                "INSERT OR IGNORE INTO documents(id,title,kind,source_name,source_url) VALUES (?,?,?,?,?)",
                (doc["id"], doc["title"], doc["kind"], doc["source_name"], doc["source_url"]),
            )
        for article in doc["articles"]:
            key = str(article["number"]).strip()
            sha = fingerprint(article["text"])
            prior = conn.execute(
                "SELECT sha256 FROM article_versions WHERE document_id=? AND article_key=? "
                "ORDER BY version_number DESC LIMIT 1", (doc["id"], key)
            ).fetchone()
            if prior and prior["sha256"] == sha:
                result["unchanged"] += 1
                continue
            existing = conn.execute(
                "SELECT id FROM review_queue WHERE document_id=? AND article_key=? AND sha256=? "
                "AND decision='pending' LIMIT 1", (doc["id"], key, sha)
            ).fetchone()
            if existing:
                result["already_pending"] += 1
                continue
            result["proposed"] += 1
            if not dry_run:
                conn.execute(
                    "INSERT INTO review_queue(document_id,article_key,proposed_text,sha256,source_url,effective_from) "
                    "VALUES (?,?,?,?,?,?)",
                    (doc["id"], key, article["text"], sha,
                     article.get("source_url", doc["source_url"]), article.get("effective_from")),
                )
    if not dry_run:
        conn.commit()
    return result
