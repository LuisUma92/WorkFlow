"""Output formatters for notes CLI commands.

Two output modes: human-readable table and JSON.
Mirrors evaluation/formatters.py pattern.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from workflow.validation.schemas import NoteFrontmatter

if TYPE_CHECKING:
    from workflow.db.models.notes import NoteEdge

__all__ = [
    "format_note_json",
    "format_note_table",
    "format_notes_list_json",
    "format_notes_list_table",
    "format_edge_table",
    "format_edge_json",
    "format_edges_list_table",
    "format_edges_list_json",
]


def _note_to_list_dict(path: Path, fm: NoteFrontmatter) -> dict[str, Any]:
    """Minimal dict for list output — locked JSON shape (plan §JSON shape)."""
    return {
        "id": fm.id,
        "title": fm.title,
        "tags": list(fm.tags),
        "concepts": list(fm.concepts),
        "candidate_project": fm.candidate_project,
        "type": fm.type,
        "path": str(path.resolve()),
    }


def _note_to_full_dict(path: Path, fm: NoteFrontmatter) -> dict[str, Any]:
    """Full dict for show output — includes extended fields."""
    d = _note_to_list_dict(path, fm)
    d.update({
        "references": list(fm.references),
        "exercises": list(fm.exercises),
        "images": list(fm.images),
        "created": fm.created,
    })
    return d


def format_notes_list_json(items: list[tuple[Path, NoteFrontmatter]]) -> str:
    data = [_note_to_list_dict(p, fm) for p, fm in items]
    return json.dumps(data, ensure_ascii=False, indent=2)


def format_notes_list_table(items: list[tuple[Path, NoteFrontmatter]]) -> str:
    if not items:
        return "No notes found."
    lines: list[str] = []
    for path, fm in items:
        tags_str = ", ".join(fm.tags) if fm.tags else "-"
        lines.append(f"  [{fm.type:10s}] {fm.id:30s}  {fm.title:40s}  tags: {tags_str}")
    return "\n".join(lines)


def format_note_json(path: Path, fm: NoteFrontmatter) -> str:
    return json.dumps(_note_to_full_dict(path, fm), ensure_ascii=False, indent=2)


def format_note_table(path: Path, fm: NoteFrontmatter) -> str:
    d = _note_to_full_dict(path, fm)
    lines = [
        f"id:         {d['id']}",
        f"title:      {d['title']}",
        f"type:       {d['type']}",
        f"tags:       {', '.join(d['tags']) or '-'}",
        f"concepts:   {', '.join(d['concepts']) or '-'}",
        f"references: {', '.join(d['references']) or '-'}",
        f"exercises:  {', '.join(d['exercises']) or '-'}",
        f"images:     {', '.join(d['images']) or '-'}",
        f"created:    {d['created'] or '-'}",
        f"project:    {d['candidate_project'] or '-'}",
        f"path:       {d['path']}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Edge formatters
# ---------------------------------------------------------------------------


def _edge_to_dict(edge: "NoteEdge") -> dict[str, Any]:
    return {
        "id": edge.id,
        "source_id": edge.source_id,
        "target_id": edge.target_id,
        "target_zettel_id": edge.target_zettel_id,
        "edge_class": edge.edge_class,
        "relation_type": edge.relation_type,
        "weight": edge.weight,
        "rationale": edge.rationale,
        "created_at": edge.created_at.isoformat() if edge.created_at else None,
    }


def format_edges_list_json(rows: "list[tuple[NoteEdge, str | None]]") -> str:
    items = []
    for edge, src_zettel_id in rows:
        d = _edge_to_dict(edge)
        d["source_zettel_id"] = src_zettel_id
        items.append(d)
    return json.dumps(items, ensure_ascii=False, indent=2)


def format_edges_list_table(rows: "list[tuple[NoteEdge, str | None]]") -> str:
    if not rows:
        return "No edges found."
    lines: list[str] = []
    for edge, src_zettel_id in rows:
        src_label = src_zettel_id or str(edge.source_id)
        tgt_id = f" (id={edge.target_id})" if edge.target_id is not None else ""
        lines.append(
            f"  [{edge.id:>6}] {edge.edge_class:12s} {edge.relation_type:12s}"
            f"  src={src_label}  tgt={edge.target_zettel_id}{tgt_id}"
            f"  w={edge.weight:.2f}"
        )
    return "\n".join(lines)


def format_edge_json(edge: "NoteEdge") -> str:
    return json.dumps(_edge_to_dict(edge), ensure_ascii=False, indent=2)


def format_edge_table(edge: "NoteEdge") -> str:
    d = _edge_to_dict(edge)
    tgt_id_str = str(d["target_id"]) if d["target_id"] is not None else "(unresolved)"
    lines = [
        f"id:               {d['id']}",
        f"source_id:        {d['source_id']}",
        f"target_zettel_id: {d['target_zettel_id']}",
        f"target_id:        {tgt_id_str}",
        f"edge_class:       {d['edge_class']}",
        f"relation_type:    {d['relation_type']}",
        f"weight:           {d['weight']:.4f}",
        f"rationale:        {d['rationale'] or '-'}",
        f"created_at:       {d['created_at'] or '-'}",
    ]
    return "\n".join(lines)
