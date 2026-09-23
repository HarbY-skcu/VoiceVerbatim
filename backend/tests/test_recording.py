import asyncio

from fastapi.testclient import TestClient

from backend.app.main import app, recording_session, audio_registry, silence_monitor, streaming_orchestrator

client = TestClient(app)


def setup_function():
    silence_monitor.cancel()
    asyncio.run(recording_session.reset())
    asyncio.run(audio_registry.clear())
    # See test_recording_transcription.py's setup_function for why this is
    # needed: the shared streaming_orchestrator can hold state from a
    # previous test module's event loop.
    streaming_orchestrator.reset()
    asyncio.run(
        audio_registry.register(
            [
                __import__(
                    "backend.app.audio_sources", fromlist=["AudioSource"]
                ).AudioSource(id="default", label="Default Mic")
            ]
        )
    )


def test_status_is_idle_before_anything_happens():
    response = client.get("/api/recording")
    assert response.status_code == 200
    assert response.json() == {"state": "idle"}


def test_start_begins_a_recording_session():
    response = client.post("/api/recording/start")
    assert response.status_code == 200
    assert response.json() == {"state": "recording"}
    assert client.get("/api/recording").json() == {"state": "recording"}


def test_starting_a_second_recording_while_one_is_active_is_rejected():
    client.post("/api/recording/start")

    response = client.post("/api/recording/start")

    assert response.status_code == 409
    assert client.get("/api/recording").json() == {"state": "recording"}


def test_pause_stops_the_mic_and_enables_editing():
    client.post("/api/recording/start")

    response = client.post("/api/recording/pause")

    assert response.status_code == 200
    assert response.json() == {
        "state": "paused",
        "transcription": {"inserted": None, "error": None},
    }


def test_pausing_when_not_recording_is_rejected():
    response = client.post("/api/recording/pause")

    assert response.status_code == 409
    assert client.get("/api/recording").json() == {"state": "idle"}


def test_resume_restarts_capture_from_paused():
    client.post("/api/recording/start")
    client.post("/api/recording/pause")

    response = client.post("/api/recording/resume")

    assert response.status_code == 200
    assert response.json() == {"state": "recording"}


def test_resuming_when_not_paused_is_rejected():
    client.post("/api/recording/start")

    response = client.post("/api/recording/resume")

    assert response.status_code == 409
    assert client.get("/api/recording").json() == {"state": "recording"}


def test_stop_ends_the_session_and_returns_to_idle():
    client.post("/api/recording/start")

    response = client.post("/api/recording/stop")

    assert response.status_code == 200
    assert response.json() == {
        "state": "idle",
        "transcription": {"inserted": None, "error": None},
    }
    assert client.get("/api/recording").json() == {"state": "idle"}


def test_stop_from_paused_also_ends_the_session():
    client.post("/api/recording/start")
    client.post("/api/recording/pause")

    response = client.post("/api/recording/stop")

    assert response.status_code == 200
    assert response.json() == {
        "state": "idle",
        "transcription": {"inserted": None, "error": None},
    }


def test_stopping_when_idle_is_rejected():
    response = client.post("/api/recording/stop")

    assert response.status_code == 409
