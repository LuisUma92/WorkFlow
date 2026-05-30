"""Shared result types for `workflow topic import` (bulk hierarchy import).

Pinned contract: `bulk_import.py` (the engine) returns an ``ImportResult``;
`import_formatters.py` renders it; `cli.py` maps it to exit codes. Keeping the
shape here lets the engine and formatters be built independently.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RowError:
    """A single per-row failure during import.

    entity: one of "topic" | "content" | "concept".
    row:    human identifier for the offending row (a name or a concept code).
    reason: short explanation (usually the caught exception's message).
    """

    entity: str
    row: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"entity": self.entity, "row": self.row, "reason": self.reason}


@dataclass(frozen=True)
class ImportResult:
    """Outcome of an import run.

    Counts reflect rows actually created (or, under ``dry_run``, that WOULD be
    created). ``skipped`` counts idempotent duplicates. ``errors`` holds
    per-row failures that did not stop the run (partial-failure → exit 3).
    """

    created_topics: int = 0
    created_contents: int = 0
    created_concepts: int = 0
    skipped: int = 0
    errors: tuple[RowError, ...] = ()
    dry_run: bool = False

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def created_dict(self) -> dict[str, int]:
        """The `{"topics": N, "contents": N, "concepts": N}` sub-object."""
        return {
            "topics": self.created_topics,
            "contents": self.created_contents,
            "concepts": self.created_concepts,
        }


__all__ = ["RowError", "ImportResult"]
