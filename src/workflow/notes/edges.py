"""ITEP-0013 P2.2 (amended 2026-07-09, F2) — parse relations: frontmatter into RelationEntry.

Frontmatter schema (canonical, flat — Obsidian Properties compatible):

    Obsidian Properties cannot store nested mappings/lists-of-dicts; a nested
    ``relations:`` block gets silently collapsed to a string and the graph is
    destroyed on save. The canonical schema is therefore 9 FLAT keys, one per
    relation_type, prefixed by edge_class family and derived from
    ``workflow.db.models.notes.FRONTMATTER_RELATION_KEYS`` (never hard-coded):

    derived_from_continuation: [<zettel_id>, ...]
    derived_from_refines: [<zettel_id>, ...]
    derived_from_branches: [<zettel_id>, ...]
    derived_from_synthesis: [<zettel_id>, ...]
    derived_from_rebuttal: [<zettel_id>, ...]
    links_supports: [<zettel_id>, ...]
    links_contradicts: [<zettel_id>, ...]
    links_expands: [<zettel_id>, ...]
    links_see_also: [<zettel_id>, ...]

    Each value is a plain list of zettel_id strings. Empty/absent keys are
    omitted. ``weight``/``note`` (rationale) are no longer representable in
    frontmatter (decision 2026-07-09) — flat-parsed entries always carry
    weight=1.0, rationale=None.

    Notes without any relation key are valid lineage roots.

LEGACY (nested ``relations:``, pre-2026-07-09)
-----------------------------------------------
Superseded by the flat schema above but still parsed when no flat key is
present, for backward compatibility with un-migrated notes::

    relations:
      derived_from:           # structural edges (lineage)
        - id: <zettel_id>
          type: continuation|refines|branches|synthesis|rebuttal
          weight: 0.9         # optional, default 1.0
          note: "rationale"   # optional
      links:                  # associative edges (semantic)
        - id: <zettel_id>
          type: supports|contradicts|expands|see_also

If both schemas are present in the same frontmatter dict, flat WINS and the
nested ``relations:`` block is ignored entirely (deterministic dispatch).
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

# Single source of truth — ITEP-0013 vocabulary lives on the NoteEdge model.
from workflow.db.models.notes import (
    ASSOCIATIVE_RELATION_TYPES as _ASSOCIATIVE_TYPES,
    FRONTMATTER_RELATION_KEYS,
    STRUCTURAL_RELATION_TYPES as _STRUCTURAL_TYPES,
    ZETTEL_ID_RE as _ZETTEL_ID_RE,
    relation_frontmatter_key,
)


@dataclass(frozen=True)
class RelationEntry:
    """One parsed edge from a note's relations frontmatter."""

    target_zettel_id: str
    relation_type: str
    edge_class: str          # "structural" | "associative"
    weight: float = 1.0
    rationale: str | None = None


def parse_relations_frontmatter(fm: dict) -> list[RelationEntry]:
    """Parse relation edges from a raw frontmatter dict.

    Dispatches between the flat (canonical) and nested (legacy) schemas:
    if any of the 9 flat keys is present, flat wins and the nested
    ``relations:`` block (if any) is ignored entirely — deterministic,
    no silent merge of two sources of truth. Otherwise falls back to the
    legacy nested parser.

    Returns a list of RelationEntry objects. Invalid or incomplete entries
    are silently skipped (lenient — missing relation keys is a valid root).
    """
    if any(key in fm for key in FRONTMATTER_RELATION_KEYS):
        return _parse_flat(fm)
    return _parse_nested(fm)


def _coerce_zettel_id(value: object) -> str | None:
    """Coerce a frontmatter id scalar to a validated zettel_id string.

    Accepts ``str`` and ``int`` — timestamp-style ids (e.g. ``202604010900``)
    are bare digits and YAML parses them as ``int``; rejecting them here would
    silently drop the edge (permanent data loss in ``migrate-relations``).
    ``bool`` is rejected explicitly because ``isinstance(True, int)`` is True
    in Python. ``float``/``None``/``dict``/``list`` are rejected too. Coerce
    with ``str(value)`` FIRST, then ``.strip()``, then validate against
    ``ZETTEL_ID_RE`` exactly as before. Returns the id, or ``None`` to skip.
    """
    if isinstance(value, bool):
        return None
    if not isinstance(value, (str, int)):
        return None
    target_id = str(value).strip()
    if not target_id or not _ZETTEL_ID_RE.match(target_id):
        return None
    return target_id


def _parse_flat(fm: dict) -> list[RelationEntry]:
    entries: list[RelationEntry] = []
    for key, (edge_class, relation_type) in FRONTMATTER_RELATION_KEYS.items():
        raw = fm.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            target_id = _coerce_zettel_id(item)
            if target_id is None:
                continue
            entries.append(
                RelationEntry(
                    target_zettel_id=target_id,
                    relation_type=relation_type,
                    edge_class=edge_class,
                    weight=1.0,
                    rationale=None,
                )
            )
    return entries


def relations_to_flat_fm(entries: Iterable[RelationEntry]) -> dict[str, list[str]]:
    """Serialize RelationEntry objects into the flat frontmatter schema.

    Keys follow FRONTMATTER_RELATION_KEYS order; empty keys are omitted
    (never emit e.g. ``links_supports: []``). Target ids are deduped within
    a key, preserving first-seen order. weight/rationale are dropped —
    they are not representable in the flat schema (decision 2026-07-09).
    """
    by_key: dict[str, list[str]] = {}
    for entry in entries:
        key = relation_frontmatter_key(entry.edge_class, entry.relation_type)
        bucket = by_key.setdefault(key, [])
        if entry.target_zettel_id not in bucket:
            bucket.append(entry.target_zettel_id)

    ordered: dict[str, list[str]] = {}
    for key in FRONTMATTER_RELATION_KEYS:
        if key in by_key and by_key[key]:
            ordered[key] = by_key[key]
    return ordered


def has_legacy_relations(fm: dict) -> bool:
    """True if fm carries a legacy nested ``relations:`` block.

    A non-empty dict value is the well-formed legacy shape. A ``str`` value
    is ALSO treated as legacy-present: it is the signature of a note that
    Obsidian Properties has already corrupted (collapsed the nested mapping
    to a single string), so callers (e.g. a migration command) can fail
    loudly instead of silently treating it as "no relations". An empty dict
    or an absent key is not considered legacy.
    """
    relations = fm.get("relations")
    if isinstance(relations, dict):
        return bool(relations)
    return isinstance(relations, str)


def _parse_nested(fm: dict) -> list[RelationEntry]:
    relations = fm.get("relations")
    if not isinstance(relations, dict):
        return []

    entries: list[RelationEntry] = []
    entries.extend(_parse_block(relations.get("derived_from"), "structural", _STRUCTURAL_TYPES))
    entries.extend(_parse_block(relations.get("links"), "associative", _ASSOCIATIVE_TYPES))
    return entries


# LEGACY (nested relations:, pre-2026-07-09)
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
        target_id = _coerce_zettel_id(item.get("id"))
        relation_type = item.get("type")
        if target_id is None:
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
                target_zettel_id=target_id,
                relation_type=relation_type,
                edge_class=edge_class,
                weight=weight,
                rationale=rationale,
            )
        )
    return entries
