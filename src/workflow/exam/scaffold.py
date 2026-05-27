"""Moodle XML quiz scaffold generator.

Generates a skeleton Moodle XML quiz with CDATA[TODO] placeholders from a
block specification. No DB access required — pure string generation.

Design notes
------------
- stdlib ElementTree does NOT emit CDATA sections; we use string templating
  for the CDATA-containing fragments and inject them into the serialized body.
- Block boundary comments are injected via string manipulation after the
  XML body is assembled (ElementTree strips comments).
- All distractor labels are distinct (Answer 1 … Answer 4) to prevent the
  duplicate-paste bug documented in the request.
"""

from __future__ import annotations

import re
from typing import List, Tuple

__all__ = ["parse_blocks_spec", "build_moodle_quiz_xml"]

# Number of answer options per multichoice question
_ANSWER_COUNT = 4

# Regex: name may contain word chars and hyphens; count is an integer (sign validated later)
_BLOCK_ITEM_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9\s_-]*?)\s*:\s*(-?\d+)$")


def parse_blocks_spec(spec: str) -> List[Tuple[str, int]]:
    """Parse a ``Name:count,...`` blocks specification string.

    Parameters
    ----------
    spec:
        Comma-separated ``Name:count`` pairs, e.g. ``"Recordar:4,Usar:4"``.
        Names may contain word characters, spaces, underscores, and hyphens.
        Leading/trailing whitespace around names and counts is stripped.

    Returns
    -------
    list of (name, count) tuples

    Raises
    ------
    ValueError
        On empty spec, malformed pair, non-integer count, or count < 1.
    """
    spec = spec.strip()
    if not spec:
        raise ValueError("--blocks cannot be empty")

    result: List[Tuple[str, int]] = []
    for raw_item in spec.split(","):
        item = raw_item.strip()
        if not item:
            continue
        m = _BLOCK_ITEM_RE.match(item)
        if m is None:
            raise ValueError(
                f"Invalid block spec item {item!r}. Expected format: 'Name:count'"
            )
        name = m.group(1).strip()
        if not name:
            raise ValueError(f"Invalid block spec item {item!r}: name is empty")
        try:
            count = int(m.group(2))
        except ValueError:
            raise ValueError(
                f"Invalid block spec item {item!r}: count must be an integer"
            )
        if count < 1:
            raise ValueError(
                f"Invalid block spec item {item!r}: count must be >= 1"
            )
        result.append((name, count))

    if not result:
        raise ValueError("--blocks cannot be empty")
    return result


# ---------------------------------------------------------------------------
# XML template fragments
# ---------------------------------------------------------------------------

_XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>\n'

_CATEGORY_QUESTION_TMPL = """\
<question type="category">
  <category>
    <text><![CDATA[{category}]]></text>
  </category>
  <info format="html">
    <text><![CDATA[{course} {cycle} G{group} — {label}]]></text>
  </info>
</question>"""

_MULTICHOICE_QUESTION_TMPL = """\
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
  <defaultgrade>{grade}</defaultgrade>
  <penalty>{penalty}</penalty>
  <hidden>0</hidden>
  <single>true</single>
  <shuffleanswers>1</shuffleanswers>
  <answernumbering>abc</answernumbering>
{answers}</question>"""

_ANSWER_CORRECT_TMPL = """\
  <answer fraction="100" format="html">
    <text><![CDATA[Answer 1]]></text>
    <feedback format="html">
      <text><![CDATA[TODO]]></text>
    </feedback>
  </answer>"""

_ANSWER_WRONG_TMPL = """\
  <answer fraction="0" format="html">
    <text><![CDATA[Answer {n}]]></text>
    <feedback format="html">
      <text><![CDATA[TODO]]></text>
    </feedback>
  </answer>"""

_BLOCK_COMMENT_TMPL = "<!-- {name} -->"


def _build_answers_block() -> str:
    """Return the answers block with distinct distractor labels."""
    parts: List[str] = [_ANSWER_CORRECT_TMPL]
    for n in range(2, _ANSWER_COUNT + 1):
        parts.append(_ANSWER_WRONG_TMPL.format(n=n))
    return "\n".join(parts) + "\n"


def _build_question_name(
    prefix: str, block_name: str, course: str, label: str, seq: int
) -> str:
    """Build a unique question name from available metadata."""
    parts = []
    if prefix:
        parts.append(prefix)
    parts.append(block_name)
    parts.append(f"{course}-{label}-{seq:02d}")
    return " ".join(parts)


def build_moodle_quiz_xml(
    *,
    course: str,
    cycle: str,
    group: str,
    label: str,
    category: str,
    blocks: List[Tuple[str, int]],
    question_prefix: str = "",
    penalty: float = 0.25,
    grade: int = 1,
) -> str:
    """Build a complete Moodle XML quiz scaffold string.

    Parameters
    ----------
    course, cycle, group, label:
        Identifiers used in category text and question names.
    category:
        Moodle category path inserted in the ``<category>`` question.
    blocks:
        List of ``(name, count)`` tuples from :func:`parse_blocks_spec`.
    question_prefix:
        Optional text prepended to each question name.
    penalty:
        Per-wrong-answer penalty fraction for every ``<question>``.
    grade:
        Default grade for every multichoice ``<question>``.

    Returns
    -------
    str
        ``<?xml version="1.0" encoding="UTF-8"?>\\n<quiz>...</quiz>``
    """
    answers_block = _build_answers_block()
    penalty_str = f"{penalty:.10g}"

    # Build fragments list: (is_block_comment, text)
    # We accumulate raw XML fragments with block comments interleaved.
    fragments: List[str] = []
    fragments.append(_CATEGORY_QUESTION_TMPL.format(
        category=category,
        course=course,
        cycle=cycle,
        group=group,
        label=label,
    ))

    seq = 1
    for block_name, count in blocks:
        # Inject block boundary comment
        fragments.append(_BLOCK_COMMENT_TMPL.format(name=block_name))
        for _ in range(count):
            q_name = _build_question_name(question_prefix, block_name, course, label, seq)
            q_xml = _MULTICHOICE_QUESTION_TMPL.format(
                name=q_name,
                grade=grade,
                penalty=penalty_str,
                answers=answers_block,
            )
            fragments.append(q_xml)
            seq += 1

    inner = "\n".join(fragments)
    return f"{_XML_DECLARATION}<quiz>\n{inner}\n</quiz>"
