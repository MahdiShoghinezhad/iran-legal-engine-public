"""Synthetic fixtures only; unverified third-party legal texts are never bundled."""
import copy
import json
import pytest

from legalcore.store import connect, initialize
from legalcore.research import (
    import_civil_research, research_stats, research_article,
    research_search, export_research_preview,
)


@pytest.fixture
def volumes(tmp_path):
    result = []
    for i, (a, b) in enumerate(((1,955), (956,1256), (1257,1335)), start=1):
        p = tmp_path / f'vol{i}.json'
        content = {'divisions': [{'title': f'بخش {i}', 'articles': [
            {'article_number': n, 'text': f'ماده پژوهشی {n}: جستجوی عبارت آزمايشي {n}.'}
            for n in range(a,b+1)]}]}
        p.write_text(json.dumps(content, ensure_ascii=False), encoding='utf-8')
        result.append(str(p))
    return result


@pytest.fixture
def db(tmp_path):
    conn = connect(str(tmp_path / 'civil.sqlite3'))
    initialize(conn)
    yield conn
    conn.close()


def test_import_is_quarantined_and_complete(db, volumes):
    result = import_civil_research(db, volumes)
    assert result['article_count'] == 1335
    assert result['confidence'] == 'UNVERIFIED'
    assert research_article(db, 1335)['article_number'] == 1335
    assert research_article(db, 1)['raw_text'].startswith('ماده پژوهشی')
    assert research_stats(db)['publicly_published'] is False
    assert db.execute('SELECT COUNT(*) FROM article_versions').fetchone()[0] == 0
    assert db.execute('SELECT COUNT(*) FROM review_queue').fetchone()[0] == 0


def test_import_is_idempotent(db, volumes):
    first = import_civil_research(db, volumes)
    again = import_civil_research(db, volumes)
    assert first['imported'] is True
    assert again['imported'] is False
    assert first['snapshot_id'] == again['snapshot_id']
    assert db.execute('SELECT COUNT(*) FROM civil_research_articles').fetchone()[0] == 1335


def test_missing_article_rejected_atomically(db, volumes):
    content = json.loads(open(volumes[1], encoding='utf-8').read())
    content['divisions'][0]['articles'].pop()
    open(volumes[1], 'w', encoding='utf-8').write(json.dumps(content, ensure_ascii=False))
    with pytest.raises(ValueError, match='missing, duplicated'):
        import_civil_research(db, volumes)
    assert db.execute('SELECT COUNT(*) FROM article_versions').fetchone()[0] == 0


def test_duplicate_article_rejected(db, volumes):
    content = json.loads(open(volumes[0], encoding='utf-8').read())
    content['divisions'][0]['articles'][-1]['article_number'] = 1
    open(volumes[0], 'w', encoding='utf-8').write(json.dumps(content, ensure_ascii=False))
    with pytest.raises(ValueError, match='missing, duplicated'):
        import_civil_research(db, volumes)


def test_changed_source_is_new_immutable_snapshot(db, volumes):
    original = import_civil_research(db, volumes)
    content = json.loads(open(volumes[0], encoding='utf-8').read())
    content['divisions'][0]['articles'][0]['text'] = 'نسخه جدید پژوهشی و تأیید نشده'
    open(volumes[0], 'w', encoding='utf-8').write(json.dumps(content, ensure_ascii=False))
    updated = import_civil_research(db, volumes)
    assert updated['snapshot_id'] != original['snapshot_id']
    assert research_article(db, 1)['raw_text'] == 'نسخه جدید پژوهشی و تأیید نشده'
    assert research_article(db, 1, snapshot_id=original['snapshot_id'])['raw_text'].startswith('ماده پژوهشی')
    assert len(research_stats(db)['snapshots']) == 2


def test_persian_unicode_and_offline_viewer(db, volumes, tmp_path):
    import_civil_research(db, volumes)
    results = research_search(db, 'آزمایشی ۹۵۵')
    assert results['total'] >= 1
    assert any(r['article_number']==955 for r in results['results'])
    path = tmp_path / 'preview.html'
    out = export_research_preview(db, str(path))
    assert out['offline_only'] is True
    assert out['articles'] == 1335
    content = path.read_text('utf-8')
    assert 'تأییدنشده' in content
    assert 'ماده پژوهشی 1335' in content
    assert '<script>' in content


def test_safe_html_embedded_data(db, volumes, tmp_path):
    content = json.loads(open(volumes[0], encoding='utf-8').read())
    content['divisions'][0]['articles'][0]['text'] = '</script><script>alert(42)</script>'
    open(volumes[0], 'w', encoding='utf-8').write(json.dumps(content, ensure_ascii=False))
    import_civil_research(db, volumes)
    path=tmp_path/'preview.html'
    export_research_preview(db,str(path))
    data=path.read_text('utf-8')
    assert '</script><script>alert(42)' not in data
    assert r'\u003c/script\u003e' in data
