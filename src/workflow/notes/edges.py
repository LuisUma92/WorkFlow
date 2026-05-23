"""ITEP-0013 P2.2 — parse relations: frontmatter block into RelationEntry objects.

Frontmatter schema (canonical, from ADR ITEP-0013):

    relations:
      derived_from:           # structural edges (lineage)
        - id: <zettel_id>
          type: continuation|refines|branches|synthesis|rebuttal
          weight: 0.9         # optional, default 1.0
          note: "rationale"   # optional
      links:                  # associative edges (semantic)
        - id: <zettel_id>
          type: supports|contradicts|expands|see_also

Notes without a relations: block are valid lineage roots.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

# Locked in ITEP-0015: NanoID, 8-21 chars, URL-safe alphabet.
_ZETTEL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,21}$")

_STRUCTURAL_TYPES: frozenset[str] = frozenset(
    {"continuation", "refines", "branches", "synthesis", "rebuttal"}
)
_ASSOCIATIVE_TYPES: frozenset[str] = frozenset(
    {"supports", "contradicts", "expands", "see_also"}
)


@dataclass(frozen=True)
class RelationEntry:
    """One parsed edge from a note's relations: frontmatter block."""

    target_zettel_id: str
    relation_type: str
    edge_class: str          # "structural" | "associative"
    weight: float = 1.0
    rationale: str | None = None


def parse_relations_frontmatter(fm: dict) -> list[RelationEntry]:
    """Parse the relations: block from a raw frontmatter dict.

    Returns a list of RelationEntry objects. Invalid or incomplete entries
    are silently skipped (lenient — missing relations: block is a valid root).
    """
    relations = fm.get("relations")
    if not isinstance(relations, dict):
        return []

    entries: list[RelationEntry] = []
    entries.extend(_parse_block(relations.get("derived_from"), "structural", _STRUCTURAL_TYPES))
    entries.extend(_parse_block(relations.get("links"), "associative", _ASSOCIATIVE_TYPES))
    return entries


def _parse_block(
    raw: object,
    edge_class: str,
    valid_types: frozenset[str],
) -> list[RelationEntry]:
    if not isinstance(raw, list):
        return []
    entries: list[RelationEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        target_id = item.get("id")
        relation_type = item.get("type")
        if not isinstance(target_id, str) or not target_id.strip():
            continue
        target_id = target_id.strip()
        if not _ZETTEL_ID_RE.match(target_id):
            continue
        if not isinstance(relation_type, str) or relation_type not in valid_types:
            continue
        weight_raw = item.get("weight", 1.0)
        try:
            weight = float(weight_raw)
            # Reject non-finite values (inf/nan corrupt graph arithmetic)
            if not math.isfinite(weight) or weight <= 0.0:
                weight = 1.0
        except (TypeError, ValueError):
            weight = 1.0
        rationale_raw = item.get("note")
        # Only str values are accepted; integers/bools silently become None
        rationale = rationale_raw if isinstance(rationale_raw, str) and rationale_raw else None
        entries.append(
            RelationEntry(
                target_zettel_id=target_id.strip(),
                relation_type=relation_type,
                edge_class=edge_class,
                weight=weight,
                rationale=rationale,
            )
        )
    return entries
