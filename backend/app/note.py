"""Minimal in-memory stand-in for the persisted Note (ticket 05 owns real
persistence).

Ticket 14 moved cursor/insertion-position ownership to the frontend: the
frontend composes the full note text locally (splicing streamed/batch
transcription results and manual edits at whatever position it tracks)
and pushes the resulting full text here via `set_text`. `ActiveNote`'s
role narrows to: hold the current text/title, and observe that a save
happened. It no longer tracks a cursor or does any splicing of its own.
"""

from dataclasses import dataclass


@dataclass
class ActiveNote:
    text: str = ""
    saved_text: str | None = None
    # Ticket 14: assigned at creation time (record start), before any text
    # exists to derive a title from. See note_store.NoteTitleGenerator.
    title: str | None = None

    def set_text(self, text: str) -> None:
        """Overwrites the note's text wholesale.

        The frontend is the sole authority on composition/positioning now
        (ticket 14): it decides where transcription results and manual
        edits land, and pushes the resulting full text here. This is a
        dumb sink -- no splicing, no cursor tracking.
        """
        self.text = text

    def save(self) -> None:
        self.saved_text = self.text
