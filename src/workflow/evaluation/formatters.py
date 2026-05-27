"""Output formatters for evaluation CLI commands.

Two output modes: human-readable table and JSON (for nvim integration).
"""

from __future__ import annotations

import json
from typing import Any

from workflow.db.models.academic import (
    Course,
    CourseEvaluation,
    EvaluationTemplate,
    Item,
)


# ── Evaluation templates ──────────────────────────────────────────────────


def _eval_to_dict(tmpl: EvaluationTemplate, full: bool = False) -> dict[str, Any]:
    inst_name = tmpl.institution.short_name if tmpl.institution else "?"
    d: dict[str, Any] = {
        "id": tmpl.id,
        "institution": inst_name,
        "name": tmpl.name,
        "description": tmpl.description or "",
        "total_points": tmpl.total_points,
        "item_count": len(tmpl.evaluation_items),
    }
    if full:
        d["items"] = [
            {
                "item_name": ei.item.name if ei.item else "?",
                "taxonomy_domain": ei.item.taxonomy_domain if ei.item else "?",
                "taxonomy_level": ei.item.taxonomy_level if ei.item else "?",
                "amount": ei.total_amount,
                "points_per_item": ei.points_per_item,
            }
            for ei in tmpl.evaluation_items
        ]
    return d


def format_eval_table(templates: list[EvaluationTemplate], full: bool = False) -> str:
    if not templates:
        return "No evaluation templates found."

    lines: list[str] = []
    for tmpl in templates:
        d = _eval_to_dict(tmpl, full=full)
        header = (
            f"[{d['institution']}] {d['name']} "
            f"({d['total_points']} pts, {d['item_count']} items)"
        )
        lines.append(header)
        if full and d.get("description"):
            lines.append(f"  {d['description']}")
        if full and "items" in d:
            for i, it in enumerate(d["items"], 1):
                lines.append(
                    f"  {i}. {it['item_name']} — "
                    f"{it['taxonomy_domain']} / {it['taxonomy_level']}  "
                    f"{it['amount']} × {it['points_per_item']} pts"
                )
    return "\n".join(lines)


def format_eval_json(templates: list[EvaluationTemplate], full: bool = False) -> str:
    data = [_eval_to_dict(tmpl, full=full) for tmpl in templates]
    return json.dumps(data, ensure_ascii=False, indent=2)


def format_eval_detail_table(tmpl: EvaluationTemplate) -> str:
    """Format a single template with full item breakdown."""
    return format_eval_table([tmpl], full=True)


def format_eval_detail_json(tmpl: EvaluationTemplate) -> str:
    """Format a single template as JSON with items."""
    return json.dumps(_eval_to_dict(tmpl, full=True), ensure_ascii=False, indent=2)


# ── Items ─────────────────────────────────────────────────────────────────


def _item_to_dict(item: Item) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "taxonomy_domain": item.taxonomy_domain,
        "taxonomy_level": item.taxonomy_level,
    }


def format_item_table(items: list[Item]) -> str:
    if not items:
        return "No items found."

    lines: list[str] = []
    for it in items:
        lines.append(
            f"  {it.id:4d}  {it.name:40s}  "
            f"{it.taxonomy_domain:25s}  {it.taxonomy_level}"
        )
    return "\n".join(lines)


def format_item_json(items: list[Item]) -> str:
    data = [_item_to_dict(it) for it in items]
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── Courses ───────────────────────────────────────────────────────────────


def _course_to_dict(course: Course) -> dict[str, Any]:
    inst_name = course.institution.short_name if course.institution else "?"
    return {
        "id": course.id,
        "institution": inst_name,
        "code": course.code,
        "name": course.name,
        "lectures_per_week": course.lectures_per_week,
        "hours_per_lecture": course.hours_per_lecture,
    }


def format_course_table(courses: list[Course]) -> str:
    if not courses:
        return "No courses found."

    lines: list[str] = []
    for c in courses:
        d = _course_to_dict(c)
        lines.append(
            f"  [{d['institution']}] {d['code']:10s}  {d['name']:40s}  "
            f"{d['lectures_per_week']}lpw {d['hours_per_lecture']}hpl"
        )
    return "\n".join(lines)


def format_course_json(courses: list[Course]) -> str:
    data = [_course_to_dict(c) for c in courses]
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── Course practices ──────────────────────────────────────────────────────


def _practice_to_dict(
    ce: CourseEvaluation,
    course_code: str,
) -> dict[str, Any]:
    return {
        "id": ce.id,
        "course": course_code,
        "type": ce.practice_type,
        "serial": ce.serial_number,
        "name": ce.practice_name or "",
        "week": ce.evaluation_week,
        "file": ce.source_file or "",
    }


def format_practice_json(
    rows: list[CourseEvaluation],
    course_code: str,
) -> str:
    data = [_practice_to_dict(ce, course_code) for ce in rows]
    return json.dumps(data, ensure_ascii=False, indent=2)


def format_practice_single_json(ce: CourseEvaluation, course_code: str) -> str:
    return json.dumps(_practice_to_dict(ce, course_code), ensure_ascii=False, indent=2)


def format_practice_table(
    rows: list[CourseEvaluation],
    course_code: str,
) -> str:
    if not rows:
        return f"No practices/quizzes found for {course_code}."
    lines: list[str] = []
    for ce in rows:
        d = _practice_to_dict(ce, course_code)
        file_part = f"  [{d['file']}]" if d["file"] else ""
        lines.append(
            f"  {d['type']:8s}  #{d['serial']:3d}  wk{d['week']:2d}  "
            f"{d['name']:40s}{file_part}"
        )
    return "\n".join(lines)
