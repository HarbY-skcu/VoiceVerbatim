"""Backend ownership of Audio Source selection.

The frontend enumerates OS-reported input devices (a browser-only capability) and
registers them here. From that point on the backend is the single authority on
which Audio Source is active: it picks the default, validates every change, and
holds the selection while the app is open. The frontend only displays what this
registry reports.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AudioSource:
    id: str
    label: str = ""


class UnknownAudioSource(KeyError):
    """Raised when a caller tries to activate a source that was never registered."""


class AudioSourceRegistry:
    def __init__(self) -> None:
        self._sources: list[AudioSource] = []
        self._active: str | None = None

    def clear(self) -> None:
        self._sources = []
        self._active = None

    def snapshot(self) -> dict:
        return {
            "sources": [{"id": s.id, "label": s.label} for s in self._sources],
            "active": self._active,
        }

    def register(self, sources: list[AudioSource]) -> dict:
        """Replace the known device list and (re)resolve the active source.

        A selection already in effect is preserved if the device is still
        present; otherwise the backend falls back to the default.
        """
        self._sources = list(sources)
        present = {s.id for s in self._sources}
        if self._active not in present:
            self._active = self._default_source_id()
        return self.snapshot()

    def set_active(self, source_id: str) -> dict:
        if source_id not in {s.id for s in self._sources}:
            raise UnknownAudioSource(source_id)
        self._active = source_id
        return self.snapshot()

    def _default_source_id(self) -> str | None:
        for source in self._sources:
            if source.id == "default":
                return source.id
        return self._sources[0].id if self._sources else None
