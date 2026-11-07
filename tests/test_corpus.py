"""Tests for quarantined bulk research corpus; every fixture is fictional."""
from __future__ import annotations

import copy
import json

import pytest
from fastapi.testclient import TestClient
from legalcore.api import app
from legalcore.corpus import (
    corpus_search, corpus_stats, import_directory, initialize_corpus,
    validate_batch,
)
from legalcore.store import connect, initialize


@pytest.fixture
def corpus_db(tmp_path):
    db = connect(str(tmp_path / 'corpus.sqlite3'))
    initialize_corpus(db)
    yield db
    db.close()


@pytest.fixture
def sample():
    return json.loads(open('examples/corpus-demo/sample-batch.json', encoding='utf-8').read())


def stage(tmp_path, payload, filename='sample.json'):
    folder = tmp_path / 'batch'
    folder.mkdir(exist_ok=True)
    (folder / filename).write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    return str(folder)


def test_imports_two_kinds_without_publication(corpus_db, sample, tmp_path):
    result = import_directory(corpus_db, stage(tmp_path, sample))
    assert result['files_ok'] == 1
    assert result['new_snapshots'] == 2
    assert result['new_units'] == 3
    assert result['errors'] == []
    stats = corpus_stats(corpus_db)
    assert stats['instruments'] == 2
    assert stats['snapshots'] == 2
    assert stats['latest_units'] == 3
    assert sorted(item['kind'] for item in stats['by_kind']) == ['law', 'regulation']
    assert stats['publicly_published'] is False
    tables = {x[0] for x in corpus_db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert 'article_versions' not in tables
    assert 'review_queue' not in tables


def test_idempotent_with_source_sha(corpus_db, sample, tmp_path):
    path = stage(tmp_path, sample)
    first = import_directory(corpus_db, path)
    again = import_directory(corpus_db, path)
    assert first['new_snapshots'] == 2
    assert again['new_snapshots'] == 0
    assert again['unchanged_snapshots'] == 2
    assert corpus_db.execute('SELECT COUNT(*) FROM corpus_snapshots').fetchone()[0] == 2
    assert corpus_db.execute('SELECT COUNT(*) FROM corpus_import_runs').fetchone()[0] == 2


def test_changed_document_new_snapshot_preserves_history(corpus_db, sample, tmp_path):
    path = stage(tmp_path, sample)
    import_directory(corpus_db, path)
    changed = copy.deepcopy(sample)
    changed['documents'][0]['units'][0]['text'] += ' این نسخه جدید و ساختگی است.'
    stage(tmp_path, changed)
    result = import_directory(corpus_db, path)
    assert result['new_snapshots'] == 1
    assert result['unchanged_snapshots'] == 1
    assert corpus_stats(corpus_db)['snapshots'] == 3
    assert corpus_stats(corpus_db)['latest_units'] == 3
    assert corpus_search(corpus_db, 'نسخه جدید')['total'] == 1
    assert corpus_search(corpus_db, 'برای آزمون ورود گروهی')['total'] == 1
    text_rows = corpus_db.execute('SELECT raw_text FROM corpus_units WHERE unit_key=? ORDER BY snapshot_id', ('1',)).fetchall()
    assert len(text_rows) == 3
    assert text_rows[0]['raw_text'] != text_rows[-1]['raw_text']


def test_dry_run_reports_without_inserting(corpus_db, sample, tmp_path):
    result = import_directory(corpus_db, stage(tmp_path, sample), dry_run=True)
    assert result['dry_run'] is True
    assert result['new_snapshots'] == 2
    assert corpus_stats(corpus_db)['instruments'] == 0
    assert corpus_db.execute('SELECT COUNT(*) FROM corpus_import_runs').fetchone()[0] == 0


@pytest.mark.parametrize('mutate', [
    lambda x: x['documents'][0]['units'].append(x['documents'][0]['units'][0].copy()),
    lambda x: x['documents'][1].update(id=x['documents'][0]['id']),
    lambda x: x['documents'][0].update(kind='unknown'),
    lambda x: x.update(dataset_type='PRODUCTION_VERIFIED'),
    lambda x: x['documents'][0].update(review_state='VERIFIED'),
    lambda x: x['documents'][0].update(source_url='file:///etc/passwd'),
    lambda x: x['documents'][0]['dates'].update(approval={'calendar':'gregorian','value':'2025-02-30'}),
])
def test_invalid_files_fail_atomically(corpus_db, sample, tmp_path, mutate):
    bad = copy.deepcopy(sample)
    mutate(bad)
    report = import_directory(corpus_db, stage(tmp_path, bad))
    assert report['new_snapshots'] == 0
    assert report['files_ok'] == 0
    assert len(report['errors']) == 1
    assert corpus_stats(corpus_db)['instruments'] == 0
    assert corpus_db.execute('SELECT result FROM corpus_import_runs').fetchone()[0] == 'failed'


def test_errors_do_not_block_other_files(corpus_db, sample, tmp_path):
    folder = stage(tmp_path, sample, 'a-good.json')
    (tmp_path / 'batch' / 'b-bad.json').write_text('{bad json', encoding='utf-8')
    report = import_directory(corpus_db, folder)
    assert report['files_checked'] == 2
    assert report['files_ok'] == 1
    assert report['new_snapshots'] == 2
    assert len(report['errors']) == 1
    assert corpus_stats(corpus_db)['instruments'] == 2


def test_corpus_search_normalizes_persian_and_ignores_old_snapshots(corpus_db, sample, tmp_path):
    folder = stage(tmp_path, sample)
    import_directory(corpus_db, folder)
    assert corpus_search(corpus_db, 'آزمايشي')['total'] >= 2
    assert corpus_search(corpus_db, 'آزمایشی')['total'] >= 2
    edited = copy.deepcopy(sample)
    edited['documents'][0]['units'][0]['text'] = 'ماده جدید به‌صورت ساختگی اصلاح شد.'
    stage(tmp_path, edited)
    import_directory(corpus_db, folder)
    assert corpus_search(corpus_db, 'اصلاح شد')['total'] == 1
    assert corpus_search(corpus_db, 'برای آزمون ورود گروهی')['total'] == 0


def test_public_api_does_not_publish_research(corpus_db, sample, tmp_path, monkeypatch):
    import_directory(corpus_db, stage(tmp_path, sample))
    monkeypatch.setenv('LEGAL_DB', str(tmp_path / 'corpus.sqlite3'))
    # The public API cannot query any corpus tables; the approved public tables remain empty.
    client = TestClient(app)
    assert client.get('/api/v1/documents').json()['documents'] == []
    assert corpus_db.execute("SELECT COUNT(*) FROM corpus_instruments").fetchone()[0] == 2


def test_corpus_search_rejects_bad_limits(corpus_db):
    with pytest.raises(ValueError):
        corpus_search(corpus_db, 'x')
    with pytest.raises(ValueError):
        corpus_search(corpus_db, 'sample', limit=101)


def test_validation_handles_dates_and_relations(sample):
    result = validate_batch(sample)
    assert len(result) == 2
    assert result[1]['relations'][0]['target_id'] == 'fictional-iran-law-001'
