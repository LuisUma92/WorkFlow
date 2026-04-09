"""Tests for SqlEvalTemplateRepo, SqlItemRepo, SqlCourseRepo."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.academic import (
    Course,
    EvaluationItem,
    EvaluationTemplate,
    Institution,
    Item,
)
from workflow.db.repos.sqlalchemy import (
    SqlCourseRepo,
    SqlEvalTemplateRepo,
    SqlItemRepo,
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
    ucr = Institution(short_name="UCR", full_name="Universidad de Costa Rica",
                      cycle_weeks=16, cycle_name="Semestre")
    ufide = Institution(short_name="UFide", full_name="Universidad Fidélitas",
                        cycle_weeks=15, cycle_name="Cuatrimestre")
    db_session.add_all([ucr, ufide])
    db_session.flush()
    return {"UCR": ucr, "UFide": ufide}


class TestSqlEvalTemplateRepo:
    def test_list_all_empty(self, db_session):
        repo = SqlEvalTemplateRepo(db_session)
        assert repo.list_all() == []

    def test_list_all_returns_templates(self, db_session, seed_institutions):
        inst = seed_institutions["UFide"]
        tmpl = EvaluationTemplate(
            institution_id=inst.id, name="Estudio de caso"
        )
        db_session.add(tmpl)
        db_session.flush()

        repo = SqlEvalTemplateRepo(db_session)
        results = repo.list_all()
        assert len(results) == 1
        assert results[0].name == "Estudio de caso"

    def test_list_all_filter_by_institution(self, db_session, seed_institutions):
        for name, inst in seed_institutions.items():
            db_session.add(
                EvaluationTemplate(institution_id=inst.id, name=f"Eval {name}")
            )
        db_session.flush()

        repo = SqlEvalTemplateRepo(db_session)
        ucr_only = repo.list_all(institution="UCR")
        assert len(ucr_only) == 1
        assert ucr_only[0].name == "Eval UCR"

    def test_get_detail_loads_items(self, db_session, seed_institutions):
        inst = seed_institutions["UCR"]
        tmpl = EvaluationTemplate(institution_id=inst.id, name="Parcial")
        db_session.add(tmpl)
        db_session.flush()

        it = Item(
            name="SU - Info/Recordar",
            taxonomy_level="Recordar",
            taxonomy_domain="Información",
        )
        db_session.add(it)
        db_session.flush()

        ei = EvaluationItem(
            evaluation_id=tmpl.id, item_id=it.id,
            total_amount=2, points_per_item=5,
        )
        db_session.add(ei)
        db_session.flush()

        repo = SqlEvalTemplateRepo(db_session)
        detail = repo.get_detail(tmpl.id)
        assert detail is not None
        assert len(detail.evaluation_items) == 1
        assert detail.evaluation_items[0].item.name == "SU - Info/Recordar"

    def test_get_detail_nonexistent(self, db_session):
        repo = SqlEvalTemplateRepo(db_session)
        assert repo.get_detail(9999) is None


class TestSqlItemRepo:
    def test_list_all_empty(self, db_session):
        repo = SqlItemRepo(db_session)
        assert repo.list_all() == []

    def test_list_all_returns_items(self, db_session):
        db_session.add(Item(
            name="SU - Info/Recordar",
            taxonomy_level="Recordar",
            taxonomy_domain="Información",
        ))
        db_session.add(Item(
            name="Desarrollo - Proc. Mental/Aplicar",
            taxonomy_level="Usar-Aplicar",
            taxonomy_domain="Procedimiento Mental",
        ))
        db_session.flush()

        repo = SqlItemRepo(db_session)
        results = repo.list_all()
        assert len(results) == 2

    def test_list_all_filter_by_domain(self, db_session):
        db_session.add(Item(
            name="A", taxonomy_level="Recordar", taxonomy_domain="Información",
        ))
        db_session.add(Item(
            name="B", taxonomy_level="Usar-Aplicar",
            taxonomy_domain="Procedimiento Mental",
        ))
        db_session.flush()

        repo = SqlItemRepo(db_session)
        results = repo.list_all(domain="Información")
        assert len(results) == 1
        assert results[0].name == "A"

    def test_list_all_filter_by_level(self, db_session):
        db_session.add(Item(
            name="A", taxonomy_level="Recordar", taxonomy_domain="Información",
        ))
        db_session.add(Item(
            name="B", taxonomy_level="Comprender", taxonomy_domain="Información",
        ))
        db_session.flush()

        repo = SqlItemRepo(db_session)
        results = repo.list_all(level="Comprender")
        assert len(results) == 1
        assert results[0].name == "B"


class TestSqlCourseRepo:
    def test_list_all_empty(self, db_session):
        repo = SqlCourseRepo(db_session)
        assert repo.list_all() == []

    def test_list_all_returns_courses(self, db_session, seed_institutions):
        inst = seed_institutions["UCR"]
        db_session.add(Course(
            institution_id=inst.id, code="FI-201", name="Física II",
        ))
        db_session.flush()

        repo = SqlCourseRepo(db_session)
        results = repo.list_all()
        assert len(results) == 1
        assert results[0].code == "FI-201"

    def test_list_all_filter_by_institution(self, db_session, seed_institutions):
        for name, inst in seed_institutions.items():
            db_session.add(Course(
                institution_id=inst.id, code=f"C-{name}", name=f"Course {name}",
            ))
        db_session.flush()

        repo = SqlCourseRepo(db_session)
        ufide_only = repo.list_all(institution="UFide")
        assert len(ufide_only) == 1
        assert ufide_only[0].code == "C-UFide"
