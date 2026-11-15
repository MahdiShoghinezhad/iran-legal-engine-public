"""First-party source registry for an OFFLINE, quarantined Iranian legal research corpus.

Entries are *candidate portals*, NOT approved automated connectors. This module
performs zero networking and cannot authorize mass retrieval or publication.
"""
from __future__ import annotations

import re
import sqlite3
from urllib.parse import urlsplit

# Site names and roles are public identifiers only, not a third-party dataset.
SEED_SOURCES = (
    ("qavanin", "سامانه ملی قوانین و مقررات", "https://qavanin.ir/", "legislation_and_regulations"),
    ("rrk", "روزنامه رسمی کشور", "https://rrk.ir/", "official_publication"),
    ("dotic", "پایگاه اطلاع‌رسانی قوانین و مقررات", "https://dotic.ir/", "government_legal_information"),
)
ROLES = frozenset({
    "legislation_and_regulations", "official_publication",
    "government_legal_information", "court_decisions", "agency_regulations",
    "third_party_research", "test_fixture",
})
SCHEMA = """
CREATE TABLE IF NOT EXISTS legal_source_registry (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    site_host TEXT NOT NULL,
    role TEXT NOT NULL,
    access_rights_state TEXT NOT NULL DEFAULT 'UNASSESSED'
        CHECK(access_rights_state='UNASSESSED'),
    redistribution_state TEXT NOT NULL DEFAULT 'UNASSESSED'
        CHECK(redistribution_state='UNASSESSED'),
    connector_state TEXT NOT NULL DEFAULT 'NOT_IMPLEMENTED'
        CHECK(connector_state='NOT_IMPLEMENTED'),
    automatic_fetch_enabled INTEGER NOT NULL DEFAULT 0
        CHECK(automatic_fetch_enabled=0),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS legal_source_evidence_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES legal_source_registry(id),
    evidence_id INTEGER NOT NULL REFERENCES corpus_source_evidence(id),
    identity_verified INTEGER NOT NULL DEFAULT 0 CHECK(identity_verified=0),
    linked_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source_id,evidence_id)
);
CREATE INDEX IF NOT EXISTS idx_source_links ON legal_source_evidence_links(source_id,linked_at);
"""


def initialize_source_registry(db: sqlite3.Connection) -> None:
    db.executescript(SCHEMA)
    db.commit()


def _validated_url(url: str) -> tuple[str, str]:
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("Source URL must be a short HTTPS URL")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.port is not None):
        raise ValueError("Source URL must be HTTPS without credentials or a custom port")
    if parsed.fragment:
        raise ValueError("Source URL must not have a fragment")
    return url, parsed.hostname.lower()


def register_source(db: sqlite3.Connection, source_id: str, name: str, url: str, role: str) -> dict:
    """Create an owner-defined source profile; no scraping or permission claims."""
    initialize_source_registry(db)
    if not isinstance(source_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", source_id):
        raise ValueError("Source ID must be 2–64 lowercase ASCII characters")
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise ValueError("Source name must be 1–200 characters")
    if role not in ROLES:
        raise ValueError("Unrecognized source role")
    url, host = _validated_url(url)
    with db:
        db.execute(
            "INSERT INTO legal_source_registry(id,display_name,base_url,site_host,role) VALUES(?,?,?,?,?)",
            (source_id, name.strip(), url, host, role),
        )
    return get_source(db, source_id)


def bootstrap_sources(db: sqlite3.Connection) -> dict:
    """Add three candidate domains without contacting them. Safe to repeat."""
    initialize_source_registry(db)
    added = 0
    with db:
        for identifier, name, url, role in SEED_SOURCES:
            _, host = _validated_url(url)
            cursor = db.execute(
                "INSERT OR IGNORE INTO legal_source_registry"
                "(id,display_name,base_url,site_host,role) VALUES(?,?,?,?,?)",
                (identifier, name, url, host, role),
            )
            added += cursor.rowcount
    return {"candidate_profiles_added": added, "automatic_fetch_enabled": False,
            "permissions_reviewed": False, "data_collected": False}


def list_sources(db: sqlite3.Connection) -> dict:
    initialize_source_registry(db)
    rows = db.execute(
        "SELECT r.id,r.display_name,r.base_url,r.role,r.access_rights_state,"
        "r.redistribution_state,r.connector_state,r.automatic_fetch_enabled,"
        "(SELECT COUNT(*) FROM legal_source_evidence_links l WHERE l.source_id=r.id) AS linked_evidence "
        "FROM legal_source_registry r ORDER BY r.id"
    ).fetchall()
    return {"sources": [dict(row) for row in rows], "count": len(rows),
            "network_connections_made": 0, "official_api_integrations": 0}


def get_source(db: sqlite3.Connection, source_id: str) -> dict:
    initialize_source_registry(db)
    row = db.execute(
        "SELECT id,display_name,base_url,site_host,role,access_rights_state,"
        "redistribution_state,connector_state,automatic_fetch_enabled,created_at "
        "FROM legal_source_registry WHERE id=?", (source_id,)
    ).fetchone()
    if row is None:
        raise ValueError("Unknown source ID")
    return {**dict(row), "legal_authenticity_verified": False,
            "source_access_permission_verified": False}


def associate_evidence(db: sqlite3.Connection, source_id: str, evidence_id: int) -> dict:
    """Link an existing local evidence receipt to a claimed source domain.

    The domain match checks for typos only. It does NOT authenticate a website or
    prove that a provided local file came from that website.
    """
    initialize_source_registry(db)
    source = get_source(db, source_id)
    row = db.execute(
        "SELECT id, observed_url, snapshot_id, legal_status FROM corpus_source_evidence WHERE id=?",
        (evidence_id,)
    ).fetchone()
    if row is None:
        raise ValueError("Evidence receipt does not exist; attach original bytes first")
    observed_url = row["observed_url"]
    _, claimed_host = _validated_url(observed_url)
    host = source["site_host"]
    if claimed_host.removeprefix("www.") != host.removeprefix("www."):
        raise ValueError("Evidence URL hostname is not the selected source hostname")
    if row["legal_status"] != "UNVERIFIED":
        raise ValueError("Unexpected evidence authenticity status")
    with db:
        db.execute(
            "INSERT OR IGNORE INTO legal_source_evidence_links(source_id,evidence_id) VALUES(?,?)",
            (source_id, evidence_id),
        )
    return {"source_id": source_id, "evidence_id": evidence_id,
            "snapshot_id": row["snapshot_id"], "claimed_url": observed_url,
            "official_identity_verified": False, "rights_verified": False,
            "legal_validity_verified": False}
