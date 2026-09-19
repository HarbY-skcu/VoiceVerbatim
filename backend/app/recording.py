"""Recording lifecycle state machine.

Owns whether a Recording session is idle, active, or paused. This is the
backend's single source of truth for the Recording state — the frontend
only ever reflects what this reports. No audio bytes are held here; only
the lifecycle state.

Transitions are async and serialised through an internal asyncio.Lock: once
audio streaming runs concurrently with the rest of the system (Silence
Timeout, Navigation Stop, and manual actions can all race to call this at
the same time), the lock is what keeps the state machine consistent instead
of callers having to coordinate themselves.
"""

import asyncio
from dataclasses import dataclass, field


class InvalidRecordingTransition(Exception):
    """Raised when an action is attempted from a state that does not allow it."""


@dataclass
class RecordingSession:
    _state: str = "idle"
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def reset(self) -> None:
        async with self._lock:
            self._state = "idle"

    @property
    def state(self) -> str:
        return self._state

    async def start(self) -> str:
        async with self._lock:
            if self._state != "idle":
                raise InvalidRecordingTransition(
                    f"Cannot start: a Recording is already {self._state}"
                )
            self._state = "recording"
            return self._state

    async def pause(self) -> str:
        async with self._lock:
            if self._state != "recording":
                raise InvalidRecordingTransition(
                    f"Cannot pause: Recording is {self._state}, not recording"
                )
            self._state = "paused"
            return self._state

    async def resume(self) -> str:
        async with self._lock:
            if self._state != "paused":
                raise InvalidRecordingTransition(
                    f"Cannot resume: Recording is {self._state}, not paused"
                )
            self._state = "recording"
            return self._state

    async def stop(self) -> str:
        async with self._lock:
            if self._state == "idle":
                raise InvalidRecordingTransition("Cannot stop: no active Recording")
            self._state = "idle"
            return self._state
