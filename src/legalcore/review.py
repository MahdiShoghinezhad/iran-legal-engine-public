"""Explicit human review boundary. No automatic legal validity determination."""
from __future__ import annotations
import sqlite3


def pending(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, document_id, article_key, sha256, source_url, effective_from, detected_at "
        "FROM review_queue WHERE decision='pending' ORDER BY id"
    ).fetchall()
    return [dict(row) for row in rows]


def decide(conn: sqlite3.Connection, review_id: int, reviewer: str, *, approve: bool) -> dict:
    if not reviewer.strip():
        raise ValueError("Reviewer name is required")
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM review_queue WHERE id=? AND decision='pending'", (review_id,)).fetchone()
        if not row:
            raise ValueError("Review item not found or already decided")
        if approve:
            prior = conn.execute(
                "SELECT COALESCE(MAX(version_number), 0) AS version FROM article_versions "
                "WHERE document_id=? AND article_key=?", (row["document_id"], row["article_key"])
            ).fetchone()["version"]
            conn.execute(
                "INSERT INTO article_versions(document_id,article_key,version_number,text,sha256,source_url,effective_from,reviewed_by) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (row["document_id"], row["article_key"], prior + 1, row["proposed_text"],
                 row["sha256"], row["source_url"], row["effective_from"], reviewer),
            )
        decision = "approved" if approve else "rejected"
        conn.execute(
            "UPDATE review_queue SET decision=?, reviewed_by=?, reviewed_at=datetime('now') WHERE id=?",
            (decision, reviewer, review_id),
        )
        conn.commit()
        return {"review_id": review_id, "decision": decision, "reviewed_by": reviewer}
    except Exception:
        conn.rollback()
        raise


def show_pending(conn: sqlite3.Connection, review_id: int) -> dict:
    """Display the whole proposed text and claimed provenance for manual review."""
    row = conn.execute(
        "SELECT id, document_id, article_key, proposed_text, source_url, effective_from, "
        "detected_at, decision FROM review_queue WHERE id=?", (review_id,)
    ).fetchone()
    if row is None:
        raise ValueError("Review item not found")
    return dict(row)
