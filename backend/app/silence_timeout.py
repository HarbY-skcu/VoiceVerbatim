"""Silence Timeout: auto-stop a Recording after a period with no new
transcription text.

Runs as a background asyncio task once a Recording starts. Every
`poll_interval` seconds it checks how long it has been since the last
transcription result (interim or final) arrived from the streaming
pipeline; once that gap reaches `timeout_seconds` it fires `on_timeout`
(the same stop-and-save path a manual Stop uses) and stops itself.
`notify_speech` resets the gap -- called by the streaming orchestrator for
every result it forwards, not just finals, so a long uninterrupted
sentence never times out mid-utterance, only a genuine pause between
words/sentences does. `cancel` stops watching entirely (used on Stop,
where there's nothing left to time out).

`timeout_seconds`, `poll_interval`, and `clock` are constructor parameters
rather than hardcoded so tests can exercise real firing behaviour in
milliseconds instead of waiting on the real multi-second threshold.
"""

import asyncio
import time
from typing import Awaitable, Callable


class SilenceTimeoutMonitor:
    def __init__(
        self,
        on_timeout: Callable[[], Awaitable[None]],
        timeout_seconds: float = 5.0,
        poll_interval: float = 0.5,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.on_timeout = on_timeout
        self.timeout_seconds = timeout_seconds
        self.poll_interval = poll_interval
        self.clock = clock
        self._last_activity: float = 0.0
        self._task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Begin (or restart) watching for silence from now."""
        self.cancel()
        self._last_activity = self.clock()
        self._task = asyncio.create_task(self._run())

    def notify_speech(self) -> None:
        """Reset the silence gap; called whenever transcribed speech arrives."""
        self._last_activity = self.clock()

    def cancel(self) -> None:
        """Stop watching without firing. Idempotent."""
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.poll_interval)
                if self.clock() - self._last_activity >= self.timeout_seconds:
                    self._task = None
                    await self.on_timeout()
                    return
        except asyncio.CancelledError:
            pass
