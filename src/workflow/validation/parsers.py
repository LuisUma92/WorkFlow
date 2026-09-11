from __future__ import annotations

from pathlib import Path

import yaml

from workflow.latex.comments import extract_commented_yaml

__all__ = ["parse_md_frontmatter", "parse_tex_metadata"]

_MAX_FILE_SIZE = 1_048_576  # 1 MB


def _read_frontmatter_source(filepath: Path) -> str | None:
    """Read a file's text, honoring the size guard.

    Mirrors the original inline logic exactly: the size check happens
    before any try/except, so a nonexistent file still raises
    FileNotFoundError from `.stat()` uncaught.
    """
    if filepath.stat().st_size > _MAX_FILE_SIZE:
        return None
    try:
        return filepath.read_text(encoding="utf-8")
    except OSError:
        return None


def _extract_frontmatter_block(lines: list[str]) -> str | None:
    """Find the '---'-delimited block at the top of the lines, if any."""
    if not lines or lines[0].strip() != "---":
        return None

    end_index = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = i
            break

    if end_index is None:
        return None

    return "\n".join(lines[1:end_index])


def _parse_yaml_mapping(yaml_block: str) -> dict | None:
    """Parse a YAML block, returning None unless it is a mapping."""
    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None

    return parsed


def parse_md_frontmatter(filepath: Path) -> dict | None:
    """Extract YAML frontmatter from a Markdown file.

    Reads text between the first pair of '---' markers at the top of the file.
    Returns the parsed dict, or None if no frontmatter block is found.
    """
    text = _read_frontmatter_source(filepath)
    if text is None:
        return None

    yaml_block = _extract_frontmatter_block(text.splitlines())
    if yaml_block is None:
        return None

    return _parse_yaml_mapping(yaml_block)


def parse_tex_metadata(filepath: Path) -> dict | None:
    """Parse commented YAML metadata from a .tex file."""
    try:
        if filepath.stat().st_size > _MAX_FILE_SIZE:
            return None
        text = filepath.read_text(encoding="utf-8")
    except OSError:
        return None
    metadata, _ = extract_commented_yaml(text)
    return metadata if isinstance(metadata, dict) else None
