"""Transient accumulation of audio chunks for a single Recording.

Holds raw audio bytes between a Recording Start and the next flush point
(Stop). Deliberately dumb: it does not know about transcription, the
Recording state machine, or the Note. `TranscriptionPipeline` is the seam
that flushes it and hands the bytes off.
"""

from dataclasses import dataclass, field


@dataclass
class AudioBuffer:
    _chunks: list[bytes] = field(default_factory=list)

    def append(self, chunk: bytes) -> None:
        self._chunks.append(chunk)

    @property
    def is_empty(self) -> bool:
        return not self._chunks

    def flush(self) -> bytes:
        """Return the accumulated audio and clear the buffer.

        Clearing on flush is what makes the next Start accumulate a fresh
        buffer per the ticket's acceptance criterion — the caller never
        has to remember to reset it separately.
        """
        audio = b"".join(self._chunks)
        self._chunks = []
        return audio
