"""One-shot, owner-controlled local manifest sync. No Internet fetches."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from pathlib import Path
from .ingest import validate_manifest, ingest_manifest


def sync_local_manifest(conn: sqlite3.Connection, path: str, *, dry_run: bool = False) -> dict:
    """Detect local edits; stage review proposals, NEVER automatically approve.

    A system scheduler can run this process independently after deployment.
    No government API is connected and no text is regarded as authoritative.
    """
    input_path = Path(path)
    data = input_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    try:
        payload = validate_manifest(json.loads(data.decode("utf-8-sig")))
    except (ValueError, UnicodeDecodeError, TypeError):
        if not dry_run:
            conn.execute(
                "INSERT INTO local_sync_runs(manifest_name, content_sha256, status) "
                "VALUES (?, ?, 'failed')", (input_path.name, digest)
            )
            conn.commit()
        raise
    result = ingest_manifest(conn, payload, dry_run=dry_run)
    output = {
        "source": "local_file_only",
        "manifest_name": input_path.name,
        "content_sha256": digest,
        "status": "dry_run" if dry_run else "ok",
        **result,
    }
    if not dry_run:
        conn.execute(
            "INSERT INTO local_sync_runs(manifest_name, content_sha256, status, proposed, unchanged, already_pending) "
            "VALUES (?, ?, 'ok', ?, ?, ?)",
            (input_path.name, digest, result["proposed"], result["unchanged"], result["already_pending"])
        )
        conn.commit()
    return output
