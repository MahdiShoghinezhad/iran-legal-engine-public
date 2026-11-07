"""Offline, source-aware Persian search over approved demo texts only.

This version intentionally uses a bounded output and a linear scan to keep the
portfolio demo dependency-free. A production deployment needs an FTS index.
"""
from __future__ import annotations
import sqlite3
from .ingest import normalize_persian


def search_reviewed_articles(conn: sqlite3.Connection, query: str, *, limit: int = 30) -> dict:
    phrase = normalize_persian(query).casefold()
    if len(phrase) < 2 or len(phrase) > 120:
        raise ValueError("Search must be between 2 and 120 normalized characters")
    if not 1 <= limit <= 50:
        raise ValueError("Limit must be between 1 and 50")

    matches = []
    rows = conn.execute(
        "SELECT v.document_id, d.title, v.article_key, v.version_number, "
        "v.text, v.source_url, v.approved_at "
        "FROM article_versions v JOIN documents d ON d.id=v.document_id "
        "WHERE v.version_number = ("
        "  SELECT MAX(older.version_number) FROM article_versions older "
        "  WHERE older.document_id=v.document_id AND older.article_key=v.article_key"
        ")"
    )
    terms = phrase.split()
    for row in rows:
        normalized_text = normalize_persian(row["text"]).casefold()
        normalized_title = normalize_persian(row["title"]).casefold()
        normalized_key = normalize_persian(str(row["article_key"])).casefold()
        searchable = " ".join((normalized_title, normalized_key, normalized_text))
        if not all(term in searchable for term in terms):
            continue
        rank = (
            0 if phrase == normalized_key else
            1 if phrase in normalized_title else
            2 if phrase in normalized_text else 3
        )
        # Keep original legal text unchanged; snippet is for UI preview only.
        excerpt = row["text"][:190] + ("…" if len(row["text"]) > 190 else "")
        matches.append((rank, row["document_id"], str(row["article_key"]), {
            "document_id": row["document_id"],
            "title": row["title"],
            "article_key": row["article_key"],
            "version_number": row["version_number"],
            "snippet": excerpt,
            "source_url": row["source_url"],
            "approved_at": row["approved_at"],
        }))
    matches.sort(key=lambda item: (item[0], item[1], item[2]))
    return {"total": len(matches), "results": [m[3] for m in matches[:limit]], "limit": limit}
