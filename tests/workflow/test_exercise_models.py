"""Tests for workflow.db.models.exercises — Exercise and ExerciseOption ORM."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.exercises import Exercise, ExerciseOption


def _enable_fk(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def db_session():
    """In-memory SQLite session with FK enforcement."""
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk)
    GlobalBase.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class TestExerciseModel:
    def test_create_exercise(self, db_session):
        ex = Exercise(
            exercise_id="phys-gauss-001",
            source_path="/home/luis/Documents/00EE/serway-ch01/ex001.tex",
            file_hash="abc123" * 10 + "abcd",
            status="complete",
            type="multichoice",
            difficulty="medium",
            taxonomy_level="Usar-Aplicar",
            taxonomy_domain="Procedimiento Mental",
            option_count=4,
        )
        db_session.add(ex)
        db_session.commit()

        loaded = db_session.get(Exercise, ex.id)
        assert loaded is not None
        assert loaded.exercise_id == "phys-gauss-001"
        assert loaded.status == "complete"
        assert loaded.type == "multichoice"

    def test_exercise_id_unique(self, db_session):
        ex1 = Exercise(
            exercise_id="unique-001",
            source_path="/path/a.tex",
            file_hash="a" * 64,
        )
        ex2 = Exercise(
            exercise_id="unique-001",
            source_path="/path/b.tex",
            file_hash="b" * 64,
        )
        db_session.add(ex1)
        db_session.commit()
        db_session.add(ex2)
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_default_values(self, db_session):
        ex = Exercise(
            exercise_id="defaults-001",
            source_path="/path/c.tex",
            file_hash="c" * 64,
        )
        db_session.add(ex)
        db_session.commit()

        loaded = db_session.get(Exercise, ex.id)
        assert loaded.status == "placeholder"
        assert loaded.penalty == 0.0
        assert loaded.has_images is False
        assert loaded.option_count == 0

    def test_repr(self, db_session):
        ex = Exercise(
            exercise_id="repr-001",
            source_path="/path/d.tex",
            file_hash="d" * 64,
            status="in_progress",
        )
        assert "repr-001" in repr(ex)
        assert "in_progress" in repr(ex)


class TestExerciseOptionModel:
    def test_create_options(self, db_session):
        ex = Exercise(
            exercise_id="opts-001",
            source_path="/path/e.tex",
            file_hash="e" * 64,
            option_count=3,
        )
        db_session.add(ex)
        db_session.flush()

        for i, (label, correct) in enumerate([("a", False), ("b", True), ("c", False)]):
            opt = ExerciseOption(
                exercise_id=ex.id,
                label=label,
                is_correct=correct,
                sort_order=i,
            )
            db_session.add(opt)

        db_session.commit()

        loaded = db_session.get(Exercise, ex.id)
        assert len(loaded.options) == 3
        correct_opts = [o for o in loaded.options if o.is_correct]
        assert len(correct_opts) == 1
        assert correct_opts[0].label == "b"

    def test_cascade_delete(self, db_session):
        ex = Exercise(
            exercise_id="cascade-001",
            source_path="/path/f.tex",
            file_hash="f" * 64,
        )
        db_session.add(ex)
        db_session.flush()

        opt = ExerciseOption(
            exercise_id=ex.id,
            label="a",
            sort_order=0,
        )
        db_session.add(opt)
        db_session.commit()

        db_session.delete(ex)
        db_session.commit()

        remaining = db_session.query(ExerciseOption).all()
        assert remaining == []

    def test_option_repr(self):
        opt_correct = ExerciseOption(label="a", is_correct=True, sort_order=0)
        opt_wrong = ExerciseOption(label="b", is_correct=False, sort_order=1)
        assert "✓" in repr(opt_correct)
        assert "✓" not in repr(opt_wrong)
