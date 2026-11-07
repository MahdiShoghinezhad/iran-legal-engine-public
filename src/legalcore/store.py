"""SQLite persistence for the public demo. Production design targets PostgreSQL."""
from __future__ import annotations
import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id),
    article_key TEXT NOT NULL,
    proposed_text TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    source_url TEXT NOT NULL,
    effective_from TEXT,
    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
    decision TEXT NOT NULL DEFAULT 'pending'
        CHECK (decision IN ('pending', 'approved', 'rejected')),
    reviewed_by TEXT,
    reviewed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_review_pending ON review_queue(decision, document_id);
CREATE TABLE IF NOT EXISTS article_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id),
    article_key TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    text TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    source_url TEXT NOT NULL,
    effective_from TEXT,
    reviewed_by TEXT NOT NULL,
    approved_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(document_id, article_key, version_number)
);
CREATE INDEX IF NOT EXISTS idx_versions_lookup
    ON article_versions(document_id, article_key, version_number DESC);
"""

def connect(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
