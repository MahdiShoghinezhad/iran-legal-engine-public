"""Quarantined, provenance-aware research copies of unverified Civil Code texts.

NOT part of the public approved-law API. Does not fetch the Internet or publish law.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
from pathlib import Path

from .ingest import normalize_persian

SOURCE = "https://github.com/GeekNeuron/IranLegalHUB/tree/main/laws/civil_code"
EXPECTED_RANGES = ((1, 955), (956, 1256), (1257, 1335))

RESEARCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS civil_research_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    source_hash TEXT NOT NULL UNIQUE,
    volume_hashes_json TEXT NOT NULL,
    article_count INTEGER NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'UNVERIFIED',
    imported_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS civil_research_articles (
    snapshot_id INTEGER NOT NULL REFERENCES civil_research_snapshots(id),
    article_number INTEGER NOT NULL CHECK(article_number BETWEEN 1 AND 1335),
    section_title TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    PRIMARY KEY(snapshot_id, article_number)
);
CREATE INDEX IF NOT EXISTS idx_research_snapshot ON civil_research_articles(snapshot_id, article_number);
"""


def initialize_research(db: sqlite3.Connection) -> None:
    db.executescript(RESEARCH_SCHEMA)
    db.commit()


def _validate_volumes(volumes: list[str]) -> tuple[list[dict], list[str], str]:
    if len(volumes) != 3:
        raise ValueError('Expected exactly three volume JSON files, in volume order')
    all_articles = []
    volume_hashes = []
    for position, (path, expected) in enumerate(zip(volumes, EXPECTED_RANGES), start=1):
        binary = Path(path).read_bytes()
        volume_hashes.append(hashlib.sha256(binary).hexdigest())
        try:
            data = json.loads(binary.decode('utf-8-sig'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f'Volume {position} is not valid UTF-8 JSON') from exc
        if not isinstance(data, dict) or not isinstance(data.get('divisions'), list):
            raise ValueError(f'Volume {position} lacks divisions')
        items = []
        for division in data['divisions']:
            if not isinstance(division, dict) or not isinstance(division.get('articles'), list):
                raise ValueError(f'Volume {position}: invalid division')
            section = division.get('title')
            if not isinstance(section, str) or not section.strip():
                raise ValueError(f'Volume {position}: missing section title')
            for article in division['articles']:
                if not isinstance(article, dict):
                    raise ValueError('Invalid article object')
                number, text = article.get('article_number'), article.get('text')
                if type(number) is not int or not isinstance(text, str) or not text.strip():
                    raise ValueError(f'Volume {position}: invalid number or article text')
                items.append({'number': number, 'section': section, 'text': text})
        expected_set = set(range(expected[0], expected[1] + 1))
        actual = [a['number'] for a in items]
        if len(items) != len(expected_set) or set(actual) != expected_set:
            raise ValueError(f'Volume {position}: missing, duplicated, or out-of-range article numbers')
        all_articles.extend(items)
    if len(all_articles) != 1335:
        raise ValueError('Incorrect Civil Code article count')
    # The digest is deterministic and provenance-bound to the three original files.
    digest = hashlib.sha256(('civil-research-v1:' + ':'.join(volume_hashes)).encode('ascii')).hexdigest()
    return sorted(all_articles, key=lambda a: a['number']), volume_hashes, digest


def import_civil_research(db: sqlite3.Connection, volumes: list[str]) -> dict:
    """Store a complete immutable snapshot in a research-only table.

    Repeated identical imports do not duplicate data. No statement of legal validity.
    """
    articles, hashes, digest = _validate_volumes(volumes)
    initialize_research(db)
    existing = db.execute('SELECT id FROM civil_research_snapshots WHERE source_hash=?', (digest,)).fetchone()
    if existing:
        return {'snapshot_id': existing['id'], 'imported': False, 'article_count': 1335,
                'source_hash': digest, 'confidence': 'UNVERIFIED'}
    with db:
        cur = db.execute(
            'INSERT INTO civil_research_snapshots(source_url,source_hash,volume_hashes_json,article_count) VALUES(?,?,?,?)',
            (SOURCE, digest, json.dumps(hashes), len(articles)),
        )
        snapshot_id = cur.lastrowid
        db.executemany(
            'INSERT INTO civil_research_articles(snapshot_id,article_number,section_title,raw_text,content_sha256) VALUES (?,?,?,?,?)',
            [(snapshot_id, a['number'], a['section'], a['text'], hashlib.sha256(a['text'].encode('utf-8')).hexdigest())
             for a in articles]
        )
    return {'snapshot_id': snapshot_id, 'imported': True, 'article_count': len(articles),
            'source_hash': digest, 'confidence': 'UNVERIFIED'}


def _snapshot_id(db: sqlite3.Connection, selected: int | None = None) -> int:
    initialize_research(db)
    if selected is None:
        row = db.execute('SELECT id FROM civil_research_snapshots ORDER BY id DESC LIMIT 1').fetchone()
    else:
        row = db.execute('SELECT id FROM civil_research_snapshots WHERE id=?', (selected,)).fetchone()
    if row is None:
        raise ValueError('No matching research snapshot; import three volumes first')
    return row['id']


def research_stats(db: sqlite3.Connection) -> dict:
    initialize_research(db)
    rows = db.execute('SELECT id,source_hash,article_count,confidence,imported_at FROM civil_research_snapshots ORDER BY id DESC').fetchall()
    return {'confidence': 'UNVERIFIED', 'publicly_published': False, 'snapshots': [dict(r) for r in rows]}


def research_article(db: sqlite3.Connection, article_number: int, *, snapshot_id: int | None = None) -> dict:
    sid = _snapshot_id(db, snapshot_id)
    row = db.execute('SELECT article_number,section_title,raw_text,content_sha256 FROM civil_research_articles WHERE snapshot_id=? AND article_number=?', (sid, article_number)).fetchone()
    if row is None:
        raise ValueError('Article not found')
    return {'snapshot_id': sid, 'confidence': 'UNVERIFIED', **dict(row)}


def research_search(db: sqlite3.Connection, phrase: str, *, limit: int = 20) -> dict:
    term = normalize_persian(phrase).casefold()
    if not 2 <= len(term) <= 120 or not 1 <= limit <= 100:
        raise ValueError('Search length must be 2–120 and limit must be 1–100')
    sid = _snapshot_id(db)
    rows = db.execute('SELECT article_number,section_title,raw_text FROM civil_research_articles WHERE snapshot_id=? ORDER BY article_number', (sid,))
    matches = []
    for row in rows:
        if term in normalize_persian(row['raw_text']).casefold() or term == str(row['article_number']):
            matches.append({'article_number': row['article_number'], 'section_title': row['section_title'],
                            'preview': row['raw_text'][:220]})
    return {'snapshot_id': sid, 'confidence': 'UNVERIFIED', 'total': len(matches), 'results': matches[:limit]}


def export_research_preview(db: sqlite3.Connection, output: str) -> dict:
    """Build a standalone, LOCAL, offline browser viewer; no public API endpoint."""
    sid = _snapshot_id(db)
    rows = db.execute('SELECT article_number,section_title,raw_text FROM civil_research_articles WHERE snapshot_id=? ORDER BY article_number', (sid,)).fetchall()
    items = [{'number': r['article_number'], 'section': r['section_title'], 'text': r['raw_text']} for r in rows]
    data_json = json.dumps(items, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    viewer = '''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>قانون مدنی - آرشیو پژوهشی تأییدنشده</title><style>
body{font:16px/2 Tahoma,Arial;background:#f4f7fa;color:#213547;margin:0}main{max-width:1100px;margin:0 auto;padding:24px}h1{font-size:25px}.warning{background:#fff3d9;border:2px solid #eab44c;padding:18px;border-radius:12px;font-weight:bold}input{padding:14px;border:1px solid #bbb;border-radius:8px;width:100%;box-sizing:border-box;margin:16px 0}section{background:white;padding:18px;margin:12px 0;border:1px solid #dce2e9;border-radius:10px;white-space:pre-wrap}.meta{font-size:13px;color:#657487}.badge{background:#e9ecf0;padding:4px 9px;border-radius:15px;font-size:12px}button{padding:10px;border:1px solid #aaa;border-radius:8px;cursor:pointer}footer{font-size:12px;color:#677;margin:20px 0}</style></head><body><main><h1>قانون مدنی ایران — نمای پژوهشی محلی</h1><div class="warning">⚠ متن گردآوری‌شده از منبع شخص ثالث؛ تأییدنشده، تنقیح رسمی نیست و برای استناد حقوقی معتبرسازی نشده است. این فایل فقط برای بررسی داخلی است.</div><p class="meta">بدون اینترنت و بدون اتصال به سرور. تعداد مواد: ۱۳۳۵</p><input id="q" aria-label="جست‌وجو" placeholder="شماره ماده یا عبارتی از متن را جست‌وجو کنید…"><div id="count"></div><div id="results"></div><footer>هیچ داده‌ای به سرور ارسال نمی‌شود. برای انتشار یا استناد، اصلاحات و اعتبار مواد را با مراجع رسمی تطبیق دهید.</footer></main><script>
const A=__DATA__; const q=document.getElementById('q');const out=document.getElementById('results');const count=document.getElementById('count');const normalize=s=>String(s).replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/[۰-۹]/g,c=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c))).toLowerCase().trim();
function draw(){const phrase=normalize(q.value);const hits=A.filter(a=>!phrase || normalize(a.text).includes(phrase) || normalize(a.number)===phrase);out.replaceChildren();count.textContent='نتایج: '+hits.length+' — نمایش حداکثر ۳۰ ماده';for(const a of hits.slice(0,30)){const el=document.createElement('section');const head=document.createElement('strong');head.textContent='ماده '+a.number;const sub=document.createElement('div');sub.className='meta';sub.textContent=a.section;const body=document.createElement('div');body.textContent=a.text;el.append(head,sub,body);out.append(el);}} q.addEventListener('input',draw); draw();
</script></body></html>'''.replace('__DATA__', data_json)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(viewer, encoding='utf-8')
    return {'output': str(path), 'articles': len(items), 'snapshot_id': sid, 'confidence': 'UNVERIFIED', 'offline_only': True}
