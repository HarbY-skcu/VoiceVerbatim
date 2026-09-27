"""Integration coverage for `FfmpegTranscoder` against the real `ffmpeg`
binary (rather than the `FakeTranscoder` used in test_vosk_transcription.py).

test_vosk_transcription.py deliberately fakes the Transcoder/Recognizer
seams so VoskStreamingTranscriptionSession's orchestration logic can be
tested without a real ffmpeg binary or Vosk model. This module complements
that by exercising FfmpegTranscoder itself end-to-end: real WebM/Opus bytes
(generated with ffmpeg) go in, real decoded 16kHz mono PCM16 comes out.

Requires the `ffmpeg` binary to be installed and on PATH.
"""

import shutil
import subprocess

import pytest

from backend.app.vosk_transcription import SAMPLE_RATE, FfmpegTranscoder

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg binary not available"
)


def _encode_tone_to_webm_opus(duration_seconds: float = 1.0) -> bytes:
    """Uses ffmpeg itself to synthesize a sine tone and encode it to
    WebM/Opus, i.e. the same container/codec a browser's MediaRecorder
    typically sends."""
    process = subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration_seconds}",
            "-c:a",
            "libopus",
            "-f",
            "webm",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    )
    return process.stdout


def _chunk(data: bytes, size: int = 2048) -> list[bytes]:
    return [data[i : i + size] for i in range(0, len(data), size)]


async def test_feed_and_flush_decode_real_webm_opus_to_expected_pcm_length():
    webm_bytes = _encode_tone_to_webm_opus(duration_seconds=1.0)
    transcoder = FfmpegTranscoder()

    pcm = bytearray()
    for chunk in _chunk(webm_bytes):
        pcm.extend(await transcoder.feed(chunk))
    pcm.extend(await transcoder.flush())

    # 16kHz, mono, 16-bit PCM for ~1s of audio == ~32000 bytes. ffmpeg's
    # opus decoder framing means the exact byte count can drift slightly
    # from the nominal duration, so assert within a generous tolerance
    # rather than an exact match.
    expected_bytes = int(SAMPLE_RATE * 1.0) * 2
    assert abs(len(pcm) - expected_bytes) < expected_bytes * 0.1


async def test_decoded_pcm_is_not_silence():
    webm_bytes = _encode_tone_to_webm_opus(duration_seconds=1.0)
    transcoder = FfmpegTranscoder()

    pcm = bytearray()
    for chunk in _chunk(webm_bytes):
        pcm.extend(await transcoder.feed(chunk))
    pcm.extend(await transcoder.flush())

    assert any(byte != 0 for byte in pcm)


async def test_flush_with_no_input_returns_empty_bytes():
    transcoder = FfmpegTranscoder()

    assert await transcoder.flush() == b""


async def test_feed_can_be_called_multiple_times_before_flush():
    webm_bytes = _encode_tone_to_webm_opus(duration_seconds=0.5)
    transcoder = FfmpegTranscoder()

    total_fed = 0
    pcm = bytearray()
    for chunk in _chunk(webm_bytes, size=512):
        total_fed += len(chunk)
        pcm.extend(await transcoder.feed(chunk))
    pcm.extend(await transcoder.flush())

    assert total_fed == len(webm_bytes)
    assert len(pcm) > 0


async def test_rapid_small_feeds_then_flush_do_not_corrupt_the_stdout_stream():
    """Regression test: feeding many small chunks in quick succession used
    to call `asyncio.wait_for(process.stdout.read(...), timeout=...)` on
    every `feed()`, and cancelling that read on timeout could corrupt
    `StreamReader`'s internal waiter state, causing a *later* `feed()` or
    `flush()` call to raise `RuntimeError: read() called while another
    coroutine is already waiting for incoming data`. Reproduces the bug
    from real streaming traffic: many tiny WebSocket audio chunks arriving
    faster than ffmpeg can emit decoded PCM, so most `feed()` calls hit the
    drain timeout with nothing yet available.
    """
    webm_bytes = _encode_tone_to_webm_opus(duration_seconds=1.0)
    transcoder = FfmpegTranscoder()

    pcm = bytearray()
    # Tiny chunks (well under ffmpeg's typical read buffering) maximize the
    # chance that `_read_available()` times out with nothing queued yet,
    # which is what used to trigger the corrupted-waiter bug.
    for chunk in _chunk(webm_bytes, size=64):
        pcm.extend(await transcoder.feed(chunk))
    pcm.extend(await transcoder.flush())

    assert len(pcm) > 0


async def test_flush_after_feed_reaches_eof_does_not_raise():
    """Once ffmpeg's stdout hits EOF during feed()'s drain, a subsequent
    flush() must still return cleanly (not hang or raise) rather than
    trying to read a stream that's already been fully consumed."""
    webm_bytes = _encode_tone_to_webm_opus(duration_seconds=0.2)
    transcoder = FfmpegTranscoder()

    pcm = bytearray()
    for chunk in _chunk(webm_bytes, size=4096):
        pcm.extend(await transcoder.feed(chunk))

    # Give ffmpeg a moment to finish emitting/close stdout on its own.
    import asyncio

    await asyncio.sleep(0.2)

    pcm.extend(await transcoder.flush())

    assert len(pcm) > 0
