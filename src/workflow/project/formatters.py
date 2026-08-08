"""Formatters for ``workflow project list`` / ``workflow project adopt``."""

from __future__ import annotations

import json

from workflow.project.service import AdoptResult, ProjectRow

__all__ = [
    "format_project_list_json",
    "format_project_list_table",
    "format_adopt_result_json",
]


def _row_to_dict(row: ProjectRow) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "code": row.code,
        "title": row.title,
        "year_init": row.year_init,
        "project_initials": row.project_initials,
        "status": row.status,
        "abs_parent_dir": row.abs_parent_dir,
    }


def format_project_list_json(rows: list[ProjectRow]) -> str:
    return json.dumps([_row_to_dict(r) for r in rows], ensure_ascii=False, indent=2)


def format_project_list_table(rows: list[ProjectRow]) -> str:
    if not rows:
        return "No projects found."
    code_w = max((len(r.code or "") for r in rows), default=4)
    title_w = max((len(r.title or "") for r in rows), default=5)
    header = (
        f"{'ID':<4}  {'Kind':<8}  {'Code':<{code_w}}  {'Title':<{title_w}}  "
        f"{'YY':<3}  {'PP':<3}  {'Status':<10}  Parent dir"
    )
    lines = [header, "-" * len(header)]
    for r in rows:
        lines.append(
            f"{r.id:<4}  {r.kind:<8}  {(r.code or ''):<{code_w}}  "
            f"{(r.title or ''):<{title_w}}  "
            f"{(str(r.year_init) if r.year_init is not None else ''):<3}  "
            f"{(r.project_initials or ''):<3}  "
            f"{(r.status or ''):<10}  {r.abs_parent_dir}"
        )
    return "\n".join(lines)


def format_adopt_result_json(result: AdoptResult) -> str:
    return json.dumps(
        {
            "created": result.created,
            "dry_run": result.dry_run,
            "main_topic_code": result.main_topic_code,
            "title": result.title,
            "year_init": result.year_init,
            "project_initials": result.project_initials,
            "abs_parent_dir": result.abs_parent_dir,
            "abs_src_dir": result.abs_src_dir,
            "project_id": result.project_id,
        },
        ensure_ascii=False,
        indent=2,
    )
