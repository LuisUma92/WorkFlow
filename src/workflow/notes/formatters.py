"""Output formatters for notes CLI commands.

Two output modes: human-readable table and JSON.
Mirrors evaluation/formatters.py pattern.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workflow.validation.schemas import NoteFrontmatter

__all__ = [
    "format_note_json",
    "format_note_table",
    "format_notes_list_json",
    "format_notes_list_table",
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
