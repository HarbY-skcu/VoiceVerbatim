"""Minimal in-memory stand-in for the persisted Note (ticket 05 owns real
persistence). Ticket 04 only needs a place to insert transcribed text at a
cursor position and to observe that a save happened.
"""

from dataclasses import dataclass


@dataclass
class ActiveNote:
    text: str = ""
    cursor: int = 0
    saved_text: str | None = None

    def insert_at_cursor(self, insertion: str) -> None:
        self.text = self.text[: self.cursor] + insertion + self.text[self.cursor :]
        self.cursor += len(insertion)

    def save(self) -> None:
        self.saved_text = self.text
