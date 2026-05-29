"""Content formatters — JSON and table output."""
from __future__ import annotations

import json

from workflow.db.models.knowledge import Content

__all__ = [
    "format_content_json",
    "format_content_list_json",
    "format_content_list_table",
]


def _content_to_dict(c: Content) -> dict:
    return {
        "id": c.id,
        "topic_id": c.topic_id,
        "name": c.name,
    }


def format_content_json(c: Content) -> str:
    return json.dumps(_content_to_dict(c), ensure_ascii=False)


def format_content_list_json(contents: list[Content]) -> str:
    return json.dumps([_content_to_dict(c) for c in contents], ensure_ascii=False, indent=2)


def format_content_list_table(contents: list[Content]) -> str:
    if not contents:
        return "No content found."
    lines = [f"{'ID':<4}  {'Topic ID':<8}  Name", "-" * 36]
    for c in contents:
        lines.append(f"{c.id:<4}  {c.topic_id:<8}  {c.name}")
    return "\n".join(lines)
