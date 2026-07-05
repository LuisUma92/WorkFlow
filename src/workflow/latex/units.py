"""workflow.latex.units — minimal lint of ``\\si``/``\\SI`` unit usage.

Checks that unit macros used inside ``\\si{...}``/``\\SI{<num>}{...}`` calls in
an exercise ``.tex`` body are either siunitx built-ins or declared via
``\\DeclareSIUnit\\<name>{...}`` in ``share/latex/sty/SetUnits.sty``.

Deliberately **not** a general LaTeX parser: only the two constructs above are
recognized (regex-based, per the plan's scope note — no brace-counting
extractor is reused/extended here since ``.sty`` macro tables and exercise
``.tex`` frontmatter are different shapes of document).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from workflow import paths

__all__ = [
    "LintIssue",
    "default_units_sty_path",
    "load_declared_units",
    "find_undeclared_units",
    "format_unit_warnings",
]

_DECLARE_SI_UNIT_RE = re.compile(r"\\DeclareSIUnit\\([A-Za-z]+)")
_SI_ONE_ARG_RE = re.compile(r"\\si\*?\s*\{([^{}]*)\}")
_SI_TWO_ARG_RE = re.compile(r"\\SI\*?\s*\{[^{}]*\}\s*\{([^{}]*)\}")
_UNIT_TOKEN_RE = re.compile(r"\\([A-Za-z]+)")

# siunitx SI-prefix macros — modify the unit that follows, never unit names
# themselves (e.g. \si{\kilo\gram}).
_SIUNITX_PREFIXES = frozenset(
    {
        "yocto", "zepto", "atto", "femto", "pico", "nano", "micro", "milli",
        "centi", "deci", "deca", "hecto", "kilo", "mega", "giga", "tera",
        "peta", "exa", "zetta", "yotta",
        "kibi", "mebi", "gibi", "tebi", "pebi", "exbi", "zebi", "yobi",
    }
)

# siunitx power/operator macros inside a unit argument — not unit names
# (e.g. \si{\meter\per\second}).
_SIUNITX_MODIFIERS = frozenset(
    {"per", "square", "squared", "cubed", "cubic", "tothe", "raisto", "of"}
)

# Built-in siunitx unit macros in common physics use. Not exhaustive — this
# is a minimal lint against silently-undeclared *custom* units, not a full
# siunitx reimplementation.
_SIUNITX_BUILTIN_UNITS = frozenset(
    {
        "ampere", "angstrom", "arcminute", "arcsecond", "astronomicalunit",
        "atomicmassunit", "bar", "becquerel", "bel", "bohr", "candela",
        "celsius", "clight", "coulomb", "dalton", "day", "decibel", "degree",
        "degreeCelsius", "electronmass", "electronvolt", "elementarycharge",
        "farad", "gram", "gramme", "gray", "hartree", "hectare", "henry",
        "hertz", "hour", "joule", "katal", "kelvin", "kilogram", "liter",
        "litre", "lumen", "lux", "meter", "metre", "minute",
        "mmHg", "mole", "neper", "newton", "ohm", "pascal", "percent",
        "planckbar", "radian", "second", "siemens", "sievert", "steradian",
        "tesla", "tonne", "volt", "watt", "weber",
    }
)


@dataclass(frozen=True)
class LintIssue:
    """One undeclared-unit finding inside a ``\\si``/``\\SI`` invocation."""

    line: int
    unit_token: str
    suggestion: str | None


def default_units_sty_path() -> Path:
    """XDG-resolved location of ``SetUnits.sty`` (symlink-agnostic, ADR-0008)."""
    return paths.data_dir() / "sty" / "SetUnits.sty"


def load_declared_units(sty_path: Path) -> frozenset[str]:
    """Parse ``\\DeclareSIUnit\\<name>{...}`` lines from a ``.sty`` file.

    Minimal regex parser — not a general LaTeX parser. Returns an empty set
    if the file is missing or unreadable (fail-soft: lint degrades to
    "builtins only" rather than raising).
    """
    try:
        text = sty_path.read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    return frozenset(_DECLARE_SI_UNIT_RE.findall(text))


def _iter_unit_args(tex_body: str):
    """Yield ``(start_offset, unit_arg_text)`` for each ``\\si``/``\\SI`` call."""
    for m in _SI_ONE_ARG_RE.finditer(tex_body):
        yield m.start(), m.group(1)
    for m in _SI_TWO_ARG_RE.finditer(tex_body):
        yield m.start(), m.group(1)


def find_undeclared_units(tex_body: str, declared: frozenset[str]) -> list[LintIssue]:
    """Flag unit macros in ``\\si``/``\\SI`` calls not in builtins ∪ ``declared``.

    Prefix macros (``\\kilo``) and operator macros (``\\per``, ``\\square``,
    ...) are ignored — they modify a unit but are never unit names themselves.
    """
    known = declared | _SIUNITX_BUILTIN_UNITS
    issues: list[LintIssue] = []
    for start, unit_arg in _iter_unit_args(tex_body):
        line = tex_body.count("\n", 0, start) + 1
        for token in _UNIT_TOKEN_RE.findall(unit_arg):
            if token in _SIUNITX_PREFIXES or token in _SIUNITX_MODIFIERS:
                continue
            if token in known:
                continue
            matches = difflib.get_close_matches(token, known, n=1)
            suggestion = matches[0] if matches else None
            issues.append(LintIssue(line=line, unit_token=token, suggestion=suggestion))
    return issues


def format_unit_warnings(issues: list[LintIssue]) -> list[str]:
    """Render ``LintIssue``s as warning strings (Bundle A difflib precedent)."""
    warnings: list[str] = []
    for issue in issues:
        msg = f"line {issue.line}: undeclared unit '\\{issue.unit_token}'"
        if issue.suggestion:
            msg += f" — did you mean '\\{issue.suggestion}'?"
        warnings.append(msg)
    return warnings
