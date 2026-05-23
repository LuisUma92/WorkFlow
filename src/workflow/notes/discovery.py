"""Note file discovery and frontmatter parsing.

Filesystem-only — no DB access.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

import yaml

__all__ = ["iter_note_files", "walk_note_files", "parse_frontmatter"]

_log = logging.getLogger(__name__)

# Directories to skip during discovery (lessons.md row 18 — avoid loops + non-note dirs).
_SKIP_DIR_NAMES = frozenset({
    "images", "__pycache__", "node_modules", "templates",
})


def iter_note_files(root: Path) -> Iterator[Path]:
    """Yield .md files directly inside *root* (top-level only, no recursion).

    Top-level symlinks to .md files are included (H6: no loops without recursion).
    Directory symlinks are still skipped to prevent accidental recursion if the
    caller ever adds subdirectory traversal later.
    """
    if not root.is_dir():
        return
    for entry in sorted(root.iterdir()):
        # Skip symlinks that point to directories (loop risk when/if recursion added)
        if entry.is_symlink() and entry.is_dir():
            continue
        if entry.is_file() and entry.suffix == ".md":
            yield entry


def walk_note_files(root: Path) -> Iterator[Path]:
    """Yield all .md files under *root*, recursively.

    Skips: hidden directories (``.git``, ``.obsidian``, ``.workflow`` …), the
    ``templates/`` directory, build/cache dirs, and directory symlinks (loop
    safety). Files resolved outside ``root`` (escape via symlink) are dropped.
    """
    if not root.is_dir():
        return
    root_resolved = root.resolve()
    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except (PermissionError, OSError):
            continue
        for entry in entries:
            if entry.is_symlink() and entry.is_dir():
                continue
            if entry.is_dir():
                if entry.name.startswith(".") or entry.name in _SKIP_DIR_NAMES:
                    continue
                stack.append(entry)
            elif entry.is_file() and entry.suffix == ".md":
                try:
                    if entry.resolve().is_relative_to(root_resolved):
                        yield entry
                except (OSError, ValueError):
                    continue


def parse_frontmatter(path: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter from a Markdown file.

    Returns ``(frontmatter_dict, body_text)`` where ``body_text`` is
    everything after the closing ``---`` fence, byte-exact (H3).

    Raises ``ValueError`` if the file does not start with ``---``.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(
            f"No YAML frontmatter fences found in {path}; "
            "file must start with '---'"
        )

    # Find closing fence using character-position search (H3: byte-exact).
    # We look for a line that is exactly "---" (allowing \r) after the opening fence.
    # Search starts after the first "---\n" or "---\r\n".
    open_end = text.index("\n") + 1  # position right after the first line
    search_start = open_end

    close_pos: int | None = None
    pos = search_start
    while pos < len(text):
        newline_pos = text.find("\n", pos)
        if newline_pos == -1:
            break
        line = text[pos:newline_pos]
        if line.rstrip("\r") == "---":
            close_pos = newline_pos + 1  # character position right after the closing \n
            fm_text = text[open_end:pos].rstrip("\r\n")  # strip trailing newline from fm block
            break
        pos = newline_pos + 1

    if close_pos is None:
        raise ValueError(
            f"Unclosed YAML frontmatter in {path}; "
            "could not find closing '---'"
        )

    body = text[close_pos:]  # everything after closing fence, byte-exact (H3)

    fm_dict = yaml.safe_load(fm_text) or {}
    if not isinstance(fm_dict, dict):
        raise ValueError(f"YAML frontmatter in {path} did not parse to a dict")

    return fm_dict, body
