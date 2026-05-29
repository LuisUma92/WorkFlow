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
    name_w = max((len(t.name) for t in topics), default=4)
    da_w = max((len(t.discipline_area.code) for t in topics), default=2)
    header = f"{'ID':<4}  {'DA':<{da_w}}  {'Serial':<6}  Name"
    sep = "-" * (4 + 2 + da_w + 2 + 6 + 2 + name_w)
    lines = [header, sep]
    for t in topics:
        lines.append(f"{t.id:<4}  {t.discipline_area.code:<{da_w}}  {t.serial_number:<6}  {t.name}")
    return "\n".join(lines)
