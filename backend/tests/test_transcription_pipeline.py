"""Ticket 04: Transcription on Stop.

Covers the pipeline that turns buffered audio into text inserted into the
active Note, without touching HTTP — the endpoint wiring is exercised
separately in test_recording.py.
"""

from backend.app.audio_buffer import AudioBuffer
from backend.app.note import ActiveNote
from backend.app.transcription import TranscriptionError
from backend.app.transcription_pipeline import TranscriptionPipeline


class FakeTranscriptionService:
    def __init__(self, text: str = "hello world", fail: bool = False):
        self.text = text
        self.fail = fail
        self.received: list[bytes] = []

    async def transcribe(self, audio: bytes) -> str:
        self.received.append(audio)
        if self.fail:
            raise TranscriptionError("transcription service unavailable")
        return self.text


def make_pipeline(text="hello world", fail=False):
    buffer = AudioBuffer()
    note = ActiveNote()
    service = FakeTranscriptionService(text=text, fail=fail)
    pipeline = TranscriptionPipeline(buffer=buffer, note=note, service=service)
    return pipeline, buffer, note, service


async def test_flush_with_empty_buffer_does_nothing():
    pipeline, buffer, note, service = make_pipeline()

    result = await pipeline.flush_and_transcribe()

    assert result == {"inserted": None, "error": None}
    assert service.received == []
    assert note.text == ""


async def test_flush_sends_buffered_audio_to_the_transcription_service():
    pipeline, buffer, note, service = make_pipeline(text="the quick fox")
    buffer.append(b"chunk-1")
    buffer.append(b"chunk-2")

    result = await pipeline.flush_and_transcribe()

    assert service.received == [b"chunk-1chunk-2"]
    assert result == {"inserted": "the quick fox", "error": None}


async def test_flush_clears_the_buffer_so_resume_starts_a_new_one():
    pipeline, buffer, note, service = make_pipeline()
    buffer.append(b"chunk-1")

    await pipeline.flush_and_transcribe()

    assert buffer.is_empty


async def test_transcribed_text_is_inserted_at_the_current_cursor_position():
    pipeline, buffer, note, service = make_pipeline(text=" world")
    note.text = "hello"
    note.cursor = 5
    buffer.append(b"audio")

    await pipeline.flush_and_transcribe()

    assert note.text == "hello world"
    assert note.cursor == len("hello world")


async def test_note_is_auto_saved_after_transcription_finishes():
    pipeline, buffer, note, service = make_pipeline(text="saved text")
    buffer.append(b"audio")

    await pipeline.flush_and_transcribe()

    assert note.saved_text == "saved text"


async def test_transcription_error_surfaces_without_corrupting_the_note():
    pipeline, buffer, note, service = make_pipeline(fail=True)
    note.text = "existing content"
    note.cursor = len("existing content")
    buffer.append(b"audio")

    result = await pipeline.flush_and_transcribe()

    assert result["inserted"] is None
    assert result["error"] == "transcription service unavailable"
    assert note.text == "existing content"
    assert note.saved_text is None
