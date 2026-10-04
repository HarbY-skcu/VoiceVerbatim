"""Real-time streaming orchestration.

Bridges a `StreamingTranscriptionSession`'s results onward to whatever
results channel is attached (ticket 13). Callers never touch the Note
directly, they only ask this seam to start/stop a session and forward
audio.

Ticket 14 moved composition/positioning ownership to the frontend: this
orchestrator no longer writes streamed results into `ActiveNote` itself
(there is no cursor to splice at here anymore, and a backend-side
accumulation of raw fragments would silently diverge from wherever the
frontend actually placed them the moment the user repositions the
cursor). `note.text` only ever changes via the frontend's own
`set_text` push, so it may lag the live stream by design -- accepted
staleness, not a bug.

A background task consumes `session.results()` and forwards each result
to the attached channel as it arrives, and (via `on_result`) notifies the
Silence Timeout monitor that text just arrived -- interim or final, both
count as "still talking" (see `silence_timeout.py`). `stop()` treats the
caller's action (a dropped socket, Navigation Stop, manual Stop, Silence
Timeout) uniformly: it closes the session (responsible for
force-finalizing any trailing partial utterance so nothing is lost) and
closes the attached results channel, which is the frontend's signal that
the Recording actually ended -- the channel is no longer closed merely
because one interim/final result happened to be forwarded; it stays open
for the whole Recording.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Callable, Protocol

from .transcription import StreamingTranscriptionService, StreamingTranscriptionSession


class ResultsChannel(Protocol):
    """Destination for streaming transcription results (ticket 13).

    Implementations forward each result onward (e.g. over a WebSocket);
    the orchestrator only ever calls `send`, never touches the underlying
    transport itself.
    """

    async def send(self, *, text: str, final: bool) -> None: ...

    async def close(self) -> None:
        """Ends the channel, signalling its consumer (e.g. a WebSocket
        handler) that the Recording has ended and no more results are
        coming."""
        ...


@dataclass
class StreamingTranscriptionOrchestrator:
    service: StreamingTranscriptionService
    # Called for every result (interim or final) forwarded to the results
    # channel -- the orchestrator's seam for notifying the Silence Timeout
    # monitor that transcription text just arrived, without the
    # orchestrator needing to know that monitor exists.
    on_result: "Callable[[], None] | None" = None
    _session: StreamingTranscriptionSession | None = field(default=None, init=False)
    _consume_task: asyncio.Task | None = field(default=None, init=False)
    # Guards session-affecting operations. Without this, a concurrent
    # `stop()` (from Navigation Stop, a dropped socket, or manual Stop,
    # each triggered by its own request/task) can close the session
    # -- tearing down ffmpeg's subprocess -- while `send_audio()` is
    # mid-flight writing/draining to that same subprocess's stdin from the
    # WebSocket loop's task, raising `ConnectionResetError: Connection
    # lost`. Serializing start/stop/send_audio on one lock makes each of
    # them atomic with respect to the others.
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _results_channel: ResultsChannel | None = field(default=None, init=False)

    @property
    def has_results_channel(self) -> bool:
        """Whether a results-delivery channel (ticket 13) is attached.

        `/api/recording/stream` refuses to accept audio unless this is
        true: streaming with nowhere for results to go is an error
        condition, not silently tolerated.
        """
        return self._results_channel is not None

    def attach_results_channel(self, channel: ResultsChannel) -> None:
        """Register the channel results are forwarded to as they arrive.

        Stays attached for the whole Recording -- only detached by
        `stop()` (which also closes it) or by the channel's own consumer
        disconnecting (`detach_results_channel`).
        """
        self._results_channel = channel

    def detach_results_channel(self, channel: ResultsChannel) -> None:
        """Clear the channel, but only if it's still the current one."""
        if self._results_channel is channel:
            self._results_channel = None

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
        defensive: `MediaRecorder` can (and does, per the field reports
        this guards against) emit one last buffered chunk right around a
        Stop request, after the session has already been closed by
        `stop()`. That's an expected race, not an error -- there's no
        session left to forward the trailing chunk to, and nothing useful
        would come of raising here (the caller can't do anything about a
        chunk that arrived a moment too late).
        """
        async with self._lock:
            if self._session is None:
                return
            await self._session.send_audio(chunk)

    async def stop(self) -> None:
        """Close the session, close the results channel, and stop
        consuming results.

        Used for Navigation Stop, manual Stop, Silence Timeout, and a
        dropped socket — all treated identically. The session's own
        `close()` is responsible for force-finalizing any trailing partial
        utterance; closing the channel is the frontend's signal that the
        Recording has actually ended, not just that a result happened to
        be final.
        """
        async with self._lock:
            if self._session is not None:
                await self._session.close()
            self._session = None
            channel = self._results_channel
            self._results_channel = None
        if channel is not None:
            await channel.close()
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
            if self.on_result is not None:
                self.on_result()
            channel = self._results_channel
            if channel is not None:
                await channel.send(text=result.text, final=result.final)
