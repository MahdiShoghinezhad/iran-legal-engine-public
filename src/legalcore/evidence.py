"""Content-addressed receipt vault for locally supplied UNVERIFIED legal-source files.

An intact file hash is not proof of official authenticity or redistribution rights.
No HTTP requests are made and nothing is published through the legal API.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .corpus import initialize_corpus

EXTENSIONS = {'.pdf', '.html', '.htm', '.json', '.txt', '.xml'}
MAX_FILE_BYTES = 25 * 1024 * 1024
SCHEMA = '''
CREATE TABLE IF NOT EXISTS corpus_source_evidence (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 snapshot_id INTEGER NOT NULL REFERENCES corpus_snapshots(id),
 filename TEXT NOT NULL,
 sha256 TEXT NOT NULL,
 file_bytes INTEGER NOT NULL CHECK(file_bytes > 0),
 relative_path TEXT NOT NULL,
 observed_url TEXT NOT NULL,
 source_reference TEXT NOT NULL,
 capture_time TEXT NOT NULL,
 legal_status TEXT NOT NULL DEFAULT 'UNVERIFIED' CHECK(legal_status='UNVERIFIED'),
 rights_status TEXT NOT NULL DEFAULT 'NOT_ASSESSED' CHECK(rights_status='NOT_ASSESSED'),
 UNIQUE(snapshot_id, sha256, observed_url, source_reference)
);
CREATE INDEX IF NOT EXISTS idx_source_evidence ON corpus_source_evidence(snapshot_id, id DESC);
'''


def initialize_evidence(db: sqlite3.Connection) -> None:
    initialize_corpus(db)
    db.executescript(SCHEMA)
    db.commit()


def _source_url(raw: str) -> str:
    if not isinstance(raw, str) or len(raw) > 2048:
        raise ValueError('Invalid source URL')
    parsed = urlsplit(raw)
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None):
        raise ValueError('Source must be an HTTP(S) URL without embedded credentials')
    return raw


def _snapshot(db: sqlite3.Connection, instrument_id: str, snapshot_id: int | None) -> int:
    if snapshot_id is None:
        row = db.execute('SELECT id FROM corpus_snapshots WHERE instrument_id=? '
                         'ORDER BY id DESC LIMIT 1', (instrument_id,)).fetchone()
    else:
        row = db.execute('SELECT id FROM corpus_snapshots WHERE instrument_id=? AND id=?',
                         (instrument_id, snapshot_id)).fetchone()
    if row is None:
        raise ValueError('Matching research snapshot not found: import corpus first')
    return int(row['id'])


def attach_evidence(db: sqlite3.Connection, instrument_id: str, original_file: str,
                    observed_url: str, *, source_reference: str = '',
                    snapshot_id: int | None = None,
                    evidence_root: str = 'storage/source-evidence') -> dict:
    """Copy local original bytes into a content-addressed vault, never auto-publish."""
    initialize_evidence(db)
    url = _source_url(observed_url)
    if not isinstance(source_reference, str) or len(source_reference) > 256:
        raise ValueError('Invalid source reference')
    path = Path(original_file)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Original must be a normal non-symlink file')
    suffix = path.suffix.lower()
    if suffix not in EXTENSIONS:
        raise ValueError('Unsupported source file extension')
    size = path.stat().st_size
    if not 0 < size <= MAX_FILE_BYTES:
        raise ValueError('Original must be between 1 byte and 25 MiB')
    data = path.read_bytes()
    if len(data) != size:
        raise ValueError('Original changed during read')
    if suffix == '.pdf' and not data.startswith(b'%PDF-'):
        raise ValueError('Bad PDF signature')
    if suffix == '.json':
        try:
            json.loads(data.decode('utf-8-sig'))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError('Bad JSON original') from exc
    elif suffix != '.pdf':
        try:
            data.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError('Source text must be UTF-8') from exc
    sid = _snapshot(db, instrument_id, snapshot_id)
    sha = hashlib.sha256(data).hexdigest()
    root = Path(evidence_root).resolve()
    rel = f'{sha[:2]}/{sha}{suffix}'
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if (target.is_symlink() or not target.is_file() or
                hashlib.sha256(target.read_bytes()).hexdigest() != sha):
            raise ValueError('Evidence storage collision or corrupted content')
    else:
        tmp = target.parent / ('.' + uuid.uuid4().hex + '.tmp')
        try:
            with tmp.open('xb') as out:
                out.write(data)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
    captured = datetime.now(timezone.utc).isoformat(timespec='seconds')
    with db:
        db.execute('INSERT OR IGNORE INTO corpus_source_evidence('
                   'snapshot_id,filename,sha256,file_bytes,relative_path,observed_url,'
                   'source_reference,capture_time) VALUES (?,?,?,?,?,?,?,?)',
                   (sid, path.name, sha, len(data), rel, url, source_reference, captured))
    record = db.execute('SELECT id FROM corpus_source_evidence '
                        'WHERE snapshot_id=? AND sha256=? AND observed_url=? '
                        'AND source_reference=?', (sid, sha, url, source_reference)).fetchone()
    return {'evidence_id': record['id'], 'snapshot_id': sid, 'sha256': sha,
            'relative_path': rel, 'legal_status': 'UNVERIFIED',
            'rights_status': 'NOT_ASSESSED', 'source_url_claim': url}


def list_evidence(db: sqlite3.Connection, instrument_id: str,
                  *, snapshot_id: int | None = None) -> dict:
    initialize_evidence(db)
    sid = _snapshot(db, instrument_id, snapshot_id)
    rows = db.execute('SELECT * FROM corpus_source_evidence WHERE snapshot_id=? '
                      'ORDER BY id', (sid,)).fetchall()
    return {'snapshot_id': sid, 'legal_authenticity_verified': False,
            'count': len(rows), 'evidence': [dict(r) for r in rows]}


def check_evidence(db: sqlite3.Connection, evidence_id: int,
                   *, evidence_root: str = 'storage/source-evidence') -> dict:
    initialize_evidence(db)
    row = db.execute('SELECT id,sha256,file_bytes,relative_path FROM corpus_source_evidence '
                     'WHERE id=?', (evidence_id,)).fetchone()
    if row is None:
        raise ValueError('Unknown evidence ID')
    rel = Path(row['relative_path'])
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Unsafe vault path')
    path = Path(evidence_root).resolve() / rel
    if not path.is_file() or path.is_symlink():
        state = 'missing'
    else:
        state = ('ok' if path.stat().st_size == row['file_bytes'] and
                 hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256'] else 'tampered')
    return {'evidence_id': evidence_id, 'file_integrity': state,
            'legal_authenticity_verified': False, 'rights_assessed': False}
