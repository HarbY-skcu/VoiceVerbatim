"""Ticket 04: Transcription on Stop.

Orchestrates the core value-delivery moment of the app: flush the buffered
audio from a completed Recording and send it for transcription.

Ticket 14 moved composition/positioning ownership to the frontend: this
pipeline no longer inserts the result into the Note itself (there is no
cursor here to insert "at" anymore) -- it just returns the transcribed
text for the frontend to splice into its own locally-tracked text and
push back via `ActiveNote.set_text`.

Kept as a single seam so Stop, Silence Timeout, and Navigation Stop all
share identical behaviour instead of re-implementing this logic at each
call site.
"""

from dataclasses import dataclass

from .audio_buffer import AudioBuffer
from .note import ActiveNote
from .transcription import TranscriptionError, TranscriptionService


@dataclass
class TranscriptionPipeline:
    buffer: AudioBuffer
    note: ActiveNote
    service: TranscriptionService

    async def flush_and_transcribe(self) -> dict:
        if self.buffer.is_empty:
            return {"inserted": None, "error": None}

        audio = self.buffer.flush()
        try:
            text = await self.service.transcribe(audio)
        except TranscriptionError as exc:
            return {"inserted": None, "error": str(exc)}

        return {"inserted": text, "error": None}
