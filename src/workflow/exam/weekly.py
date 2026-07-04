"""Weekly DC.md-driven Moodle XML quiz scaffolding.

Extends the ``exam scaffold-xml`` command with a weekly, category-driven mode
(coexisting with the legacy ``--blocks`` mode in ``scaffold.py``). Reuses the
same CDATA/answers/idnumber conventions but derives categories from a DC.md's
level-2 (``##``) markdown headings instead of an explicit ``--blocks`` spec.

Conventions extracted from the gap log (``~/01-U/.claude/gaps/raw/exam-author.md``,
``exam-author`` sub-agent — anchors quoted below; do not re-derive):

- **idnumber scheme ``WWCCNN``** (week / category-index / question-index, each
  2-digit zero-padded). Anchor 2026-06-30 14:10: "the idnumber prefix (`05`
  for week 5)" plus 2026-07-01: "idnumber convention (week*10000 +
  section*100 + cat)". We encode this as string concatenation of the three
  zero-padded fields rather than the literal arithmetic formula — equivalent
  for 2-digit fields and clearer to read back.
- **Hierarchical category path** ``$course$/top/SemanaWW/{Comprensión,Práctica}/<Cat>``
  — anchor 2026-06-30 14:10 (UCIMED CI0007 weekly quiz pilot).
- **Practica-N -> PC-N -> Tema #(N+1) offset** — anchor 2026-06-15
  ("FS0211 PC11 RE-AUTHORED hierarchical -> flat"): Práctica 11 (PC11) files
  under category ``Tema #12 Momento de inercia``, i.e. week N maps to
  ``Tema #(N+1)``. The gap log documents this offset only for
  ``kind=practica``; this module applies :func:`tema_label_for_practica`
  exclusively to that kind. ``kind=comprension`` has no documented Tema
  offset in the gap log, so its flat/hierarchical category names use the
  week number directly (our own default, not sourced from the gap log).
- **Flat vs hierarchical drift** — anchor 2026-06-15 ("category-scheme drift
  CONFIRMED"): 9 of 11 UCR PC files ended up flat (single category), only
  PC01 stayed hierarchical; flat is documented as the "operational norm".
  Hence ``--category-style`` defaults to ``flat`` here too, with
  ``hierarchical`` as the documented opt-in matching the CI0007 pilot scheme.

DC.md parsing is deliberately MINIMAL (see request notes): only ``##``
headings become category names, one TODO stub question per heading unless a
fixed count is documented (it is not, so ``questions_per_category`` defaults
to 1). This is not a general DC.md parser — that is out of scope (R4
territory).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from workflow.exam.scaffold import _build_answers_block

__all__ = [
    "parse_dc_headings",
    "tema_label_for_practica",
    "build_idnumber",
    "build_category_path",
    "build_weekly_quiz_xml",
    "count_weekly_questions",
]

_CDATA_TERMINATOR = "]]>"
_MAX_FIELD_WIDTH = 99

_DC_HEADING_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)

# Display labels for the two weekly quiz kinds (UCIMED CI0007 convention).
_KIND_LABELS = {"comprension": "Comprensión", "practica": "Práctica"}

_CATEGORY_QUESTION_TMPL = """\
<question type="category">
  <category>
    <text><![CDATA[{path}]]></text>
  </category>
</question>"""

_MULTICHOICE_STUB_TMPL = """\
<!-- TODO: author -->
<question type="multichoice">
  <name>
    <text><![CDATA[{name}]]></text>
  </name>
  <questiontext format="html">
    <text><![CDATA[TODO]]></text>
  </questiontext>
  <generalfeedback format="html">
    <text><![CDATA[TODO]]></text>
  </generalfeedback>
  <defaultgrade>1</defaultgrade>
  <penalty>0.25</penalty>
  <hidden>0</hidden>
  <single>true</single>
  <shuffleanswers>1</shuffleanswers>
  <answernumbering>abc</answernumbering>
  <idnumber>{idnumber}</idnumber>
{answers}</question>"""


def parse_dc_headings(dc_path: Path | str) -> List[str]:
    """Extract level-2 (``##``) markdown headings as category names.

    Parameters
    ----------
    dc_path:
        Path to the DC.md file.

    Returns
    -------
    list of category names, in document order.

    Raises
    ------
    ValueError
        If no level-2 heading is found, or if a heading contains the CDATA
        terminator ``]]>`` (which would otherwise be interpolated raw into
        an ``<![CDATA[...]]>`` block and produce malformed XML).
    """
    text = Path(dc_path).read_text(encoding="utf-8")
    headings = [m.group(1).strip() for m in _DC_HEADING_RE.finditer(text)]
    if not headings:
        raise ValueError(f"No level-2 (##) headings found in {dc_path!r}")
    for heading in headings:
        if _CDATA_TERMINATOR in heading:
            raise ValueError(
                f"Heading {heading!r} in {dc_path!r} contains {_CDATA_TERMINATOR!r}, "
                "which is not allowed (would break CDATA interpolation)"
            )
    return headings


def tema_label_for_practica(week: int) -> str:
    """Return the ``Tema #(N+1)`` label for a Práctica week.

    Encodes the Practica-N -> PC-N -> Tema #(N+1) offset (gap log anchor
    2026-06-15: PC11 -> "Tema #12 Momento de inercia") as a named function so
    it is never left as tribal knowledge.
    """
    return f"Tema #{week + 1:02d}"


def build_idnumber(*, week: int, category_index: int, question_index: int) -> str:
    """Build a ``WWCCNN`` idnumber (week / category-index / question-index).

    All three fields are 2-digit zero-padded (gap log anchors 2026-06-30
    14:10 and 2026-07-01 — see module docstring).

    Raises
    ------
    ValueError
        If any of ``week``, ``category_index``, ``question_index`` is
        outside ``1..99`` — the fixed-width 2-digit contract cannot
        represent it, and silently truncating/overflowing would corrupt
        the idnumber scheme (e.g. ``week=100`` -> ``"1000101"``, 7 digits
        instead of 6).
    """
    for field_name, value in (
        ("week", week),
        ("category_index", category_index),
        ("question_index", question_index),
    ):
        if not (1 <= value <= _MAX_FIELD_WIDTH):
            raise ValueError(
                f"{field_name}={value} is out of range for the 2-digit "
                f"WWCCNN idnumber scheme (expected 1..{_MAX_FIELD_WIDTH})"
            )
    return f"{week:02d}{category_index:02d}{question_index:02d}"


def build_category_path(
    course: str,
    week: int,
    kind: str,
    category_name: str,
    *,
    style: str = "flat",
) -> str:
    """Build a Moodle category path for one DC.md category.

    Parameters
    ----------
    course, week, kind, category_name:
        Identifiers for the weekly quiz and this specific category.
    style:
        ``"hierarchical"`` -> ``$course$/top/SemanaWW/<Kind>/<Cat>`` (gap log
        anchor 2026-06-30 14:10). ``"flat"`` (default) -> a single flat
        category combining course/week/kind/category (our default, mirroring
        the UCR PC02-10 flat convention documented at 2026-06-15 as the
        operational norm).

    Raises
    ------
    ValueError
        If ``style`` is not ``"flat"`` or ``"hierarchical"``.
    """
    kind_label = _KIND_LABELS.get(kind, kind)
    if style == "hierarchical":
        return f"$course$/top/Semana{week:02d}/{kind_label}/{category_name}"
    if style == "flat":
        return f"{course} Semana{week:02d} {kind_label} — {category_name}"
    raise ValueError(f"Unknown --category-style {style!r}; expected 'flat' or 'hierarchical'")


def count_weekly_questions(
    categories: List[str], *, questions_per_category: int = 1
) -> int:
    """Return the total question count :func:`build_weekly_quiz_xml` emits.

    One category question plus ``questions_per_category`` multichoice stubs
    per category. Centralized here so callers (e.g. the CLI summary) never
    have to re-derive or hardcode the per-category question count.
    """
    return len(categories) * (1 + questions_per_category)


def build_weekly_quiz_xml(
    *,
    course: str,
    week: int,
    kind: str,
    categories: List[str],
    category_style: str = "flat",
    questions_per_category: int = 1,
) -> str:
    """Build a full weekly Moodle XML quiz scaffold from DC.md categories.

    Emits one ``<question type="category">`` block per category followed by
    ``questions_per_category`` TODO-stub ``<question type="multichoice">``
    blocks, each carrying a unique ``idnumber`` (see :func:`build_idnumber`).
    No content authoring — all question text is a marked TODO stub.

    Parameters
    ----------
    course, week, kind:
        Identifiers for the weekly quiz. ``kind`` must be ``"comprension"``
        or ``"practica"``.
    categories:
        Category names, in order (typically from :func:`parse_dc_headings`).
    category_style:
        ``"flat"`` (default) or ``"hierarchical"`` — see
        :func:`build_category_path`.
    questions_per_category:
        Number of TODO-stub multichoice questions per category. Defaults to
        1 — the gap log documents variable observed densities (e.g. ~6-7 per
        category for comprensión) but no fixed contract, so this module does
        not invent one.

    Returns
    -------
    str
        Complete ``<?xml ...?><quiz>...</quiz>`` document. Passes
        ``validate_moodle_xml(..., strict=True)`` with zero violations by
        construction — categories are expected to come from
        :func:`parse_dc_headings`, which rejects any heading containing the
        CDATA terminator ``]]>`` before it ever reaches this function.

    Raises
    ------
    ValueError
        If ``kind`` is not ``"comprension"`` or ``"practica"``.
    """
    if kind not in _KIND_LABELS:
        raise ValueError(f"Unknown --kind {kind!r}; expected 'comprension' or 'practica'")

    answers_block = _build_answers_block()
    fragments: List[str] = []
    seq = 1
    for cat_idx, cat_name in enumerate(categories, start=1):
        path = build_category_path(course, week, kind, cat_name, style=category_style)
        fragments.append(_CATEGORY_QUESTION_TMPL.format(path=path))
        for q_idx in range(1, questions_per_category + 1):
            idnumber = build_idnumber(week=week, category_index=cat_idx, question_index=q_idx)
            name = f"{course} Semana{week:02d} {cat_name} {seq:03d}"
            fragments.append(
                _MULTICHOICE_STUB_TMPL.format(
                    name=name, idnumber=idnumber, answers=answers_block
                )
            )
            seq += 1

    inner = "\n".join(fragments)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<quiz>\n{inner}\n</quiz>'
