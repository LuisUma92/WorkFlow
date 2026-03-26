"""
Concrete SQLAlchemy 2.0 implementations of the repository Protocols.

Each repo takes a Session in __init__ and uses it for all queries.
Return types are model instances — no SQLAlchemy internals leak through.
"""

from __future__ import annotations

from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from pathlib import Path

from workflow.db.models.bibliography import Author, BibEntry
from workflow.db.models.academic import BibContent, Content
from workflow.db.models.exercises import Exercise
from workflow.db.models.notes import Link, Note, NoteTag, Tag


# ── Bibliography ────────────────────────────────────────────────────────────


class SqlBibRepo:
    """Implements BibRepo against the global workflow.db."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, bib_id: int) -> BibEntry | None:
        return self._session.get(BibEntry, bib_id)

    def get_by_bibkey(self, bibkey: str) -> BibEntry | None:
        stmt = select(BibEntry).where(BibEntry.bibkey == bibkey)
        return self._session.scalars(stmt).first()

    def search(self, query: str, limit: int = 20) -> list[BibEntry]:
        pattern = f"%{query}%"
        stmt = (
            select(BibEntry)
            .where(
                or_(
                    BibEntry.title.ilike(pattern),
                    BibEntry.bibkey.ilike(pattern),
                    BibEntry.notes.ilike(pattern),
                )
            )
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def create(self, **fields) -> BibEntry:
        entry = BibEntry(**fields)
        self._session.add(entry)
        self._session.flush()
        return entry

    def list_all(self, limit: int = 100, offset: int = 0) -> list[BibEntry]:
        stmt = select(BibEntry).offset(offset).limit(limit)
        return list(self._session.scalars(stmt).all())


# ── Author ──────────────────────────────────────────────────────────────────


class SqlAuthorRepo:
    """Implements AuthorRepo against the global workflow.db."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(self, first_name: str, last_name: str) -> Author:
        stmt = select(Author).where(
            Author.first_name == first_name,
            Author.last_name == last_name,
        )
        existing = self._session.scalars(stmt).first()
        if existing is not None:
            return existing
        author = Author(first_name=first_name, last_name=last_name)
        self._session.add(author)
        self._session.flush()
        return author

    def search(self, query: str) -> list[Author]:
        pattern = f"%{query}%"
        stmt = select(Author).where(
            or_(
                Author.first_name.ilike(pattern),
                Author.last_name.ilike(pattern),
            )
        )
        return list(self._session.scalars(stmt).all())


# ── Content ─────────────────────────────────────────────────────────────────


class SqlContentRepo:
    """Implements ContentRepo against the global workflow.db."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_bib_entry(self, bib_entry_id: int) -> list[Content]:
        stmt = (
            select(Content)
            .join(BibContent, BibContent.content_id == Content.id)
            .where(BibContent.bib_entry_id == bib_entry_id)
        )
        return list(self._session.scalars(stmt).all())

    def get_exercises_for_chapter(
        self, bib_entry_id: int, chapter: int
    ) -> list[Content]:
        stmt = (
            select(Content)
            .join(BibContent, BibContent.content_id == Content.id)
            .where(
                BibContent.bib_entry_id == bib_entry_id,
                Content.chapter_number == chapter,
                Content.first_exercise.is_not(None),
            )
        )
        return list(self._session.scalars(stmt).all())


# ── Note ─────────────────────────────────────────────────────────────────────


class SqlNoteRepo:
    """Implements NoteRepo against a project's slipbox.db."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_filename(self, filename: str) -> Note | None:
        stmt = select(Note).where(Note.filename == filename)
        return self._session.scalars(stmt).first()

    def get_by_reference(self, reference: str) -> Note | None:
        stmt = select(Note).where(Note.reference == reference)
        return self._session.scalars(stmt).first()

    def create(self, filename: str, reference: str) -> Note:
        note = Note(filename=filename, reference=reference)
        self._session.add(note)
        self._session.flush()
        return note

    def list_all(self, limit: int = 100) -> list[Note]:
        stmt = select(Note).limit(limit)
        return list(self._session.scalars(stmt).all())

    def delete(self, filename: str) -> bool:
        note = self.get_by_filename(filename)
        if note is None:
            return False
        self._session.delete(note)
        self._session.flush()
        return True


# ── Link ─────────────────────────────────────────────────────────────────────


class SqlLinkRepo:
    """Implements LinkRepo against a project's slipbox.db."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_links_from(self, note_id: int) -> list[Link]:
        stmt = select(Link).where(Link.source_id == note_id)
        return list(self._session.scalars(stmt).all())

    def get_links_to(self, label_id: int) -> list[Link]:
        stmt = select(Link).where(Link.target_id == label_id)
        return list(self._session.scalars(stmt).all())

    def create(self, source_id: int, target_id: int) -> Link:
        link = Link(source_id=source_id, target_id=target_id)
        self._session.add(link)
        self._session.flush()
        return link


# ── Tag ──────────────────────────────────────────────────────────────────────


class SqlTagRepo:
    """Implements TagRepo against a project's slipbox.db."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(self, name: str) -> Tag:
        stmt = select(Tag).where(Tag.name == name)
        existing = self._session.scalars(stmt).first()
        if existing is not None:
            return existing
        tag = Tag(name=name)
        self._session.add(tag)
        self._session.flush()
        return tag

    def get_notes_by_tag(self, tag_name: str) -> list[Note]:
        stmt = (
            select(Note)
            .join(NoteTag, NoteTag.note_id == Note.id)
            .join(Tag, Tag.id == NoteTag.tag_id)
            .where(Tag.name == tag_name)
        )
        return list(self._session.scalars(stmt).all())


# ── Exercise ────────────────────────────────────────────────────────────────


class SqlExerciseRepo:
    """Implements ExerciseRepo against the global workflow.db."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_exercise_id(self, exercise_id: str) -> Exercise | None:
        stmt = select(Exercise).where(Exercise.exercise_id == exercise_id)
        return self._session.scalars(stmt).first()

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
    ) -> list[Exercise]:
        stmt = select(Exercise)

        if difficulty is not None:
            stmt = stmt.where(Exercise.difficulty == difficulty)
        if taxonomy_level is not None:
            stmt = stmt.where(Exercise.taxonomy_level == taxonomy_level)
        if taxonomy_domain is not None:
            stmt = stmt.where(Exercise.taxonomy_domain == taxonomy_domain)
        if status is not None:
            stmt = stmt.where(Exercise.status == status)
        if exercise_type is not None:
            stmt = stmt.where(Exercise.type == exercise_type)
        if tags is not None:
            for tag in tags:
                stmt = stmt.where(Exercise.tags.contains(f'"{tag}"'))

        stmt = stmt.offset(offset).limit(limit)
        return list(self._session.scalars(stmt).all())

    # Fields that can be updated during upsert
    _UPDATABLE_FIELDS = (
        "source_path",
        "file_hash",
        "status",
        "type",
        "difficulty",
        "taxonomy_level",
        "taxonomy_domain",
        "tags",
        "concepts",
        "content_id",
        "book_id",
        "default_grade",
        "penalty",
        "has_images",
        "image_refs",
        "diagram_id",
        "option_count",
    )

    def upsert(self, exercise: Exercise) -> Exercise:
        existing = self.get_by_exercise_id(exercise.exercise_id)
        if existing is not None:
            for field in self._UPDATABLE_FIELDS:
                value = getattr(exercise, field)
                if value is not None:
                    setattr(existing, field, value)
            self._session.flush()
            return existing
        else:
            self._session.add(exercise)
            self._session.flush()
            return exercise

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Exercise]:
        stmt = select(Exercise).offset(offset).limit(limit)
        return list(self._session.scalars(stmt).all())

    def delete(self, exercise_id: str) -> bool:
        exercise = self.get_by_exercise_id(exercise_id)
        if exercise is None:
            return False
        self._session.delete(exercise)
        self._session.flush()
        return True

    def get_orphans(self) -> list[Exercise]:
        """Return exercises whose source_path no longer exists on disk."""
        all_exercises = list(self._session.scalars(select(Exercise)).all())
        return [ex for ex in all_exercises if not Path(ex.source_path).exists()]


__all__ = [
    "SqlAuthorRepo",
    "SqlBibRepo",
    "SqlContentRepo",
    "SqlExerciseRepo",
    "SqlLinkRepo",
    "SqlNoteRepo",
    "SqlTagRepo",
]
