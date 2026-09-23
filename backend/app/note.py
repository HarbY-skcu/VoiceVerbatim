"""Minimal in-memory stand-in for the persisted Note (ticket 05 owns real
persistence). Ticket 04 needs a place to insert transcribed text at a
cursor position and to observe that a save happened; ticket 04.1 adds
streaming interim/final reconciliation on top of that.
"""

from dataclasses import dataclass


@dataclass
class ActiveNote:
    text: str = ""
    cursor: int = 0
    saved_text: str | None = None
    # (start, end) span in `text` currently occupied by an uncommitted
    # interim streaming result. None when there is no open span (idle, or
    # right after a final commit). Not touched by insert_at_cursor, which
    # is the atomic batch-transcription path from ticket 04.
    _pending_span: tuple[int, int] | None = None

    def insert_at_cursor(self, insertion: str) -> None:
        self.text = self.text[: self.cursor] + insertion + self.text[self.cursor :]
        self.cursor += len(insertion)

    def insert_streaming(self, text: str, *, final: bool) -> None:
        """Insert (or revise) a streamed transcription result.

        The first call in a streaming utterance anchors a pending span at
        the current cursor. Every subsequent call before `final=True`
        replaces that span's contents (the speech engine revising its
        guess) instead of appending beside it. `final=True` commits the
        span, moves the cursor to just after it, and clears the span so
        the next utterance starts a fresh one rather than overwriting
        already-committed text.
        """
        if self._pending_span is None:
            start = self.cursor
        else:
            start, end = self._pending_span
            self.text = self.text[:start] + self.text[end:]

        self.text = self.text[:start] + text + self.text[start:]
        end = start + len(text)

        if final:
            self.cursor = end
            self._pending_span = None
        else:
            self._pending_span = (start, end)

    def save(self) -> None:
        self.saved_text = self.text
