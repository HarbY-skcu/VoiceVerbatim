"""Real-time streaming orchestration.

Bridges a `StreamingTranscriptionSession`'s results into the active Note via
`insert_streaming`: callers never touch the Note directly, they only ask
this seam to start/stop a session and forward audio.

A background task consumes `session.results()` and applies each result to
the Note as it arrives (interim results replace the pending span; the final
result commits it). `stop()` treats the caller's action (Pause, a dropped
socket, Navigation Stop, Stop) uniformly: it closes the session, which is
responsible for force-finalizing any trailing partial utterance so nothing
is lost when the session ends.
"""

import asyncio
from dataclasses import dataclass, field

from .note import ActiveNote
from .transcription import StreamingTranscriptionService, StreamingTranscriptionSession


@dataclass
class StreamingTranscriptionOrchestrator:
    note: ActiveNote
    service: StreamingTranscriptionService
    _session: StreamingTranscriptionSession | None = field(default=None, init=False)
    _consume_task: asyncio.Task | None = field(default=None, init=False)
    # Guards session-affecting operations. Without this, a concurrent
    # `stop()` (from Pause, Navigation Stop, a dropped socket, or manual
    # Stop, each triggered by its own request/task) can close the session
    # -- tearing down ffmpeg's subprocess -- while `send_audio()` is
    # mid-flight writing/draining to that same subprocess's stdin from the
    # WebSocket loop's task, raising `ConnectionResetError: Connection
    # lost`. Serializing start/stop/send_audio on one lock makes each of
    # them atomic with respect to the others.
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def start(self) -> None:
        """Open a new streaming session and begin consuming its results."""
        async with self._lock:
            self._session = await self.service.start_session()
            # Captured now, not read lazily from `self._session` inside
            # `_consume()`: `create_task()` only schedules the coroutine,
            # it doesn't run it immediately, so a `stop()` racing in
            # before the task gets its first turn on the event loop could
            # already have cleared `self._session` to None by the time
            # `_consume()` started executing.
            self._consume_task = asyncio.create_task(self._consume(self._session))

    async def send_audio(self, chunk: bytes) -> None:
        """Forwards a chunk to the open session.

        Silently drops the chunk if no session is open. This isn't just
        defensive: the frontend keeps its WebSocket connection open across
        Pause/Resume and only closes/reopens it *after* the Pause request
        completes, so `MediaRecorder` can (and does, per the field reports
        this guards against) emit one last buffered chunk after the
        session has already been closed by `stop()`. That's an expected
        race, not an error -- there's no session left to forward the
        trailing chunk to, and nothing useful would come of raising here
        (the caller can't do anything about a chunk that arrived a moment
        too late).
        """
        async with self._lock:
            if self._session is None:
                return
            await self._session.send_audio(chunk)

    async def stop(self) -> None:
        """Close the session and stop consuming results.

        Used for Pause, Navigation Stop, manual Stop, and a dropped socket —
        all treated identically. The session's own `close()` is responsible
        for force-finalizing any trailing partial utterance.
        """
        async with self._lock:
            if self._session is not None:
                await self._session.close()
            self._session = None
        await self.stop_consuming()

    async def stop_consuming(self) -> None:
        """Wait for the result-consuming task to finish (results() ended)."""
        if self._consume_task is not None:
            await self._consume_task
            self._consume_task = None

    def reset(self) -> None:
        """Forcibly drop session/task references without awaiting anything.

        For test teardown only. Each test module's TestClient runs its own
        anyio portal thread with its own event loop, but they all share
        this orchestrator's module-level instance (via `main.py`'s
        singleton). A `_consume_task` created on one test's loop is a
        foreign object on any other loop: it can't safely be awaited,
        cancelled, or even inspected from a different thread, so this just
        drops the references and lets Python garbage-collect the task
        (its own loop is already gone by the time the next test runs).
        """
        self._consume_task = None
        self._session = None

    async def _consume(self, session: StreamingTranscriptionSession) -> None:
        async for result in session.results():
            self.note.insert_streaming(result.text, final=result.final)
