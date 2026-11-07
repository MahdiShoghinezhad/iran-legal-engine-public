"""Persian text search is read-only and excludes unreviewed or obsolete versions."""
import copy
import pytest
from fastapi.testclient import TestClient
from legalcore.api import app
from legalcore.store import connect, initialize
from legalcore.ingest import load_manifest, ingest_manifest
from legalcore.review import pending, decide


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "search.sqlite3")
    monkeypatch.setenv("LEGAL_DB", db_path)
    return TestClient(app), db_path


def test_search_never_exposes_pending(client):
    http, db_path = client
    with connect(db_path) as db:
        initialize(db)
        ingest_manifest(db, load_manifest("examples/demo-manifest.json"))
    data = http.get("/api/v1/search", params={"q": "آزمایشی"}).json()
    assert data["total"] == 0
    assert data["results"] == []


def test_search_by_text_number_and_persian_variants(client):
    http, db_path = client
    with connect(db_path) as db:
        initialize(db)
        ingest_manifest(db, load_manifest("examples/demo-manifest.json"))
        for item in pending(db):
            decide(db, item["id"], "demo-reviewer", approve=True)

    assert http.get("/api/v1/search", params={"q": "آزمایشی"}).json()["total"] == 2
    assert http.get("/api/v1/search", params={"q": "ماده آزمايشي ۱"}).json()["total"] == 1
    by_number = http.get("/api/v1/search", params={"q": "۱۲"}).json()
    assert by_number["total"] == 0
    data = http.get("/api/v1/search", params={"q": "آزمایشی", "limit": 1}).json()
    assert data["total"] == 2
    assert len(data["results"]) == 1
    assert data["results"][0]["source_url"].startswith("https://")


def test_only_latest_reviewed_article_searchable(client):
    http, db_path = client
    manifest = load_manifest("examples/demo-manifest.json")
    with connect(db_path) as db:
        initialize(db)
        ingest_manifest(db, manifest)
        decide(db, pending(db)[0]["id"], "reviewer", approve=True)
        old_phrase = "نمایش عملکرد نرم‌افزار"
        assert http.get("/api/v1/search", params={"q": old_phrase}).json()["total"] == 1

        changed = copy.deepcopy(manifest)
        changed["documents"][0]["articles"][0]["text"] = "این متن جدید صرفاً برای آزمون نسخه‌بندی جدید است."
        ingest_manifest(db, changed)
        assert http.get("/api/v1/search", params={"q": old_phrase}).json()["total"] == 1
        assert http.get("/api/v1/search", params={"q": "نسخه‌بندی جدید"}).json()["total"] == 0
        item = next(x for x in pending(db) if x["article_key"] == "1")
        decide(db, item["id"], "reviewer", approve=True)
        assert http.get("/api/v1/search", params={"q": old_phrase}).json()["total"] == 0
        assert http.get("/api/v1/search", params={"q": "نسخه‌بندی جدید"}).json()["total"] == 1


@pytest.mark.parametrize("params", [
    {"q": "ب"},
    {"q": "ب" * 121},
    {"q": "آزمایشی", "limit": 0},
    {"q": "آزمایشی", "limit": 100},
])
def test_search_input_validated(client, params):
    http, _ = client
    assert http.get("/api/v1/search", params=params).status_code == 422
