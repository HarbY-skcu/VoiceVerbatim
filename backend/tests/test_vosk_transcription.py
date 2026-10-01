"""Seam under test: VoskStreamingTranscriptionSession's send_audio()/
results()/close() against the Transcoder and Recognizer protocols, using
fakes so no real ffmpeg binary or Vosk model is required.

VoskStreamingTranscriptionService.start_session() is exercised below via a
monkeypatched `_load_model`, since loading a real Vosk model isn't
available in this environment. Those tests also assert that model loading
is offloaded to a worker thread rather than run directly on the event
loop's thread (the bug behind the "POST /api/recording/start looks stuck
until Ctrl-C" symptom).
"""

import asyncio
import threading

import backend.app.vosk_transcription as vosk_transcription
from backend.app.transcription import StreamingResult, TranscriptionError
from backend.app.vosk_transcription import (
    VoskStreamingTranscriptionService,
    VoskStreamingTranscriptionSession,
)


class FakeTranscoder:
    """Returns pre-programmed PCM per feed() call, in order."""

    def __init__(self, feed_outputs=None, flush_output=b""):
        self.feed_outputs = list(feed_outputs or [])
        self.flush_output = flush_output
        self.fed_chunks: list[bytes] = []
        self.flushed = False

    async def feed(self, chunk: bytes) -> bytes:
        self.fed_chunks.append(chunk)
        if self.feed_outputs:
            return self.feed_outputs.pop(0)
        return b""

    async def flush(self) -> bytes:
        self.flushed = True
        return self.flush_output


class FakeRecognizer:
    """Scriptable recognizer: caller queues whether each accept_waveform()
    call should report an endpoint, and what result()/partial_result()/
    final_result() should then return."""

    def __init__(self):
        self.endpoints: list[bool] = []
        self.results: list[str] = []
        self.partials: list[str] = []
        self.final: str = ""
        self.accepted: list[bytes] = []

    def accept_waveform(self, pcm: bytes) -> bool:
        self.accepted.append(pcm)
        return self.endpoints.pop(0) if self.endpoints else False

    def result(self) -> str:
        return self.results.pop(0) if self.results else ""

    def partial_result(self) -> str:
        return self.partials.pop(0) if self.partials else ""

    def final_result(self) -> str:
        return self.final


async def _drain_available(session: VoskStreamingTranscriptionSession) -> list:
    """Collect whatever results are already queued without blocking."""
    collected = []
    while not session._queue.empty():
        item = session._queue.get_nowait()
        if item is not None:
            collected.append(item)
    return collected


async def test_send_audio_with_no_decoded_pcm_yields_nothing():
    transcoder = FakeTranscoder(feed_outputs=[b""])
    recognizer = FakeRecognizer()
    session = VoskStreamingTranscriptionSession(
        recognizer=recognizer, transcoder=transcoder
    )

    await session.send_audio(b"webm-chunk")

    assert transcoder.fed_chunks == [b"webm-chunk"]
    assert recognizer.accepted == []
    assert await _drain_available(session) == []


async def test_send_audio_with_interim_pcm_yields_a_non_final_result():
    transcoder = FakeTranscoder(feed_outputs=[b"\x00\x01pcm"])
    recognizer = FakeRecognizer()
    recognizer.endpoints = [False]
    recognizer.partials = ["hello wor"]
    session = VoskStreamingTranscriptionSession(
        recognizer=recognizer, transcoder=transcoder
    )

    await session.send_audio(b"webm-chunk")

    results = await _drain_available(session)
    assert results == [StreamingResult(text="hello wor", final=False)]
    assert recognizer.accepted == [b"\x00\x01pcm"]


async def test_send_audio_at_an_endpoint_yields_a_final_result():
    transcoder = FakeTranscoder(feed_outputs=[b"\x00\x01pcm"])
    recognizer = FakeRecognizer()
    recognizer.endpoints = [True]
    recognizer.results = ["hello world"]
    session = VoskStreamingTranscriptionSession(
        recognizer=recognizer, transcoder=transcoder
    )

    await session.send_audio(b"webm-chunk")

    results = await _drain_available(session)
    assert results == [StreamingResult(text="hello world", final=True)]


async def test_send_audio_with_empty_partial_yields_nothing():
    transcoder = FakeTranscoder(feed_outputs=[b"\x00\x01pcm"])
    recognizer = FakeRecognizer()
    recognizer.endpoints = [False]
    recognizer.partials = [""]
    session = VoskStreamingTranscriptionSession(
        recognizer=recognizer, transcoder=transcoder
    )

    await session.send_audio(b"webm-chunk")

    assert await _drain_available(session) == []


async def test_close_flushes_the_transcoder_and_feeds_remaining_pcm():
    transcoder = FakeTranscoder(flush_output=b"\x00\x01trailing-pcm")
    recognizer = FakeRecognizer()
    recognizer.final = ""
    session = VoskStreamingTranscriptionSession(
        recognizer=recognizer, transcoder=transcoder
    )

    await session.close()

    assert transcoder.flushed
    assert recognizer.accepted == [b"\x00\x01trailing-pcm"]


async def test_close_force_finalizes_a_trailing_partial_utterance():
    transcoder = FakeTranscoder()
    recognizer = FakeRecognizer()
    recognizer.final = "trailing text"
    session = VoskStreamingTranscriptionSession(
        recognizer=recognizer, transcoder=transcoder
    )

    await session.close()

    results = await _drain_available(session)
    assert results == [StreamingResult(text="trailing text", final=True)]


async def test_close_with_no_trailing_text_yields_no_final_result():
    transcoder = FakeTranscoder()
    recognizer = FakeRecognizer()
    recognizer.final = ""
    session = VoskStreamingTranscriptionSession(
        recognizer=recognizer, transcoder=transcoder
    )

    await session.close()

    assert await _drain_available(session) == []


async def test_results_stream_ends_after_close():
    transcoder = FakeTranscoder()
    recognizer = FakeRecognizer()
    session = VoskStreamingTranscriptionSession(
        recognizer=recognizer, transcoder=transcoder
    )

    async def consume():
        return [r async for r in session.results()]

    consume_task = asyncio.create_task(consume())
    await session.close()
    collected = await consume_task

    assert collected == []


async def test_start_session_loads_the_model_off_the_event_loop(monkeypatch):
    """start_session() must not block the event loop while the (multi-GB)
    model loads: it should run _load_model() in a worker thread, not on
    the calling coroutine's thread."""
    main_thread = threading.current_thread()
    load_thread = None

    def fake_load_model(model_path):
        nonlocal load_thread
        load_thread = threading.current_thread()
        return object()

    monkeypatch.setattr(vosk_transcription, "_load_model", fake_load_model)
    # start_session() also constructs a real VoskRecognizer/FfmpegTranscoder
    # from the loaded model; stub those too so this test only needs the
    # fake model object above, not a real Vosk model or ffmpeg binary.
    monkeypatch.setattr(
        vosk_transcription, "VoskRecognizer", lambda model: FakeRecognizer()
    )
    monkeypatch.setattr(
        vosk_transcription, "FfmpegTranscoder", lambda: FakeTranscoder()
    )
    service = VoskStreamingTranscriptionService(model_path="unused")

    session = await service.start_session()

    assert isinstance(session, VoskStreamingTranscriptionSession)
    assert load_thread is not None
    assert load_thread is not main_thread


async def test_start_session_wraps_model_load_failures(monkeypatch):
    def failing_load_model(model_path):
        raise RuntimeError("boom")

    monkeypatch.setattr(vosk_transcription, "_load_model", failing_load_model)
    service = VoskStreamingTranscriptionService(model_path="unused")

    try:
        await service.start_session()
    except TranscriptionError as exc:
        assert "Could not load speech-to-text model" in str(exc)
    else:
        raise AssertionError("expected TranscriptionError")
