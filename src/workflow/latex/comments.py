"""Commented YAML extraction and comment stripping for LaTeX files.

Extracts YAML metadata from comment blocks delimited by ``% ---``
markers. Used by both exercise and TikZ parsers.

See ADR-0011 for design rationale.
"""

from __future__ import annotations

import re
from typing import Any

import yaml


def extract_commented_yaml(text: str) -> tuple[dict[str, Any] | None, str]:
    """Extract a commented YAML block from LaTeX source.

    Looks for a block delimited by ``% ---`` lines.  Each line between
    the delimiters has its leading ``%`` (and optional space) stripped
    before being parsed as YAML.

    Parameters
    ----------
    text : str
        The full LaTeX source text.

    Returns
    -------
    tuple[dict | None, str]
        ``(metadata_dict, remaining_text)``.  If no YAML block is
        found, returns ``(None, text)`` unchanged.  ``remaining_text``
        is the original text with the YAML block removed.
    """
    lines = text.split("\n")
    yaml_start = None
    yaml_end = None

    # Find the YAML block delimiters
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "% ---":
            if yaml_start is None:
                yaml_start = idx
            else:
                yaml_end = idx
                break

    if yaml_start is None or yaml_end is None:
        return None, text

    # Extract and strip comment prefixes from YAML lines
    yaml_lines: list[str] = []
    for line in lines[yaml_start + 1 : yaml_end]:
        # Remove leading whitespace, then "% " or "%"
        cleaned = re.sub(r"^\s*%\s?", "", line)
        yaml_lines.append(cleaned)

    yaml_text = "\n".join(yaml_lines)

    try:
        metadata = yaml.safe_load(yaml_text)
        if metadata is None:
            metadata = {}
    except yaml.YAMLError:
        metadata = None

    # Build remaining text: everything except the YAML block
    remaining_lines = lines[:yaml_start] + lines[yaml_end + 1 :]
    remaining = "\n".join(remaining_lines)

    return metadata, remaining


def strip_comments(text: str) -> str:
    """Remove full-line LaTeX comments from text.

    Removes lines whose first non-whitespace character is ``%``,
    unless the ``%`` is escaped as ``\\%``.  Lines that contain
    non-comment content (even if a ``%`` appears mid-line) are
    kept intact.

    Parameters
    ----------
    text : str
        LaTeX source text.

    Returns
    -------
    str
        Text with full-line comments removed.
    """
    result_lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("%") and not stripped.startswith("\\%"):
            continue
        result_lines.append(line)
    return "\n".join(result_lines)
