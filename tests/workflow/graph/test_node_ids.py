"""Unit tests for workflow.graph.node_ids helpers."""
from workflow.graph.node_ids import NOTE_PREFIX, is_note, parse_note_id


# ── is_note ───────────────────────────────────────────────────────────────────

class TestIsNote:
    def test_valid_note_id(self):
        assert is_note("note:5") is True

    def test_valid_note_id_zero(self):
        assert is_note("note:0") is True

    def test_valid_note_id_large(self):
        assert is_note("note:99999") is True

    def test_concept_prefix_is_not_note(self):
        assert is_note("concept:5") is False

    def test_notes_plural_is_not_note(self):
        assert is_note("notes:5") is False

    def test_bare_note_colon_empty_suffix(self):
        # prefix match is True; is_note is a prefix-only check
        assert is_note("note:") is True

    def test_note_alpha_suffix_is_still_note(self):
        # is_note is prefix-only — does NOT validate the int
        assert is_note("note:abc") is True

    def test_empty_string(self):
        assert is_note("") is False

    def test_no_colon(self):
        assert is_note("note") is False

    def test_different_prefix(self):
        assert is_note("tag:5") is False

    def test_note_prefix_constant(self):
        assert NOTE_PREFIX == "note:"


# ── parse_note_id ─────────────────────────────────────────────────────────────

class TestParseNoteId:
    def test_valid_int(self):
        assert parse_note_id("note:42") == 42

    def test_valid_zero(self):
        assert parse_note_id("note:0") == 0

    def test_valid_large_int(self):
        assert parse_note_id("note:123456") == 123456

    def test_alpha_suffix_returns_none(self):
        assert parse_note_id("note:abc") is None

    def test_empty_suffix_returns_none(self):
        assert parse_note_id("note:") is None

    def test_wrong_prefix_returns_none(self):
        assert parse_note_id("concept:1") is None

    def test_notes_plural_returns_none(self):
        assert parse_note_id("notes:5") is None

    def test_empty_string_returns_none(self):
        assert parse_note_id("") is None

    def test_no_prefix_returns_none(self):
        assert parse_note_id("42") is None

    def test_float_suffix_returns_none(self):
        assert parse_note_id("note:3.14") is None

    def test_negative_int_suffix(self):
        # int("-5") succeeds — parse_note_id returns -5; callers guard via DB query
        assert parse_note_id("note:-5") == -5

    def test_whitespace_suffix_returns_none(self):
        assert parse_note_id("note: ") is None

    def test_extra_colon_returns_none(self):
        assert parse_note_id("note:5:6") is None

    def test_leading_zeros_parsed(self):
        assert parse_note_id("note:007") == 7
