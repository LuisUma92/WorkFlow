"""Brace-counting LaTeX macro argument extraction.

Provides zero-dependency, pure-Python utilities for extracting
brace-delimited arguments from known LaTeX macros. Handles
nested braces correctly via depth counting.

See ADR-0011 for design rationale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MacroMatch:
    """Result of extracting a macro's arguments from LaTeX source."""

    args: tuple[str, ...]
    start: int  # position where the macro name starts
    end: int  # position after the last closing brace


def extract_brace_arg(text: str, start: int) -> tuple[str, int]:
    """Extract content between matched braces starting at or after `start`.

    Scans forward from `start` to find the first ``{``, then counts
    brace depth to find the matching ``}``.  Escaped braces (``\\{``
    and ``\\}``) are ignored.

    Parameters
    ----------
    text : str
        The full LaTeX source text.
    start : int
        Position to begin scanning for an opening brace.

    Returns
    -------
    tuple[str, int]
        ``(content, end_position)`` where *content* is the text
        between the matched braces (exclusive) and *end_position*
        is the index immediately after the closing ``}``.

    Raises
    ------
    ValueError
        If no opening brace is found or braces are unmatched.
    """
    i = start
    # Find opening brace
    while i < len(text) and text[i] != "{":
        i += 1
    if i >= len(text):
        raise ValueError(f"No opening brace found starting at position {start}")

    content_start = i + 1
    depth = 1
    i += 1

    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "\\":
            # Skip escaped character
            i += 2
            if i >= len(text):
                break
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1

    if depth != 0:
        raise ValueError(f"Unmatched brace starting at position {content_start - 1}")

    return text[content_start : i - 1], i


def extract_macro_args(text: str, macro_name: str, n_args: int) -> list[MacroMatch]:
    r"""Find all occurrences of ``\macro_name`` and extract arguments.

    For zero-argument macros (like ``\rightoption``), returns matches
    with empty ``args`` lists.

    The macro is matched as a whole word — ``\question`` will not
    match ``\questiontext``.

    Parameters
    ----------
    text : str
        The full LaTeX source text.
    macro_name : str
        Macro name without the leading backslash.
    n_args : int
        Number of brace-delimited arguments to extract.

    Returns
    -------
    list[MacroMatch]
        All matches found, in order of appearance.
    """
    # Match \macroname not followed by a word character
    pattern = re.compile(r"\\" + re.escape(macro_name) + r"(?![a-zA-Z@])")
    matches: list[MacroMatch] = []

    for m in pattern.finditer(text):
        macro_start = m.start()
        pos = m.end()
        args: list[str] = []

        try:
            for _ in range(n_args):
                content, pos = extract_brace_arg(text, pos)
                args.append(content)
        except ValueError:
            # Malformed macro — skip this occurrence
            continue

        matches.append(MacroMatch(args=tuple(args), start=macro_start, end=pos))

    return matches
