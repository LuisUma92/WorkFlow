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
    bkeys = [bc.bib_entry.bibkey if bc.bib_entry else str(bc.bib_entry_id) for bc in links]
    bk_w = max((len(bk) for bk in bkeys), default=6)
    header = f"{'BibKey':<{bk_w}}  {'Content':<8}  Ch   Sec  Pages"
    sep = "-" * (bk_w + 2 + 8 + 2 + 4 + 1 + 4 + 1 + 9)
    lines = [header, sep]
    for bc, bk in zip(links, bkeys):
        lines.append(
            f"{bk:<{bk_w}}  {bc.content_id:<8}  {bc.chapter_number:<4} {bc.section_number:<4} "
            f"{bc.first_page}-{bc.last_page}"
        )
    return "\n".join(lines)
