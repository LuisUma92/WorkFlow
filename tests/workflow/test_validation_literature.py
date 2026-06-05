"""Tests for Wave C C1 PRISMA-provenance frontmatter keys in literature notes.

Covers validate_note_frontmatter for the five optional literature-only fields:
bibkey, prisma_review_record_id, prisma_keyword_id, origin, created.

File name chosen to avoid collision with any prisma-agent test files
(which live under tests/workflow/prisma/).
"""
from workflow.validation.schemas import validate_note_frontmatter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE = {"id": "lit-001", "title": "A Literature Note", "type": "literature"}
_BASE_PERMANENT = {"id": "per-001", "title": "Permanent Note", "type": "permanent"}
_BASE_FLEETING = {"id": "flt-001", "title": "Fleeting Note", "type": "fleeting"}


# ---------------------------------------------------------------------------
# Literature notes WITH all five new keys
# ---------------------------------------------------------------------------

class TestLiteratureProvenanceAllKeys:
    def test_all_five_keys_accepted(self):
        data = {
            **_BASE,
            "bibkey": "Smith2024",
            "prisma_review_record_id": 42,
            "prisma_keyword_id": 7,
            "origin": "prisma",
            "created": "2024-03-15",
        }
        result, errors = validate_note_frontmatter(data)
        assert errors == [], f"unexpected errors: {errors}"
        assert result is not None
        assert result.bibkey == "Smith2024"
        assert result.prisma_review_record_id == 42
        assert result.prisma_keyword_id == 7
        assert result.origin == "prisma"
        assert result.created == "2024-03-15"

    def test_origin_manual_accepted(self):
        data = {**_BASE, "origin": "manual"}
        result, errors = validate_note_frontmatter(data)
        assert errors == []
        assert result is not None
        assert result.origin == "manual"

    def test_origin_prisma_accepted(self):
        data = {**_BASE, "origin": "prisma"}
        result, errors = validate_note_frontmatter(data)
        assert errors == []
        assert result is not None
        assert result.origin == "prisma"

    def test_origin_arbitrary_string_accepted(self):
        """Unknown origin strings are accepted leniently — no whitelist rejection."""
        data = {**_BASE, "origin": "imported"}
        result, errors = validate_note_frontmatter(data)
        assert errors == []
        assert result is not None
        assert result.origin == "imported"


# ---------------------------------------------------------------------------
# Literature notes WITHOUT new keys (backward-compat: must still validate)
# ---------------------------------------------------------------------------

class TestLiteratureProvenanceOptional:
    def test_no_provenance_keys_validates(self):
        result, errors = validate_note_frontmatter(_BASE)
        assert errors == []
        assert result is not None
        assert result.bibkey is None
        assert result.prisma_review_record_id is None
        assert result.prisma_keyword_id is None
        assert result.origin is None

    def test_bibkey_absent_is_none(self):
        result, _ = validate_note_frontmatter(_BASE)
        assert result is not None
        assert result.bibkey is None

    def test_partial_keys_validate(self):
        data = {**_BASE, "bibkey": "Jones2023"}
        result, errors = validate_note_frontmatter(data)
        assert errors == []
        assert result is not None
        assert result.bibkey == "Jones2023"
        assert result.prisma_review_record_id is None


# ---------------------------------------------------------------------------
# prisma_review_record_id type variants
# ---------------------------------------------------------------------------

class TestPrismaReviewRecordId:
    def test_integer_accepted(self):
        data = {**_BASE, "prisma_review_record_id": 99}
        result, errors = validate_note_frontmatter(data)
        assert errors == []
        assert result is not None
        assert result.prisma_review_record_id == 99

    def test_null_accepted(self):
        data = {**_BASE, "prisma_review_record_id": None}
        result, errors = validate_note_frontmatter(data)
        assert errors == []
        assert result is not None
        assert result.prisma_review_record_id is None

    def test_string_rejected(self):
        data = {**_BASE, "prisma_review_record_id": "not-an-int"}
        result, errors = validate_note_frontmatter(data)
        assert result is None
        assert any("prisma_review_record_id" in e for e in errors)

    def test_bool_rejected(self):
        """bool is a subclass of int in Python; we explicitly reject it."""
        data = {**_BASE, "prisma_review_record_id": True}
        result, errors = validate_note_frontmatter(data)
        assert result is None
        assert any("prisma_review_record_id" in e for e in errors)


# ---------------------------------------------------------------------------
# prisma_keyword_id type variants
# ---------------------------------------------------------------------------

class TestPrismaKeywordId:
    def test_integer_accepted(self):
        data = {**_BASE, "prisma_keyword_id": 3}
        result, errors = validate_note_frontmatter(data)
        assert errors == []
        assert result is not None
        assert result.prisma_keyword_id == 3

    def test_null_accepted(self):
        data = {**_BASE, "prisma_keyword_id": None}
        result, errors = validate_note_frontmatter(data)
        assert errors == []
        assert result is not None
        assert result.prisma_keyword_id is None

    def test_string_rejected(self):
        data = {**_BASE, "prisma_keyword_id": "bad"}
        result, errors = validate_note_frontmatter(data)
        assert result is None
        assert any("prisma_keyword_id" in e for e in errors)


# ---------------------------------------------------------------------------
# Existing note types unaffected
# ---------------------------------------------------------------------------

class TestExistingTypesUnaffected:
    def test_permanent_note_validates(self):
        result, errors = validate_note_frontmatter(_BASE_PERMANENT)
        assert errors == []
        assert result is not None
        assert result.type == "permanent"

    def test_fleeting_note_validates(self):
        result, errors = validate_note_frontmatter(_BASE_FLEETING)
        assert errors == []
        assert result is not None
        assert result.type == "fleeting"

    def test_permanent_note_provenance_fields_are_none(self):
        """Provenance keys on a permanent note are not validated — fields stay None."""
        data = {**_BASE_PERMANENT, "bibkey": "SomeKey", "origin": "prisma"}
        result, errors = validate_note_frontmatter(data)
        # permanent notes must still pass; provenance keys silently ignored
        assert errors == []
        assert result is not None
        assert result.bibkey is None
        assert result.origin is None

    def test_invalid_type_still_rejected(self):
        data = {"id": "x", "title": "X", "type": "unknown"}
        result, errors = validate_note_frontmatter(data)
        assert result is None
        assert any("type" in e for e in errors)
