"""Output formatters for PRISMA CLI commands.

Two output modes: human-readable table and JSON (for nvim integration).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workflow.db.models.bibliography import (
    BibEntry,
    BibKeyword,
    BibTag,
    RationaleOption,
    ReviewRecord,
)

from workflow.prisma.importer import ImportResult
from workflow.prisma.recompute import BibkeyChange
from workflow.prisma.service import (
    REVIEW_STATUS_LABELS,
    ChecklistItem,
    ReviewStats,
)


# ── Bibliography entries ─────────────────────────────────────────────────


def _bib_to_dict(entry: BibEntry) -> dict[str, Any]:
    authors = []
    for link in entry.author_links:
        a = link.author
        if a:
            authors.append(
                {
                    "first_name": a.first_name,
                    "last_name": a.last_name,
                    "role": link.author_type.type_of_author
                    if link.author_type
                    else "author",
                    "first_author": link.first_author,
                }
            )
    return {
        "id": entry.id,
        "bibkey": entry.bibkey,
        "entry_type": entry.entry_type,
        "title": entry.title,
        "year": entry.year,
        "journaltitle": entry.journaltitle,
        "abstract_text": entry.abstract_text,
        "doi": entry.doi,
        "authors": authors,
    }


def format_bib_table(entries: list[BibEntry]) -> str:
    if not entries:
        return "No bibliography entries found."

    lines: list[str] = []
    for e in entries:
        d = _bib_to_dict(e)
        author_str = ", ".join(
            a["last_name"] for a in d["authors"] if a["first_author"]
        )
        if not author_str:
            author_str = ", ".join(a["last_name"] for a in d["authors"][:2])
        title = d["title"] or "(no title)"
        if len(title) > 60:
            title = title[:57] + "..."
        lines.append(
            f"  {d['id']:4d}  ({d['year'] or '?':>4})  {author_str:20s}  {title}"
        )
    return "\n".join(lines)


def format_bib_json(entries: list[BibEntry]) -> str:
    data = [_bib_to_dict(e) for e in entries]
    return json.dumps(data, ensure_ascii=False, indent=2)


def format_bib_detail_table(entry: BibEntry) -> str:
    d = _bib_to_dict(entry)
    lines = [
        f"[{d['entry_type'] or '?'}] {d['title']}",
        f"  Year: {d['year'] or '?'}",
        f"  Key: {d['bibkey'] or '?'}",
    ]
    if d["journaltitle"]:
        lines.append(f"  Journal: {d['journaltitle']}")
    if d["doi"]:
        lines.append(f"  DOI: {d['doi']}")
    if d["authors"]:
        names = ", ".join(f"{a['last_name']}, {a['first_name']}" for a in d["authors"])
        lines.append(f"  Authors: {names}")
    if d["abstract_text"]:
        lines.append(f"  Abstract: {d['abstract_text'][:200]}")
    return "\n".join(lines)


def format_bib_detail_json(entry: BibEntry) -> str:
    return json.dumps(_bib_to_dict(entry), ensure_ascii=False, indent=2)


# ── Keywords ─────────────────────────────────────────────────────────────


def _keyword_to_dict(kw: BibKeyword) -> dict[str, Any]:
    return {
        "id": kw.id,
        "keyword_list": kw.keyword_list,
    }


def format_keyword_table(keywords: list[BibKeyword]) -> str:
    if not keywords:
        return "No keywords found."

    lines: list[str] = []
    for kw in keywords:
        lines.append(f"  {kw.id:4d}  {kw.keyword_list}")
    return "\n".join(lines)


def format_keyword_json(keywords: list[BibKeyword]) -> str:
    data = [_keyword_to_dict(kw) for kw in keywords]
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── Review records ───────────────────────────────────────────────────────


def _review_to_dict(rec: ReviewRecord) -> dict[str, Any]:
    entry = rec.bib_entry
    return {
        "id": rec.id,
        "bib_entry_id": rec.bib_entry_id,
        "title": entry.title if entry else "?",
        "year": entry.year if entry else None,
        "bibkey": entry.bibkey if entry else "?",
        "retrieved": rec.retrieved,
        "included": rec.included,
        "include_rationale": rec.include_rationale,
        "retrieve_rationale": rec.retrieve_rationale,
    }


def format_review_table(records: list[ReviewRecord], keyword_text: str = "") -> str:
    if not records:
        return "No review records found."

    status_map = REVIEW_STATUS_LABELS
    lines: list[str] = []
    if keyword_text:
        lines.append(f"Keyword: {keyword_text}")
        lines.append("")
    for rec in records:
        d = _review_to_dict(rec)
        status = status_map.get(d["included"], "?")
        title = d["title"] or "(no title)"
        if len(title) > 50:
            title = title[:47] + "..."
        lines.append(f"  {d['id']:4d}  [{status:8s}]  ({d['year'] or '?':>4})  {title}")
    return "\n".join(lines)


def format_review_json(records: list[ReviewRecord]) -> str:
    data = [_review_to_dict(rec) for rec in records]
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── Tags ─────────────────────────────────────────────────────────────────


def _tag_to_dict(tag: BibTag) -> dict[str, Any]:
    return {"id": tag.id, "tag": tag.tag}


def format_tag_table(tags: list[BibTag]) -> str:
    if not tags:
        return "No tags found."
    return "\n".join(f"  {t.id:4d}  {t.tag}" for t in tags)


def format_tag_json(tags: list[BibTag]) -> str:
    return json.dumps([_tag_to_dict(t) for t in tags], ensure_ascii=False, indent=2)


# ── Rationales ───────────────────────────────────────────────────────────


def _rationale_to_dict(opt: RationaleOption) -> dict[str, Any]:
    return {"id": opt.id, "rationale_argument": opt.rationale_argument}


def format_rationale_table(rationales: list[RationaleOption]) -> str:
    if not rationales:
        return "No rationales found."
    return "\n".join(f"  {r.id:4d}  {r.rationale_argument or ''}" for r in rationales)


def format_rationale_json(rationales: list[RationaleOption]) -> str:
    return json.dumps(
        [_rationale_to_dict(r) for r in rationales], ensure_ascii=False, indent=2
    )


# ── Import results (P2) ──────────────────────────────────────────────────


def format_import_result_table(result: ImportResult, verbose: bool = False) -> str:
    lines = [
        f"Created: {result.created}",
        f"Skipped: {result.skipped}",
        f"Errors:  {len(result.errors)}",
    ]
    if verbose and result.statuses:
        lines.append("")
        lines.extend(f"  {key}: {status}" for key, status in result.statuses)
    if result.errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(f"  - {e}" for e in result.errors)
    return "\n".join(lines)


def format_stats_table(stats: ReviewStats) -> str:
    """Render `get_review_stats` result as a human-readable block."""
    lines = [
        f"Keyword: {stats['keyword']} (id={stats['keyword_id']})",
        f"  Included: {stats['included']}",
        f"  Excluded: {stats['excluded']}",
        f"  Pending:  {stats['pending']}",
        f"  Total:    {stats['total']}",
    ]
    return "\n".join(lines)


def format_stats_json(stats: ReviewStats) -> str:
    """Render `get_review_stats` result as a JSON object."""
    return json.dumps(stats, ensure_ascii=False, indent=2)


# ── Checklist ───────────────────────────────────────────────────────────


def format_checklist_table(items: list[ChecklistItem]) -> str:
    """Render `get_checklist` result as `[x]` / `[ ]` rows with details."""
    lines = []
    for item in items:
        mark = "[x]" if item["satisfied"] else "[ ]"
        lines.append(f"  {mark} {item['item']} — {item['detail']}")
    return "\n".join(lines) if lines else "No checklist items."


def format_checklist_json(items: list[ChecklistItem]) -> str:
    """Render `get_checklist` result as a JSON list."""
    return json.dumps(items, ensure_ascii=False, indent=2)


# ── Recompute-keys results (P3) ──────────────────────────────────────────


def format_recompute_table(
    changes: list[BibkeyChange],
    *,
    backup: "Path | None",
    dry_run: bool,
) -> str:
    """Return a human-readable table of recompute changes."""
    mode = "DRY RUN — " if dry_run else ""
    if not changes:
        return f"{mode}No changes needed."

    header = f"{mode}{len(changes)} key(s) to update:\n"
    rows = [
        f"  [{c.entry_id}] {(c.title or '')[:50]!r:52s}  "
        f"{(c.old_bibkey or 'NULL'):30s} → {c.new_bibkey}"
        for c in changes
    ]
    return header + "\n".join(rows)


def format_recompute_json(
    changes: list[BibkeyChange],
    *,
    backup: "Path | None",
    dry_run: bool,
) -> str:
    """Return a JSON string describing the recompute result."""
    return json.dumps(
        {
            "dry_run": dry_run,
            "backup": str(backup) if backup else None,
            "count": len(changes),
            "changes": [
                {
                    "entry_id": c.entry_id,
                    "title": c.title,
                    "old": c.old_bibkey,
                    "new": c.new_bibkey,
                }
                for c in changes
            ],
        },
        indent=2,
    )


def format_import_result_json(result: ImportResult) -> str:
    return json.dumps(
        {
            "created": result.created,
            "skipped": result.skipped,
            "errors": list(result.errors),
            "statuses": [{"bibkey": k, "status": s} for k, s in result.statuses],
        },
        ensure_ascii=False,
        indent=2,
    )
