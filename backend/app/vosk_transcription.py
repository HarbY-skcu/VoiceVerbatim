"""Local, offline speech-to-text backend (Vosk).

There is a single streaming seam (`StreamingTranscriptionService` /
`StreamingTranscriptionSession` in `transcription.py`): arbitrary-size audio
chunks go in via `send_audio()`, `StreamingResult`s come out via
`results()`. No separate batch/one-shot path exists.

Two collaborators are injectable so this module is testable without a real
model file or the `ffmpeg` binary:

- `Transcoder`: converts whatever the browser sends (WebM/Opus, browser
  dependent) into 16kHz mono 16-bit PCM, which is what Vosk's recognizer
  requires. `FfmpegTranscoder` is the real implementation, run as a
  persistent `ffmpeg` subprocess for the lifetime of one session.
- `Recognizer`: wraps `vosk.KaldiRecognizer`. `VoskRecognizer` is the real
  implementation; tests inject a fake.

The Vosk model itself is loaded once per process (large, several hundred MB
to a few GB) and shared across sessions.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Protocol

from .transcription import StreamingResult, TranscriptionError

# Resolved relative to this file (backend/app/vosk_transcription.py), not the
# process's current working directory, so the model loads correctly
# regardless of where the server is launched from.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = str(_REPO_ROOT / "backend" / "models" / "vosk-model-en-us-0.22")
SAMPLE_RATE = 16000


class Transcoder(Protocol):
    """Converts a session's incoming audio chunks into 16kHz mono PCM16."""

    async def feed(self, chunk: bytes) -> bytes:
        """Feed one incoming chunk; returns whatever PCM is decodable so far.

        May return an empty `bytes` if not enough input has arrived yet to
        produce output (e.g. still inside a container header).
        """
        ...

    async def flush(self) -> bytes:
        """Signal end of input and return any remaining decoded PCM."""
        ...


class Recognizer(Protocol):
    """Wraps a speech-to-text engine's single-utterance-aware recognizer."""

    def accept_waveform(self, pcm: bytes) -> bool:
        """Feed PCM in. Returns True when an endpoint (utterance boundary)
        was detected, meaning `result()` now holds a final result."""
        ...

    def result(self) -> str:
        """The finalized text for the utterance that just ended."""
        ...

    def partial_result(self) -> str:
        """The best-guess text for the still-in-progress utterance."""
        ...

    def final_result(self) -> str:
        """Force-finalizes and returns the text of any trailing utterance
        that hadn't reached its own endpoint yet."""
        ...


class FfmpegTranscoder:
    """Runs `ffmpeg` as a persistent subprocess for one streaming session.

    Audio chunks (WebM/Opus, browser-dependent) are written to its stdin as
    they arrive; decoded 16kHz mono PCM16 is read back from its stdout.
    """

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        # `feed()`/`flush()` never read `process.stdout` directly (see
        # `_pump_stdout` below for why); instead a single background task
        # continuously reads it and pushes chunks (and a final b"" at EOF)
        # onto this queue.
        self._stdout_queue: "asyncio.Queue[bytes] | None" = None
        self._reader_task: "asyncio.Task[None] | None" = None

    async def _ensure_started(self) -> asyncio.subprocess.Process:
        if self._process is None:
            self._process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-f",
                "s16le",
                "-ar",
                str(SAMPLE_RATE),
                "-ac",
                "1",
                "pipe:1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._stdout_queue = asyncio.Queue()
            self._reader_task = asyncio.create_task(
                self._pump_stdout(self._process)
            )
        return self._process

    async def _pump_stdout(self, process: asyncio.subprocess.Process) -> None:
        """Continuously reads ffmpeg's stdout into `_stdout_queue`.

        This is the only coroutine that ever calls `process.stdout.read()`.
        `feed()`/`flush()` used to call it directly under `asyncio.wait_for`
        to get a non-blocking "read whatever's available" effect, but
        cancelling `StreamReader.read()` via `wait_for` on timeout can
        corrupt the stream's internal waiter state, causing a later read to
        fail with "read() called while another coroutine is already
        waiting for incoming data". Routing all reads through one
        uncancelled task and having consumers poll a `Queue` instead (whose
        `get()` *is* safely cancellable) avoids that entirely.
        """
        assert process.stdout is not None
        while True:
            chunk = await process.stdout.read(4096)
            await self._stdout_queue.put(chunk)
            if not chunk:
                return

    async def feed(self, chunk: bytes) -> bytes:
        process = await self._ensure_started()
        assert process.stdin is not None
        process.stdin.write(chunk)
        await process.stdin.drain()
        return await self._read_available()

    async def flush(self) -> bytes:
        if self._process is None:
            return b""
        process = self._process
        assert process.stdin is not None
        process.stdin.close()
        chunks = []
        assert self._stdout_queue is not None
        while True:
            chunk = await self._stdout_queue.get()
            if not chunk:
                break
            chunks.append(chunk)
        if self._reader_task is not None:
            await self._reader_task
        await process.wait()
        self._process = None
        self._stdout_queue = None
        self._reader_task = None
        return b"".join(chunks)

    async def _read_available(self) -> bytes:
        """Drains whatever chunks are already queued, without blocking for
        new ones beyond a short grace window."""
        assert self._stdout_queue is not None
        chunks = []
        try:
            while True:
                chunk = await asyncio.wait_for(
                    self._stdout_queue.get(), timeout=0.01
                )
                if not chunk:
                    # EOF: put it back so a subsequent flush() also sees it.
                    await self._stdout_queue.put(chunk)
                    break
                chunks.append(chunk)
        except asyncio.TimeoutError:
            pass
        return b"".join(chunks)


class VoskRecognizer:
    """Adapts `vosk.KaldiRecognizer` to the `Recognizer` protocol."""

    def __init__(self, model: "object") -> None:
        import vosk

        self._recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)

    def accept_waveform(self, pcm: bytes) -> bool:
        return bool(self._recognizer.AcceptWaveform(pcm))

    def result(self) -> str:
        return json.loads(self._recognizer.Result()).get("text", "")

    def partial_result(self) -> str:
        return json.loads(self._recognizer.PartialResult()).get("partial", "")

    def final_result(self) -> str:
        return json.loads(self._recognizer.FinalResult()).get("text", "")


_model = None


def _load_model(model_path: str = DEFAULT_MODEL_PATH) -> "object":
    global _model
    if _model is None:
        import vosk

        _model = vosk.Model(model_path)
    return _model


@dataclass
class VoskStreamingTranscriptionSession:
    recognizer: Recognizer
    transcoder: Transcoder
    _queue: "asyncio.Queue[StreamingResult | None]" = field(
        default_factory=asyncio.Queue, init=False
    )

    async def send_audio(self, chunk: bytes) -> None:
        pcm = await self.transcoder.feed(chunk)
        if not pcm:
            return
        if self.recognizer.accept_waveform(pcm):
            text = self.recognizer.result()
            if text:
                await self._queue.put(StreamingResult(text=text, final=True))
        else:
            text = self.recognizer.partial_result()
            if text:
                await self._queue.put(StreamingResult(text=text, final=False))

    async def results(self) -> AsyncIterator[StreamingResult]:
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item

    async def close(self) -> None:
        """Flushes any buffered audio and force-finalizes a trailing
        partial utterance so it isn't lost, then ends the results stream."""
        pcm = await self.transcoder.flush()
        if pcm:
            self.recognizer.accept_waveform(pcm)
        text = self.recognizer.final_result()
        if text:
            await self._queue.put(StreamingResult(text=text, final=True))
        await self._queue.put(None)


@dataclass
class VoskStreamingTranscriptionService:
    model_path: str = DEFAULT_MODEL_PATH

    async def start_session(self) -> VoskStreamingTranscriptionSession:
        try:
            # Loading the model parses ~2-3GB of files and can take tens of
            # seconds; running it directly on the event loop would block
            # every other request (including this one's own response) for
            # the entire duration. Offload to a thread so the loop stays
            # responsive, and so this is safe to call repeatedly (the
            # in-process cache in `_load_model` makes subsequent calls fast).
            model = await asyncio.to_thread(_load_model, self.model_path)
        except Exception as exc:  # pragma: no cover - environment-dependent
            raise TranscriptionError(
                f"Could not load speech-to-text model: {exc}"
            ) from exc
        return VoskStreamingTranscriptionSession(
            recognizer=VoskRecognizer(model), transcoder=FfmpegTranscoder()
        )
