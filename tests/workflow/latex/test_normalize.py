"""Tests for workflow.latex.normalize — TDD RED phase.

All tests should FAIL before normalize.py is implemented.
"""

from __future__ import annotations

import pytest
from workflow.latex.normalize import (
    MacroRule,
    DEFAULT_MACRO_MAP,
    normalize,
    convert_math_delimiters,
    _expand_one_macro,
)


# ---------------------------------------------------------------------------
# MacroRule and _expand_one_macro
# ---------------------------------------------------------------------------


class TestMacroRuleExpansion:
    r"""Individual macro expansions via _expand_one_macro."""

    def test_vc_single_arg(self):
        result = _expand_one_macro(r"\vc{E}", r"\vc", DEFAULT_MACRO_MAP[r"\vc"])
        assert result == r"\vec{\mathbf{E}}"

    def test_scrp_single_arg(self):
        result = _expand_one_macro(
            r"\scrp{enc}", r"\scrp", DEFAULT_MACRO_MAP[r"\scrp"]
        )
        assert result == r"_{\mbox{\scriptsize{enc}}}"

    def test_nc_two_args(self):
        result = _expand_one_macro(r"\nc{2}{H}", r"\nc", DEFAULT_MACRO_MAP[r"\nc"])
        assert result == r"$^{2}$H"

    def test_ncm_two_args(self):
        result = _expand_one_macro(r"\ncm{2}{H}", r"\ncm", DEFAULT_MACRO_MAP[r"\ncm"])
        assert result == r"^{2}\text{H}"

    def test_then_zero_args(self):
        result = _expand_one_macro(r"x \then y", r"\then", DEFAULT_MACRO_MAP[r"\then"])
        assert result == r"x = y"

    def test_pts_one_arg(self):
        result = _expand_one_macro(r"\pts{5}", r"\pts", DEFAULT_MACRO_MAP[r"\pts"])
        assert result == "(5 pts.)"

    def test_pts_optional_arg_skipped(self):
        result = _expand_one_macro(
            r"\pts[add]{5}", r"\pts", DEFAULT_MACRO_MAP[r"\pts"]
        )
        assert result == "(5 pts.)"

    def test_upt_zero_args(self):
        result = _expand_one_macro(r"\upt", r"\upt", DEFAULT_MACRO_MAP[r"\upt"])
        assert result == "(1 pt.)"

    def test_uptcu_zero_args(self):
        result = _expand_one_macro(
            r"\uptcu", r"\uptcu", DEFAULT_MACRO_MAP[r"\uptcu"]
        )
        assert result == "(1 pt. c/u.)"

    def test_ptscu_one_arg(self):
        result = _expand_one_macro(
            r"\ptscu{3}", r"\ptscu", DEFAULT_MACRO_MAP[r"\ptscu"]
        )
        assert result == "(3 pts. c/u.)"

    def test_rightoption_zero_args(self):
        result = _expand_one_macro(
            r"text \rightoption more",
            r"\rightoption",
            DEFAULT_MACRO_MAP[r"\rightoption"],
        )
        assert result == "text  more"

    def test_consolidatePoints_one_arg(self):
        result = _expand_one_macro(
            r"\consolidatePoints{label}",
            r"\consolidatePoints",
            DEFAULT_MACRO_MAP[r"\consolidatePoints"],
        )
        assert result == ""

    def test_inputline_zero_args(self):
        result = _expand_one_macro(
            r"\inputline", r"\inputline", DEFAULT_MACRO_MAP[r"\inputline"]
        )
        assert result == "______"

    def test_completeline_one_arg(self):
        result = _expand_one_macro(
            r"\completeline{answer}",
            r"\completeline",
            DEFAULT_MACRO_MAP[r"\completeline"],
        )
        assert result == "answer"

    def test_textcolor_strips_color(self):
        result = _expand_one_macro(
            r"\textcolor{red}{important}",
            r"\textcolor",
            DEFAULT_MACRO_MAP[r"\textcolor"],
        )
        assert result == "important"

    def test_multiple_occurrences(self):
        result = _expand_one_macro(
            r"\inputline and \inputline",
            r"\inputline",
            DEFAULT_MACRO_MAP[r"\inputline"],
        )
        assert result == "______ and ______"

    def test_macro_at_end_of_string(self):
        result = _expand_one_macro(
            r"end \upt",
            r"\upt",
            DEFAULT_MACRO_MAP[r"\upt"],
        )
        assert result == "end (1 pt.)"

    def test_unknown_macro_left_unchanged(self):
        # _expand_one_macro only affects the given macro; unknown macros untouched
        text = r"\unknown{arg} \vc{A}"
        result = _expand_one_macro(text, r"\vc", DEFAULT_MACRO_MAP[r"\vc"])
        assert r"\unknown{arg}" in result
        assert r"\vec{\mathbf{A}}" in result


# ---------------------------------------------------------------------------
# convert_math_delimiters
# ---------------------------------------------------------------------------


class TestConvertMathDelimiters:
    def test_single_dollar_to_paren(self):
        assert convert_math_delimiters(r"$x^2$") == r"\(x^2\)"

    def test_double_dollar_to_bracket(self):
        assert convert_math_delimiters(r"$$E=mc^2$$") == r"\[E=mc^2\]"

    def test_already_paren_unchanged(self):
        assert convert_math_delimiters(r"\(x\)") == r"\(x\)"

    def test_already_bracket_unchanged(self):
        assert convert_math_delimiters(r"\[x\]") == r"\[x\]"

    def test_mixed(self):
        result = convert_math_delimiters(r"$a$ and $$b$$")
        assert result == r"\(a\) and \[b\]"

    def test_double_dollar_before_single(self):
        # Ensure $$...$$ is not consumed by two $...$ passes
        result = convert_math_delimiters(r"$$hello$$")
        assert result == r"\[hello\]"

    def test_escaped_dollar_not_converted(self):
        # \$ should not be treated as a math delimiter
        text = r"Cost is \$5 and \$10"
        result = convert_math_delimiters(text)
        assert result == text  # no change


# ---------------------------------------------------------------------------
# symbf replacement
# ---------------------------------------------------------------------------


class TestSymbfReplacement:
    def test_symbf_becomes_mathbf(self):
        result = normalize(r"\symbf{E}")
        assert result == r"\mathbf{E}"

    def test_symbf_nested(self):
        result = normalize(r"\vc{\symbf{A}}")
        # After normalize: \vc expands, \symbf inside may expand too
        assert r"\mathbf" in result


# ---------------------------------------------------------------------------
# Full normalize function
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_empty_input(self):
        assert normalize("") == ""

    def test_combines_macro_and_math(self):
        result = normalize(r"$\vc{E}$")
        assert result == r"\(\vec{\mathbf{E}}\)"

    def test_nested_macros_expand(self):
        # \vc{\scrp{x}} should expand both
        result = normalize(r"\vc{\scrp{x}}")
        assert r"\vec" in result
        assert r"\scriptsize" in result

    def test_standard_latex_unchanged(self):
        text = r"\frac{1}{2}"
        assert normalize(text) == text

    def test_vec_unchanged(self):
        text = r"\vec{E}"
        assert normalize(text) == text

    def test_enumerate_unchanged(self):
        text = r"\begin{enumerate}"
        assert normalize(text) == text

    def test_pts_in_context(self):
        result = normalize(r"Question worth \pts{5}.")
        assert "(5 pts.)" in result

    def test_math_delimiter_in_normalize(self):
        result = normalize(r"$$E=mc^2$$")
        assert result == r"\[E=mc^2\]"

    def test_multiple_macros_same_type(self):
        result = normalize(r"\inputline \inputline")
        assert result == "______ ______"

    def test_upt_optional_arg_skipped(self):
        # \upt has has_optional=True but zero required args; [opt] should be consumed
        result = normalize(r"\upt[note]")
        assert result == "(1 pt.)"
