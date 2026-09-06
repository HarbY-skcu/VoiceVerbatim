from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_sidebar_tabs_returns_all_notes_and_bookmarks():
    response = client.get("/api/sidebar/tabs")
    assert response.status_code == 200
    data = response.json()
    assert data["tabs"] == ["All Notes", "Bookmarks"]


def test_sidebar_tabs_returns_default_active_tab():
    response = client.get("/api/sidebar/tabs")
    data = response.json()
    assert data["active"] == "All Notes"
