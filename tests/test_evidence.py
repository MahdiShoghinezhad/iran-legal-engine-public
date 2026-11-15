"""No real law or third-party APIs; integration tests use fictional corpus fixtures."""
import pytest
from legalcore.store import connect, initialize
from legalcore.corpus import import_directory
from legalcore.evidence import attach_evidence, list_evidence, check_evidence

@pytest.fixture
def fixture(tmp_path):
    db = connect(str(tmp_path / 'research.sqlite3'))
    initialize(db)
    result = import_directory(db, 'examples/corpus-demo')
    assert result['new_snapshots'] == 2
    original = tmp_path / 'original.txt'
    original.write_text('ماده ساختگی پژوهشی', encoding='utf-8')
    yield db, original, tmp_path / 'vault'
    db.close()

def add(fixture, *, url='https://example.invalid/original'):
    db, original, vault = fixture
    return attach_evidence(db, 'fictional-iran-law-001', str(original), url,
                           evidence_root=str(vault))

def test_receipt_integrity_and_isolation(fixture):
    db, _, vault = fixture
    record = add(fixture)
    assert record['legal_status'] == 'UNVERIFIED'
    assert record['rights_status'] == 'NOT_ASSESSED'
    assert list_evidence(db, 'fictional-iran-law-001')['count'] == 1
    assert check_evidence(db, record['evidence_id'], evidence_root=str(vault))['file_integrity'] == 'ok'
    assert db.execute('SELECT COUNT(*) FROM article_versions').fetchone()[0] == 0

def test_duplicate_is_idempotent(fixture):
    assert add(fixture)['evidence_id'] == add(fixture)['evidence_id']

def test_changed_file_is_new_receipt(fixture):
    first = add(fixture)
    fixture[1].write_text('نسخه دوم پژوهشی ساختگی', encoding='utf-8')
    second = add(fixture)
    assert first['sha256'] != second['sha256']
    assert first['evidence_id'] != second['evidence_id']

def test_tamper_detection(fixture):
    db, original, root = fixture
    r = add(fixture)
    (root / r['relative_path']).write_text('tampered', encoding='utf-8')
    assert check_evidence(db, r['evidence_id'], evidence_root=str(root))['file_integrity'] == 'tampered'
    with pytest.raises(ValueError, match='collision'):
        add(fixture)

def test_missing_detection(fixture):
    db, original, root = fixture
    r = add(fixture)
    (root / r['relative_path']).unlink()
    assert check_evidence(db, r['evidence_id'], evidence_root=str(root))['file_integrity'] == 'missing'

def test_unknown_research_document_fails(fixture):
    db, original, root = fixture
    with pytest.raises(ValueError, match='snapshot'):
        attach_evidence(db, 'unknown-law', str(original), 'https://example.invalid/x',
                        evidence_root=str(root))

def test_invalid_file_types_and_url(fixture, tmp_path):
    db, original, root = fixture
    bogus = tmp_path / 'fake.pdf'
    bogus.write_bytes(b'not a PDF')
    with pytest.raises(ValueError, match='PDF'):
        attach_evidence(db, 'fictional-iran-law-001', str(bogus), 'https://example.invalid/x',
                        evidence_root=str(root))
    with pytest.raises(ValueError, match='HTTP'):
        add(fixture, url='file:///etc/passwd')
    with pytest.raises(ValueError, match='HTTP'):
        add(fixture, url='https://user:secret@example.invalid/source')
