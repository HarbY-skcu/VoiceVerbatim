"""Transcription service seams.

`StreamingTranscriptionService` is the sole transcription seam: it opens a
session that accepts audio chunks as they arrive and yields
`StreamingResult`s (interim, then a final) as the engine's guess firms up.
There is no separate one-shot/batch protocol — a single audio chunk in,
text out, looped for the lifetime of a Recording.
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
        """Ends the session without forcing a final result (e.g. on a dropped socket)."""
        ...


class StreamingTranscriptionService(Protocol):
    async def start_session(self) -> StreamingTranscriptionSession: ...
