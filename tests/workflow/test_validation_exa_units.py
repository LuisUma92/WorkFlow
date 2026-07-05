"""Tests for `\\si`/`\\SI` unit lint against SetUnits.sty declarations.

Covers Phase 2a of tasks/plans/2026-07-03-freeze-window-features-plan.md
(audit slug #5 "\\exa lint-units" / raw gap-log line 98 "exercise
lint-units <file>"): warn (never error, Bundle A precedent) when an exercise
`.tex` body uses a `\\si{...}`/`\\SI{n}{...}` unit macro that is neither a
siunitx built-in nor declared via `\\DeclareSIUnit\\<name>{...}` in
`share/latex/sty/SetUnits.sty`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from workflow.latex.units import (
    LintIssue,
    find_undeclared_units,
    format_unit_warnings,
    load_declared_units,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SET_UNITS_STY = _REPO_ROOT / "share" / "latex" / "sty" / "SetUnits.sty"


class TestLoadDeclaredUnits:
    def test_parses_all_declared_units_from_real_sty(self):
        declared = load_declared_units(_SET_UNITS_STY)
        # Confirmed at least these custom units at SetUnits.sty:17-40
        for name in ("barn", "fbarn", "ace", "vel", "denV", "denA", "denL",
                     "angvel", "angace", "psi"):
            assert name in declared
        assert len(declared) >= 20

    def test_missing_file_returns_empty_set_not_raise(self, tmp_path):
        declared = load_declared_units(tmp_path / "does-not-exist.sty")
        assert declared == frozenset()

    def test_parses_from_minimal_fixture(self, tmp_path):
        sty = tmp_path / "fixture.sty"
        sty.write_text(
            "\\DeclareSIUnit\\widget{w}\n"
            "\\DeclareSIUnit\\gadget{g}\n"
        )
        declared = load_declared_units(sty)
        assert declared == frozenset({"widget", "gadget"})


class TestFindUndeclaredUnits:
    def test_builtin_unit_is_not_flagged(self):
        issues = find_undeclared_units(r"\si{\meter}", declared=frozenset())
        assert issues == []

    def test_declared_custom_unit_is_not_flagged(self):
        issues = find_undeclared_units(
            r"\si{\barn}", declared=frozenset({"barn"})
        )
        assert issues == []

    def test_undeclared_custom_unit_is_flagged(self):
        issues = find_undeclared_units(
            r"\si{\barn}", declared=frozenset()
        )
        assert len(issues) == 1
        assert issues[0].unit_token == "barn"

    def test_two_arg_si_form_checked(self):
        issues = find_undeclared_units(
            r"\SI{5}{\foobarunit}", declared=frozenset()
        )
        assert len(issues) == 1
        assert issues[0].unit_token == "foobarunit"

    def test_prefix_and_operator_macros_ignored(self):
        # \kilo (prefix) and \per (operator) are never unit names themselves.
        issues = find_undeclared_units(
            r"\si{\kilo\gram\per\second}", declared=frozenset()
        )
        assert issues == []

    def test_line_number_reported(self):
        text = "line one\nline two\n\\si{\\foobarunit}\n"
        issues = find_undeclared_units(text, declared=frozenset())
        assert len(issues) == 1
        assert issues[0].line == 3

    def test_close_match_suggestion(self):
        issues = find_undeclared_units(
            r"\si{\bran}", declared=frozenset({"barn"})
        )
        assert len(issues) == 1
        assert issues[0].suggestion == "barn"

    def test_no_suggestion_when_no_close_match(self):
        issues = find_undeclared_units(
            r"\si{\zzzznope}", declared=frozenset({"barn"})
        )
        assert len(issues) == 1
        assert issues[0].suggestion is None

    def test_multiple_calls_all_scanned(self):
        text = r"\si{\meter} and \si{\foobarunit} and \SI{2}{\bazunit}"
        issues = find_undeclared_units(text, declared=frozenset())
        tokens = {issue.unit_token for issue in issues}
        assert tokens == {"foobarunit", "bazunit"}

    def test_kilogram_builtin_not_flagged(self):
        # Real siunitx builtin — was missing from _SIUNITX_BUILTIN_UNITS.
        issues = find_undeclared_units(r"\si{\kilogram}", declared=frozenset())
        assert issues == []

    def test_degreecelsius_builtin_not_flagged(self):
        # Real siunitx builtin (correct spelling). SetUnits.sty:26 only
        # declares the typo'd \degreeCelsuis — \degreeCelsius must still
        # resolve via the builtin set, not via the .sty declaration.
        issues = find_undeclared_units(r"\si{\degreeCelsius}", declared=frozenset())
        assert issues == []

    def test_still_unknown_unit_still_warns(self):
        # Sanity check: completing the builtin set must not make the lint
        # a no-op — a genuinely unknown token still flags.
        issues = find_undeclared_units(r"\si{\flurbo}", declared=frozenset())
        assert len(issues) == 1
        assert issues[0].unit_token == "flurbo"


class TestFormatUnitWarnings:
    def test_formats_with_suggestion(self):
        issues = [LintIssue(line=3, unit_token="bran", suggestion="barn")]
        warnings = format_unit_warnings(issues)
        assert len(warnings) == 1
        assert "line 3" in warnings[0]
        assert "bran" in warnings[0]
        assert "barn" in warnings[0]

    def test_formats_without_suggestion(self):
        issues = [LintIssue(line=1, unit_token="zzz", suggestion=None)]
        warnings = format_unit_warnings(issues)
        assert "zzz" in warnings[0]
        assert "?" not in warnings[0]


class TestExaUnitsCliWiring:
    """`workflow validate exercises PATH` surfaces undeclared-unit warnings.

    Follows the Bundle A precedent (unknown-frontmatter-key check): warning
    only, never an error — `validate exercises` must still exit 0.
    """

    UNDECLARED_UNIT_TEX = """\
% ---
% id: units-001
% type: essay
% difficulty: easy
% taxonomy_level: Recordar
% taxonomy_domain: Información
% status: complete
% ---
\\question{Compute the value in \\si{\\foobarunit}.}{Solution.}
"""

    DECLARED_UNIT_TEX = """\
% ---
% id: units-002
% type: essay
% difficulty: easy
% taxonomy_level: Recordar
% taxonomy_domain: Información
% status: complete
% ---
\\question{Compute the cross-section in \\si{\\barn}.}{Solution.}
"""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_undeclared_unit_warns_but_exits_0(self, runner, tmp_path):
        from workflow.validation.cli import validate

        (tmp_path / "bad_unit.tex").write_text(self.UNDECLARED_UNIT_TEX)

        result = runner.invoke(validate, ["exercises", str(tmp_path)])
        assert result.exit_code == 0
        assert "foobarunit" in result.output

    def test_declared_custom_unit_produces_no_unit_warning(
        self, runner, tmp_path, monkeypatch
    ):
        # Test isolation routes WORKFLOW_DATA_DIR to a per-test tmp dir with
        # no `sty/SetUnits.sty` (tests/conftest.py autouse fixture) — point
        # the CLI's lookup at the real repo file so the "barn" declaration
        # is actually visible, exercising the real wiring end-to-end.
        import workflow.validation.cli as validation_cli

        monkeypatch.setattr(
            validation_cli, "default_units_sty_path", lambda: _SET_UNITS_STY
        )

        (tmp_path / "good_unit.tex").write_text(self.DECLARED_UNIT_TEX)

        result = runner.invoke(validation_cli.validate, ["exercises", str(tmp_path)])
        assert result.exit_code == 0
        assert "undeclared unit" not in result.output
