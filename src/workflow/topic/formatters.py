"""Topic formatters — JSON and table output."""
from __future__ import annotations

import json

from workflow.db.models.knowledge import Topic

__all__ = [
    "format_topic_json",
    "format_topic_list_json",
    "format_topic_list_table",
]


def _topic_to_dict(t: Topic) -> dict:
    return {
        "id": t.id,
        "discipline_area_code": t.discipline_area.code,
        "name": t.name,
        "serial_number": t.serial_number,
    }


def format_topic_json(t: Topic) -> str:
    return json.dumps(_topic_to_dict(t), ensure_ascii=False)


def format_topic_list_json(topics: list[Topic]) -> str:
    return json.dumps([_topic_to_dict(t) for t in topics], ensure_ascii=False, indent=2)


def format_topic_list_table(topics: list[Topic]) -> str:
    if not topics:
        return "No topics found."
    lines = [f"{'ID':<4}  {'DA':<8}  {'Serial':<6}  Name", "-" * 40]
    for t in topics:
        lines.append(f"{t.id:<4}  {t.discipline_area.code:<8}  {t.serial_number:<6}  {t.name}")
    return "\n".join(lines)
