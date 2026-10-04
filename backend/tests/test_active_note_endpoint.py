"""Ticket 14: GET /api/note exposes the Note being built from the flowing
transcript, including the gap-filling "Untitled N" title assigned at
record start."""

import asyncio

from fastapi.testclient import TestClient

from backend.app.main import app, recording_session, audio_registry, note, note_titles, silence_monitor, streaming_orchestrator

client = TestClient(app)


class FakeStreamingSession:
    async def send_audio(self, chunk: bytes) -> None:
        pass

    async def results(self):
        return
        yield  # pragma: no cover

    async def close(self) -> None:
        pass


class FakeStreamingService:
    async def start_session(self):
        return FakeStreamingSession()


def setup_function():
    silence_monitor.cancel()
    asyncio.run(recording_session.reset())
    asyncio.run(audio_registry.clear())
    streaming_orchestrator.reset()
    streaming_orchestrator.service = FakeStreamingService()
    note.text = ""
    note.saved_text = None
    note.title = None
    note_titles._free.clear()
    note_titles._in_use.clear()
    note_titles._next_if_no_gap = 1


def test_note_has_no_title_before_recording_starts():
    response = client.get("/api/note")
    assert response.status_code == 200
    assert response.json()["title"] is None


def test_starting_a_recording_assigns_an_untitled_n_title():
    client.post("/api/recording/start")

    response = client.get("/api/note")

    assert response.json()["title"] == "Untitled 1"


def test_stopping_and_starting_again_keeps_the_existing_title():
    client.post("/api/recording/start")
    client.post("/api/recording/stop")

    client.post("/api/recording/start")

    assert client.get("/api/note").json()["title"] == "Untitled 1"


def test_get_note_no_longer_exposes_a_cursor_field():
    """Ticket 14: cursor/positioning ownership moved to the frontend --
    the backend no longer tracks or returns one."""
    response = client.get("/api/note")

    assert "cursor" not in response.json()


def test_put_note_overwrites_the_text_wholesale():
    """Ticket 14: the frontend is the sole authority on composition/
    positioning -- it pushes a full-text overwrite, and the backend is a
    dumb sink with no splicing of its own."""
    client.put("/api/note", json={"text": "hello world"})

    response = client.get("/api/note")

    assert response.json()["text"] == "hello world"


def test_put_note_can_replace_text_with_something_unrelated_entirely():
    client.put("/api/note", json={"text": "first draft"})

    client.put("/api/note", json={"text": "a completely different second draft"})

    assert client.get("/api/note").json()["text"] == "a completely different second draft"


def test_put_note_persists_the_text_via_save():
    client.put("/api/note", json={"text": "hello world"})

    assert note.saved_text == "hello world"
