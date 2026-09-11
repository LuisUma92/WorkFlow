"""Characterization tests for resolve_taxonomy_filter (pre-refactor pin).

Pins the CURRENT behaviour of branches not covered by
tests/workflow/graph/test_filters.py, specifically:

- MainTopic resolved by numeric id that does not exist -> ValueError
- DisciplineArea resolved by numeric id that DOES exist -> resolves to id
- DisciplineArea resolved by numeric id that does not exist -> ValueError

These tests MUST pass against the unmodified
src/workflow/graph/collectors.py before any refactor is applied, and MUST
continue to pass unchanged afterwards (behaviour-preserving refactor).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import DisciplineArea, MainTopic
from workflow.graph.collectors import resolve_taxonomy_filter

# ── Helpers (copied from tests/workflow/graph/test_filters.py) ─────────────


def _make_session() -> Session:
    """Create an in-memory GlobalBase session with all tables."""
    engine = create_engine("sqlite:///:memory:")
    import workflow.db.models.academic  # noqa: F401
    import workflow.db.models.bibliography  # noqa: F401
    import workflow.db.models.exercises  # noqa: F401
    import workflow.db.models.notes  # noqa: F401

    GlobalBase.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class TestResolveTaxonomyFilterCharacterization:
    def test_unknown_main_topic_numeric_id_raises(self):
        session = _make_session()
        with pytest.raises(
            ValueError, match=r"MainTopic id='99999' not found"
        ):
            resolve_taxonomy_filter(session, main_topic="99999")

    def test_resolve_discipline_area_by_numeric_id(self):
        session = _make_session()
        da = DisciplineArea(
            code="FI0000",
            name="Fisica",
            discipline_num=10,
            topic_num=0,
            area_initials="FI",
        )
        session.add(da)
        session.flush()

        tf = resolve_taxonomy_filter(session, discipline_area=str(da.id))
        assert tf.discipline_area_ids == frozenset([da.id])

    def test_unknown_discipline_area_numeric_id_raises(self):
        session = _make_session()
        with pytest.raises(
            ValueError, match=r"DisciplineArea id='99999' not found"
        ):
            resolve_taxonomy_filter(session, discipline_area="99999")

    def test_all_three_axes_together_resolve(self):
        """Ordering/side-effect pin: main_topic, discipline_area, topic can
        all be supplied together and each populates its own frozenset,
        independent of resolution order in the function body.
        """
        session = _make_session()
        da = DisciplineArea(
            code="FI0001",
            name="Quimica",
            discipline_num=11,
            topic_num=0,
            area_initials="QU",
        )
        session.add(da)
        session.flush()

        mt = MainTopic(code="FI0002", name="Termo", discipline_area_id=da.id)
        session.add(mt)
        session.flush()

        from workflow.db.models.knowledge import Topic

        tp = Topic(discipline_area_id=da.id, name="Calor", serial_number=1)
        session.add(tp)
        session.flush()

        tf = resolve_taxonomy_filter(
            session,
            main_topic=mt.code,
            discipline_area=da.code,
            topic=str(tp.id),
        )
        assert tf.main_topic_ids == frozenset([mt.id])
        assert tf.discipline_area_ids == frozenset([da.id])
        assert tf.topic_ids == frozenset([tp.id])
