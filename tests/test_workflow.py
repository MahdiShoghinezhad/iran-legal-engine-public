"""No live third-party dependencies: all tests use mock legal sources."""
import copy
import json
import pytest
from legalcore.store import connect, initialize
from legalcore.ingest import fingerprint, ingest_manifest, load_manifest
from legalcore.review import decide, pending

@pytest.fixture
def db(tmp_path):
    connection = connect(str(tmp_path / "test.sqlite3"))
    initialize(connection)
    yield connection
    connection.close()

@pytest.fixture
def manifest():
    return load_manifest("examples/demo-manifest.json")

def test_ingest_creates_review_not_publication(db, manifest):
    result = ingest_manifest(db, manifest)
    assert result["proposed"] == 2
    assert len(pending(db)) == 2
    assert db.execute("SELECT COUNT(*) FROM article_versions").fetchone()[0] == 0

def test_dry_run_does_not_create_documents_or_reviews(db, manifest):
    result = ingest_manifest(db, manifest, dry_run=True)
    assert result["proposed"] == 2
    assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0
    assert not pending(db)

def test_idempotent_import(db, manifest):
    ingest_manifest(db, manifest)
    result = ingest_manifest(db, manifest)
    assert result["proposed"] == 0
    assert result["already_pending"] == 2

def test_approval_is_explicit_and_versioned(db, manifest):
    ingest_manifest(db, manifest)
    item = pending(db)[0]
    decide(db, item["id"], "sample-reviewer", approve=True)
    latest = db.execute("SELECT version_number FROM article_versions WHERE article_key='1'").fetchone()
    assert latest["version_number"] == 1
    assert ingest_manifest(db, manifest)["unchanged"] == 1
    updated = copy.deepcopy(manifest)
    updated["documents"][0]["articles"][0]["text"] += " نسخه اصلاحی آزمایشی."
    result = ingest_manifest(db, updated)
    assert result["proposed"] == 1
    assert db.execute("SELECT COUNT(*) FROM article_versions WHERE article_key='1'").fetchone()[0] == 1
    new_item = next(r for r in pending(db) if r["article_key"] == "1")
    decide(db, new_item["id"], "sample-reviewer", approve=True)
    versions = db.execute("SELECT version_number FROM article_versions WHERE article_key='1' ORDER BY version_number").fetchall()
    assert [row[0] for row in versions] == [1, 2]

def test_rejection_does_not_publish(db, manifest):
    ingest_manifest(db, manifest)
    decide(db, pending(db)[0]["id"], "sample-reviewer", approve=False)
    assert db.execute("SELECT COUNT(*) FROM article_versions").fetchone()[0] == 0

def test_duplicate_review_fails(db, manifest):
    ingest_manifest(db, manifest)
    item = pending(db)[0]
    decide(db, item["id"], "reviewer", approve=True)
    with pytest.raises(ValueError):
        decide(db, item["id"], "reviewer", approve=True)

def test_persian_normalization_hash():
    assert fingerprint("قانون ک ي ۱۲۳") == fingerprint("قانون ک ی 123")

def test_manifest_duplicate_detection(tmp_path, manifest):
    other = copy.deepcopy(manifest)
    other["documents"][0]["articles"].append(other["documents"][0]["articles"][0])
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(other, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate article"):
        load_manifest(str(p))
