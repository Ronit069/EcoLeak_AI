"""Module I - Circular Alternative Knowledge Base loader and query API.

Static reference data lives in p4/interventions/intervention_library.json and
is validated through `InterventionEntry` (frozen DB fields + P4 metadata) on
load. Nothing here depends on the database or on P3's engines.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from p4.models import InterventionEntry

DEFAULT_LIBRARY_PATH = Path(__file__).resolve().parent / "interventions" / "intervention_library.json"


class InterventionLibrary:
    """Read-only, deterministic view over the Module I knowledge base."""

    def __init__(self, entries: Iterable[InterventionEntry]):
        self._entries: list[InterventionEntry] = list(entries)
        self._by_code: dict[str, InterventionEntry] = {}
        for entry in self._entries:
            if entry.intervention_code in self._by_code:
                raise ValueError(f"duplicate intervention_code: {entry.intervention_code}")
            self._by_code[entry.intervention_code] = entry

    @classmethod
    def from_file(cls, path: Optional[Path] = None) -> "InterventionLibrary":
        source = Path(path) if path is not None else DEFAULT_LIBRARY_PATH
        raw = json.loads(source.read_text(encoding="utf-8"))
        entries = [InterventionEntry.model_validate(item) for item in raw]
        return cls(entries)

    def all(self) -> list[InterventionEntry]:
        return list(self._entries)

    def active(self) -> list[InterventionEntry]:
        return [entry for entry in self._entries if entry.active]

    def get(self, intervention_code: str) -> InterventionEntry:
        try:
            return self._by_code[intervention_code]
        except KeyError as exc:
            raise KeyError(f"unknown intervention_code: {intervention_code}") from exc

    def codes(self) -> set[str]:
        return set(self._by_code)

    def __len__(self) -> int:
        return len(self._entries)

    def by_industry(self, industry_sector: Optional[str]) -> list[InterventionEntry]:
        if not industry_sector:
            return self.active()
        return [
            entry
            for entry in self._entries
            if entry.active and entry.industry_sector in (None, "All", industry_sector)
        ]


_default_library: Optional[InterventionLibrary] = None


def default_library() -> InterventionLibrary:
    """Process-wide default library (loaded once, immutable in practice)."""

    global _default_library
    if _default_library is None:
        _default_library = InterventionLibrary.from_file()
    return _default_library
