"""
Normalization tests for workflow.db models — Phase 1A.

Validates:
- GlobalBase.metadata.create_all succeeds
- configure_mappers() is clean
- Concept canonical location (knowledge.py, not notes.py)
- BibContent canonical location (bibliography.py, not knowledge.py)
- ExerciseConcept tablename has no typo
- Content ↔ Concept bidirectional relationship wiring
"""

from __future__ import annotations

import ast
import importlib
import pathlib

import pytest
from sqlalchemy import create_engine
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

        topic = Topic(main_topic_id=mt.id, name="Kinematics", serial_number=1)
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
