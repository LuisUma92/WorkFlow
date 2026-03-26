"""Tests for workflow.exercise.parser — exercise .tex file parser."""

import pytest

from workflow.exercise.parser import parse_exercise


# ── Fixtures: realistic exercise content ─────────────────────────────────


COMPLETE_EXERCISE = """\
% ---
% id: phys-gauss-001
% type: multichoice
% difficulty: medium
% taxonomy_level: Usar-Aplicar
% taxonomy_domain: Procedimiento Mental
% tags: [physics, electrostatics]
% concepts:
%   - 20260320-physics-gauss-law
% status: complete
% ---
\\ifthenelse{\\boolean{main}}{
  \\exa[1]{5}
}{
}
\\question{
  Given a sphere of radius $r$, find $\\vec{E}$.
  \\includegraphics[width=0.5\\textwidth]{img/gauss-sphere.pdf}
  \\begin{enumerate}[a)]
    \\qpart{\\pts{5} Determine $\\vec{E}$ inside.}{
      Use Gauss's law: $\\oint \\vec{E} \\cdot d\\vec{A} = \\frac{Q}{\\epsilon_0}$
    }
    \\qpart{\\rightoption \\pts{5} Determine $\\vec{E}$ outside.}{
      Apply $E = \\frac{Q}{4\\pi\\epsilon_0 r^2}$
    }
    \\qpart{\\pts{3} Sketch the field lines.}{
      Radial lines outward from center.
    }
  \\end{enumerate}
}{
  The key insight is spherical symmetry.
}
"""

MINIMAL_EXERCISE = """\
\\question{What is $2+2$?}{$4$}
"""

PLACEHOLDER_EXERCISE = """\
% ---
% id: placeholder-001
% type: essay
% difficulty: easy
% taxonomy_level: Recordar
% taxonomy_domain: Información
% ---
\\ifthenelse{\\boolean{main}}{
  \\exa[1]{1}
}{
}
\\question{...}{
}
"""

WITH_FEEDBACK = """\
% ---
% id: fb-001
% type: shortanswer
% difficulty: easy
% taxonomy_level: Recordar
% taxonomy_domain: Información
% ---
\\question{What is the SI unit of force?}{Newton}
\\qfeedback{The SI unit of force is the Newton (N), named after Isaac Newton.}
"""

WITH_DIAGRAM = """\
% ---
% id: diag-001
% type: multichoice
% difficulty: hard
% taxonomy_level: Análisis
% taxonomy_domain: Procedimiento Mental
% ---
\\question{
  Identify the circuit in \\qdiagram{circuit-rc-001}.
  \\begin{enumerate}[a)]
    \\qpart{\\rightoption RC circuit}{Correct, it has R and C.}
    \\qpart{RL circuit}{No, there is no inductor.}
  \\end{enumerate}
}{General notes.}
"""


# ── Tests ────────────────────────────────────────────────────────────────


class TestParseCompleteExercise:
    def test_metadata_parsed(self):
        result = parse_exercise(COMPLETE_EXERCISE, "/path/ex.tex")
        assert result.errors == ()
        ex = result.exercise
        assert ex is not None
        assert ex.metadata is not None
        assert ex.metadata.id == "phys-gauss-001"
        assert ex.metadata.type == "multichoice"
        assert ex.metadata.difficulty == "medium"
        assert ex.metadata.taxonomy_level == "Usar-Aplicar"
        assert "physics" in ex.metadata.tags

    def test_stem_extracted(self):
        result = parse_exercise(COMPLETE_EXERCISE)
        ex = result.exercise
        assert "find $\\vec{E}$" in ex.stem

    def test_solution_extracted(self):
        result = parse_exercise(COMPLETE_EXERCISE)
        ex = result.exercise
        assert "spherical symmetry" in ex.solution

    def test_options_extracted(self):
        result = parse_exercise(COMPLETE_EXERCISE)
        ex = result.exercise
        assert len(ex.options) == 3
        assert ex.options[0].label == "a"
        assert ex.options[1].label == "b"
        assert ex.options[2].label == "c"

    def test_correct_option_detected(self):
        result = parse_exercise(COMPLETE_EXERCISE)
        ex = result.exercise
        # Option b has \rightoption
        assert ex.options[0].is_correct is False
        assert ex.options[1].is_correct is True
        assert ex.options[2].is_correct is False

    def test_points_per_option(self):
        result = parse_exercise(COMPLETE_EXERCISE)
        ex = result.exercise
        assert ex.options[0].points == 5.0
        assert ex.options[1].points == 5.0
        assert ex.options[2].points == 3.0

    def test_image_refs_detected(self):
        result = parse_exercise(COMPLETE_EXERCISE)
        ex = result.exercise
        assert "img/gauss-sphere.pdf" in ex.image_refs

    def test_status_from_yaml(self):
        result = parse_exercise(COMPLETE_EXERCISE)
        assert result.exercise.status == "complete"

    def test_source_path_preserved(self):
        result = parse_exercise(COMPLETE_EXERCISE, "/path/to/ex.tex")
        assert result.source_path == "/path/to/ex.tex"

    def test_no_errors(self):
        result = parse_exercise(COMPLETE_EXERCISE)
        assert result.errors == ()


class TestParseMinimalExercise:
    def test_no_metadata_warning(self):
        result = parse_exercise(MINIMAL_EXERCISE)
        assert any("No YAML metadata" in w for w in result.warnings)

    def test_stem_and_solution(self):
        result = parse_exercise(MINIMAL_EXERCISE)
        ex = result.exercise
        assert ex is not None
        assert "2+2" in ex.stem
        assert "4" in ex.solution

    def test_no_options(self):
        result = parse_exercise(MINIMAL_EXERCISE)
        assert result.exercise.options == ()

    def test_status_inferred_in_progress(self):
        result = parse_exercise(MINIMAL_EXERCISE)
        # Has stem and solution but no metadata → in_progress
        assert result.exercise.status == "in_progress"


class TestParsePlaceholder:
    def test_placeholder_status(self):
        result = parse_exercise(PLACEHOLDER_EXERCISE)
        ex = result.exercise
        assert ex is not None
        assert ex.status == "placeholder"


class TestParseFeedback:
    def test_feedback_extracted(self):
        result = parse_exercise(WITH_FEEDBACK)
        ex = result.exercise
        assert ex.feedback is not None
        assert "Newton" in ex.feedback

    def test_stem_content(self):
        result = parse_exercise(WITH_FEEDBACK)
        assert "SI unit of force" in result.exercise.stem


class TestParseDiagram:
    def test_diagram_id_extracted(self):
        result = parse_exercise(WITH_DIAGRAM)
        ex = result.exercise
        assert ex.diagram_id == "circuit-rc-001"

    def test_diagram_in_image_refs(self):
        result = parse_exercise(WITH_DIAGRAM)
        assert "circuit-rc-001" in result.exercise.image_refs

    def test_options_with_rightoption(self):
        result = parse_exercise(WITH_DIAGRAM)
        ex = result.exercise
        assert len(ex.options) == 2
        assert ex.options[0].is_correct is True
        assert ex.options[1].is_correct is False


class TestParseEdgeCases:
    def test_status_inferred_in_progress_no_solution(self):
        """Exercise with metadata but empty solution → in_progress."""
        text = (
            "% ---\n"
            "% id: edge-001\n"
            "% type: essay\n"
            "% difficulty: easy\n"
            "% taxonomy_level: Recordar\n"
            "% taxonomy_domain: Información\n"
            "% ---\n"
            "\\question{A real stem with content.}{\n}\n"
        )
        result = parse_exercise(text)
        assert result.exercise.status == "in_progress"

    def test_invalid_explicit_status_falls_back_to_infer(self):
        """Invalid status value in YAML falls back to inference."""
        text = (
            "% ---\n"
            "% id: edge-002\n"
            "% type: essay\n"
            "% difficulty: easy\n"
            "% taxonomy_level: Recordar\n"
            "% taxonomy_domain: Información\n"
            "% status: draft\n"
            "% ---\n"
            "\\question{Real stem.}{Real solution.}\n"
        )
        result = parse_exercise(text)
        assert result.exercise.status == "complete"  # inferred, not "draft"

    def test_exercise_number_extracted(self):
        """\\exa{5} extracts exercise number."""
        text = "\\exa{5}\\question{stem}{sol}\n"
        result = parse_exercise(text)
        assert result.exercise.exercise_number == (None, 5)

    def test_default_grade_from_standalone_pts(self):
        """Standalone \\pts{10} in stem sets default_grade."""
        text = "\\question{\\pts{10} What is $2+2$?}{$4$}\n"
        result = parse_exercise(text)
        assert result.exercise.default_grade == 10.0

    def test_metadata_validation_error_produces_warning(self):
        """Invalid metadata fields produce warnings, not errors."""
        text = (
            "% ---\n"
            "% id: warn-001\n"
            "% type: unknown_type\n"
            "% difficulty: easy\n"
            "% taxonomy_level: Recordar\n"
            "% taxonomy_domain: Información\n"
            "% ---\n"
            "\\question{Stem}{Solution}\n"
        )
        result = parse_exercise(text)
        assert result.exercise is not None
        assert any("Metadata:" in w for w in result.warnings)
        assert result.exercise.metadata is None  # validation failed


class TestParseErrors:
    def test_no_question_macro(self):
        result = parse_exercise("Just some random text, no exercise.")
        assert result.exercise is None
        assert any("\\question" in e for e in result.errors)

    def test_empty_file(self):
        result = parse_exercise("")
        assert result.exercise is None
        assert len(result.errors) > 0
