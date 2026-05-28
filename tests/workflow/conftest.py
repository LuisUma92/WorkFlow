"""Shared helpers for workflow test sub-package.

Plain functions (not fixtures) so they can be imported directly.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from workflow.db.models.knowledge import DisciplineArea, MainTopic, Topic, Content


def seed_concept_chain(
    session: Session,
    *,
    da_code: str = "FI0000",
    mt_code: str = "FI0001",
    domain: str = "Información",
) -> tuple[DisciplineArea, MainTopic, Topic, Content]:
    """Seed DisciplineArea -> MainTopic + Topic (rooted at DA) -> Content.

    Topic FK is now discipline_area_id (post Phase 4B re-root). MainTopic still
    created for callers that need a project-context object, but Topic no longer
    hangs off MainTopic.

    Returns (da, mt, tp, ct).
    """
    da = DisciplineArea(
        code=da_code, name="Fisica",
        discipline_num=10, topic_num=0, area_initials="FI",
    )
    session.add(da)
    session.flush()
    mt = MainTopic(code=mt_code, name="Mecanica", discipline_area_id=da.id)
    session.add(mt)
    session.flush()
    tp = Topic(discipline_area_id=da.id, name="Cinematica", serial_number=1)
    session.add(tp)
    session.flush()
    ct = Content(topic_id=tp.id, name="Movimiento rectilineo")
    session.add(ct)
    session.flush()
    return da, mt, tp, ct
