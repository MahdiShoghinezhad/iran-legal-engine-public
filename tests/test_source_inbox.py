"""Integration tests use only fictional documents; network access is never needed."""
import json
import shutil
import pytest

from legalcore.store import connect, initialize
from legalcore.corpus import import_directory
from legalcore.evidence import initialize_evidence, list_evidence
from legalcore.source_registry import register_source, initialize_source_registry, list_sources
from legalcore.source_inbox import import_inbox, inbox_history, inbox_diff


@pytest.fixture
def workspace(tmp_path):
    db = connect(str(tmp_path / "research.sqlite3"))
    initialize(db)
    assert import_directory(db, "examples/corpus-demo")["new_snapshots"] == 2
    initialize_evidence(db)
    initialize_source_registry(db)
    register_source(db, "demo-source", "Example research source", "https://example.invalid/", "test_fixture")
    inbox = tmp_path / "inbox"
    shutil.copytree("examples/source-inbox-demo", inbox)
    yield db, inbox, str(tmp_path / "vault")
    db.close()


def _load(folder):
    path = folder / "inbox.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _save(folder, payload):
    path = folder / "inbox.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_initial_intake_keeps_research_quarantined(workspace):
    db, folder, vault = workspace
    out = import_inbox(db, str(folder / "inbox.json"), evidence_root=vault)
    assert out["records"][0]["change_state"] == "FIRST_SEEN"
    assert out["network_requests"] == 0
    assert out["legal_authenticity_verified"] is False
    assert out["publicly_published"] is False
    assert db.execute("SELECT COUNT(*) FROM article_versions").fetchone()[0] == 0
    assert list_evidence(db, "fictional-iran-law-001")["count"] == 1
    assert list_sources(db)["sources"][0]["linked_evidence"] == 1
    history = inbox_history(db, "demo-source", "fictional-iran-law-001", "TEST-001")
    assert history["count"] == 1
    assert inbox_diff(db, "demo-source", "fictional-iran-law-001", "TEST-001", evidence_root=vault)["file_bytes_changed"] is False


def test_repeat_intake_marks_unchanged_and_deduplicates_vault(workspace):
    db, folder, vault = workspace
    path = str(folder / "inbox.json")
    import_inbox(db, path, evidence_root=vault)
    second = import_inbox(db, path, evidence_root=vault)
    assert second["records"][0]["change_state"] == "UNCHANGED"
    assert list_evidence(db, "fictional-iran-law-001")["count"] == 1
    assert inbox_history(db, "demo-source", "fictional-iran-law-001", "TEST-001")["count"] == 2


def test_source_bytes_change_and_text_diff(workspace):
    db, folder, vault = workspace
    path = str(folder / "inbox.json")
    import_inbox(db, path, evidence_root=vault)
    (folder / "demo-original.txt").write_text("این نسخه جدید ساختگی است.\nتغییر پژوهشی آزمایشی\n", encoding="utf-8")
    changed = import_inbox(db, path, evidence_root=vault)
    assert changed["records"][0]["change_state"] == "CHANGED_BYTES"
    assert changed["records"][0]["review_required"] is True
    result = inbox_diff(db, "demo-source", "fictional-iran-law-001", "TEST-001", evidence_root=vault)
    assert result["file_bytes_changed"] is True
    assert "تغییر پژوهشی" in result["unified_diff"]
    assert result["legal_amendment_verified"] is False
    assert db.execute("SELECT COUNT(*) FROM article_versions").fetchone()[0] == 0


def test_dry_run_does_not_copy_or_store_observations(workspace, tmp_path):
    db, folder, vault = workspace
    result = import_inbox(db, str(folder / "inbox.json"), dry_run=True, evidence_root=vault)
    assert result["records"][0]["change_state"] == "FIRST_SEEN"
    assert not (tmp_path / "vault").exists()
    assert db.execute("SELECT COUNT(*) FROM source_inbox_observations").fetchone()[0] == 0
    assert list_evidence(db, "fictional-iran-law-001")["count"] == 0


def test_mismatched_source_host_fails_before_copy(workspace):
    db, folder, vault = workspace
    payload = _load(folder)
    payload["records"][0]["observed_url"] = "https://example.invalid.malicious.test/other"
    with pytest.raises(ValueError, match="hostname"):
        import_inbox(db, _save(folder, payload), evidence_root=vault)
    assert db.execute("SELECT COUNT(*) FROM source_inbox_observations").fetchone()[0] == 0


def test_path_traversal_is_rejected(workspace):
    db, folder, vault = workspace
    payload = _load(folder)
    payload["records"][0]["local_file"] = "../outside.txt"
    with pytest.raises(ValueError, match="local_file"):
        import_inbox(db, _save(folder, payload), evidence_root=vault)


def test_symlink_rejected(workspace):
    db, folder, vault = workspace
    source = folder / "link.txt"
    try:
        source.symlink_to(folder / "demo-original.txt")
    except OSError:
        pytest.skip("Symlinks unavailable on this platform")
    payload = _load(folder)
    payload["records"][0]["local_file"] = "link.txt"
    with pytest.raises(ValueError, match="Symlink"):
        import_inbox(db, _save(folder, payload), evidence_root=vault)


def test_inbox_rejects_duplicate_reference_and_missing_document(workspace):
    db, folder, vault = workspace
    payload = _load(folder)
    payload["records"].append(payload["records"][0].copy())
    with pytest.raises(ValueError, match="Duplicate"):
        import_inbox(db, _save(folder, payload), evidence_root=vault)
    payload["records"].pop()
    payload["records"][0]["instrument_id"] = "missing-legal-document"
    with pytest.raises(ValueError, match="Import the research corpus"):
        import_inbox(db, _save(folder, payload), evidence_root=vault)


def test_inbox_no_reliance_on_external_api(workspace):
    db, folder, vault = workspace
    result = import_inbox(db, str(folder / "inbox.json"), evidence_root=vault)
    assert result["network_requests"] == 0
    assert not result["publicly_published"]
    assert not result["legal_authenticity_verified"]
