"""Transcription service seams.

`TranscriptionService` (ticket 04) is a `Protocol` so the batch pipeline can
be tested against a fake without a real speech-to-text backend.

`StreamingTranscriptionService` (ticket 04.1) is the real-time counterpart:
rather than one whole-blob call, it opens a session that accepts audio
chunks as they arrive and yields `StreamingResult`s (interim, then a final)
as the engine's guess firms up. Concrete implementations (the actual
model/API calls) are wired in later — out of scope here.
"""

from dataclasses import dataclass
from typing import AsyncIterator, Protocol


class TranscriptionError(Exception):
    """Raised when audio cannot be transcribed. Never corrupts the Note."""


class TranscriptionService(Protocol):
    async def transcribe(self, audio: bytes) -> str: ...


@dataclass(frozen=True)
class StreamingResult:
    text: str
    final: bool


class StreamingTranscriptionSession(Protocol):
    """One open streaming utterance against the speech-to-text backend."""

    async def send_audio(self, chunk: bytes) -> None: ...

    def results(self) -> AsyncIterator[StreamingResult]:
        """Yields interim results as they're revised, then one final result."""
        ...

    async def close(self) -> None:
        """Ends the session without forcing a final result (e.g. on Pause)."""
        ...


class StreamingTranscriptionService(Protocol):
    async def start_session(self) -> StreamingTranscriptionSession: ...
