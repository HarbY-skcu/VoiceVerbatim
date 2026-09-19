"""Transcription service seam.

`TranscriptionService` is a `Protocol` so the pipeline can be tested against
a fake without a real speech-to-text backend. The concrete implementation
(the actual model/API call) is wired in later — out of scope for ticket 04.
"""

from typing import Protocol


class TranscriptionError(Exception):
    """Raised when audio cannot be transcribed. Never corrupts the Note."""


class TranscriptionService(Protocol):
    async def transcribe(self, audio: bytes) -> str: ...
