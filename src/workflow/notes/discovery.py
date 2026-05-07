"""Note file discovery and frontmatter parsing.

Filesystem-only — no DB access.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

import yaml

__all__ = ["iter_note_files", "parse_frontmatter"]

# Directories to skip during discovery (lessons.md row 18 — avoid loops)
_SKIP_DIRS = frozenset({"images", "__pycache__", "node_modules"})


def iter_note_files(root: Path) -> Iterator[Path]:
    """Yield .md files directly inside *root* (top-level only, no recursion).

    Skips symlinks to avoid loops (lessons.md row 18).
    """
    if not root.is_dir():
        return
    for entry in sorted(root.iterdir()):
        if entry.is_symlink():
            continue
        if entry.is_file() and entry.suffix == ".md":
            yield entry


def parse_frontmatter(path: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter from a Markdown file.

    Returns ``(frontmatter_dict, body_text)`` where ``body_text`` is
    everything after the closing ``---`` fence.

    Raises ``ValueError`` if the file does not start with ``---``.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(
            f"No YAML frontmatter fences found in {path}; "
            "file must start with '---'"
        )

    # Find the closing fence (second ``---`` on its own line)
    lines = text.split("\n")
    close_idx: int | None = None
    for i, line in enumerate(lines[1:], start=1):
        if line.rstrip() == "---":
            close_idx = i
            break

    if close_idx is None:
        raise ValueError(
            f"Unclosed YAML frontmatter in {path}; "
            "could not find closing '---'"
        )

    fm_text = "\n".join(lines[1:close_idx])
    body = "\n".join(lines[close_idx + 1:])

    fm_dict = yaml.safe_load(fm_text) or {}
    if not isinstance(fm_dict, dict):
        raise ValueError(f"YAML frontmatter in {path} did not parse to a dict")

    return fm_dict, body


def iter_note_files_warn(root: Path) -> Iterator[Path]:
    """Like ``iter_note_files`` but emits a stderr warning for unparseable files.

    Used by ``list_notes`` so bad files are skipped silently.
    """
    for path in iter_note_files(root):
        try:
            parse_frontmatter(path)
            yield path
        except (ValueError, yaml.YAMLError) as exc:
            print(f"[WARN] Skipping {path.name}: {exc}", file=sys.stderr)
