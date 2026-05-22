"""Output formatters for concept CLI commands.

Two output modes: human-readable table and JSON (for nvim integration).
Mirrors src/workflow/evaluation/formatters.py pattern.
"""

from __future__ import annotations

import json
from typing import Any

from workflow.db.models.notes import Concept

__all__ = [
    "format_concept_json",
    "format_concept_show_json",
    "format_concept_show_table",
    "format_concepts_list_table",
    "format_concepts_list_json",
    "format_tree_ascii",
    "format_tree_json",
]


# ── Single concept ────────────────────────────────────────────────────────


def _concept_to_dict(concept: Concept) -> dict[str, Any]:
    """Base dict matching the locked JSON shape (plan §JSON Shapes)."""
    return {
        "id": concept.id,
        "code": concept.code,
        "label": concept.label,
        "main_topic": concept.main_topic.code if concept.main_topic else None,
        "parent": concept.parent.code if concept.parent else None,
        "description": concept.description,
    }


def _concept_show_dict(concept: Concept, child_count: int) -> dict[str, Any]:
    d = _concept_to_dict(concept)
    d["child_count"] = child_count
    if concept.created_at is not None:
        d["created_at"] = concept.created_at.isoformat()
    else:
        d["created_at"] = None
    return d


def format_concept_json(concept: Concept) -> str:
    """JSON for `concept add` output (same shape as show minus child_count)."""
    return json.dumps(_concept_to_dict(concept), ensure_ascii=False, indent=2)


def format_concept_show_json(concept: Concept, child_count: int) -> str:
    """JSON for `concept show` output."""
    return json.dumps(
        _concept_show_dict(concept, child_count), ensure_ascii=False, indent=2
    )


def format_concept_show_table(concept: Concept, child_count: int) -> str:
    """Human-readable for `concept show`."""
    parent_str = concept.parent.code if concept.parent else "(root)"
    mt_str = concept.main_topic.code if concept.main_topic else "?"
    lines = [
        f"Concept: {concept.code}",
        f"  label       : {concept.label}",
        f"  main_topic  : {mt_str}",
        f"  parent      : {parent_str}",
        f"  child_count : {child_count}",
        f"  description : {concept.description or ''}",
    ]
    return "\n".join(lines)


# ── List ──────────────────────────────────────────────────────────────────


def format_concepts_list_table(concepts: list[Concept]) -> str:
    if not concepts:
        return "No concepts found."
    lines: list[str] = []
    for c in concepts:
        parent_code = c.parent.code if c.parent else ""
        mt_code = c.main_topic.code if c.main_topic else "?"
        lines.append(
            f"  {c.id:4d}  {c.code:32s}  {c.label:40s}  {mt_code:8s}  {parent_code}"
        )
    return "\n".join(lines)


def format_concepts_list_json(concepts: list[Concept]) -> str:
    data = [_concept_to_dict(c) for c in concepts]
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── Tree ──────────────────────────────────────────────────────────────────


def format_tree_json(tree: list[dict]) -> str:
    return json.dumps(tree, ensure_ascii=False, indent=2)


def format_tree_ascii(tree: list[dict], _indent: int = 0) -> str:
    lines: list[str] = []
    prefix = "  " * _indent
    for node in tree:
        lines.append(f"{prefix}{node['code']}  ({node['label']})")
        if node.get("children"):
            lines.append(format_tree_ascii(node["children"], _indent + 1))
    return "\n".join(line for line in lines if line)
