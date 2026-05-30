"""Import formatters — JSON and table output for `workflow topic import`."""
from __future__ import annotations

import json

from workflow.topic.import_types import ImportResult

__all__ = [
    "format_import_json",
    "format_import_table",
]


def format_import_json(result: ImportResult) -> str:
    """Return a JSON string summarising an import result.

    Shape::

        {
            "created": {"topics": N, "contents": N, "concepts": N},
            "skipped": S,
            "errors": [{"entity": ..., "row": ..., "reason": ...}, ...]
        }
    """
    payload = {
        "created": result.created_dict(),
        "skipped": result.skipped,
        "errors": [e.to_dict() for e in result.errors],
    }
    return json.dumps(payload, ensure_ascii=False)


def format_import_table(result: ImportResult) -> str:
    """Return a human-readable summary string for an import result.

    Dry-run prefix: ``[DRY-RUN] Would create …``
    Real run:       ``Created …``

    Error lines (only when present) are appended, one per ``RowError``,
    indented with two spaces::

        [DRY-RUN] Would create 3 topics, 6 contents, 12 concepts (2 skipped)
          [ERROR] concept FS01-X-001: duplicate code
    """
    t = result.created_topics
    c = result.created_contents
    k = result.created_concepts
    s = result.skipped

    if result.dry_run:
        summary = (
            f"[DRY-RUN] Would create {t} topics, {c} contents, {k} concepts"
            f" ({s} skipped)"
        )
    else:
        summary = f"Created {t} topics, {c} contents, {k} concepts ({s} skipped)"

    lines = [summary]
    for err in result.errors:
        lines.append(f"  [ERROR] {err.entity} {err.row}: {err.reason}")

    return "\n".join(lines)
