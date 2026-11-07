"""Read-only API. Pending proposals are intentionally never exposed."""
from __future__ import annotations
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from .store import connect, initialize
from .search import search_reviewed_articles

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


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def demo_home():
    """User-facing read-only demo backed by the exact same API and database."""
    return HTMLResponse((Path(__file__).parent / "web" / "index.html").read_text(encoding="utf-8"))


@app.get("/api/v1/updates/status")
def update_status():
    """Honest status: a licensed official-source connector has not been implemented."""
    return {
        "source_sync": "not_connected",
        "automatic_monitoring": False,
        "publication_policy": "review_required",
        "demo_only": True,
        "message": "Official source integration is not connected. Changes are currently imported manually.",
    }


@app.get("/api/v1/documents/{document_id}/articles")
def document_articles(document_id: str):
    with connect(db_path()) as db:
        initialize(db)
        doc = db.execute("SELECT id, title FROM documents WHERE id=?", (document_id,)).fetchone()
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        rows = db.execute(
            "SELECT a.article_key, a.version_number, a.approved_at "
            "FROM article_versions a "
            "JOIN (SELECT article_key, MAX(version_number) AS latest FROM article_versions "
            "WHERE document_id=? GROUP BY article_key) q "
            "ON a.article_key=q.article_key AND a.version_number=q.latest "
            "WHERE a.document_id=? ORDER BY CAST(a.article_key AS INTEGER), a.article_key",
            (document_id, document_id),
        ).fetchall()
        return {"demo_only": True, "document": dict(doc), "articles": [dict(row) for row in rows]}


@app.get("/api/v1/search")
def search(q: str = Query(..., min_length=2, max_length=120),
           limit: int = Query(30, ge=1, le=50)):
    """Search ONLY the latest approved version of each article."""
    with connect(db_path()) as db:
        initialize(db)
        return {
            "demo_only": True,
            "query": q,
            **search_reviewed_articles(db, q, limit=limit),
        }


# Administrative routes are disabled by default and require explicit credentials.
from .admin import router as admin_router
app.include_router(admin_router)
