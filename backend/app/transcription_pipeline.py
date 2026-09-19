"""Ticket 04: Transcription on Stop.

Orchestrates the core value-delivery moment of the app: flush the buffered
audio from a completed (or paused) Recording, send it for transcription,
insert the result into the active Note at the cursor, and auto-save.

Kept as a single seam so Stop, Silence Timeout, Navigation Stop, and Pause
all share identical behaviour (per the ticket, Pause flushes the buffer the
same way Stop does) instead of re-implementing this logic at each call site.
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

        self.note.insert_at_cursor(text)
        self.note.save()
        return {"inserted": text, "error": None}
