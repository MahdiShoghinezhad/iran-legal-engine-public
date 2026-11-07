"""The browser preview exposes only reviewed demo content."""
from fastapi.testclient import TestClient
from legalcore.api import app

client = TestClient(app)

def test_ui_is_accessible():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "پیشخوان اسناد حقوقی" in response.text

def test_source_status_is_honest():
    response = client.get("/api/v1/updates/status")
    assert response.status_code == 200
    data = response.json()
    assert data["automatic_monitoring"] is False
    assert data["source_sync"] == "not_connected"
