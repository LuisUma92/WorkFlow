"""TDD tests for workflow exam scaffold-xml command.

Covers:
- parse_blocks_spec: valid + invalid inputs
- build_moodle_quiz_xml: structure, CDATA, penalty/grade, block comments, distinct distractors
- CLI command: --json flag, exit codes, file output
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from xml.etree import ElementTree as ET

import pytest
from click.testing import CliRunner

from workflow.exam.scaffold import parse_blocks_spec, build_moodle_quiz_xml
from workflow.exam.cli import exam


# ---------------------------------------------------------------------------
# parse_blocks_spec
# ---------------------------------------------------------------------------


class TestParseBlocksSpec:
    def test_single_block(self):
        result = parse_blocks_spec("Recordar:4")
        assert result == [("Recordar", 4)]

    def test_multiple_blocks(self):
        result = parse_blocks_spec("Recordar:4,Comprender:4,Analizar:4")
        assert result == [("Recordar", 4), ("Comprender", 4), ("Analizar", 4)]

    def test_blocks_with_hyphens(self):
        result = parse_blocks_spec("Analizar-info:4,Usar-Aplicar:4")
        assert result == [("Analizar-info", 4), ("Usar-Aplicar", 4)]

    def test_invalid_missing_count(self):
        with pytest.raises(ValueError, match="Invalid block spec"):
            parse_blocks_spec("Recordar")

    def test_invalid_zero_count(self):
        with pytest.raises(ValueError, match="count must be >= 1"):
            parse_blocks_spec("Recordar:0")

    def test_invalid_negative_count(self):
        with pytest.raises(ValueError, match="count must be >= 1"):
            parse_blocks_spec("Recordar:-1")

    def test_invalid_non_integer_count(self):
        with pytest.raises(ValueError, match="Invalid block spec"):
            parse_blocks_spec("Recordar:abc")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="--blocks cannot be empty"):
            parse_blocks_spec("")

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="Invalid block spec"):
            parse_blocks_spec(":4")

    def test_whitespace_stripped(self):
        result = parse_blocks_spec("Recordar : 4 , Comprender : 3")
        assert result == [("Recordar", 4), ("Comprender", 3)]


# ---------------------------------------------------------------------------
# build_moodle_quiz_xml
# ---------------------------------------------------------------------------

_BLOCKS_5 = [
    ("Recordar", 4),
    ("Comprender", 4),
    ("Analizar-info", 4),
    ("Analizar-proc", 4),
    ("Usar-Aplicar", 4),
]

_COMMON_KWARGS = dict(
    course="FS0211",
    cycle="2026C1",
    group="001",
    label="PC04",
    category="Tema #06",
    blocks=_BLOCKS_5,
    question_prefix="",
    penalty=0.25,
    grade=1,
)


class TestBuildMoodleQuizXml:
    def test_basic_returns_string(self):
        xml_text = build_moodle_quiz_xml(**_COMMON_KWARGS)
        assert isinstance(xml_text, str)
        assert xml_text.startswith("<?xml")

    def test_total_question_count(self):
        """5 blocks x 4 = 20 multichoice + 1 category = 21 questions total."""
        xml_text = build_moodle_quiz_xml(**_COMMON_KWARGS)
        root = ET.fromstring(xml_text.split("\n", 1)[1])  # strip xml declaration
        questions = root.findall("question")
        assert len(questions) == 21  # 1 category + 20 multichoice

    def test_first_question_is_category(self):
        xml_text = build_moodle_quiz_xml(**_COMMON_KWARGS)
        root = ET.fromstring(xml_text.split("\n", 1)[1])
        first = root.findall("question")[0]
        assert first.get("type") == "category"

    def test_multichoice_question_count(self):
        xml_text = build_moodle_quiz_xml(**_COMMON_KWARGS)
        root = ET.fromstring(xml_text.split("\n", 1)[1])
        mc_questions = [q for q in root.findall("question") if q.get("type") == "multichoice"]
        assert len(mc_questions) == 20

    def test_penalty_reflected(self):
        xml_text = build_moodle_quiz_xml(**{**_COMMON_KWARGS, "penalty": 0.33})
        root = ET.fromstring(xml_text.split("\n", 1)[1])
        mc_questions = [q for q in root.findall("question") if q.get("type") == "multichoice"]
        for q in mc_questions:
            penalty_elem = q.find("penalty")
            assert penalty_elem is not None
            assert float(penalty_elem.text) == pytest.approx(0.33)

    def test_grade_reflected(self):
        xml_text = build_moodle_quiz_xml(**{**_COMMON_KWARGS, "grade": 2})
        root = ET.fromstring(xml_text.split("\n", 1)[1])
        mc_questions = [q for q in root.findall("question") if q.get("type") == "multichoice"]
        for q in mc_questions:
            grade_elem = q.find("defaultgrade")
            assert grade_elem is not None
            assert int(grade_elem.text) == 2

    def test_cdata_in_questiontext(self):
        xml_text = build_moodle_quiz_xml(**_COMMON_KWARGS)
        # CDATA sections appear as literal strings in the serialized XML
        assert "<![CDATA[TODO]]>" in xml_text

    def test_cdata_in_answers(self):
        xml_text = build_moodle_quiz_xml(**_COMMON_KWARGS)
        # Count occurrences: each question has 4 answers + 1 questiontext + feedback
        assert xml_text.count("<![CDATA[TODO]]>") >= 20 * 5  # conservative lower bound

    def test_block_comments_present(self):
        xml_text = build_moodle_quiz_xml(**_COMMON_KWARGS)
        for block_name, _ in _BLOCKS_5:
            assert f"<!-- {block_name} -->" in xml_text

    def test_distinct_distractor_labels(self):
        xml_text = build_moodle_quiz_xml(**_COMMON_KWARGS)
        # Each multichoice question should have Answer 1, 2, 3, 4 within it
        assert "Answer 1" in xml_text
        assert "Answer 2" in xml_text
        assert "Answer 3" in xml_text
        assert "Answer 4" in xml_text

    def test_no_duplicate_distractors_within_question(self):
        """Within each <question>, the 4 answer labels must be distinct."""
        xml_text = build_moodle_quiz_xml(**_COMMON_KWARGS)
        root = ET.fromstring(xml_text.split("\n", 1)[1])
        mc_questions = [q for q in root.findall("question") if q.get("type") == "multichoice"]
        for q in mc_questions:
            labels = []
            for answer in q.findall("answer"):
                text_elem = answer.find("text")
                if text_elem is not None:
                    labels.append(text_elem.text)
            # After CDATA stripping, labels should be distinct
            assert len(labels) == len(set(labels)), f"Duplicate distractor labels: {labels}"

    def test_valid_xml_parse(self):
        """Output must parse without error."""
        xml_text = build_moodle_quiz_xml(**_COMMON_KWARGS)
        # Use ElementTree as fallback validation
        # Strip the XML declaration for fromstring
        body = xml_text.split("\n", 1)[1] if xml_text.startswith("<?xml") else xml_text
        root = ET.fromstring(body)
        assert root.tag == "quiz"

    def test_single_block(self):
        xml_text = build_moodle_quiz_xml(
            **{**_COMMON_KWARGS, "blocks": [("Solo", 3)]}
        )
        root = ET.fromstring(xml_text.split("\n", 1)[1])
        questions = root.findall("question")
        assert len(questions) == 4  # 1 category + 3

    def test_question_prefix_in_name(self):
        xml_text = build_moodle_quiz_xml(**{**_COMMON_KWARGS, "question_prefix": "Leyes"})
        assert "Leyes" in xml_text

    def test_answernumbering_present(self):
        xml_text = build_moodle_quiz_xml(**_COMMON_KWARGS)
        assert "answernumbering" in xml_text

    def test_shuffleanswers_present(self):
        xml_text = build_moodle_quiz_xml(**_COMMON_KWARGS)
        assert "shuffleanswers" in xml_text


# ---------------------------------------------------------------------------
# xmllint validation (optional — skips if not installed)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    subprocess.run(["which", "xmllint"], capture_output=True).returncode != 0,
    reason="xmllint not installed",
)
def test_xmllint_validation():
    xml_text = build_moodle_quiz_xml(**_COMMON_KWARGS)
    with tempfile.NamedTemporaryFile(suffix=".xml", mode="w", delete=False) as f:
        f.write(xml_text)
        tmp_path = f.name
    result = subprocess.run(["xmllint", "--noout", tmp_path], capture_output=True)
    assert result.returncode == 0, f"xmllint failed: {result.stderr.decode()}"


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


_BASE_CLI_ARGS = [
    "scaffold-xml",
    "--course", "FS0211",
    "--cycle", "2026C1",
    "--group", "001",
    "--label", "PC04",
    "--category", "Tema #06",
    "--blocks", "Recordar:4,Comprender:4,Analizar-info:4,Analizar-proc:4,Usar-Aplicar:4",
]


class TestScaffoldXmlCLI:
    def test_writes_xml_file(self, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "quiz.xml"
        result = runner.invoke(exam, _BASE_CLI_ARGS + ["--out", str(out_file)])
        assert result.exit_code == 0, result.output
        assert out_file.exists()
        content = out_file.read_text()
        assert "<?xml" in content

    def test_stdout_message(self, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "quiz.xml"
        result = runner.invoke(exam, _BASE_CLI_ARGS + ["--out", str(out_file)])
        assert result.exit_code == 0
        assert "21 questions" in result.output
        assert "1 category" in result.output

    def test_json_output(self, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "quiz.xml"
        result = runner.invoke(exam, _BASE_CLI_ARGS + ["--out", str(out_file), "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["questions"] == 21
        assert data["valid_xml"] is True
        assert len(data["blocks"]) == 5
        assert data["blocks"][0] == {"name": "Recordar", "count": 4}
        assert "path" in data

    def test_invalid_blocks_exits_1(self, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "quiz.xml"
        result = runner.invoke(
            exam,
            ["scaffold-xml", "--course", "X", "--cycle", "Y", "--group", "1",
             "--label", "L", "--category", "C", "--blocks", "Bad-spec",
             "--out", str(out_file)],
        )
        assert result.exit_code == 1

    def test_penalty_and_grade_options(self, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "quiz.xml"
        result = runner.invoke(
            exam,
            _BASE_CLI_ARGS + ["--penalty", "0.33", "--grade", "2", "--out", str(out_file)],
        )
        assert result.exit_code == 0
        content = out_file.read_text()
        assert "0.33" in content
        # grade=2 in defaultgrade
        assert "<defaultgrade>2</defaultgrade>" in content

    def test_question_prefix_option(self, tmp_path):
        runner = CliRunner()
        out_file = tmp_path / "quiz.xml"
        result = runner.invoke(
            exam,
            _BASE_CLI_ARGS + ["--question-prefix", "Leyes", "--out", str(out_file)],
        )
        assert result.exit_code == 0
        content = out_file.read_text()
        assert "Leyes" in content

    def test_unwritable_path_exits_1(self):
        runner = CliRunner()
        result = runner.invoke(
            exam,
            _BASE_CLI_ARGS + ["--out", "/nonexistent_dir/quiz.xml"],
        )
        assert result.exit_code == 1

    def test_xmllint_passes(self, tmp_path):
        if subprocess.run(["which", "xmllint"], capture_output=True).returncode != 0:
            pytest.skip("xmllint not installed")
        runner = CliRunner()
        out_file = tmp_path / "quiz.xml"
        runner.invoke(exam, _BASE_CLI_ARGS + ["--out", str(out_file)])
        result = subprocess.run(["xmllint", "--noout", str(out_file)], capture_output=True)
        assert result.returncode == 0
