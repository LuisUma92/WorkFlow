"""Tests for SqlExerciseRepo — exercise repository implementation."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.exercises import Exercise
from workflow.db.repos.sqlalchemy import SqlExerciseRepo


def _enable_fk(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk)
    GlobalBase.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def repo(db_session):
    return SqlExerciseRepo(db_session)


def _make_exercise(exercise_id: str, **kwargs) -> Exercise:
    defaults = dict(
        source_path=f"/path/{exercise_id}.tex",
        file_hash="a" * 64,
    )
    defaults.update(kwargs)
    return Exercise(exercise_id=exercise_id, **defaults)


class TestSqlExerciseRepo:
    def test_upsert_creates_new(self, repo, db_session):
        ex = _make_exercise("new-001", status="complete")
        result = repo.upsert(ex)
        assert result.id is not None
        assert result.exercise_id == "new-001"

    def test_upsert_updates_existing(self, repo, db_session):
        ex = _make_exercise("upd-001", status="placeholder")
        repo.upsert(ex)
        db_session.commit()

        updated = _make_exercise("upd-001", status="complete", difficulty="hard")
        result = repo.upsert(updated)
        db_session.commit()

        loaded = repo.get_by_exercise_id("upd-001")
        assert loaded.status == "complete"
        assert loaded.difficulty == "hard"

    def test_get_by_exercise_id(self, repo, db_session):
        repo.upsert(_make_exercise("find-001"))
        db_session.commit()

        found = repo.get_by_exercise_id("find-001")
        assert found is not None
        assert found.exercise_id == "find-001"

        assert repo.get_by_exercise_id("nonexistent") is None

    def test_list_all(self, repo, db_session):
        for i in range(5):
            repo.upsert(_make_exercise(f"list-{i:03d}"))
        db_session.commit()

        all_ex = repo.list_all()
        assert len(all_ex) == 5

        limited = repo.list_all(limit=2)
        assert len(limited) == 2

    def test_find_by_filters_difficulty(self, repo, db_session):
        repo.upsert(_make_exercise("easy-001", difficulty="easy"))
        repo.upsert(_make_exercise("hard-001", difficulty="hard"))
        db_session.commit()

        easy = repo.find_by_filters(difficulty="easy")
        assert len(easy) == 1
        assert easy[0].exercise_id == "easy-001"

    def test_find_by_filters_status(self, repo, db_session):
        repo.upsert(_make_exercise("p-001", status="placeholder"))
        repo.upsert(_make_exercise("c-001", status="complete"))
        db_session.commit()

        complete = repo.find_by_filters(status="complete")
        assert len(complete) == 1
        assert complete[0].exercise_id == "c-001"

    def test_find_by_filters_taxonomy(self, repo, db_session):
        repo.upsert(
            _make_exercise(
                "tax-001",
                taxonomy_level="Usar-Aplicar",
                taxonomy_domain="Procedimiento Mental",
            )
        )
        repo.upsert(
            _make_exercise(
                "tax-002", taxonomy_level="Recordar", taxonomy_domain="Información"
            )
        )
        db_session.commit()

        results = repo.find_by_filters(taxonomy_level="Usar-Aplicar")
        assert len(results) == 1
        assert results[0].exercise_id == "tax-001"

    def test_delete(self, repo, db_session):
        repo.upsert(_make_exercise("del-001"))
        db_session.commit()

        assert repo.delete("del-001") is True
        assert repo.get_by_exercise_id("del-001") is None
        assert repo.delete("nonexistent") is False

    def test_upsert_preserves_field_when_new_value_is_none(self, repo, db_session):
        """Upsert with None fields does not overwrite existing non-None values."""
        repo.upsert(
            _make_exercise("preserve-001", difficulty="hard", status="complete")
        )
        db_session.commit()

        # New exercise with difficulty=None should not overwrite "hard"
        updated = _make_exercise("preserve-001", status="in_progress")
        # difficulty is not set, defaults to None
        repo.upsert(updated)
        db_session.commit()

        loaded = repo.get_by_exercise_id("preserve-001")
        assert loaded.difficulty == "hard"  # preserved, not overwritten
        assert loaded.status == "in_progress"  # updated

    def test_find_by_filters_exercise_type(self, repo, db_session):
        repo.upsert(_make_exercise("type-mc", type="multichoice"))
        repo.upsert(_make_exercise("type-es", type="essay"))
        db_session.commit()

        results = repo.find_by_filters(exercise_type="multichoice")
        assert len(results) == 1
        assert results[0].exercise_id == "type-mc"

    def test_find_by_filters_combined(self, repo, db_session):
        repo.upsert(_make_exercise("combo-1", difficulty="easy", status="complete"))
        repo.upsert(_make_exercise("combo-2", difficulty="easy", status="placeholder"))
        repo.upsert(_make_exercise("combo-3", difficulty="hard", status="complete"))
        db_session.commit()

        results = repo.find_by_filters(difficulty="easy", status="complete")
        assert len(results) == 1
        assert results[0].exercise_id == "combo-1"

    def test_get_orphans(self, repo, db_session):
        repo.upsert(_make_exercise("orphan-001", source_path="/nonexistent/path.tex"))
        db_session.commit()

        orphans = repo.get_orphans()
        assert len(orphans) == 1
        assert orphans[0].exercise_id == "orphan-001"
