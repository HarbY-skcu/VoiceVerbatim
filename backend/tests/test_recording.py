import asyncio

from fastapi.testclient import TestClient

from backend.app.main import app, recording_session, audio_registry, silence_monitor, streaming_orchestrator

client = TestClient(app)


class FakeStreamingSession:
    async def send_audio(self, chunk: bytes) -> None:
        pass

    async def results(self):
        return
        yield  # pragma: no cover - makes this an async generator

    async def close(self) -> None:
        pass


class FakeStreamingService:
    async def start_session(self):
        return FakeStreamingSession()


def setup_function():
    silence_monitor.cancel()
    asyncio.run(recording_session.reset())
    asyncio.run(audio_registry.clear())
    # The shared streaming_orchestrator can hold state from a previous test
    # module's event loop; reset it and swap in a fake service so these
    # tests don't depend on a real Vosk model / ffmpeg being available.
    streaming_orchestrator.reset()
    streaming_orchestrator.service = FakeStreamingService()
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


def test_stop_ends_the_session_and_returns_to_idle():
    client.post("/api/recording/start")

    response = client.post("/api/recording/stop")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "idle"
    assert "transcription" in body
    assert client.get("/api/recording").json() == {"state": "idle"}


def test_stopping_when_idle_is_rejected():
    response = client.post("/api/recording/stop")

    assert response.status_code == 409
