"""
Normalization tests for workflow.db models — Phase 1A + Phase 4B.

Validates:
- GlobalBase.metadata.create_all succeeds
- configure_mappers() is clean
- Concept canonical location (knowledge.py, not notes.py)
- BibContent canonical location (bibliography.py, not knowledge.py)
- ExerciseConcept tablename has no typo
- Content ↔ Concept bidirectional relationship wiring
- Topic rooted at DisciplineArea (not MainTopic) — Phase 4B
- MainTopicSyllabus composite PK + cascade — Phase 4B
- Concept.main_topic returns None gracefully after re-root — Phase 4B
"""

from __future__ import annotations

import ast
import importlib
import pathlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, configure_mappers

from workflow.db.base import GlobalBase

_MODELS_SRC = pathlib.Path(__file__).parents[3] / "src" / "workflow" / "db" / "models"


# ---------------------------------------------------------------------------
# 1. create_all succeeds
# ---------------------------------------------------------------------------

def test_create_all_succeeds():
    """GlobalBase.metadata.create_all must succeed on a fresh in-memory DB."""
    import workflow.db.models  # noqa: F401 — registers all GlobalBase models

    engine = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(engine)
    engine.dispose()


# ---------------------------------------------------------------------------
# 2. configure_mappers raises no error
# ---------------------------------------------------------------------------

def test_mapper_configuration_clean():
    """configure_mappers() must complete without ArgumentError/InvalidRequestError."""
    from sqlalchemy.exc import ArgumentError, InvalidRequestError

    import workflow.db.models  # noqa: F401

    try:
        configure_mappers()
    except (ArgumentError, InvalidRequestError) as exc:
        pytest.fail(f"configure_mappers() raised: {exc}")


# ---------------------------------------------------------------------------
# 3. Concept canonical location
# ---------------------------------------------------------------------------

def test_concept_canonical_location():
    """Concept lives in workflow.db.models.knowledge and NOT in notes."""
    from workflow.db.models.knowledge import Concept as ConceptFromKnowledge
    from workflow.db.models import Concept as ConceptFromModels

    # Re-exported via __init__ must be the same object
    assert ConceptFromKnowledge is ConceptFromModels

    # Must NOT be an attribute of notes module
    notes_mod = importlib.import_module("workflow.db.models.notes")
    assert not hasattr(notes_mod, "Concept"), (
        "Concept should NOT be importable from workflow.db.models.notes"
    )


# ---------------------------------------------------------------------------
# 4. BibContent canonical location (AST check avoids triggering import issues)
# ---------------------------------------------------------------------------

def test_bib_content_canonical_location():
    """BibContent must be defined in bibliography.py, not in knowledge.py."""
    bib_source = (_MODELS_SRC / "bibliography.py").read_text()
    knowledge_source = (_MODELS_SRC / "knowledge.py").read_text()

    bib_tree = ast.parse(bib_source)
    knowledge_tree = ast.parse(knowledge_source)

    def class_names(tree):
        return {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}

    assert "BibContent" in class_names(bib_tree), (
        "BibContent must be defined in bibliography.py"
    )
    assert "BibContent" not in class_names(knowledge_tree), (
        "BibContent must NOT be defined in knowledge.py"
    )


# ---------------------------------------------------------------------------
# 5. ExerciseConcept tablename (AST check — parallel agent owns exercises.py)
# ---------------------------------------------------------------------------

def test_exercise_concept_tablename():
    """ExerciseConcept.__tablename__ must be 'exercise_concept', not 'exercise_contcept'.

    Uses AST to avoid importing exercises.py in case other bugs remain.
    This test turns RED until the parallel agent fixes the typo.
    """
    src_text = (_MODELS_SRC / "exercises.py").read_text()
    tree = ast.parse(src_text)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ExerciseConcept":
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and stmt.targets[0].id == "__tablename__"
                    and isinstance(stmt.value, ast.Constant)
                ):
                    tablename = stmt.value.value
                    assert tablename == "exercise_concept", (
                        f"ExerciseConcept.__tablename__ == {tablename!r}; "
                        f"expected 'exercise_concept' — fix typo in exercises.py"
                    )
                    return
            pytest.fail("ExerciseConcept class found but no __tablename__ assignment")
    pytest.fail("ExerciseConcept class not found in exercises.py")


# ---------------------------------------------------------------------------
# 6. Content ↔ Concept bidirectional relationship
# ---------------------------------------------------------------------------

def test_concept_content_relationship():
    """Content.concepts ↔ Concept.content back_populates must be wired correctly."""
    import workflow.db.models  # noqa: F401

    from workflow.db.models.knowledge import (
        Concept,
        Content,
        DisciplineArea,
        MainTopic,
        Topic,
    )

    engine = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(engine)

    with Session(engine) as session:
        da = DisciplineArea(
            code="FI0101",
            name="Physics",
            dewey="530",
            discipline_num=1,
            topic_num=1,
            area_initials="FI",
        )
        session.add(da)
        session.flush()

        mt = MainTopic(
            name="Mechanics",
            code="FI01",
            ddc_mds="",
            discipline_area_id=da.id,
        )
        session.add(mt)
        session.flush()

        topic = Topic(discipline_area_id=da.id, name="Kinematics", serial_number=1)
        session.add(topic)
        session.flush()

        content = Content(topic_id=topic.id, name="Linear motion")
        session.add(content)
        session.flush()

        concept = Concept(
            content_id=content.id,
            domain="Información",
            code="linear-motion",
            label="Linear Motion",
        )
        session.add(concept)
        session.flush()

        # Verify bidirectional relationship
        assert concept.content.id == content.id
        assert concept in content.concepts

    engine.dispose()


# ---------------------------------------------------------------------------
# Phase 4B — Topic re-root at DisciplineArea
# ---------------------------------------------------------------------------

def _make_engine_with_schema():
    """Return a fresh in-memory engine with the full GlobalBase schema."""
    import workflow.db.models  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(engine)
    return engine


def test_topic_rooted_at_discipline_area():
    """Topic must have discipline_area_id and must NOT have main_topic_id."""
    from workflow.db.models.knowledge import DisciplineArea, Topic

    engine = _make_engine_with_schema()
    with Session(engine) as session:
        da = DisciplineArea(
            code="FI0101", name="Physics", dewey="530",
            discipline_num=1, topic_num=1, area_initials="FI",
        )
        session.add(da)
        session.flush()

        topic = Topic(discipline_area_id=da.id, name="Kinematics", serial_number=1)
        session.add(topic)
        session.flush()

        assert topic.discipline_area_id == da.id

        # main_topic_id must NOT exist as a mapped column
        assert not hasattr(topic, "main_topic_id"), (
            "Topic.main_topic_id must be removed after Phase 4B re-root"
        )

    engine.dispose()


def test_topic_unique_serial_per_area():
    """Two Topics with same (discipline_area_id, serial_number) must raise IntegrityError."""
    from workflow.db.models.knowledge import DisciplineArea, Topic

    engine = _make_engine_with_schema()

    with Session(engine) as session:
        da1 = DisciplineArea(
            code="FI0101", name="Physics", dewey="530",
            discipline_num=1, topic_num=1, area_initials="FI",
        )
        da2 = DisciplineArea(
            code="MA0201", name="Mathematics", dewey="510",
            discipline_num=2, topic_num=2, area_initials="MA",
        )
        session.add_all([da1, da2])
        session.flush()

        # Two topics in same area, same serial → IntegrityError
        t1 = Topic(discipline_area_id=da1.id, name="Kinematics", serial_number=1)
        t2 = Topic(discipline_area_id=da1.id, name="Dynamics", serial_number=1)
        session.add_all([t1, t2])
        with pytest.raises(IntegrityError):
            session.flush()

    # Different area, same serial → OK
    engine2 = _make_engine_with_schema()
    with Session(engine2) as session:
        da1 = DisciplineArea(
            code="FI0101", name="Physics", dewey="530",
            discipline_num=1, topic_num=1, area_initials="FI",
        )
        da2 = DisciplineArea(
            code="MA0201", name="Mathematics", dewey="510",
            discipline_num=2, topic_num=2, area_initials="MA",
        )
        session.add_all([da1, da2])
        session.flush()

        t1 = Topic(discipline_area_id=da1.id, name="Kinematics", serial_number=1)
        t2 = Topic(discipline_area_id=da2.id, name="Algebra", serial_number=1)
        session.add_all([t1, t2])
        session.flush()  # must not raise

    engine.dispose()
    engine2.dispose()


def test_main_topic_syllabus_composite_pk():
    """MainTopicSyllabus composite PK (main_topic_id, topic_id) enforced."""
    from workflow.db.models.knowledge import DisciplineArea, MainTopic, MainTopicSyllabus, Topic

    engine = _make_engine_with_schema()
    with Session(engine) as session:
        da = DisciplineArea(
            code="FI0101", name="Physics", dewey="530",
            discipline_num=1, topic_num=1, area_initials="FI",
        )
        session.add(da)
        session.flush()

        mt = MainTopic(name="Mechanics", code="FI01", ddc_mds="", discipline_area_id=da.id)
        session.add(mt)
        session.flush()

        topic = Topic(discipline_area_id=da.id, name="Kinematics", serial_number=1)
        session.add(topic)
        session.flush()

        syl = MainTopicSyllabus(main_topic_id=mt.id, topic_id=topic.id, week_no=1, order_no=1)
        session.add(syl)
        session.flush()

        # Re-insert same composite PK → IntegrityError
        syl2 = MainTopicSyllabus(main_topic_id=mt.id, topic_id=topic.id, week_no=2, order_no=2)
        session.add(syl2)
        with pytest.raises(IntegrityError):
            session.flush()

    engine.dispose()


def test_main_topic_syllabus_cascade_delete_main_topic():
    """Deleting a MainTopic must cascade-delete its MainTopicSyllabus rows."""
    from workflow.db.models.knowledge import DisciplineArea, MainTopic, MainTopicSyllabus, Topic

    engine = _make_engine_with_schema()
    with Session(engine) as session:
        da = DisciplineArea(
            code="FI0101", name="Physics", dewey="530",
            discipline_num=1, topic_num=1, area_initials="FI",
        )
        session.add(da)
        session.flush()

        mt = MainTopic(name="Mechanics", code="FI01", ddc_mds="", discipline_area_id=da.id)
        session.add(mt)
        session.flush()

        topic = Topic(discipline_area_id=da.id, name="Kinematics", serial_number=1)
        session.add(topic)
        session.flush()

        syl = MainTopicSyllabus(main_topic_id=mt.id, topic_id=topic.id, week_no=1, order_no=1)
        session.add(syl)
        session.flush()
        syl_id = (mt.id, topic.id)

        session.delete(mt)
        session.flush()

        remaining = session.query(MainTopicSyllabus).filter_by(
            main_topic_id=syl_id[0], topic_id=syl_id[1]
        ).first()
        assert remaining is None, "Syllabus row must be cascade-deleted with MainTopic"

    engine.dispose()


def test_main_topic_syllabus_cascade_delete_topic():
    """Deleting a Topic must cascade-delete its MainTopicSyllabus rows."""
    from workflow.db.models.knowledge import DisciplineArea, MainTopic, MainTopicSyllabus, Topic

    engine = _make_engine_with_schema()
    with Session(engine) as session:
        da = DisciplineArea(
            code="FI0101", name="Physics", dewey="530",
            discipline_num=1, topic_num=1, area_initials="FI",
        )
        session.add(da)
        session.flush()

        mt = MainTopic(name="Mechanics", code="FI01", ddc_mds="", discipline_area_id=da.id)
        session.add(mt)
        session.flush()

        topic = Topic(discipline_area_id=da.id, name="Kinematics", serial_number=1)
        session.add(topic)
        session.flush()

        syl = MainTopicSyllabus(main_topic_id=mt.id, topic_id=topic.id, week_no=1, order_no=1)
        session.add(syl)
        session.flush()
        mt_id = mt.id
        topic_id = topic.id

        session.delete(topic)
        session.flush()

        remaining = session.query(MainTopicSyllabus).filter_by(
            main_topic_id=mt_id, topic_id=topic_id
        ).first()
        assert remaining is None, "Syllabus row must be cascade-deleted with Topic"

    engine.dispose()


def test_concept_main_topic_property_returns_none_post_reroot():
    """Concept.main_topic must return None gracefully when Topic has no main_topic_id."""
    from workflow.db.models.knowledge import Concept, Content, DisciplineArea, Topic

    engine = _make_engine_with_schema()
    with Session(engine) as session:
        da = DisciplineArea(
            code="FI0101", name="Physics", dewey="530",
            discipline_num=1, topic_num=1, area_initials="FI",
        )
        session.add(da)
        session.flush()

        topic = Topic(discipline_area_id=da.id, name="Kinematics", serial_number=1)
        session.add(topic)
        session.flush()

        content = Content(topic_id=topic.id, name="Linear motion")
        session.add(content)
        session.flush()

        concept = Concept(
            content_id=content.id, domain="Información",
            code="linear-motion-2", label="Linear Motion",
        )
        session.add(concept)
        session.flush()

        # After re-root, Topic has no main_topic_id → Concept.main_topic must be None
        result = concept.main_topic
        assert result is None, (
            f"Concept.main_topic must return None after re-root, got {result!r}"
        )

    engine.dispose()
