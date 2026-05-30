"""Hierarchy assertions for content module exception classes (v1.14.1)."""
from __future__ import annotations

import pytest

from workflow.content.service import (
    ContentServiceError,
    ContentNotFound,
    DuplicateContent,
    EntityNotFoundError,
    TopicNotFound,
    UniquenessError,
)
from workflow.content.bib_links import (
    BibEntryNotFound,
    BibKeyAmbiguous,
    BibLinkAlreadyExists,
    BibLinkNotFound,
)


# --- intermediate bases inherit from root ---

def test_entity_not_found_error_is_content_service_error():
    assert issubclass(EntityNotFoundError, ContentServiceError)


def test_uniqueness_error_is_content_service_error():
    assert issubclass(UniquenessError, ContentServiceError)


# --- leaf errors reparented to EntityNotFoundError ---

def test_topic_not_found_is_entity_not_found():
    assert issubclass(TopicNotFound, EntityNotFoundError)


def test_content_not_found_is_entity_not_found():
    assert issubclass(ContentNotFound, EntityNotFoundError)


def test_bib_entry_not_found_is_entity_not_found():
    assert issubclass(BibEntryNotFound, EntityNotFoundError)


# --- leaf errors reparented to UniquenessError ---

def test_duplicate_content_is_uniqueness_error():
    assert issubclass(DuplicateContent, UniquenessError)


def test_bib_link_already_exists_is_uniqueness_error():
    assert issubclass(BibLinkAlreadyExists, UniquenessError)


# --- standalones stay direct ContentServiceError subclasses ---

def test_bib_key_ambiguous_is_not_entity_not_found():
    assert not issubclass(BibKeyAmbiguous, EntityNotFoundError)


def test_bib_key_ambiguous_is_not_uniqueness_error():
    assert not issubclass(BibKeyAmbiguous, UniquenessError)


def test_bib_key_ambiguous_is_content_service_error():
    assert issubclass(BibKeyAmbiguous, ContentServiceError)


def test_bib_link_not_found_is_not_entity_not_found():
    assert not issubclass(BibLinkNotFound, EntityNotFoundError)


def test_bib_link_not_found_is_content_service_error():
    assert issubclass(BibLinkNotFound, ContentServiceError)


# --- all leaf errors still catchable as ContentServiceError ---

def test_all_errors_catchable_as_root():
    for cls in (
        TopicNotFound, ContentNotFound, DuplicateContent,
        BibEntryNotFound, BibKeyAmbiguous, BibLinkNotFound, BibLinkAlreadyExists,
    ):
        assert issubclass(cls, ContentServiceError), f"{cls.__name__} not under ContentServiceError"


# --- instantiation smoke tests ---

def test_entity_not_found_can_be_raised():
    with pytest.raises(EntityNotFoundError):
        raise TopicNotFound("test")


def test_uniqueness_error_can_be_raised():
    with pytest.raises(UniquenessError):
        raise DuplicateContent("test")
