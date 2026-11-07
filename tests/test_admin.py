"""Administrative API must be opt-in, authenticated and demo-only."""
import copy
import pytest
from fastapi.testclient import TestClient
from legalcore.api import app
from legalcore.ingest import load_manifest
from legalcore.store import connect, initialize


@pytest.fixture
def admin_client(monkeypatch, tmp_path):
    db = str(tmp_path / "admin.sqlite3")
    monkeypatch.setenv("LEGAL_DB", db)
    monkeypatch.setenv("LEGAL_ADMIN_ENABLED", "1")
    monkeypatch.setenv("LEGAL_ADMIN_TOKEN", "a-secret-test-token-of-at-least-32-characters")
    client = TestClient(app)
    return client, db, {"X-Admin-Token": "a-secret-test-token-of-at-least-32-characters"}


def test_admin_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("LEGAL_ADMIN_ENABLED", raising=False)
    monkeypatch.delenv("LEGAL_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("LEGAL_DB", str(tmp_path / "empty.sqlite3"))
    r = TestClient(app).get("/api/v1/admin/pending")
    assert r.status_code == 503
    assert TestClient(app).post("/api/v1/admin/import-demo", json={}).status_code == 503


def test_admin_requires_secret(admin_client):
    client, db, headers = admin_client
    assert client.get("/api/v1/admin/pending").status_code == 401
    assert client.get("/api/v1/admin/pending", headers={"X-Admin-Token": "wrong"}).status_code == 401
    assert client.post("/api/v1/admin/import-demo", json=load_manifest("examples/demo-manifest.json")).status_code == 401
    assert client.get("/api/v1/admin/pending", headers=headers).status_code == 200


def test_admin_import_approve_and_history(admin_client):
    client, db_path, headers = admin_client
    manifest = load_manifest("examples/demo-manifest.json")
    imported = client.post("/api/v1/admin/import-demo", json=manifest, headers=headers)
    assert imported.status_code == 200
    assert imported.json()["proposed"] == 2
    assert client.get("/api/v1/documents").json()["documents"] == []
    queue = client.get("/api/v1/admin/pending", headers=headers).json()
    assert queue["total"] == 2
    id_ = next(item["id"] for item in queue["results"] if item["article_key"] == "1")
    item = client.get("/api/v1/admin/pending/" + str(id_), headers=headers).json()
    assert item["previous_text"] is None
    assert "آزمایشی" in item["proposed_text"]
    assert item["unified_diff"]
    decided = client.post("/api/v1/admin/pending/" + str(id_) + "/decision",
                          headers=headers, json={"action": "approve", "reviewer": "Test Reviewer"})
    assert decided.status_code == 200
    assert decided.json()["decision"] == "approved"
    article = client.get("/api/v1/documents/fictional-legal-demo/articles/1")
    assert article.status_code == 200
    assert article.json()["version_number"] == 1

    edited = copy.deepcopy(manifest)
    edited["documents"][0]["articles"][0]["text"] = "ماده نمونه اصلاح‌شده ساختگی"
    assert client.post("/api/v1/admin/import-demo", json=edited, headers=headers).json()["proposed"] == 1
    queue = client.get("/api/v1/admin/pending", headers=headers).json()
    next_id = next(x["id"] for x in queue["results"] if x["article_key"] == "1")
    comparison = client.get("/api/v1/admin/pending/" + str(next_id), headers=headers).json()
    assert comparison["previous_version_number"] == 1
    assert comparison["previous_text"] != comparison["proposed_text"]
    assert "اصلاح‌شده" not in article.json()["text"]
    assert client.post("/api/v1/admin/pending/" + str(next_id) + "/decision",
                       headers=headers, json={"action": "reject", "reviewer": "Test Reviewer"}).status_code == 200
    assert client.get("/api/v1/documents/fictional-legal-demo/articles/1").json()["version_number"] == 1
    assert client.post("/api/v1/admin/pending/" + str(next_id) + "/decision",
                       headers=headers, json={"action": "approve", "reviewer": "Test Reviewer"}).status_code == 409


def test_unverified_civil_law_fails_closed(admin_client):
    client, db_path, headers = admin_client
    data = load_manifest("examples/demo-manifest.json")
    data["dataset_type"] = "UNVERIFIED_SOURCE"
    data["documents"][0]["kind"] = "law_unverified"
    data["documents"][0]["source_url"] = "https://github.com/third-party"
    assert client.post("/api/v1/admin/import-demo", json=data, headers=headers).status_code == 422
    with connect(db_path) as db:
        initialize(db)
        assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM article_versions").fetchone()[0] == 0


def test_admin_refuses_non_demo_review_even_if_queued_elsewhere(admin_client):
    client, db_path, headers = admin_client
    with connect(db_path) as db:
        initialize(db)
        db.execute("INSERT INTO documents(id,title,kind,source_name,source_url) VALUES(?,?,?,?,?)",
                   ("civil", "Civil Code", "law_unverified", "research", "https://example.invalid/research"))
        db.execute("INSERT INTO review_queue(document_id,article_key,proposed_text,sha256,source_url) VALUES(?,?,?,?,?)",
                   ("civil", "1", "unverified law", "hash", "https://example.invalid/research"))
        db.commit()
    assert client.get("/api/v1/admin/pending", headers=headers).json()["total"] == 0
    assert client.get("/api/v1/admin/pending/1", headers=headers).status_code == 404
    assert client.post("/api/v1/admin/pending/1/decision", headers=headers,
                       json={"action": "approve", "reviewer": "Reviewer"}).status_code == 404
    assert client.get("/api/v1/documents").json()["documents"] == []


def test_admin_validation_and_secure_page(admin_client):
    client, db_path, headers = admin_client
    r = client.get("/admin")
    assert r.status_code == 200
    assert "no-store" in r.headers["cache-control"]
    assert "مدیریت مواد" in r.text
    assert "a-secret-test-token" not in r.text
    assert client.post("/api/v1/admin/import-demo", headers={**headers, "Content-Type": "application/json"},
                       content=b"x" * (256 * 1024 + 1)).status_code == 413
    assert client.post("/api/v1/admin/import-demo", headers=headers,
                       json={"dataset_type": "FICTIONAL_DEMO_ONLY", "documents": []}).status_code == 422
    assert client.get("/api/v1/admin/pending?limit=101", headers=headers).status_code == 422
