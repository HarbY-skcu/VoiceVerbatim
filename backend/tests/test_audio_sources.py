from fastapi.testclient import TestClient

from app.main import app, audio_registry

client = TestClient(app)


def setup_function():
    audio_registry.clear()


def test_get_audio_sources_is_empty_before_any_are_registered():
    response = client.get("/api/audio/sources")
    assert response.status_code == 200
    assert response.json() == {"sources": [], "active": None}


def test_registering_devices_stores_them_and_selects_the_system_default():
    response = client.put(
        "/api/audio/sources",
        json={
            "sources": [
                {"id": "default", "label": "Default – Built-in Mic"},
                {"id": "usb-mic-1", "label": "USB Microphone"},
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert [s["id"] for s in body["sources"]] == ["default", "usb-mic-1"]
    assert body["active"] == "default"
    # and it is durable for the next reader
    assert client.get("/api/audio/sources").json() == body


def test_registering_devices_without_a_system_default_selects_the_first_one():
    response = client.put(
        "/api/audio/sources",
        json={"sources": [{"id": "mic-a", "label": "Mic A"}, {"id": "mic-b", "label": "Mic B"}]},
    )
    assert response.status_code == 200
    assert response.json()["active"] == "mic-a"


def test_activating_a_known_source_changes_the_selection():
    client.put(
        "/api/audio/sources",
        json={"sources": [{"id": "default"}, {"id": "usb-mic-1"}]},
    )

    response = client.put("/api/audio/sources/active", json={"id": "usb-mic-1"})

    assert response.status_code == 200
    assert response.json()["active"] == "usb-mic-1"
    assert client.get("/api/audio/sources").json()["active"] == "usb-mic-1"


def test_activating_an_unknown_source_is_rejected_and_leaves_selection_unchanged():
    client.put(
        "/api/audio/sources",
        json={"sources": [{"id": "default"}, {"id": "usb-mic-1"}]},
    )

    response = client.put("/api/audio/sources/active", json={"id": "no-such-mic"})

    assert response.status_code == 400
    assert client.get("/api/audio/sources").json()["active"] == "default"


def test_re_registering_keeps_the_current_selection_when_that_device_is_still_present():
    client.put(
        "/api/audio/sources",
        json={"sources": [{"id": "default"}, {"id": "usb-mic-1"}]},
    )
    client.put("/api/audio/sources/active", json={"id": "usb-mic-1"})

    response = client.put(
        "/api/audio/sources",
        json={"sources": [{"id": "default"}, {"id": "usb-mic-1"}, {"id": "cam-mic"}]},
    )

    assert response.json()["active"] == "usb-mic-1"
