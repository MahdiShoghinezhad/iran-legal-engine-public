"""Opt-in local review panel for *fictional demo documents only*.

No third-party services, cookies, automatic approval, or official-law publication.
Do not expose this prototype to the public Internet.
"""
from __future__ import annotations

import difflib
import hmac
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from .ingest import ingest_manifest, validate_manifest
from .review import decide
from .store import connect, initialize


router = APIRouter()
MAX_MANIFEST_BYTES = 256 * 1024


def _database() -> str:
    return os.getenv("LEGAL_DB", "storage/portfolio.sqlite3")


def _require_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")) -> None:
    """Deny by default; require explicit opt-in and a long per-session secret."""
    configured = os.getenv("LEGAL_ADMIN_TOKEN", "")
    if os.getenv("LEGAL_ADMIN_ENABLED") != "1" or len(configured) < 32:
        raise HTTPException(503, "Admin dashboard is disabled; see docs/LOCAL_ADMIN.md")
    if not x_admin_token or not hmac.compare_digest(configured, x_admin_token):
        raise HTTPException(401, "Invalid admin credential")


class ReviewDecision(BaseModel):
    action: str = Field(pattern=r"^(approve|reject)$")
    reviewer: str = Field(min_length=2, max_length=80)


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page():
    # Contains no secret or protected data; all data/action endpoints require a token.
    page = (Path(__file__).parent / "web" / "admin.html").read_text(encoding="utf-8")
    return HTMLResponse(
        page, headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY",
                       "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"}
    )


@router.get("/api/v1/admin/pending")
def list_pending(_: None = Depends(_require_admin),
                 limit: int = Query(30, ge=1, le=100),
                 offset: int = Query(0, ge=0)):
    with connect(_database()) as db:
        initialize(db)
        count = db.execute(
            "SELECT COUNT(*) FROM review_queue q JOIN documents d ON d.id=q.document_id "
            "WHERE q.decision='pending' AND d.kind='fictional_demo'"
        ).fetchone()[0]
        rows = db.execute(
            "SELECT q.id, q.document_id, d.title, q.article_key, q.source_url, "
            "q.effective_from, q.detected_at "
            "FROM review_queue q JOIN documents d ON d.id=q.document_id "
            "WHERE q.decision='pending' AND d.kind='fictional_demo' "
            "ORDER BY q.id DESC LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return {"demo_only": True, "total": count, "limit": limit, "offset": offset,
                "results": [dict(row) for row in rows]}


@router.get("/api/v1/admin/pending/{review_id}")
def pending_detail(review_id: int, _: None = Depends(_require_admin)):
    with connect(_database()) as db:
        initialize(db)
        row = db.execute(
            "SELECT q.id, q.document_id, d.title, d.kind, q.article_key, q.proposed_text, "
            "q.source_url, q.effective_from, q.detected_at, q.decision "
            "FROM review_queue q JOIN documents d ON d.id=q.document_id "
            "WHERE q.id=? AND d.kind='fictional_demo'", (review_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Demo review item not found")
        previous = db.execute(
            "SELECT text, version_number FROM article_versions "
            "WHERE document_id=? AND article_key=? ORDER BY version_number DESC LIMIT 1",
            (row["document_id"], row["article_key"])
        ).fetchone()
        before = previous["text"] if previous else ""
        after = row["proposed_text"]
        diff = "".join(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile="previous approved demo version",
            tofile="proposed demo version"
        ))
        return {
            "demo_only": True, **dict(row),
            "previous_text": before if previous else None,
            "previous_version_number": previous["version_number"] if previous else None,
            "unified_diff": diff,
        }


@router.post("/api/v1/admin/import-demo")
async def import_demo_manifest(request: Request, _: None = Depends(_require_admin)):
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        raise HTTPException(415, "Expected application/json")
    if request.headers.get("content-length", "").isdigit() and int(request.headers["content-length"]) > MAX_MANIFEST_BYTES:
        raise HTTPException(413, "Manifest too large")
    data = await request.body()
    if len(data) > MAX_MANIFEST_BYTES:
        raise HTTPException(413, "Manifest too large")
    try:
        payload = validate_manifest(json.loads(data))
    except (ValueError, UnicodeDecodeError, TypeError, AttributeError) as exc:
        raise HTTPException(422, "Invalid manifest") from exc
    if payload.get("dataset_type") != "FICTIONAL_DEMO_ONLY" or not payload["documents"]:
        raise HTTPException(422, "Only explicit fictional demo datasets are accepted")
    for doc in payload["documents"]:
        if (doc["kind"] != "fictional_demo"
                or not doc["id"].startswith("fictional-")
                or not doc["source_url"].startswith("https://example.invalid/")):
            raise HTTPException(422, "Only fictional demo documents with example.invalid sources are accepted")
        for item in doc["articles"]:
            if item.get("source_url") and not item["source_url"].startswith("https://example.invalid/"):
                raise HTTPException(422, "Only fictional article sources are accepted")
    with connect(_database()) as db:
        initialize(db)
        # Fail closed if a pre-existing document has a different provenance/type.
        for doc in payload["documents"]:
            old = db.execute(
                "SELECT kind, source_url FROM documents WHERE id=?", (doc["id"],)
            ).fetchone()
            if old and (old["kind"] != "fictional_demo" or
                        not old["source_url"].startswith("https://example.invalid/")):
                raise HTTPException(409, "Existing document is not a fictional demo")
        result = ingest_manifest(db, payload)
    return JSONResponse({"demo_only": True, **result}, headers={"Cache-Control": "no-store"})


@router.post("/api/v1/admin/pending/{review_id}/decision")
def review_decision(review_id: int, body: ReviewDecision, _: None = Depends(_require_admin)):
    reviewer = body.reviewer.strip()
    if len(reviewer) < 2:
        raise HTTPException(422, "Reviewer name is required")
    with connect(_database()) as db:
        initialize(db)
        row = db.execute(
            "SELECT d.kind, d.source_url FROM review_queue q "
            "JOIN documents d ON d.id=q.document_id WHERE q.id=?", (review_id,)
        ).fetchone()
        if not row or row["kind"] != "fictional_demo" or not row["source_url"].startswith("https://example.invalid/"):
            raise HTTPException(404, "Demo review item not found")
        try:
            result = decide(db, review_id, reviewer, approve=(body.action == "approve"))
        except ValueError as exc:
            raise HTTPException(409, "Already reviewed or review item missing") from exc
        return JSONResponse({"demo_only": True, **result}, headers={"Cache-Control": "no-store"})
