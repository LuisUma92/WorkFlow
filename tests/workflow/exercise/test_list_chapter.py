"""Tests for `exercise list --chapter` (Phase 2b).

Covers tasks/plans/2026-07-03-freeze-window-features-plan.md Phase 2b:
1. `parse_exercise_number` extracts the trailing numeric suffix from an
   exercise_id (e.g. "phys-gauss-005" -> 5); None when unparsable.
2. `filter_by_chapter` includes an exercise whose book_id resolves (via
   BibContent) to a chapter whose [first_exercise, last_exercise] range
   contains the exercise's numeric suffix.
3. An exercise with no book_id is excluded when --chapter is passed
   (counted, not an error), included when --chapter is omitted.
4. Overlapping BibContent rows for the same book+chapter: first match wins,
   a warning is recorded (not raised).
5. CLI: `exercise list --chapter N [--json]` applies the filter; excluded
   count is reported to stderr, not silently dropped.

TDD RED -> GREEN.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.engine import _enable_fk_pragma
from workflow.db.models.bibliography import BibContent, BibEntry
from workflow.db.models.exercises import Exercise
from workflow.db.models.knowledge import Content, DisciplineArea, Topic
from workflow.exercise.chapter import filter_by_chapter, parse_exercise_number
from workflow.exercise.cli import exercise


# ── Shared fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def db_engine():
    import workflow.db.models.bibliography  # noqa: F401
    import workflow.db.models.exercises  # noqa: F401
    import workflow.db.models.knowledge  # noqa: F401
    import workflow.db.models.notes  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk_pragma)
    GlobalBase.metadata.create_all(engine)
    return engine


@pytest.fixture()
def runner():
    return CliRunner()


def _make_content(session: Session, label: str) -> Content:
    area = DisciplineArea(
        name=f"Area {label}",
        code=f"AR{label}",
        dewey="000",
        discipline_num=1,
        topic_num=1,
        area_initials="TA",
    )
    session.add(area)
    session.flush()
    topic = Topic(name=f"Topic {label}", serial_number=1, discipline_area_id=area.id)
    session.add(topic)
    session.flush()
    content = Content(name=f"Content {label}", topic_id=topic.id)
    session.add(content)
    session.flush()
    return content


def _make_book(session: Session, title: str) -> BibEntry:
    entry = BibEntry(entry_type="book", bibkey=title, title=title)
    session.add(entry)
    session.flush()
    return entry


def _make_bib_content(
    session: Session,
    book: BibEntry,
    content: Content,
    *,
    chapter_number: int,
    first_exercise: int | None,
    last_exercise: int | None,
) -> BibContent:
    row = BibContent(
        bib_entry_id=book.id,
        content_id=content.id,
        chapter_number=chapter_number,
        section_number=1,
        first_page=1,
        last_page=10,
        first_exercise=first_exercise,
        last_exercise=last_exercise,
    )
    session.add(row)
    session.flush()
    return row


def _make_exercise(
    session: Session, exercise_id: str, book_id: int | None = None
) -> Exercise:
    ex = Exercise(
        exercise_id=exercise_id,
        source_path=f"/fake/{exercise_id}.tex",
        file_hash="abc123",
        status="complete",
        book_id=book_id,
    )
    session.add(ex)
    session.flush()
    return ex


# ── parse_exercise_number ────────────────────────────────────────────────────


class TestParseExerciseNumber:
    def test_extracts_trailing_digits(self):
        assert parse_exercise_number("phys-gauss-005") == 5

    def test_extracts_single_digit(self):
        assert parse_exercise_number("ex-1") == 1

    def test_returns_none_when_no_digits(self):
        assert parse_exercise_number("phys-gauss-abc") is None


# ── filter_by_chapter ────────────────────────────────────────────────────────


class TestFilterByChapter:
    def test_includes_exercise_in_range(self, db_engine):
        with Session(db_engine) as session:
            content = _make_content(session, "A")
            book = _make_book(session, "Gauss Physics")
            _make_bib_content(
                session, book, content,
                chapter_number=3, first_exercise=1, last_exercise=20,
            )
            ex = _make_exercise(session, "phys-gauss-005", book_id=book.id)

            result = filter_by_chapter([ex], 3, session)

            assert result.matched == (ex,)
            assert result.excluded == 0
            assert result.warnings == ()

    def test_excludes_exercise_out_of_range(self, db_engine):
        with Session(db_engine) as session:
            content = _make_content(session, "A")
            book = _make_book(session, "Gauss Physics")
            _make_bib_content(
                session, book, content,
                chapter_number=3, first_exercise=1, last_exercise=20,
            )
            ex = _make_exercise(session, "phys-gauss-099", book_id=book.id)

            result = filter_by_chapter([ex], 3, session)

            assert result.matched == ()
            assert result.excluded == 1

    def test_excludes_exercise_with_no_book_id(self, db_engine):
        with Session(db_engine) as session:
            ex = _make_exercise(session, "selfmade-001", book_id=None)

            result = filter_by_chapter([ex], 3, session)

            assert result.matched == ()
            assert result.excluded == 1

    def test_overlapping_ranges_warns_and_takes_first(self, db_engine):
        with Session(db_engine) as session:
            content_a = _make_content(session, "A")
            content_b = _make_content(session, "B")
            book = _make_book(session, "Overlap Physics")
            first = _make_bib_content(
                session, book, content_a,
                chapter_number=3, first_exercise=1, last_exercise=20,
            )
            _make_bib_content(
                session, book, content_b,
                chapter_number=3, first_exercise=15, last_exercise=30,
            )
            ex = _make_exercise(session, "phys-overlap-005", book_id=book.id)

            result = filter_by_chapter([ex], 3, session)

            assert result.matched == (ex,)
            assert len(result.warnings) == 1
            assert f"content_id={first.content_id}" in result.warnings[0]


# ── CLI: exercise list --chapter ────────────────────────────────────────────


class TestListChapterCli:
    def test_json_filters_to_chapter(self, db_engine, runner):
        with Session(db_engine) as session:
            content = _make_content(session, "A")
            book = _make_book(session, "Gauss Physics")
            _make_bib_content(
                session, book, content,
                chapter_number=3, first_exercise=1, last_exercise=20,
            )
            _make_exercise(session, "phys-gauss-005", book_id=book.id)
            _make_exercise(session, "phys-gauss-099", book_id=book.id)
            _make_exercise(session, "selfmade-001", book_id=None)
            session.commit()

        result = runner.invoke(
            exercise, ["list", "--chapter", "3", "--json"], obj={"engine": db_engine}
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert [row["id"] for row in payload] == ["phys-gauss-005"]

    def test_reports_excluded_count_to_stderr(self, db_engine, runner):
        with Session(db_engine) as session:
            content = _make_content(session, "A")
            book = _make_book(session, "Gauss Physics")
            _make_bib_content(
                session, book, content,
                chapter_number=3, first_exercise=1, last_exercise=20,
            )
            _make_exercise(session, "phys-gauss-005", book_id=book.id)
            _make_exercise(session, "selfmade-001", book_id=None)
            session.commit()

        result = runner.invoke(
            exercise,
            ["list", "--chapter", "3", "--json"],
            obj={"engine": db_engine},
        )

        assert result.exit_code == 0, result.output
        assert "1 exercise" in result.stderr
        assert "excluded" in result.stderr

    def test_omitting_chapter_includes_all(self, db_engine, runner):
        with Session(db_engine) as session:
            _make_exercise(session, "selfmade-001", book_id=None)
            session.commit()

        result = runner.invoke(
            exercise, ["list", "--json"], obj={"engine": db_engine}
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert [row["id"] for row in payload] == ["selfmade-001"]
