"""Tests for workflow.exercise.moodle — Moodle XML export.

TDD: these tests are written BEFORE the implementation.
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from xml.etree.ElementTree import fromstring

import pytest

from workflow.exercise.domain import ParsedExercise, ParsedOption
from workflow.validation.schemas import ExerciseMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_metadata(**kwargs) -> ExerciseMetadata:
    defaults = dict(
        id="exercise-001",
        type="multichoice",
        difficulty="medium",
        taxonomy_level="apply",
        taxonomy_domain="analysis",
        tags=["physics", "electrostatics"],
    )
    defaults.update(kwargs)
    return ExerciseMetadata(**defaults)


def _make_multichoice() -> ParsedExercise:
    options = (
        ParsedOption(
            label="a", instruction="Option A text", solution="Wrong", is_correct=False
        ),
        ParsedOption(
            label="b", instruction="Option B text", solution="Correct!", is_correct=True
        ),
        ParsedOption(
            label="c",
            instruction="Option C text",
            solution="Also wrong",
            is_correct=False,
        ),
    )
    return ParsedExercise(
        stem="What is the answer?",
        solution="The answer is B.",
        metadata=_make_metadata(type="multichoice"),
        options=options,
        default_grade=10.0,
    )


# ---------------------------------------------------------------------------
# Test 1: Multichoice question XML structure
# ---------------------------------------------------------------------------


def test_multichoice_xml_structure():
    from workflow.exercise.moodle import exercise_to_xml

    ex = _make_multichoice()
    elem = exercise_to_xml(ex)
    xml_str = _to_string(elem)

    assert elem.tag == "question"
    assert elem.attrib.get("type") == "multichoice"

    name_text = elem.find("name/text")
    assert name_text is not None
    assert name_text.text == "exercise-001"

    qtext = elem.find("questiontext")
    assert qtext is not None
    assert "What is the answer?" in _text_content(qtext)

    feedback = elem.find("generalfeedback")
    assert feedback is not None
    assert "The answer is B." in _text_content(feedback)

    answers = elem.findall("answer")
    assert len(answers) == 3

    correct = [a for a in answers if a.attrib.get("fraction") == "100"]
    wrong = [a for a in answers if a.attrib.get("fraction") == "0"]
    assert len(correct) == 1
    assert len(wrong) == 2

    grade = elem.find("defaultgrade")
    assert grade is not None
    assert grade.text == "10.0"

    tags_elem = elem.find("tags")
    assert tags_elem is not None
    tag_texts = [t.text for t in tags_elem.findall("tag/text")]
    assert "physics" in tag_texts
    assert "electrostatics" in tag_texts


# ---------------------------------------------------------------------------
# Test 2: Essay question
# ---------------------------------------------------------------------------


def test_essay_question():
    from workflow.exercise.moodle import exercise_to_xml

    ex = ParsedExercise(
        stem="Explain Gauss's law.",
        solution="See textbook chapter 3.",
        metadata=_make_metadata(type="essay"),
    )
    elem = exercise_to_xml(ex)

    assert elem.attrib.get("type") == "essay"
    answers = elem.findall("answer")
    assert len(answers) == 0


# ---------------------------------------------------------------------------
# Test 3: Shortanswer question
# ---------------------------------------------------------------------------


def test_shortanswer_question():
    from workflow.exercise.moodle import exercise_to_xml

    ex = ParsedExercise(
        stem="What is Newton's first law?",
        solution="An object at rest stays at rest.",
        metadata=_make_metadata(type="shortanswer"),
    )
    elem = exercise_to_xml(ex)

    assert elem.attrib.get("type") == "shortanswer"
    answers = elem.findall("answer")
    assert len(answers) == 1
    assert answers[0].attrib.get("fraction") == "100"
    assert "An object at rest stays at rest." in _text_content(answers[0])


# ---------------------------------------------------------------------------
# Test 4: Numerical question
# ---------------------------------------------------------------------------


def test_numerical_question():
    from workflow.exercise.moodle import exercise_to_xml

    ex = ParsedExercise(
        stem="What is the speed of light in m/s?",
        solution="299792458",
        metadata=_make_metadata(type="numerical"),
    )
    elem = exercise_to_xml(ex)

    assert elem.attrib.get("type") == "numerical"


# ---------------------------------------------------------------------------
# Test 5: Math delimiters converted in output
# ---------------------------------------------------------------------------


def test_math_delimiters_converted():
    from workflow.exercise.moodle import exercise_to_xml

    ex = ParsedExercise(
        stem="Find $x^2$ when $x=3$.",
        solution="The result is $9$.",
        metadata=_make_metadata(type="essay"),
    )
    elem = exercise_to_xml(ex)

    qtext_content = _text_content(elem.find("questiontext"))
    assert r"\(x^2\)" in qtext_content
    assert "$x^2$" not in qtext_content
    assert r"\(x=3\)" in qtext_content


# ---------------------------------------------------------------------------
# Test 6: Custom macros expanded in output
# ---------------------------------------------------------------------------


def test_custom_macros_expanded():
    from workflow.exercise.moodle import exercise_to_xml

    ex = ParsedExercise(
        stem=r"Find the field $\vc{E}$ at point P.",
        solution=r"Use Gauss with $\vc{B}$.",
        metadata=_make_metadata(type="essay"),
    )
    elem = exercise_to_xml(ex)

    qtext_content = _text_content(elem.find("questiontext"))
    assert r"\vc{E}" not in qtext_content
    assert r"\vec{\mathbf{E}}" in qtext_content


# ---------------------------------------------------------------------------
# Test 7: Tags from metadata
# ---------------------------------------------------------------------------


def test_tags_from_metadata():
    from workflow.exercise.moodle import exercise_to_xml

    ex = ParsedExercise(
        stem="Some question.",
        solution="Some answer.",
        metadata=_make_metadata(tags=["physics", "electrostatics"]),
    )
    elem = exercise_to_xml(ex)

    tags_elem = elem.find("tags")
    assert tags_elem is not None
    tag_texts = [t.text for t in tags_elem.findall("tag/text")]
    assert "physics" in tag_texts
    assert "electrostatics" in tag_texts


# ---------------------------------------------------------------------------
# Test 8: exercise_id as idnumber
# ---------------------------------------------------------------------------


def test_exercise_id_as_idnumber():
    from workflow.exercise.moodle import exercise_to_xml

    ex = ParsedExercise(
        stem="Some question.",
        solution="Some answer.",
        metadata=_make_metadata(id="phys-gauss-001"),
    )
    elem = exercise_to_xml(ex)

    idnumber = elem.find("idnumber")
    assert idnumber is not None
    assert idnumber.text == "phys-gauss-001"


# ---------------------------------------------------------------------------
# Test 9: Missing metadata graceful handling
# ---------------------------------------------------------------------------


def test_missing_metadata_graceful():
    from workflow.exercise.moodle import exercise_to_xml

    ex = ParsedExercise(
        stem="Some question.",
        solution="Some answer.",
        metadata=None,
    )
    # Should not raise; should produce valid XML
    elem = exercise_to_xml(ex)
    assert elem.tag == "question"

    name_text = elem.find("name/text")
    assert name_text is not None
    assert name_text.text is not None  # fallback name present


# ---------------------------------------------------------------------------
# Test 10: Multiple exercises → quiz XML
# ---------------------------------------------------------------------------


def test_exercises_to_quiz_xml():
    from workflow.exercise.moodle import exercises_to_quiz_xml

    ex1 = ParsedExercise(
        stem="Question one.",
        solution="Answer one.",
        metadata=_make_metadata(id="ex-001"),
    )
    ex2 = ParsedExercise(
        stem="Question two.",
        solution="Answer two.",
        metadata=_make_metadata(id="ex-002"),
    )
    xml_str = exercises_to_quiz_xml([ex1, ex2])

    assert xml_str.startswith("<?xml")
    root = fromstring(xml_str.split("?>", 1)[1].strip())
    assert root.tag == "quiz"
    questions = root.findall("question")
    assert len(questions) == 2


# ---------------------------------------------------------------------------
# Test 11: XML special characters escaped
# ---------------------------------------------------------------------------


def test_xml_special_chars_escaped():
    from workflow.exercise.moodle import exercise_to_xml

    ex = ParsedExercise(
        stem="Is a < b & c > d?",
        solution="Yes & No.",
        metadata=_make_metadata(type="essay"),
    )
    # Should not raise; tostring must produce valid XML
    elem = exercise_to_xml(ex)
    from xml.etree.ElementTree import tostring

    xml_bytes = tostring(elem, encoding="unicode")
    # Re-parse to confirm valid XML
    reparsed = fromstring(xml_bytes)
    assert reparsed.tag == "question"


# ---------------------------------------------------------------------------
# Test 12: Feedback from \qfeedback
# ---------------------------------------------------------------------------


def test_feedback_field():
    from workflow.exercise.moodle import exercise_to_xml

    ex = ParsedExercise(
        stem="Some question.",
        solution="Ignored solution.",
        feedback="This is the actual feedback.",
        metadata=_make_metadata(type="essay"),
    )
    elem = exercise_to_xml(ex)

    gf = elem.find("generalfeedback")
    assert gf is not None
    assert "This is the actual feedback." in _text_content(gf)


# ---------------------------------------------------------------------------
# Test 13: Image embedding
# ---------------------------------------------------------------------------


def test_image_embedding():
    from workflow.exercise.moodle import exercise_to_xml

    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = Path(tmpdir) / "test-image.png"
        # Minimal 1x1 PNG (valid PNG bytes)
        img_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        img_path.write_bytes(img_bytes)

        ex = ParsedExercise(
            stem=r"\includegraphics{test-image.png} What do you see?",
            solution="An image.",
            metadata=_make_metadata(type="essay"),
            image_refs=(str(img_path),),
        )
        elem = exercise_to_xml(ex, source_dir=Path(tmpdir))

        # Find <file> element somewhere in the tree
        file_elems = elem.findall(".//file")
        assert len(file_elems) >= 1
        file_elem = file_elems[0]
        assert file_elem.attrib.get("encoding") == "base64"
        assert file_elem.attrib.get("name") == "test-image.png"
        # Verify base64 content is valid
        decoded = base64.b64decode(file_elem.text)
        assert decoded == img_bytes


# ---------------------------------------------------------------------------
# Test 14: Truefalse question type
# ---------------------------------------------------------------------------


def test_truefalse_question():
    from workflow.exercise.moodle import exercise_to_xml

    options = (
        ParsedOption(label="a", instruction="True", solution="", is_correct=True),
        ParsedOption(label="b", instruction="False", solution="", is_correct=False),
    )
    ex = ParsedExercise(
        stem="The speed of light is constant.",
        solution="Yes, by the postulates of special relativity.",
        metadata=_make_metadata(type="truefalse"),
        options=options,
    )
    elem = exercise_to_xml(ex)

    assert elem.tag == "question"
    assert elem.attrib.get("type") == "truefalse"


# ---------------------------------------------------------------------------
# Test 15: No correct answer — all fractions are "0", no crash
# ---------------------------------------------------------------------------


def test_no_correct_answer_produces_valid_xml():
    from workflow.exercise.moodle import exercise_to_xml
    from xml.etree.ElementTree import tostring

    options = (
        ParsedOption(label="a", instruction="Wrong A", solution="", is_correct=False),
        ParsedOption(label="b", instruction="Wrong B", solution="", is_correct=False),
        ParsedOption(label="c", instruction="Wrong C", solution="", is_correct=False),
    )
    ex = ParsedExercise(
        stem="Pick the correct answer.",
        solution="There is none.",
        metadata=_make_metadata(type="multichoice"),
        options=options,
    )
    # Must not raise
    elem = exercise_to_xml(ex)
    xml_bytes = tostring(elem, encoding="unicode")

    answers = elem.findall("answer")
    assert len(answers) == 3
    for answer in answers:
        assert answer.attrib.get("fraction") == "0"


# ---------------------------------------------------------------------------
# Test 16: Path traversal image reference is skipped (security)
# ---------------------------------------------------------------------------


def test_path_traversal_image_skipped(tmp_path):
    from workflow.exercise.moodle import exercise_to_xml
    from xml.etree.ElementTree import tostring

    ex = ParsedExercise(
        stem=r"\includegraphics{../../../etc/passwd} What do you see?",
        solution="Nothing safe.",
        metadata=_make_metadata(type="essay"),
        image_refs=("../../../etc/passwd",),
    )
    elem = exercise_to_xml(ex, source_dir=tmp_path)

    # No <file> elements must embed the malicious path (traversal guard applied)
    file_elems = elem.findall(".//file")
    assert len(file_elems) == 0, "Traversal image must not be embedded as a <file>"
    for fe in file_elems:
        assert "passwd" not in (fe.attrib.get("name", "") + (fe.text or ""))


# ---------------------------------------------------------------------------
# Internal helpers (not testing — just utilities for the tests)
# ---------------------------------------------------------------------------


def _to_string(elem) -> str:
    from xml.etree.ElementTree import tostring

    return tostring(elem, encoding="unicode")


def _text_content(elem) -> str:
    """Return all text content from an element and its children."""
    if elem is None:
        return ""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(_text_content(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)
