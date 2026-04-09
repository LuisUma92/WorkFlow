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
        short_name="UCR",
        full_name="Universidad de Costa Rica",
        cycle_weeks=16,
        cycle_name="Semestre",
    )
    ufide = Institution(
        short_name="UFide",
        full_name="Universidad Fidélitas",
        cycle_weeks=15,
        cycle_name="Cuatrimestre",
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

    def test_evaluation_template_accepts_description(
        self, db_session, seed_institutions
    ):
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
            name="A",
            taxonomy_level="Recordar",
            taxonomy_domain="Información",
        )
        it2 = Item(
            name="B",
            taxonomy_level="Comprender",
            taxonomy_domain="Información",
        )
        db_session.add_all([it1, it2])
        db_session.flush()

        db_session.add(
            EvaluationItem(
                evaluation_id=tmpl.id,
                item_id=it1.id,
                total_amount=2,
                points_per_item=5,
            )
        )
        db_session.add(
            EvaluationItem(
                evaluation_id=tmpl.id,
                item_id=it2.id,
                total_amount=3,
                points_per_item=10,
            )
        )
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
            db_session,
            institution_short_name="UFide",
            name="Parcial",
        )
        t2 = create_evaluation_template(
            db_session,
            institution_short_name="UCR",
            name="Parcial",
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
            db_session,
            institution_short_name="UCR",
            name="Parcial",
        )
        it = create_item(
            db_session,
            name="SU",
            taxonomy_level="Recordar",
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
                db_session,
                template_id=9999,
                item_id=1,
                amount=1,
                points_per_item=1,
            )

    def test_add_item_rejects_invalid_item(self, db_session, seed_institutions):
        from workflow.evaluation.service import (
            add_evaluation_item,
            create_evaluation_template,
        )

        tmpl = create_evaluation_template(
            db_session,
            institution_short_name="UCR",
            name="Parcial",
        )
        db_session.flush()

        with pytest.raises(ValueError, match="[Ii]tem"):
            add_evaluation_item(
                db_session,
                template_id=tmpl.id,
                item_id=9999,
                amount=1,
                points_per_item=1,
            )


# ── P2: Course creation ──────────────────────────────────────────────────


class TestCreateCourse:
    def test_create_course_basic(self, db_session, seed_institutions):
        from workflow.evaluation.service import create_course

        c = create_course(
            db_session,
            institution_short_name="UCR",
            code="FI-201",
            name="Física II",
        )
        assert c.id is not None
        assert c.code == "FI-201"
        assert c.name == "Física II"
        assert c.institution.short_name == "UCR"

    def test_create_course_with_schedule(self, db_session, seed_institutions):
        from workflow.evaluation.service import create_course

        c = create_course(
            db_session,
            institution_short_name="UFide",
            code="MAT-101",
            name="Cálculo I",
            lectures_per_week=4,
            hours_per_lecture=1,
        )
        assert c.lectures_per_week == 4
        assert c.hours_per_lecture == 1

    def test_create_course_rejects_unknown_institution(self, db_session):
        from workflow.evaluation.service import create_course

        with pytest.raises(ValueError, match="Institution"):
            create_course(
                db_session,
                institution_short_name="NONEXIST",
                code="X-1",
                name="Test",
            )

    def test_create_course_rejects_duplicate_code(self, db_session, seed_institutions):
        from workflow.evaluation.service import create_course

        create_course(
            db_session,
            institution_short_name="UCR",
            code="FI-201",
            name="Física II",
        )
        db_session.flush()

        with pytest.raises(ValueError, match="[Dd]uplicate"):
            create_course(
                db_session,
                institution_short_name="UCR",
                code="FI-201",
                name="Física II diferente",
            )

    def test_create_course_same_code_different_inst_ok(
        self,
        db_session,
        seed_institutions,
    ):
        from workflow.evaluation.service import create_course

        c1 = create_course(
            db_session,
            institution_short_name="UCR",
            code="FI-201",
            name="Física II",
        )
        c2 = create_course(
            db_session,
            institution_short_name="UFide",
            code="FI-201",
            name="Física II",
        )
        assert c1.id != c2.id


# ── P2: Edit operations ──────────────────────────────────────────────────


class TestRenameEvaluationTemplate:
    def test_rename_template(self, db_session, seed_institutions):
        from workflow.evaluation.service import (
            create_evaluation_template,
            rename_evaluation_template,
        )

        tmpl = create_evaluation_template(
            db_session,
            institution_short_name="UCR",
            name="Parcial 1",
        )
        db_session.flush()

        renamed = rename_evaluation_template(
            db_session, template_id=tmpl.id, new_name="Examen final"
        )
        assert renamed.name == "Examen final"

    def test_rename_rejects_nonexistent(self, db_session):
        from workflow.evaluation.service import rename_evaluation_template

        with pytest.raises(ValueError, match="[Tt]emplate"):
            rename_evaluation_template(db_session, template_id=9999, new_name="X")

    def test_rename_rejects_duplicate(self, db_session, seed_institutions):
        from workflow.evaluation.service import (
            create_evaluation_template,
            rename_evaluation_template,
        )

        create_evaluation_template(
            db_session,
            institution_short_name="UCR",
            name="Parcial 1",
        )
        t2 = create_evaluation_template(
            db_session,
            institution_short_name="UCR",
            name="Parcial 2",
        )
        db_session.flush()

        with pytest.raises(ValueError, match="[Dd]uplicate"):
            rename_evaluation_template(
                db_session, template_id=t2.id, new_name="Parcial 1"
            )


class TestRemoveEvaluationItem:
    def test_remove_item_from_template(self, db_session, seed_institutions):
        from workflow.evaluation.service import (
            add_evaluation_item,
            create_evaluation_template,
            create_item,
            remove_evaluation_item,
        )

        tmpl = create_evaluation_template(
            db_session,
            institution_short_name="UCR",
            name="Parcial",
        )
        it = create_item(
            db_session,
            name="SU",
            taxonomy_level="Recordar",
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
        db_session.flush()

        result = remove_evaluation_item(db_session, evaluation_item_id=ei.id)
        assert result is True

        # Verify it's gone
        assert db_session.get(EvaluationItem, ei.id) is None

    def test_remove_nonexistent_returns_false(self, db_session):
        from workflow.evaluation.service import remove_evaluation_item

        result = remove_evaluation_item(db_session, evaluation_item_id=9999)
        assert result is False

    def test_remove_rejects_wrong_template(self, db_session, seed_institutions):
        from workflow.evaluation.service import (
            add_evaluation_item,
            create_evaluation_template,
            create_item,
            remove_evaluation_item,
        )

        t1 = create_evaluation_template(
            db_session,
            institution_short_name="UCR",
            name="Template A",
        )
        t2 = create_evaluation_template(
            db_session,
            institution_short_name="UCR",
            name="Template B",
        )
        it = create_item(
            db_session,
            name="SU",
            taxonomy_level="Recordar",
            taxonomy_domain="Información",
        )
        db_session.flush()

        ei = add_evaluation_item(
            db_session,
            template_id=t1.id,
            item_id=it.id,
            amount=1,
            points_per_item=5,
        )
        db_session.flush()

        # Try to remove ei from wrong template
        with pytest.raises(ValueError, match="does not belong"):
            remove_evaluation_item(
                db_session,
                evaluation_item_id=ei.id,
                template_id=t2.id,
            )
