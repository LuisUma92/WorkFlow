"""Tests for evaluation service layer — create functions and validation.

RED phase: these tests define the expected behavior before implementation.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.academic import (
    EvaluationItem,
    EvaluationTemplate,
    Institution,
    Item,
)


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
def seed_institutions(db_session):
    ucr = Institution(
        short_name="UCR", full_name="Universidad de Costa Rica",
        cycle_weeks=16, cycle_name="Semestre",
    )
    ufide = Institution(
        short_name="UFide", full_name="Universidad Fidélitas",
        cycle_weeks=15, cycle_name="Cuatrimestre",
    )
    db_session.add_all([ucr, ufide])
    db_session.flush()
    return {"UCR": ucr, "UFide": ufide}


# ── Schema tests: new fields ─────────────────────────────────────────────


class TestSchemaAdditions:
    def test_item_accepts_item_type(self, db_session):
        """Item model should accept an optional item_type field."""
        it = Item(
            name="SU - Info/Recordar",
            taxonomy_level="Recordar",
            taxonomy_domain="Información",
            item_type="SU",
        )
        db_session.add(it)
        db_session.flush()

        loaded = db_session.get(Item, it.id)
        assert loaded.item_type == "SU"

    def test_item_type_defaults_to_none(self, db_session):
        """item_type should be optional, defaulting to None."""
        it = Item(
            name="Generic item",
            taxonomy_level="Recordar",
            taxonomy_domain="Información",
        )
        db_session.add(it)
        db_session.flush()

        loaded = db_session.get(Item, it.id)
        assert loaded.item_type is None

    def test_evaluation_template_accepts_description(self, db_session, seed_institutions):
        """EvaluationTemplate should accept a description field."""
        inst = seed_institutions["UFide"]
        tmpl = EvaluationTemplate(
            institution_id=inst.id,
            name="Estudio de caso",
            description="Evaluación basada en análisis de caso clínico.",
        )
        db_session.add(tmpl)
        db_session.flush()

        loaded = db_session.get(EvaluationTemplate, tmpl.id)
        assert loaded.description == "Evaluación basada en análisis de caso clínico."

    def test_evaluation_template_description_defaults_empty(
        self, db_session, seed_institutions
    ):
        """description should default to empty string."""
        inst = seed_institutions["UCR"]
        tmpl = EvaluationTemplate(institution_id=inst.id, name="Parcial")
        db_session.add(tmpl)
        db_session.flush()

        loaded = db_session.get(EvaluationTemplate, tmpl.id)
        assert loaded.description == ""

    def test_evaluation_template_total_points_property(
        self, db_session, seed_institutions
    ):
        """total_points property should compute sum(amount * points)."""
        inst = seed_institutions["UCR"]
        tmpl = EvaluationTemplate(institution_id=inst.id, name="Parcial")
        db_session.add(tmpl)
        db_session.flush()

        it1 = Item(
            name="A", taxonomy_level="Recordar", taxonomy_domain="Información",
        )
        it2 = Item(
            name="B", taxonomy_level="Comprender", taxonomy_domain="Información",
        )
        db_session.add_all([it1, it2])
        db_session.flush()

        db_session.add(EvaluationItem(
            evaluation_id=tmpl.id, item_id=it1.id,
            total_amount=2, points_per_item=5,
        ))
        db_session.add(EvaluationItem(
            evaluation_id=tmpl.id, item_id=it2.id,
            total_amount=3, points_per_item=10,
        ))
        db_session.flush()

        assert tmpl.total_points == 40  # 2*5 + 3*10

    def test_evaluation_template_total_points_empty(
        self, db_session, seed_institutions
    ):
        """total_points should be 0 when no items."""
        inst = seed_institutions["UCR"]
        tmpl = EvaluationTemplate(institution_id=inst.id, name="Empty")
        db_session.add(tmpl)
        db_session.flush()

        assert tmpl.total_points == 0


# ── Service layer tests ──────────────────────────────────────────────────


class TestCreateItem:
    def test_create_item_basic(self, db_session):
        from workflow.evaluation.service import create_item

        it = create_item(
            db_session,
            name="SU - Info/Recordar",
            taxonomy_level="Recordar",
            taxonomy_domain="Información",
        )
        assert it.id is not None
        assert it.name == "SU - Info/Recordar"
        assert it.taxonomy_level == "Recordar"
        assert it.taxonomy_domain == "Información"

    def test_create_item_with_item_type(self, db_session):
        from workflow.evaluation.service import create_item

        it = create_item(
            db_session,
            name="SU - Info/Recordar",
            taxonomy_level="Recordar",
            taxonomy_domain="Información",
            item_type="SU",
        )
        assert it.item_type == "SU"

    def test_create_item_rejects_invalid_level(self, db_session):
        from workflow.evaluation.service import create_item

        with pytest.raises(ValueError, match="taxonomy_level"):
            create_item(
                db_session,
                name="Bad",
                taxonomy_level="Inventado",
                taxonomy_domain="Información",
            )

    def test_create_item_rejects_invalid_domain(self, db_session):
        from workflow.evaluation.service import create_item

        with pytest.raises(ValueError, match="taxonomy_domain"):
            create_item(
                db_session,
                name="Bad",
                taxonomy_level="Recordar",
                taxonomy_domain="Inventado",
            )


class TestCreateEvaluationTemplate:
    def test_create_template_basic(self, db_session, seed_institutions):
        from workflow.evaluation.service import create_evaluation_template

        tmpl = create_evaluation_template(
            db_session,
            institution_short_name="UFide",
            name="Estudio de caso",
        )
        assert tmpl.id is not None
        assert tmpl.name == "Estudio de caso"
        assert tmpl.institution.short_name == "UFide"

    def test_create_template_with_description(self, db_session, seed_institutions):
        from workflow.evaluation.service import create_evaluation_template

        tmpl = create_evaluation_template(
            db_session,
            institution_short_name="UCR",
            name="Parcial 1",
            description="Primera evaluación parcial.",
        )
        assert tmpl.description == "Primera evaluación parcial."

    def test_create_template_rejects_unknown_institution(self, db_session):
        from workflow.evaluation.service import create_evaluation_template

        with pytest.raises(ValueError, match="Institution"):
            create_evaluation_template(
                db_session,
                institution_short_name="NONEXIST",
                name="Test",
            )

    def test_create_template_rejects_duplicate(self, db_session, seed_institutions):
        from workflow.evaluation.service import create_evaluation_template

        create_evaluation_template(
            db_session,
            institution_short_name="UFide",
            name="Estudio de caso",
        )
        db_session.flush()

        with pytest.raises(ValueError, match="[Dd]uplicate"):
            create_evaluation_template(
                db_session,
                institution_short_name="UFide",
                name="Estudio de caso",
            )

    def test_create_template_same_name_different_inst_ok(
        self, db_session, seed_institutions
    ):
        from workflow.evaluation.service import create_evaluation_template

        t1 = create_evaluation_template(
            db_session, institution_short_name="UFide", name="Parcial",
        )
        t2 = create_evaluation_template(
            db_session, institution_short_name="UCR", name="Parcial",
        )
        assert t1.id != t2.id


class TestAddEvaluationItem:
    def test_add_item_to_template(self, db_session, seed_institutions):
        from workflow.evaluation.service import (
            add_evaluation_item,
            create_evaluation_template,
            create_item,
        )

        tmpl = create_evaluation_template(
            db_session, institution_short_name="UCR", name="Parcial",
        )
        it = create_item(
            db_session, name="SU", taxonomy_level="Recordar",
            taxonomy_domain="Información",
        )
        db_session.flush()

        ei = add_evaluation_item(
            db_session,
            template_id=tmpl.id,
            item_id=it.id,
            amount=2,
            points_per_item=5,
        )
        assert ei.id is not None
        assert ei.total_amount == 2
        assert ei.points_per_item == 5

    def test_add_item_rejects_invalid_template(self, db_session):
        from workflow.evaluation.service import add_evaluation_item

        with pytest.raises(ValueError, match="[Tt]emplate"):
            add_evaluation_item(
                db_session, template_id=9999, item_id=1,
                amount=1, points_per_item=1,
            )

    def test_add_item_rejects_invalid_item(self, db_session, seed_institutions):
        from workflow.evaluation.service import (
            add_evaluation_item,
            create_evaluation_template,
        )

        tmpl = create_evaluation_template(
            db_session, institution_short_name="UCR", name="Parcial",
        )
        db_session.flush()

        with pytest.raises(ValueError, match="[Ii]tem"):
            add_evaluation_item(
                db_session, template_id=tmpl.id, item_id=9999,
                amount=1, points_per_item=1,
            )
