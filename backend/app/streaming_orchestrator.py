"""Ticket 04.1: real-time streaming orchestration.

Bridges a `StreamingTranscriptionSession`'s results into the active Note via
`insert_streaming`, the same role `TranscriptionPipeline` plays for the
batch path (ticket 04): callers never touch the Note directly, they only
ask this seam to start/stop a session and forward audio.

A background task consumes `session.results()` and applies each result to
the Note as it arrives (interim results replace the pending span; the final
result commits it). `stop()` treats the caller's action (Pause, a dropped
socket, Navigation Stop, Stop) uniformly: it closes the session without
forcing a synthetic final result, per the "implicit Pause" seam agreed for
disconnects.
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

    async def start(self) -> None:
        """Open a new streaming session and begin consuming its results."""
        self._session = await self.service.start_session()
        self._consume_task = asyncio.create_task(self._consume())

    async def send_audio(self, chunk: bytes) -> None:
        if self._session is None:
            raise RuntimeError("Cannot send audio: no streaming session is open")
        await self._session.send_audio(chunk)

    async def stop(self) -> None:
        """Close the session (no forced final) and stop consuming results.

        Used for Pause, Navigation Stop, manual Stop, and a dropped socket —
        all treated identically per the ticket's seam.
        """
        if self._session is not None:
            await self._session.close()
        await self.stop_consuming()
        self._session = None

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

    async def _consume(self) -> None:
        assert self._session is not None
        async for result in self._session.results():
            self.note.insert_streaming(result.text, final=result.final)
