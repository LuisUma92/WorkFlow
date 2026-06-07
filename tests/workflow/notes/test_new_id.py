"""Tests for workflow notes new-id command and generate_zettel_id() generator."""

from __future__ import annotations

import re

import pytest
from click.testing import CliRunner

from workflow.notes.cli import notes

_ZETTEL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,21}$")


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# Unit tests for generate_zettel_id()
# ---------------------------------------------------------------------------

class TestGenerateZettelId:
    def test_default_length_12(self):
        from workflow.notes.ids import generate_zettel_id
        zid = generate_zettel_id()
        assert len(zid) == 12

    def test_matches_zettel_id_regex(self):
        from workflow.notes.ids import generate_zettel_id
        for _ in range(50):
            assert _ZETTEL_ID_RE.match(generate_zettel_id()), "failed regex"

    def test_custom_length_8(self):
        from workflow.notes.ids import generate_zettel_id
        assert len(generate_zettel_id(8)) == 8

    def test_custom_length_21(self):
        from workflow.notes.ids import generate_zettel_id
        assert len(generate_zettel_id(21)) == 21

    def test_custom_length_15(self):
        from workflow.notes.ids import generate_zettel_id
        zid = generate_zettel_id(15)
        assert len(zid) == 15
        assert _ZETTEL_ID_RE.match(zid)

    def test_uniqueness_across_many_calls(self):
        from workflow.notes.ids import generate_zettel_id
        ids = {generate_zettel_id() for _ in range(200)}
        # Very likely all unique (probability of collision ~ negligible)
        assert len(ids) >= 195, "too many collisions — likely broken RNG"

    def test_only_alphabet_chars(self):
        from workflow.notes.ids import generate_zettel_id
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")
        for _ in range(50):
            zid = generate_zettel_id()
            assert set(zid) <= allowed, f"invalid chars in {zid!r}"

    def test_raises_on_length_below_min(self):
        from workflow.notes.ids import generate_zettel_id
        with pytest.raises(ValueError, match="length"):
            generate_zettel_id(7)

    def test_raises_on_length_above_max(self):
        from workflow.notes.ids import generate_zettel_id
        with pytest.raises(ValueError, match="length"):
            generate_zettel_id(22)

    def test_raises_on_zero_length(self):
        from workflow.notes.ids import generate_zettel_id
        with pytest.raises(ValueError):
            generate_zettel_id(0)


# ---------------------------------------------------------------------------
# CLI tests for `workflow notes new-id`
# ---------------------------------------------------------------------------

class TestNewIdCommand:
    def test_exit_zero(self, runner):
        result = runner.invoke(notes, ["new-id"])
        assert result.exit_code == 0, result.output

    def test_output_matches_regex(self, runner):
        result = runner.invoke(notes, ["new-id"])
        zid = result.output.strip()
        assert _ZETTEL_ID_RE.match(zid), f"output {zid!r} does not match regex"

    def test_default_length_12(self, runner):
        result = runner.invoke(notes, ["new-id"])
        assert len(result.output.strip()) == 12

    def test_length_option_8(self, runner):
        result = runner.invoke(notes, ["new-id", "--length", "8"])
        assert result.exit_code == 0
        assert len(result.output.strip()) == 8

    def test_length_option_21(self, runner):
        result = runner.invoke(notes, ["new-id", "--length", "21"])
        assert result.exit_code == 0
        assert len(result.output.strip()) == 21

    def test_length_option_15(self, runner):
        result = runner.invoke(notes, ["new-id", "--length", "15"])
        assert result.exit_code == 0
        zid = result.output.strip()
        assert len(zid) == 15
        assert _ZETTEL_ID_RE.match(zid)

    def test_length_below_min_is_usage_error(self, runner):
        result = runner.invoke(notes, ["new-id", "--length", "7"])
        assert result.exit_code != 0

    def test_length_above_max_is_usage_error(self, runner):
        result = runner.invoke(notes, ["new-id", "--length", "22"])
        assert result.exit_code != 0

    def test_uniqueness_across_calls(self, runner):
        ids = set()
        for _ in range(20):
            result = runner.invoke(notes, ["new-id"])
            ids.add(result.output.strip())
        assert len(ids) >= 18

    def test_no_db_needed(self, runner):
        """new-id must not require a DB."""
        result = runner.invoke(notes, ["new-id"])
        assert result.exit_code == 0
        assert "Error" not in result.output
