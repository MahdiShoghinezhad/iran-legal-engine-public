"""Tests use fictional offline data; never fetch external law sources."""
import copy
import json
import pytest
from legalcore.ingest import load_manifest
from legalcore.review import decide, pending, show_pending
from legalcore.store import connect, initialize
from legalcore.sync import sync_local_manifest


@pytest.fixture
def local_store(tmp_path):
    path = str(tmp_path / "sync.sqlite3")
    connection = connect(path)
    initialize(connection)
    yield connection
    connection.close()


def write_manifest(tmp_path, payload):
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_first_sync_only_stages_and_logs(local_store, tmp_path):
    result = sync_local_manifest(local_store, write_manifest(tmp_path, load_manifest("examples/demo-manifest.json")))
    assert result["proposed"] == 2
    assert result["source"] == "local_file_only"
    assert len(pending(local_store)) == 2
    assert local_store.execute("SELECT COUNT(*) FROM article_versions").fetchone()[0] == 0
    assert local_store.execute("SELECT status FROM local_sync_runs").fetchone()[0] == "ok"


def test_repeat_sync_idempotent(local_store, tmp_path):
    path = write_manifest(tmp_path, load_manifest("examples/demo-manifest.json"))
    sync_local_manifest(local_store, path)
    repeated = sync_local_manifest(local_store, path)
    assert repeated["proposed"] == 0
    assert repeated["already_pending"] == 2
    assert len(pending(local_store)) == 2


def test_amendment_requires_review(local_store, tmp_path):
    manifest = load_manifest("examples/demo-manifest.json")
    path = write_manifest(tmp_path, manifest)
    sync_local_manifest(local_store, path)
    first = pending(local_store)[0]
    assert "آزمایشی" in show_pending(local_store, first["id"])["proposed_text"]
    decide(local_store, first["id"], "demo-reviewer", approve=True)
    edited = copy.deepcopy(manifest)
    edited["documents"][0]["articles"][0]["text"] += " تغییر ساختگی دوم."
    write_manifest(tmp_path, edited)
    result = sync_local_manifest(local_store, path)
    assert result["proposed"] == 1
    assert local_store.execute("SELECT COUNT(*) FROM article_versions WHERE article_key='1'").fetchone()[0] == 1
    item = next(x for x in pending(local_store) if x["article_key"] == "1")
    assert "تغییر ساختگی دوم" in show_pending(local_store, item["id"])["proposed_text"]
    decide(local_store, item["id"], "demo-reviewer", approve=True)
    assert local_store.execute("SELECT COUNT(*) FROM article_versions WHERE article_key='1'").fetchone()[0] == 2


def test_dry_run_never_writes(local_store, tmp_path):
    result = sync_local_manifest(local_store, write_manifest(tmp_path, load_manifest("examples/demo-manifest.json")), dry_run=True)
    assert result["status"] == "dry_run"
    assert result["proposed"] == 2
    assert local_store.execute("SELECT COUNT(*) FROM local_sync_runs").fetchone()[0] == 0
    assert len(pending(local_store)) == 0


def test_invalid_document_audited_without_publication(local_store, tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"documents":[{"id":"test"}]}', encoding="utf-8")
    with pytest.raises(ValueError):
        sync_local_manifest(local_store, str(path))
    assert local_store.execute("SELECT status FROM local_sync_runs").fetchone()[0] == "failed"
    assert len(pending(local_store)) == 0
