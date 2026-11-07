import pytest
from fastapi.testclient import TestClient
from legalcore.api import app
from legalcore.store import connect, initialize
from legalcore.ingest import load_manifest, ingest_manifest
from legalcore.review import decide, pending

@pytest.fixture
def client(tmp_path, monkeypatch):
    path = str(tmp_path / "api.sqlite3")
    monkeypatch.setenv("LEGAL_DB", path)
    yield TestClient(app), path

def test_api_hides_unreviewed(client):
    testclient, path = client
    with connect(path) as db:
        initialize(db)
        ingest_manifest(db, load_manifest("examples/demo-manifest.json"))
    assert testclient.get("/api/v1/documents").json()["documents"] == []
    assert testclient.get("/api/v1/documents/fictional-legal-demo/articles/1").status_code == 404

def test_api_publishes_approved_demo_only(client):
    testclient, path = client
    with connect(path) as db:
        initialize(db)
        ingest_manifest(db, load_manifest("examples/demo-manifest.json"))
        decide(db, pending(db)[0]["id"], "test-reviewer", approve=True)
    res = testclient.get("/api/v1/documents/fictional-legal-demo/articles/1")
    assert res.status_code == 200
    assert res.json()["demo_only"] is True
    assert res.json()["version_number"] == 1
    assert len(testclient.get("/api/v1/documents").json()["documents"]) == 1
