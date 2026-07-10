#!/usr/bin/env python3
"""One-off: add just-the-docs nav front matter to docs/wiki and docs/ADR pages.

- Wiki pages (except Home.md): fill empty ``title:`` from the first body H1
  (fallback: filename with dashes as spaces) and add ``parent: Wiki``.
- ADR pages (except INDEX.md): add ``parent: ADRs`` and a sequential
  ``nav_order`` following filename sort order; existing titles untouched.

Front matter is edited line-wise (never yaml round-tripped) so the
Obsidian-style key order and formatting survive. Idempotent: keys that
already hold a value are left alone.
"""

from __future__ import annotations

import argparse
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"


def split_frontmatter(text: str) -> tuple[list[str], list[str]] | None:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], lines[i + 1:]
    return None


def get_value(fm: list[str], key: str) -> str | None:
    for line in fm:
        if line.startswith(f"{key}:"):
            return line[len(key) + 1:].strip()
    return None


def set_key(fm: list[str], key: str, value: str) -> list[str]:
    """Set key only if absent or empty; returns a new list."""
    out = list(fm)
    for i, line in enumerate(out):
        if line.startswith(f"{key}:"):
            if line[len(key) + 1:].strip() == "":
                out[i] = f"{key}: {value}"
            return out
    return out[:1] + [f"{key}: {value}"] + out[1:] if out else [f"{key}: {value}"]


def title_from_body(body: list[str], path: Path) -> str:
    for line in body:
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ")


def quote(value: str) -> str:
    return f'"{value}"' if ":" in value else value


def patch_file(path: Path, updates: dict[str, str], dry_run: bool) -> bool:
    text = path.read_text(encoding="utf-8")
    parts = split_frontmatter(text)
    if parts is None:
        # No front matter at all: create one so the page gets a title + nav slot.
        fm, body = [], text.split("\n")
        updates = {"title": quote(title_from_body(body, path)), **updates}
    else:
        fm, body = parts
    new_fm = list(fm)
    for key, value in updates.items():
        new_fm = set_key(new_fm, key, value)
    if new_fm == fm:
        return False
    if not dry_run:
        joined = "\n".join(["---", *new_fm, "---", *body])
        path.write_text(joined, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    changed = 0

    for path in sorted((DOCS / "wiki").glob("*.md")):
        if path.name == "Home.md":
            continue
        text = path.read_text(encoding="utf-8")
        parts = split_frontmatter(text)
        updates = {"parent": "Wiki"}
        if parts is not None and (get_value(parts[0], "title") or "") == "":
            updates["title"] = quote(title_from_body(parts[1], path))
        if patch_file(path, updates, args.dry_run):
            changed += 1
            print(f"patched: {path.relative_to(DOCS)}")

    adr_files = [p for p in sorted((DOCS / "ADR").glob("*.md")) if p.name != "INDEX.md"]
    for order, path in enumerate(adr_files, start=1):
        updates = {"parent": "ADRs", "nav_order": str(order)}
        if patch_file(path, updates, args.dry_run):
            changed += 1
            print(f"patched: {path.relative_to(DOCS)}")

    print(f"{'would change' if args.dry_run else 'changed'}: {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
