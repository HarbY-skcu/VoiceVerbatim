"""Recording lifecycle state machine.

Owns whether a Recording session is idle, active, or paused. This is the
backend's single source of truth for the Recording state — the frontend
only ever reflects what this reports. No audio bytes are held here; only
the lifecycle state, since ticket 03 wires the state machine without
transcription.
"""

from dataclasses import dataclass


class InvalidRecordingTransition(Exception):
    """Raised when an action is attempted from a state that does not allow it."""


@dataclass
class RecordingSession:
    _state: str = "idle"

    def reset(self) -> None:
        self._state = "idle"

    @property
    def state(self) -> str:
        return self._state

    def start(self) -> str:
        if self._state != "idle":
            raise InvalidRecordingTransition(
                f"Cannot start: a Recording is already {self._state}"
            )
        self._state = "recording"
        return self._state

    def pause(self) -> str:
        if self._state != "recording":
            raise InvalidRecordingTransition(
                f"Cannot pause: Recording is {self._state}, not recording"
            )
        self._state = "paused"
        return self._state

    def resume(self) -> str:
        if self._state != "paused":
            raise InvalidRecordingTransition(
                f"Cannot resume: Recording is {self._state}, not paused"
            )
        self._state = "recording"
        return self._state

    def stop(self) -> str:
        if self._state == "idle":
            raise InvalidRecordingTransition("Cannot stop: no active Recording")
        self._state = "idle"
        return self._state
