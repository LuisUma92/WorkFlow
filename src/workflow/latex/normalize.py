"""LaTeX normalization: expand custom macros to standard LaTeX.

Used before Moodle XML export so that custom institution macros
are rendered correctly in the target system.

See ADR-0012 for design rationale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from workflow.latex.braces import extract_brace_arg


@dataclass(frozen=True)
class MacroRule:
    """Expansion rule for a custom LaTeX macro."""

    n_args: int  # number of required {brace} arguments
    template: str  # Python format string: {0}, {1} for args
    has_optional: bool = False  # True if [optional] arg may precede required args


# ---------------------------------------------------------------------------
# Default macro expansion map derived from shared/sty/ files
# ---------------------------------------------------------------------------

DEFAULT_MACRO_MAP: dict[str, MacroRule] = {
    # SetCommands.sty
    r"\vc": MacroRule(1, r"\vec{{\mathbf{{{0}}}}}"),
    r"\scrp": MacroRule(1, r"_{{\mbox{{\scriptsize{{{0}}}}}}}"),
    r"\nc": MacroRule(2, r"$^{{{0}}}${1}"),
    r"\ncm": MacroRule(2, r"^{{{0}}}\text{{{1}}}"),
    r"\then": MacroRule(0, "="),
    r"\ifpause": MacroRule(0, ""),
    r"\mailto": MacroRule(1, "{0}"),
    # PartialCommands.sty
    r"\pts": MacroRule(1, "({0} pts.)", has_optional=True),
    r"\upt": MacroRule(0, "(1 pt.)", has_optional=True),
    r"\uptcu": MacroRule(0, "(1 pt. c/u.)"),
    r"\ptscu": MacroRule(1, "({0} pts. c/u.)"),
    r"\rightoption": MacroRule(0, ""),
    r"\consolidatePoints": MacroRule(1, ""),
    r"\inputline": MacroRule(0, "______"),
    r"\completeline": MacroRule(1, "{0}"),
    # Color stripping
    r"\textcolor": MacroRule(2, "{1}"),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_OPTIONAL_ARG_RE = re.compile(r"\s*\[([^\]]*)\]")


def _find_macro_spans(
    text: str, macro_name: str, rule: MacroRule
) -> list[tuple[int, int, list[str]]]:
    """Return all (start, end, args) spans for ``macro_name`` in ``text``.

    Processes right-to-left order is handled by the caller; this returns
    spans in left-to-right order.
    """
    # Match the macro name not followed by a word char
    name_no_slash = macro_name.lstrip("\\")
    pattern = re.compile(r"\\" + re.escape(name_no_slash) + r"(?![a-zA-Z@])")
    spans: list[tuple[int, int, list[str]]] = []

    for m in pattern.finditer(text):
        pos = m.end()

        # Optionally skip [optional] argument
        if rule.has_optional:
            opt_m = _OPTIONAL_ARG_RE.match(text, pos)
            if opt_m:
                pos = opt_m.end()

        args: list[str] = []
        try:
            for _ in range(rule.n_args):
                content, pos = extract_brace_arg(text, pos)
                args.append(content)
        except ValueError:
            continue  # malformed — skip

        spans.append((m.start(), pos, args))

    return spans


def _expand_one_macro(text: str, macro_name: str, rule: MacroRule) -> str:
    """Expand all occurrences of ``macro_name`` in ``text`` using ``rule``.

    Replacements are applied right-to-left to preserve character positions.
    """
    spans = _find_macro_spans(text, macro_name, rule)

    # Right-to-left to keep earlier positions valid
    for start, end, args in reversed(spans):
        expansion = rule.template.format(*args)
        text = text[:start] + expansion + text[end:]

    return text


# ---------------------------------------------------------------------------
# Math delimiter conversion
# ---------------------------------------------------------------------------


def convert_math_delimiters(text: str) -> str:
    r"""Convert ``$...$`` / ``$$...$$`` delimiters to ``\(...\)`` / ``\[...\]``.

    Rules (applied in order):
    1. ``$$...$$``  →  ``\[...\]``  (double-dollar first, before single)
    2. ``$...$``    →  ``\(...\)``  (non-greedy, skip ``\$``)

    Already-converted ``\(...\)`` and ``\[...\]`` are left alone.
    Escaped dollar signs (``\$``) are not treated as delimiters.
    """
    # Step 1: Replace $$...$$ → \[...\]
    # Use a non-greedy match; $$...$$ should not match inside \$
    # We temporarily protect \$ by replacing it with a placeholder
    placeholder = "\x00DOLLAR\x00"
    protected = text.replace(r"\$", placeholder)

    # Double dollar
    protected = re.sub(
        r"\$\$(.+?)\$\$",
        lambda m: r"\[" + m.group(1) + r"\]",
        protected,
        flags=re.DOTALL,
    )

    # Single dollar (non-greedy, must not start with \)
    protected = re.sub(
        r"(?<!\\)\$(.+?)\$",
        lambda m: r"\(" + m.group(1) + r"\)",
        protected,
        flags=re.DOTALL,
    )

    # Restore escaped dollars
    result = protected.replace(placeholder, r"\$")
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize(
    text: str,
    macro_map: dict[str, MacroRule] | None = None,
    max_passes: int = 10,
) -> str:
    """Normalize LaTeX source by expanding custom macros.

    Steps:
    1. Iteratively expand all macros in ``macro_map`` (up to ``max_passes``
       or until convergence).
    2. Replace ``\\symbf{X}`` with ``\\mathbf{X}``.
    3. Convert math delimiters (``$...$`` → ``\\(...\\)`` etc.).

    Parameters
    ----------
    text:
        Raw LaTeX source.
    macro_map:
        Macro expansion rules. Defaults to :data:`DEFAULT_MACRO_MAP`.
    max_passes:
        Maximum iteration count to handle nested macros.

    Returns
    -------
    str
        Normalized LaTeX source.
    """
    if not text:
        return text

    if macro_map is None:
        macro_map = DEFAULT_MACRO_MAP

    # Iterative macro expansion
    for _ in range(max_passes):
        prev = text
        for macro_name, rule in macro_map.items():
            text = _expand_one_macro(text, macro_name, rule)
        if text == prev:
            break  # convergence

    # Replace \symbf{X} → \mathbf{X}
    text = re.sub(r"\\symbf\{", r"\\mathbf{", text)

    # Math delimiter conversion
    text = convert_math_delimiters(text)

    return text
