"""Read-only API. Pending proposals are intentionally never exposed."""
from __future__ import annotations
import os
from fastapi import FastAPI, HTTPException
from .store import connect, initialize

app = FastAPI(
    title="Iran Legal Engine – Public Demo",
    version="0.1.0",
    description="Demonstration only. Not an authoritative legal database or legal advice.",
)


def db_path() -> str:
    return os.getenv("LEGAL_DB", "storage/portfolio.sqlite3")


@app.get("/health")
def health():
    return {"status": "ok", "demo_only": True}


@app.get("/api/v1/documents")
def documents():
    with connect(db_path()) as db:
        initialize(db)
        rows = db.execute(
            "SELECT d.id, d.title, d.kind, d.source_name, d.source_url, "
            "COUNT(DISTINCT a.article_key) AS published_articles "
            "FROM documents d JOIN article_versions a ON d.id=a.document_id "
            "GROUP BY d.id, d.title, d.kind, d.source_name, d.source_url ORDER BY d.title"
        ).fetchall()
        return {"demo_only": True, "documents": [dict(row) for row in rows]}


@app.get("/api/v1/documents/{document_id}/articles/{article_key}")
def article(document_id: str, article_key: str):
    with connect(db_path()) as db:
        initialize(db)
        row = db.execute(
            "SELECT a.document_id, a.article_key, a.version_number, a.text, a.source_url, "
            "a.effective_from, a.approved_at, d.title "
            "FROM article_versions a JOIN documents d ON d.id=a.document_id "
            "WHERE a.document_id=? AND a.article_key=? ORDER BY a.version_number DESC LIMIT 1",
            (document_id, article_key),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="No reviewed article found")
        return {"demo_only": True, "warning": "Reviewed demo data, not legally authenticated", **dict(row)}


@app.get("/api/v1/documents/{document_id}/articles/{article_key}/history")
def history(document_id: str, article_key: str):
    with connect(db_path()) as db:
        initialize(db)
        rows = db.execute(
            "SELECT version_number, text, source_url, effective_from, reviewed_by, approved_at "
            "FROM article_versions WHERE document_id=? AND article_key=? ORDER BY version_number DESC",
            (document_id, article_key),
        ).fetchall()
        return {"demo_only": True, "history": [dict(row) for row in rows]}
