"""Ticket 04: Transcription on Stop — HTTP wiring.

Exercises the endpoints that let audio reach the buffer and that trigger
transcription on Stop/Pause, using a fake transcription service installed
via dependency override so no real speech-to-text call is made.
"""

import asyncio
import base64

from fastapi.testclient import TestClient

from backend.app.main import app, recording_session, audio_registry, note, pipeline, streaming_orchestrator
from backend.app.transcription import TranscriptionError

client = TestClient(app)


class FakeTranscriptionService:
    def __init__(self, text: str = "hello world", fail: bool = False):
        self.text = text
        self.fail = fail

    async def transcribe(self, audio: bytes) -> str:
        if self.fail:
            raise TranscriptionError("transcription service unavailable")
        return self.text


def setup_function():
    asyncio.run(recording_session.reset())
    asyncio.run(audio_registry.clear())
    note.text = ""
    note.cursor = 0
    note.saved_text = None
    pipeline.buffer.flush()
    pipeline.service = FakeTranscriptionService()
    # A previous test module (e.g. test_recording_stream_ws.py) may have
    # left the shared streaming_orchestrator holding a session/consume task
    # bound to its own already-closed event loop; without this, /pause and
    # /stop here would try to await that stale task and raise a spurious
    # CancelledError unrelated to anything under test in this module.
    streaming_orchestrator.reset()


def send_audio(chunk: bytes):
    return client.post(
        "/api/recording/audio-chunk",
        json={"data": base64.b64encode(chunk).decode()},
    )


def test_audio_chunk_is_accepted_while_recording():
    client.post("/api/recording/start")

    response = send_audio(b"some-audio")

    assert response.status_code == 200


def test_stop_transcribes_buffered_audio_and_inserts_into_the_note():
    pipeline.service = FakeTranscriptionService(text="hello world")
    client.post("/api/recording/start")
    send_audio(b"audio-bytes")

    response = client.post("/api/recording/stop")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "idle"
    assert body["transcription"] == {"inserted": "hello world", "error": None}
    assert note.text == "hello world"
    assert note.saved_text == "hello world"


def test_pause_flushes_the_buffer_for_transcription():
    pipeline.service = FakeTranscriptionService(text="partial")
    client.post("/api/recording/start")
    send_audio(b"audio-bytes")

    response = client.post("/api/recording/pause")

    assert response.status_code == 200
    body = response.json()
    assert body["transcription"] == {"inserted": "partial", "error": None}
    assert note.text == "partial"


def test_resume_starts_a_new_buffer_after_pause_flushed_it():
    pipeline.service = FakeTranscriptionService(text="first")
    client.post("/api/recording/start")
    send_audio(b"audio-1")
    client.post("/api/recording/pause")

    pipeline.service = FakeTranscriptionService(text=" second")
    client.post("/api/recording/resume")
    send_audio(b"audio-2")
    client.post("/api/recording/stop")

    assert note.text == "first second"


def test_transcription_error_on_stop_surfaces_without_corrupting_the_note():
    note.text = "existing content"
    note.cursor = len("existing content")
    pipeline.service = FakeTranscriptionService(fail=True)
    client.post("/api/recording/start")
    send_audio(b"audio-bytes")

    response = client.post("/api/recording/stop")

    assert response.status_code == 200
    body = response.json()
    assert body["transcription"]["error"] == "transcription service unavailable"
    assert note.text == "existing content"
    assert note.saved_text is None


def test_stop_with_no_buffered_audio_reports_no_insertion():
    client.post("/api/recording/start")

    response = client.post("/api/recording/stop")

    assert response.json()["transcription"] == {"inserted": None, "error": None}
