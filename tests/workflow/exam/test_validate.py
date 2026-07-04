"""Tests for ``workflow exam validate`` — Moodle XML structural lint.

Fixture XMLs live in tests/fixtures/moodle/. Each violation class has its
own fixture; the valid fixture passes both normal and --strict mode.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from workflow.exam.cli import exam
from workflow.exam.validate import validate_moodle_xml

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "moodle"


# ---------------------------------------------------------------------------
# Engine-level tests (validate_moodle_xml)
# ---------------------------------------------------------------------------


def test_valid_file_no_violations():
    report = validate_moodle_xml(FIXTURES / "valid.xml")
    assert report.violations == ()
    assert report.questions == 2


def test_valid_file_strict_no_violations():
    report = validate_moodle_xml(FIXTURES / "valid.xml", strict=True)
    assert report.violations == ()


def test_bad_fractions_zero_correct():
    report = validate_moodle_xml(FIXTURES / "bad-fractions.xml")
    rules = [v.rule for v in report.violations]
    assert "fraction-100" in rules
    v = next(v for v in report.violations if v.rule == "fraction-100")
    assert v.question  # violation names the offending question


def test_bad_fractions_two_correct():
    report = validate_moodle_xml(FIXTURES / "bad-fractions-double.xml")
    rules = [v.rule for v in report.violations]
    assert "fraction-100" in rules


def test_too_few_distractors():
    report = validate_moodle_xml(FIXTURES / "bad-distractors.xml")
    rules = [v.rule for v in report.violations]
    assert "fraction-0" in rules


def test_missing_cdata():
    report = validate_moodle_xml(FIXTURES / "bad-cdata.xml")
    rules = [v.rule for v in report.violations]
    assert "cdata" in rules


def test_missing_defaultgrade_penalty_single():
    report = validate_moodle_xml(FIXTURES / "bad-missing-fields.xml")
    rules = {v.rule for v in report.violations}
    assert {"defaultgrade", "penalty", "single"} <= rules


def test_strict_requires_idnumber():
    # valid.xml questions carry idnumber; no-idnumber fixture does not
    report = validate_moodle_xml(FIXTURES / "no-idnumber.xml", strict=True)
    rules = [v.rule for v in report.violations]
    assert "idnumber" in rules
    # same file passes without --strict
    lax = validate_moodle_xml(FIXTURES / "no-idnumber.xml")
    assert lax.violations == ()


def test_strict_requires_category():
    report = validate_moodle_xml(FIXTURES / "no-category.xml", strict=True)
    rules = [v.rule for v in report.violations]
    assert "category" in rules


def _quiz(*questions: str) -> str:
    body = "\n".join(questions)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<quiz>\n{body}\n</quiz>\n'


def _multichoice(
    name: str,
    *,
    attrs: str = 'type="multichoice"',
    cdata: bool = True,
) -> str:
    text = f"<![CDATA[Enunciado {name}]]>" if cdata else "Enunciado sin CDATA"
    return f"""
<question {attrs}>
  <name>
    <text><![CDATA[{name}]]></text>
  </name>
  <questiontext format="html">
    <text>{text}</text>
  </questiontext>
  <defaultgrade>1</defaultgrade>
  <penalty>0.25</penalty>
  <single>true</single>
  <idnumber>Q1</idnumber>
  <answer fraction="100" format="html">
    <text><![CDATA[Answer 1]]></text>
  </answer>
  <answer fraction="0" format="html">
    <text><![CDATA[Answer 2]]></text>
  </answer>
  <answer fraction="0" format="html">
    <text><![CDATA[Answer 3]]></text>
  </answer>
</question>
"""


def test_cdata_check_survives_attribute_reorder(tmp_path):
    # `type` is not the first attribute — the old positional regex required
    # `type="multichoice"` immediately after `<question `, so this fragment
    # would never be captured and the missing-CDATA violation was dropped.
    xml = _quiz(
        _multichoice("Q-reordered", attrs='id="q1" type="multichoice"', cdata=False)
    )
    path = tmp_path / "reordered.xml"
    path.write_text(xml, encoding="utf-8")

    report = validate_moodle_xml(path)

    cdata_violations = [v for v in report.violations if v.rule == "cdata"]
    assert len(cdata_violations) == 1
    assert cdata_violations[0].question == "Q-reordered"


def test_cdata_violation_attributed_correctly_with_mixed_attribute_order(tmp_path):
    # First question has reordered attrs and no CDATA; second is normal and
    # has CDATA. A positional pairing between the raw-text regex matches and
    # the etree question list could misattribute or miscount this.
    xml = _quiz(
        _multichoice("Q-first", attrs='id="q1" type="multichoice"', cdata=False),
        _multichoice("Q-second", attrs='type="multichoice"', cdata=True),
    )
    path = tmp_path / "mixed.xml"
    path.write_text(xml, encoding="utf-8")

    report = validate_moodle_xml(path)

    cdata_violations = [v for v in report.violations if v.rule == "cdata"]
    assert len(cdata_violations) == 1
    assert cdata_violations[0].question == "Q-first"


def test_cdata_check_covers_single_quoted_type_attribute(tmp_path):
    # `type='multichoice'` (single quotes) is valid XML but the old regex
    # only matched double quotes, so this question was invisible to the
    # CDATA raw-text scan entirely.
    xml = _quiz(_multichoice("Q-singlequote", attrs="type='multichoice'", cdata=False))
    path = tmp_path / "singlequote.xml"
    path.write_text(xml, encoding="utf-8")

    report = validate_moodle_xml(path)

    cdata_violations = [v for v in report.violations if v.rule == "cdata"]
    assert len(cdata_violations) == 1
    assert cdata_violations[0].question == "Q-singlequote"
    # structural rules still apply normally to this question
    assert report.questions == 1


def test_malformed_xml_raises_value_error(tmp_path):
    bad = tmp_path / "broken.xml"
    bad.write_text("<quiz><question", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_moodle_xml(bad)


# ---------------------------------------------------------------------------
# CLI-level tests (workflow exam validate)
# ---------------------------------------------------------------------------


def test_cli_valid_exit_zero():
    runner = CliRunner()
    result = runner.invoke(exam, ["validate", str(FIXTURES / "valid.xml")])
    assert result.exit_code == 0


def test_cli_bad_fractions_exit_one_names_question_and_rule():
    runner = CliRunner()
    result = runner.invoke(exam, ["validate", str(FIXTURES / "bad-fractions.xml")])
    assert result.exit_code == 1
    assert "fraction-100" in result.output


def test_cli_strict_flag():
    runner = CliRunner()
    result = runner.invoke(
        exam, ["validate", "--strict", str(FIXTURES / "no-idnumber.xml")]
    )
    assert result.exit_code == 1
    assert "idnumber" in result.output


def test_cli_json_shape():
    runner = CliRunner()
    result = runner.invoke(
        exam, ["validate", "--json", str(FIXTURES / "bad-fractions.xml")]
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert set(payload) == {"file", "questions", "violations"}
    assert payload["violations"]
    v = payload["violations"][0]
    assert set(v) == {"question", "rule", "detail"}


def test_cli_json_valid_empty_violations():
    runner = CliRunner()
    result = runner.invoke(exam, ["validate", "--json", str(FIXTURES / "valid.xml")])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["violations"] == []


def test_cli_missing_file_exit_nonzero():
    runner = CliRunner()
    result = runner.invoke(exam, ["validate", "/nonexistent/nope.xml"])
    assert result.exit_code != 0


def test_cli_malformed_xml_exit_nonzero(tmp_path):
    bad = tmp_path / "broken.xml"
    bad.write_text("<quiz><question", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(exam, ["validate", str(bad)])
    assert result.exit_code == 1
    assert "parse" in result.output.lower()
