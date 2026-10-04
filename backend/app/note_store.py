"""Gap-filling title allocation for Notes created on record start.

Ticket 05 owns real persistence; this is the minimal seam ticket 14 needs
to assign a displayable title ("Untitled N") the moment a Note is created,
before any text exists to derive a title from. Numbering gap-fills: the
lowest free slot is reused once released, rather than growing unboundedly
across a session's created/discarded/replaced notes.
"""

import heapq
from dataclasses import dataclass, field


@dataclass
class NoteTitleGenerator:
    _next_if_no_gap: int = field(default=1, init=False)
    _free: list[int] = field(default_factory=list, init=False)
    _in_use: set[int] = field(default_factory=set, init=False)

    def next_title(self) -> str:
        if self._free:
            n = heapq.heappop(self._free)
        else:
            n = self._next_if_no_gap
            self._next_if_no_gap += 1
        self._in_use.add(n)
        return f"Untitled {n}"

    def release(self, title: str) -> None:
        if not title.startswith("Untitled "):
            return
        try:
            n = int(title[len("Untitled "):])
        except ValueError:
            return
        if n in self._in_use:
            self._in_use.discard(n)
            heapq.heappush(self._free, n)
