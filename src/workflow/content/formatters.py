"""Content formatters — JSON and table output."""
from __future__ import annotations

import json

from workflow.db.models.bibliography import BibContent
from workflow.db.models.knowledge import Content

__all__ = [
    "format_content_json",
    "format_content_list_json",
    "format_content_list_table",
    "format_bib_link_json",
    "format_bib_link_list_json",
    "format_bib_link_list_table",
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


def _bib_link_to_dict(bc: BibContent) -> dict:
    return {
        "bib_entry_id": bc.bib_entry_id,
        "bib_entry_bibkey": bc.bib_entry.bibkey if bc.bib_entry else None,
        "content_id": bc.content_id,
        "chapter_number": bc.chapter_number,
        "section_number": bc.section_number,
        "first_page": bc.first_page,
        "last_page": bc.last_page,
        "first_exercise": bc.first_exercise,
        "last_exercise": bc.last_exercise,
    }


def format_bib_link_json(bc: BibContent) -> str:
    return json.dumps(_bib_link_to_dict(bc), ensure_ascii=False)


def format_bib_link_list_json(links: list[BibContent]) -> str:
    return json.dumps([_bib_link_to_dict(bc) for bc in links], ensure_ascii=False, indent=2)


def format_bib_link_list_table(links: list[BibContent]) -> str:
    if not links:
        return "No bib links found."
    lines = [f"{'BibKey':<20}  {'Content':<8}  Ch   Sec  Pages", "-" * 52]
    for bc in links:
        bk = bc.bib_entry.bibkey if bc.bib_entry else str(bc.bib_entry_id)
        lines.append(
            f"{bk:<20}  {bc.content_id:<8}  {bc.chapter_number:<4} {bc.section_number:<4} "
            f"{bc.first_page}-{bc.last_page}"
        )
    return "\n".join(lines)
