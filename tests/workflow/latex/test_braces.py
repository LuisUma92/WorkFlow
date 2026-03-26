"""Tests for workflow.latex.braces — brace-counting LaTeX extraction."""

import pytest

from workflow.latex.braces import extract_brace_arg, extract_macro_args


class TestExtractBraceArg:
    """extract_brace_arg(text, start) → (content, end_position)."""

    def test_simple_braces(self):
        text = r"\cmd{hello}"
        content, end = extract_brace_arg(text, 4)
        assert content == "hello"
        assert end == 11  # position after closing }

    def test_nested_braces(self):
        text = r"\cmd{a{b{c}d}e}"
        content, end = extract_brace_arg(text, 4)
        assert content == "a{b{c}d}e"

    def test_math_with_braces(self):
        text = r"\cmd{$\frac{a}{b}$ end}"
        content, end = extract_brace_arg(text, 4)
        assert content == r"$\frac{a}{b}$ end"

    def test_escaped_braces_ignored(self):
        text = r"\cmd{a \{ b \} c}"
        content, end = extract_brace_arg(text, 4)
        assert content == r"a \{ b \} c"

    def test_multiline_content(self):
        text = "\\cmd{\n  line1\n  line2\n}"
        content, end = extract_brace_arg(text, 4)
        assert content == "\n  line1\n  line2\n"

    def test_start_before_brace(self):
        """Start position can be before the opening brace — scanner finds it."""
        text = r"\question{stem text}"
        content, end = extract_brace_arg(text, 0)
        assert content == "stem text"

    def test_empty_braces(self):
        text = r"\cmd{}"
        content, end = extract_brace_arg(text, 4)
        assert content == ""

    def test_deeply_nested(self):
        text = r"\cmd{a{b{c{d{e}}}}}"
        content, end = extract_brace_arg(text, 4)
        assert content == "a{b{c{d{e}}}}"

    def test_no_opening_brace_raises(self):
        text = "no braces here"
        with pytest.raises(ValueError, match="No opening brace"):
            extract_brace_arg(text, 0)

    def test_unmatched_brace_raises(self):
        text = r"\cmd{unclosed"
        with pytest.raises(ValueError, match="Unmatched brace"):
            extract_brace_arg(text, 4)

    def test_trailing_backslash_raises(self):
        """Backslash at end of string inside braces should raise ValueError."""
        text = r"\cmd{a\\"  # content ends with backslash, no closing brace
        with pytest.raises(ValueError, match="Unmatched brace"):
            extract_brace_arg(text, 4)

    def test_malformed_macro_skipped_silently(self):
        """extract_macro_args skips macros with unclosed brace args."""
        from workflow.latex.braces import extract_macro_args

        text = r"\pts{unclosed"
        matches = extract_macro_args(text, "pts", 1)
        assert matches == []

    def test_latex_environment_inside(self):
        text = r"\cmd{\begin{enumerate} \item x \end{enumerate}}"
        content, end = extract_brace_arg(text, 4)
        assert content == r"\begin{enumerate} \item x \end{enumerate}"

    def test_consecutive_extractions(self):
        """Extract two arguments from \\question{stem}{solution}."""
        text = r"\question{the stem}{the solution}"
        arg1, pos1 = extract_brace_arg(text, 0)
        assert arg1 == "the stem"
        arg2, pos2 = extract_brace_arg(text, pos1)
        assert arg2 == "the solution"


class TestExtractMacroArgs:
    """extract_macro_args(text, macro_name, n_args) → list of matches."""

    def test_single_arg_macro(self):
        text = r"Some text \pts{5} more text"
        matches = extract_macro_args(text, "pts", 1)
        assert len(matches) == 1
        assert matches[0].args == ("5",)

    def test_two_arg_macro(self):
        text = r"\question{stem text}{solution text}"
        matches = extract_macro_args(text, "question", 2)
        assert len(matches) == 1
        assert matches[0].args == ("stem text", "solution text")

    def test_multiple_occurrences(self):
        text = r"\pts{3} blah \pts{5} blah \pts{2}"
        matches = extract_macro_args(text, "pts", 1)
        assert len(matches) == 3
        assert [m.args[0] for m in matches] == ["3", "5", "2"]

    def test_nested_content_in_args(self):
        text = r"\question{$\frac{1}{2}$ is half}{use $\frac{a}{b}$}"
        matches = extract_macro_args(text, "question", 2)
        assert len(matches) == 1
        assert matches[0].args[0] == r"$\frac{1}{2}$ is half"
        assert matches[0].args[1] == r"use $\frac{a}{b}$"

    def test_no_matches(self):
        text = r"no macros here"
        matches = extract_macro_args(text, "question", 2)
        assert matches == []

    def test_macro_match_positions(self):
        """MacroMatch.start and .end report correct positions."""
        text = r"abc \pts{5} xyz"
        matches = extract_macro_args(text, "pts", 1)
        assert len(matches) == 1
        assert matches[0].start == 4  # position of \
        assert matches[0].end == 11  # position after }

    def test_macro_not_confused_with_prefix(self):
        """\\question should not match \\questiontext."""
        text = r"\questiontext{blah} \question{s}{sol}"
        matches = extract_macro_args(text, "question", 2)
        assert len(matches) == 1
        assert matches[0].args == ("s", "sol")

    def test_zero_arg_macro(self):
        text = r"before \rightoption after"
        matches = extract_macro_args(text, "rightoption", 0)
        assert len(matches) == 1
        assert matches[0].args == ()

    def test_real_exercise_pattern(self):
        text = (
            "\\question{\n"
            "  Find the electric field.\n"
            "  \\begin{enumerate}[a)]\n"
            "    \\qpart{\\pts{5} Part A}{Solution A}\n"
            "    \\qpart{\\rightoption \\pts{5} Part B}{Solution B}\n"
            "  \\end{enumerate}\n"
            "}{\n"
            "  General solution notes.\n"
            "}"
        )
        matches = extract_macro_args(text, "question", 2)
        assert len(matches) == 1
        stem, solution = matches[0].args
        assert "Find the electric field." in stem
        assert "General solution notes." in solution

        # Now extract qparts from within the stem
        qparts = extract_macro_args(stem, "qpart", 2)
        assert len(qparts) == 2
        assert "Part A" in qparts[0].args[0]
        assert "Solution A" in qparts[0].args[1]
        assert "Part B" in qparts[1].args[0]
