"""Moodle XML structural lint.

Validates a Moodle XML quiz export against a set of structural rules that
Moodle itself will not catch until import time (or worse, silently accepts
with broken semantics — e.g. two "correct" answers). Two layers of checks:

- Always-on rules: exactly one 100%-fraction answer, at least two 0%-fraction
  distractors, CDATA-wrapped question text, and presence of the
  ``defaultgrade``/``penalty``/``single`` elements.
- ``--strict`` rules: every multichoice question carries an ``idnumber``, and
  the file contains at least one ``category`` question.

Design notes
------------
- stdlib ElementTree strips CDATA markers on parse, so the CDATA check is
  done via a raw-text regex scan over ``<question ... type="multichoice"
  ...>...</question>`` fragments. Each fragment is checked independently
  (its own question name is read out of the fragment text) rather than
  paired positionally with the etree question list — attribute order,
  quoting style (single/double), and internal spacing around ``type=``
  vary between real-world exports and must not desynchronize the two scans.
- If the raw-text fragment count and the etree multichoice count disagree,
  a file-level violation is emitted so a scanning mismatch is never silent.
- The parser never raises on structural violations (they become
  ``Violation`` entries); only malformed XML raises ``ValueError``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple
from xml.etree import ElementTree as ET

__all__ = ["Violation", "ValidationReport", "validate_moodle_xml"]

# Raw-text scan for multichoice question fragments (etree strips CDATA).
# Tolerant of attribute order and single/double quoting, e.g.
# <question id="1" type='multichoice'> — the ``type`` attribute need not be
# first or double-quoted.
_MULTICHOICE_FRAGMENT_RE = re.compile(
    r'<question\b[^>]*\btype\s*=\s*["\']multichoice["\'][^>]*>.*?</question>',
    re.S,
)
_QUESTIONTEXT_RE = re.compile(r"<questiontext\b.*?</questiontext>", re.S)
_NAME_TEXT_RE = re.compile(
    r"<name>\s*<text>\s*(?:<!\[CDATA\[(?P<cdata>.*?)\]\]>|(?P<plain>.*?))\s*</text>",
    re.S,
)


@dataclass(frozen=True)
class Violation:
    """A single structural rule failure for one question."""

    question: str
    rule: str
    detail: str


@dataclass(frozen=True)
class ValidationReport:
    """Aggregate validation result for one Moodle XML file."""

    file: str
    questions: int
    violations: Tuple[Violation, ...]


def _question_name(question: ET.Element) -> str:
    """Return the question's display name, or ``(unnamed)`` if absent."""
    name_text = question.find("./name/text")
    if name_text is not None and name_text.text:
        return name_text.text
    return "(unnamed)"


def _check_fractions(question: ET.Element, name: str) -> List[Violation]:
    """Check the fraction-100 and fraction-0 rules for one question."""
    violations: List[Violation] = []
    answers = question.findall("./answer")
    hundreds = [a for a in answers if a.get("fraction") == "100"]
    zeros = [a for a in answers if a.get("fraction") == "0"]

    if len(hundreds) != 1:
        violations.append(
            Violation(
                question=name,
                rule="fraction-100",
                detail=f"expected exactly one fraction=\"100\" answer, found {len(hundreds)}",
            )
        )
    if len(zeros) < 2:
        violations.append(
            Violation(
                question=name,
                rule="fraction-0",
                detail=f"expected at least two fraction=\"0\" answers, found {len(zeros)}",
            )
        )
    return violations


def _check_required_fields(question: ET.Element, name: str) -> List[Violation]:
    """Check the defaultgrade/penalty/single presence rules for one question."""
    violations: List[Violation] = []
    for tag in ("defaultgrade", "penalty", "single"):
        if question.find(f"./{tag}") is None:
            violations.append(
                Violation(
                    question=name,
                    rule=tag,
                    detail=f"missing required <{tag}> element",
                )
            )
    return violations


def _fragment_question_name(fragment: str) -> str:
    """Extract the question's display name from a raw-text fragment."""
    match = _NAME_TEXT_RE.search(fragment)
    if match is None:
        return "(unnamed)"
    text = match.group("cdata")
    if text is None:
        text = match.group("plain")
    text = text.strip()
    return text or "(unnamed)"


def _check_cdata(fragment: str) -> List[Violation]:
    """Check that the questiontext region of a raw fragment is CDATA-wrapped."""
    name = _fragment_question_name(fragment)
    match = _QUESTIONTEXT_RE.search(fragment)
    if match is None or "<![CDATA[" not in match.group(0):
        return [
            Violation(
                question=name,
                rule="cdata",
                detail="<questiontext><text> is not CDATA-wrapped",
            )
        ]
    return []


def _check_strict(question: ET.Element, name: str) -> List[Violation]:
    """Check --strict-only per-question rules (idnumber)."""
    violations: List[Violation] = []
    if question.find("./idnumber") is None:
        violations.append(
            Violation(
                question=name,
                rule="idnumber",
                detail="missing required <idnumber> element",
            )
        )
    return violations


def validate_moodle_xml(path: Path | str, *, strict: bool = False) -> ValidationReport:
    """Validate a Moodle XML quiz export file.

    Parameters
    ----------
    path:
        Path to the Moodle XML file. Missing-file errors surface as the
        natural ``OSError`` from reading the file.
    strict:
        When ``True``, also enforce per-question ``idnumber`` presence and
        require at least one ``category`` question in the file.

    Returns
    -------
    ValidationReport
        ``questions`` counts multichoice questions only; ``violations`` is a
        tuple of ``Violation`` in etree-encounter order.

    Raises
    ------
    ValueError
        If the file is not well-formed XML.
    """
    file_path = Path(path)
    raw_text = file_path.read_text(encoding="utf-8")

    try:
        root = ET.fromstring(raw_text)
    except ET.ParseError as exc:
        raise ValueError(f"malformed XML in {file_path}: {exc}") from exc

    fragments = [m.group(0) for m in _MULTICHOICE_FRAGMENT_RE.finditer(raw_text)]
    multichoice_questions = root.findall('.//question[@type="multichoice"]')

    violations: List[Violation] = []
    for question in multichoice_questions:
        name = _question_name(question)
        violations.extend(_check_fractions(question, name))
        violations.extend(_check_required_fields(question, name))
        if strict:
            violations.extend(_check_strict(question, name))

    # The CDATA check runs over the raw-text fragments independently of the
    # etree question list above — no positional pairing between the two.
    for fragment in fragments:
        violations.extend(_check_cdata(fragment))

    if len(fragments) != len(multichoice_questions):
        violations.append(
            Violation(
                question="(file)",
                rule="cdata",
                detail=(
                    "raw-text multichoice scan found "
                    f"{len(fragments)} fragment(s) but etree found "
                    f"{len(multichoice_questions)} <question type=\"multichoice\"> "
                    "element(s) — CDATA check may be incomplete for this file"
                ),
            )
        )

    if strict:
        category_questions = root.findall('.//question[@type="category"]')
        if not category_questions:
            violations.append(
                Violation(
                    question="(file)",
                    rule="category",
                    detail="file must contain at least one category question",
                )
            )

    return ValidationReport(
        file=str(file_path),
        questions=len(multichoice_questions),
        violations=tuple(violations),
    )
