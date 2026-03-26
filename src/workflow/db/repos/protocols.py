"""
Repository Protocol interfaces for WorkFlow DB.

These are the contracts that consumer modules (itep, latexzettel, CLI) use
to access data. Concrete implementations live in sqlalchemy.py.

Types are imported from their canonical model modules to avoid duplication.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from workflow.db.models.bibliography import Author, BibEntry
from workflow.db.models.academic import Content
from workflow.db.models.exercises import Exercise
from workflow.db.models.notes import Link, Note, Tag


@runtime_checkable
class BibRepo(Protocol):
    def get_by_id(self, bib_id: int) -> BibEntry | None: ...
    def get_by_bibkey(self, bibkey: str) -> BibEntry | None: ...
    def search(self, query: str, limit: int = 20) -> list[BibEntry]: ...
    def create(self, **fields) -> BibEntry: ...
    def list_all(self, limit: int = 100, offset: int = 0) -> list[BibEntry]: ...


@runtime_checkable
class AuthorRepo(Protocol):
    def get_or_create(self, first_name: str, last_name: str) -> Author: ...
    def search(self, query: str) -> list[Author]: ...


@runtime_checkable
class ContentRepo(Protocol):
    def get_by_bib_entry(self, bib_entry_id: int) -> list[Content]: ...

    def get_exercises_for_chapter(
        self, bib_entry_id: int, chapter: int
    ) -> list[Content]: ...


@runtime_checkable
class NoteRepo(Protocol):
    def get_by_filename(self, filename: str) -> Note | None: ...
    def get_by_reference(self, reference: str) -> Note | None: ...
    def create(self, filename: str, reference: str) -> Note: ...
    def list_all(self, limit: int = 100) -> list[Note]: ...
    def delete(self, filename: str) -> bool: ...


@runtime_checkable
class LinkRepo(Protocol):
    def get_links_from(self, note_id: int) -> list[Link]: ...
    def get_links_to(self, label_id: int) -> list[Link]: ...
    def create(self, source_id: int, target_id: int) -> Link: ...


@runtime_checkable
class TagRepo(Protocol):
    def get_or_create(self, name: str) -> Tag: ...
    def get_notes_by_tag(self, tag_name: str) -> list[Note]: ...


@runtime_checkable
class ExerciseRepo(Protocol):
    def get_by_exercise_id(self, exercise_id: str) -> Exercise | None: ...

    def find_by_filters(
        self,
        *,
        tags: list[str] | None = None,
        difficulty: str | None = None,
        taxonomy_level: str | None = None,
        taxonomy_domain: str | None = None,
        status: str | None = None,
        exercise_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Exercise]: ...
    def upsert(self, exercise: Exercise) -> Exercise: ...
    def list_all(self, limit: int = 100, offset: int = 0) -> list[Exercise]: ...
    def delete(self, exercise_id: str) -> bool: ...

    def get_orphans(self) -> list[Exercise]:
        """Exercises whose source_path no longer exists on disk."""
        ...


__all__ = [
    "AuthorRepo",
    "BibRepo",
    "ContentRepo",
    "ExerciseRepo",
    "LinkRepo",
    "NoteRepo",
    "TagRepo",
]
