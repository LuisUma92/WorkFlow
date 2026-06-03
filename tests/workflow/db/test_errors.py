"""Tests for workflow.db.errors neutral service-layer error taxonomy (ADR-0007).

Covers:
- Neutral bases exist and subclass WorkflowError.
- content.service taxonomy is caught by BOTH ContentServiceError AND neutral bases.
- bibliography.service.BibKeyAmbiguous and content.bib_links.BibKeyAmbiguous
  are both caught by AmbiguousLookupError (cross-layer win).
- content.bib_links.BibKeyAmbiguous is still caught by ContentServiceError.
- BibLinkNotFound is NOT an EntityNotFoundError (D2 locked decision).
- _resolve_bib_entry boundary chaining: raised BibKeyAmbiguous.__cause__ is
  the bibliography-layer BibKeyAmbiguous.
"""
from __future__ import annotations

import pytest

import workflow.db.errors as dberr
from workflow.bibliography.service import BibKeyAmbiguous as BibSvcAmbiguous
from workflow.content.bib_links import (
    BibEntryNotFound,
    BibKeyAmbiguous as BibLinksAmbiguous,
    BibLinkAlreadyExists,
    BibLinkNotFound,
    _resolve_bib_entry,
)
from workflow.content.service import (
    ContentNotFound,
    ContentServiceError,
    DuplicateContent,
    EntityNotFoundError,
    TopicNotFound,
    UniquenessError,
)


# ---------------------------------------------------------------------------
# Neutral bases
# ---------------------------------------------------------------------------


class TestNeutralBases:
    def test_workflow_error_is_exception(self):
        assert issubclass(dberr.WorkflowError, Exception)

    def test_entity_not_found_is_workflow_error(self):
        assert issubclass(dberr.EntityNotFoundError, dberr.WorkflowError)

    def test_uniqueness_error_is_workflow_error(self):
        assert issubclass(dberr.UniquenessError, dberr.WorkflowError)

    def test_ambiguous_lookup_is_workflow_error(self):
        assert issubclass(dberr.AmbiguousLookupError, dberr.WorkflowError)

    def test_neutral_bases_can_be_raised_and_caught(self):
        with pytest.raises(dberr.WorkflowError):
            raise dberr.EntityNotFoundError("missing")

    def test_ambiguous_lookup_caught_as_workflow_error(self):
        with pytest.raises(dberr.WorkflowError):
            raise dberr.AmbiguousLookupError("two rows")


# ---------------------------------------------------------------------------
# content.service taxonomy — dual catching
# ---------------------------------------------------------------------------


class TestContentServiceTaxonomy:
    def test_content_service_error_is_workflow_error(self):
        assert issubclass(ContentServiceError, dberr.WorkflowError)

    def test_entity_not_found_caught_by_content_service_error(self):
        with pytest.raises(ContentServiceError):
            raise EntityNotFoundError("missing")

    def test_entity_not_found_caught_by_neutral_entity_not_found(self):
        with pytest.raises(dberr.EntityNotFoundError):
            raise EntityNotFoundError("missing")

    def test_topic_not_found_caught_by_content_service_error(self):
        with pytest.raises(ContentServiceError):
            raise TopicNotFound("topic gone")

    def test_topic_not_found_caught_by_neutral_entity_not_found(self):
        with pytest.raises(dberr.EntityNotFoundError):
            raise TopicNotFound("topic gone")

    def test_content_not_found_caught_by_content_service_error(self):
        with pytest.raises(ContentServiceError):
            raise ContentNotFound("content gone")

    def test_content_not_found_caught_by_neutral_entity_not_found(self):
        with pytest.raises(dberr.EntityNotFoundError):
            raise ContentNotFound("content gone")

    def test_uniqueness_error_caught_by_content_service_error(self):
        with pytest.raises(ContentServiceError):
            raise UniquenessError("dup")

    def test_uniqueness_error_caught_by_neutral_uniqueness(self):
        with pytest.raises(dberr.UniquenessError):
            raise UniquenessError("dup")

    def test_duplicate_content_caught_by_content_service_error(self):
        with pytest.raises(ContentServiceError):
            raise DuplicateContent("dup content")

    def test_duplicate_content_caught_by_neutral_uniqueness(self):
        with pytest.raises(dberr.UniquenessError):
            raise DuplicateContent("dup content")

    def test_mro_is_consistent(self):
        """Python would raise TypeError at class definition time on bad MRO.

        Importing the classes is sufficient; this test ensures no MRO error
        at module load time.
        """
        assert EntityNotFoundError.__mro__ is not None
        assert UniquenessError.__mro__ is not None


# ---------------------------------------------------------------------------
# bibliography.service.BibKeyAmbiguous
# ---------------------------------------------------------------------------


class TestBibliographyAmbiguous:
    def test_bib_svc_ambiguous_is_ambiguous_lookup(self):
        assert issubclass(BibSvcAmbiguous, dberr.AmbiguousLookupError)

    def test_bib_svc_ambiguous_caught_as_workflow_error(self):
        with pytest.raises(dberr.WorkflowError):
            raise BibSvcAmbiguous("dup bibkey")

    def test_bib_svc_ambiguous_caught_as_ambiguous_lookup(self):
        with pytest.raises(dberr.AmbiguousLookupError):
            raise BibSvcAmbiguous("dup bibkey")


# ---------------------------------------------------------------------------
# content.bib_links error classes
# ---------------------------------------------------------------------------


class TestBibLinksErrors:
    def test_bib_links_ambiguous_caught_by_ambiguous_lookup(self):
        """Cross-layer win: both BibKeyAmbiguous variants share AmbiguousLookupError."""
        with pytest.raises(dberr.AmbiguousLookupError):
            raise BibLinksAmbiguous("dup at content boundary")

    def test_bib_links_ambiguous_caught_by_content_service_error(self):
        with pytest.raises(ContentServiceError):
            raise BibLinksAmbiguous("dup at content boundary")

    def test_bib_entry_not_found_caught_by_entity_not_found(self):
        with pytest.raises(dberr.EntityNotFoundError):
            raise BibEntryNotFound("bib entry gone")

    def test_bib_entry_not_found_caught_by_content_service_error(self):
        with pytest.raises(ContentServiceError):
            raise BibEntryNotFound("bib entry gone")

    def test_bib_link_already_exists_caught_by_neutral_uniqueness(self):
        with pytest.raises(dberr.UniquenessError):
            raise BibLinkAlreadyExists("already linked")

    def test_bib_link_already_exists_caught_by_content_service_error(self):
        with pytest.raises(ContentServiceError):
            raise BibLinkAlreadyExists("already linked")

    # D2 LOCKED: BibLinkNotFound stays standalone — NOT EntityNotFoundError
    def test_bib_link_not_found_is_NOT_entity_not_found(self):
        assert not issubclass(BibLinkNotFound, dberr.EntityNotFoundError)

    def test_bib_link_not_found_is_content_service_error(self):
        assert issubclass(BibLinkNotFound, ContentServiceError)

    def test_bib_link_not_found_caught_as_workflow_error(self):
        with pytest.raises(dberr.WorkflowError):
            raise BibLinkNotFound("no such link")


# ---------------------------------------------------------------------------
# Notes taxonomy graduation (architect HIGH): disconnected errors now connected
# ---------------------------------------------------------------------------


class TestNotesTaxonomyGraduation:
    def test_ambiguous_note_id_caught_by_neutral_ambiguous_base(self):
        from workflow.notes.service import AmbiguousNoteId

        with pytest.raises(dberr.AmbiguousLookupError):
            raise AmbiguousNoteId("two notes share id")

    def test_note_not_found_caught_by_neutral_entity_base(self):
        from workflow.notes.service import NoteNotFound

        with pytest.raises(dberr.EntityNotFoundError):
            raise NoteNotFound("missing note")


# ---------------------------------------------------------------------------
# Cross-layer catch: both BibKeyAmbiguous variants caught by AmbiguousLookupError
# ---------------------------------------------------------------------------


class TestCrossLayerAmbiguousCatch:
    @pytest.mark.parametrize(
        "exc_class",
        [BibSvcAmbiguous, BibLinksAmbiguous],
        ids=["bibliography.service", "content.bib_links"],
    )
    def test_both_ambiguous_caught_by_neutral_base(self, exc_class):
        with pytest.raises(dberr.AmbiguousLookupError):
            raise exc_class("two rows")


# ---------------------------------------------------------------------------
# Boundary chaining: _resolve_bib_entry wraps bibliography BibKeyAmbiguous
# ---------------------------------------------------------------------------


class TestResolveBibEntryChaining:
    def test_ambiguous_bibkey_chains_cause(self, monkeypatch):
        """_resolve_bib_entry should wrap BibBibKeyAmbiguous as __cause__."""
        original_exc = BibSvcAmbiguous("raw dup")

        def _fake_lookup(session, bibkey):
            raise original_exc

        import workflow.content.bib_links as bib_links_mod

        monkeypatch.setattr(bib_links_mod, "get_bib_entry_by_bibkey", _fake_lookup)

        with pytest.raises(BibLinksAmbiguous) as exc_info:
            _resolve_bib_entry(None, "dup_key")

        assert exc_info.value.__cause__ is original_exc

    def test_ambiguous_bibkey_caught_as_ambiguous_lookup_end_to_end(self, monkeypatch):
        """The re-raised content BibKeyAmbiguous is catchable as AmbiguousLookupError."""
        import workflow.content.bib_links as bib_links_mod

        def _raise_ambiguous(*_):
            raise BibSvcAmbiguous("two rows")

        monkeypatch.setattr(bib_links_mod, "get_bib_entry_by_bibkey", _raise_ambiguous)

        with pytest.raises(dberr.AmbiguousLookupError):
            _resolve_bib_entry(None, "dup_key")

    def test_none_result_raises_bib_entry_not_found(self, monkeypatch):
        """_resolve_bib_entry raises BibEntryNotFound when lookup returns None."""
        import workflow.content.bib_links as bib_links_mod

        monkeypatch.setattr(
            bib_links_mod, "get_bib_entry_by_bibkey", lambda *_: None
        )

        with pytest.raises(BibEntryNotFound):
            _resolve_bib_entry(None, "missing_key")
