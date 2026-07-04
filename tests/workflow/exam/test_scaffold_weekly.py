"""TDD tests for the weekly DC.md-driven `exam scaffold-xml` mode.

Covers:
- workflow.exam.weekly: parse_dc_headings, tema_label_for_practica,
  build_idnumber, build_category_path, build_weekly_quiz_xml
- CLI: mode detection (weekly vs legacy vs mixed-mode usage error),
  --category-style flat/hierarchical, --json summary, -o alias,
  round-trip strict validation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from workflow.exam.cli import exam
from workflow.exam.validate import validate_moodle_xml
from workflow.exam.weekly import (
    build_category_path,
    build_idnumber,
    build_weekly_quiz_xml,
    count_weekly_questions,
    parse_dc_headings,
    tema_label_for_practica,
)


_DC_MD = """\
# Semana11 - DC

## NaturalezaLuz

Descripcion breve.

## Reflexion

Otra descripcion.

## Refraccion
"""


@pytest.fixture()
def dc_file(tmp_path: Path) -> Path:
    p = tmp_path / "Semana11-DC.md"
    p.write_text(_DC_MD, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# parse_dc_headings
# ---------------------------------------------------------------------------


class TestParseDcHeadings:
    def test_extracts_level2_headings_in_order(self, dc_file):
        result = parse_dc_headings(dc_file)
        assert result == ["NaturalezaLuz", "Reflexion", "Refraccion"]

    def test_ignores_level1_heading(self, dc_file):
        result = parse_dc_headings(dc_file)
        assert "Semana11 - DC" not in result

    def test_no_headings_raises(self, tmp_path):
        p = tmp_path / "empty.md"
        p.write_text("just prose, no headings\n", encoding="utf-8")
        with pytest.raises(ValueError, match="No level-2"):
            parse_dc_headings(p)

    def test_heading_with_cdata_terminator_raises(self, tmp_path):
        p = tmp_path / "evil.md"
        p.write_text("## bad]]>evil\n", encoding="utf-8")
        with pytest.raises(ValueError, match=r"\]\]>"):
            parse_dc_headings(p)


# ---------------------------------------------------------------------------
# Tema offset
# ---------------------------------------------------------------------------


class TestTemaOffset:
    def test_week_11_practica_maps_to_tema_12(self):
        assert tema_label_for_practica(11) == "Tema #12"

    def test_week_1_practica_maps_to_tema_02(self):
        assert tema_label_for_practica(1) == "Tema #02"


# ---------------------------------------------------------------------------
# idnumber scheme
# ---------------------------------------------------------------------------


class TestBuildIdnumber:
    def test_zero_padded_fields(self):
        assert build_idnumber(week=11, category_index=1, question_index=3) == "110103"

    def test_single_digit_week(self):
        assert build_idnumber(week=5, category_index=2, question_index=1) == "050201"

    def test_week_99_is_ok(self):
        assert build_idnumber(week=99, category_index=1, question_index=1) == "990101"

    def test_week_over_99_raises(self):
        with pytest.raises(ValueError):
            build_idnumber(week=100, category_index=1, question_index=1)

    def test_category_index_over_99_raises(self):
        with pytest.raises(ValueError):
            build_idnumber(week=1, category_index=100, question_index=1)

    def test_question_index_over_99_raises(self):
        with pytest.raises(ValueError):
            build_idnumber(week=1, category_index=1, question_index=100)

    def test_week_below_1_raises(self):
        with pytest.raises(ValueError):
            build_idnumber(week=0, category_index=1, question_index=1)


# ---------------------------------------------------------------------------
# category path
# ---------------------------------------------------------------------------


class TestBuildCategoryPath:
    def test_hierarchical_style(self):
        path = build_category_path(
            "CI0007", 11, "comprension", "NaturalezaLuz", style="hierarchical"
        )
        assert path == "$course$/top/Semana11/Comprensión/NaturalezaLuz"

    def test_flat_style_default(self):
        path = build_category_path("CI0007", 11, "practica", "Reflexion")
        assert "CI0007" in path
        assert "Semana11" in path
        assert "Reflexion" in path

    def test_unknown_style_raises(self):
        with pytest.raises(ValueError):
            build_category_path("CI0007", 11, "practica", "X", style="bogus")


# ---------------------------------------------------------------------------
# build_weekly_quiz_xml
# ---------------------------------------------------------------------------


class TestBuildWeeklyQuizXml:
    def test_one_category_question_per_heading_plus_one_stub_each(self):
        xml_text = build_weekly_quiz_xml(
            course="CI0007",
            week=11,
            kind="comprension",
            categories=["NaturalezaLuz", "Reflexion", "Refraccion"],
        )
        assert xml_text.count('type="category"') == 3
        assert xml_text.count('type="multichoice"') == 3

    def test_idnumber_present_on_every_multichoice(self):
        xml_text = build_weekly_quiz_xml(
            course="CI0007", week=11, kind="practica", categories=["A", "B"]
        )
        assert xml_text.count("<idnumber>") == 2

    def test_todo_stub_marker_present(self):
        xml_text = build_weekly_quiz_xml(
            course="CI0007", week=11, kind="practica", categories=["A"]
        )
        assert "<!-- TODO: author -->" in xml_text
        assert "<![CDATA[TODO]]>" in xml_text

    def test_unknown_kind_raises(self):
        with pytest.raises(ValueError):
            build_weekly_quiz_xml(
                course="CI0007", week=11, kind="bogus", categories=["A"]
            )

    def test_passes_strict_validation(self, tmp_path):
        xml_text = build_weekly_quiz_xml(
            course="CI0007",
            week=11,
            kind="comprension",
            categories=["NaturalezaLuz", "Reflexion"],
        )
        out = tmp_path / "weekly.xml"
        out.write_text(xml_text, encoding="utf-8")
        report = validate_moodle_xml(out, strict=True)
        assert report.violations == ()


# ---------------------------------------------------------------------------
# count_weekly_questions helper (fixes cli.py hardcoded `* 2` assumption)
# ---------------------------------------------------------------------------


class TestCountWeeklyQuestions:
    def test_default_one_question_per_category(self):
        assert count_weekly_questions(["A", "B", "C"]) == 6

    def test_custom_questions_per_category(self):
        assert count_weekly_questions(["A", "B"], questions_per_category=3) == 8

    def test_single_category(self):
        assert count_weekly_questions(["A"]) == 2


# ---------------------------------------------------------------------------
# CLI: mode detection
# ---------------------------------------------------------------------------


class TestCliModeDetection:
    def test_weekly_mode_missing_legacy_options_ok(self, dc_file, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "out.xml"
        result = runner.invoke(
            exam,
            [
                "scaffold-xml",
                "--course", "CI0007",
                "--week", "11",
                "--dc", str(dc_file),
                "--kind", "comprension",
                "--out", str(out_file),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out_file.exists()

    def test_legacy_mode_still_requires_all_legacy_options(self):
        runner = CliRunner()
        result = runner.invoke(
            exam,
            ["scaffold-xml", "--course", "FS0211", "--out", "/tmp/x.xml"],
        )
        assert result.exit_code == 2

    def test_mixing_modes_is_usage_error(self, dc_file, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "out.xml"
        result = runner.invoke(
            exam,
            [
                "scaffold-xml",
                "--course", "CI0007",
                "--week", "11",
                "--dc", str(dc_file),
                "--kind", "comprension",
                "--blocks", "Recordar:4",
                "--out", str(out_file),
            ],
        )
        assert result.exit_code == 2

    def test_legacy_mode_unchanged_when_no_weekly_flags(self, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "legacy.xml"
        result = runner.invoke(
            exam,
            [
                "scaffold-xml",
                "--course", "FS0211",
                "--cycle", "2026C1",
                "--group", "001",
                "--label", "PC04",
                "--category", "Tema #06",
                "--blocks", "Recordar:4",
                "--out", str(out_file),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out_file.exists()


# ---------------------------------------------------------------------------
# CLI: --category-style, --json, -o alias, round-trip
# ---------------------------------------------------------------------------


class TestCliWeeklyOptions:
    def test_category_style_hierarchical(self, dc_file, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "out.xml"
        result = runner.invoke(
            exam,
            [
                "scaffold-xml",
                "--course", "CI0007",
                "--week", "11",
                "--dc", str(dc_file),
                "--kind", "comprension",
                "--category-style", "hierarchical",
                "--out", str(out_file),
            ],
        )
        assert result.exit_code == 0, result.output
        content = out_file.read_text()
        assert "$course$/top/Semana11/Comprensión" in content

    def test_o_short_alias(self, dc_file, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "out.xml"
        result = runner.invoke(
            exam,
            [
                "scaffold-xml",
                "--course", "CI0007",
                "--week", "11",
                "--dc", str(dc_file),
                "--kind", "comprension",
                "-o", str(out_file),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out_file.exists()

    def test_json_summary(self, dc_file, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "out.xml"
        result = runner.invoke(
            exam,
            [
                "scaffold-xml",
                "--course", "CI0007",
                "--week", "11",
                "--dc", str(dc_file),
                "--kind", "practica",
                "--json",
                "--out", str(out_file),
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["week"] == 11
        assert data["kind"] == "practica"
        assert data["course"] == "CI0007"
        assert data["categories"] == ["NaturalezaLuz", "Reflexion", "Refraccion"]
        assert data["tema_label"] == "Tema #12"
        assert "path" in data

    def test_json_summary_tema_label_null_for_comprension(self, dc_file, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "out.xml"
        result = runner.invoke(
            exam,
            [
                "scaffold-xml",
                "--course", "CI0007",
                "--week", "11",
                "--dc", str(dc_file),
                "--kind", "comprension",
                "--json",
                "--out", str(out_file),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["tema_label"] is None

    def test_dc_heading_with_cdata_terminator_exits_1(self, tmp_path):
        runner = CliRunner()
        evil_dc = tmp_path / "evil-DC.md"
        evil_dc.write_text("## bad]]>evil\n", encoding="utf-8")
        out_file = tmp_path / "out.xml"
        result = runner.invoke(
            exam,
            [
                "scaffold-xml",
                "--course", "CI0007",
                "--week", "11",
                "--dc", str(evil_dc),
                "--kind", "comprension",
                "--out", str(out_file),
            ],
        )
        assert result.exit_code == 1
        assert "]]>" in result.output

    def test_round_trip_strict_validation_via_cli(self, dc_file, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "out.xml"
        result = runner.invoke(
            exam,
            [
                "scaffold-xml",
                "--course", "CI0007",
                "--week", "11",
                "--dc", str(dc_file),
                "--kind", "practica",
                "--out", str(out_file),
            ],
        )
        assert result.exit_code == 0, result.output
        validate_result = runner.invoke(
            exam, ["validate", "--strict", str(out_file)]
        )
        assert validate_result.exit_code == 0, validate_result.output
