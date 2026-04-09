"""Evaluation service layer — create and validate operations.

Business logic for evaluation templates, taxonomy items, and their links.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.db.models.academic import (
    Course,
    EvaluationItem,
    EvaluationTemplate,
    Institution,
    Item,
    _TAXONOMY_DOMAINS,
    _TAXONOMY_LEVELS,
)


def create_item(
    session: Session,
    *,
    name: str,
    taxonomy_level: str,
    taxonomy_domain: str,
    item_type: str | None = None,
) -> Item:
    """Create a new taxonomy item with validation."""
    if taxonomy_level not in _TAXONOMY_LEVELS:
        raise ValueError(
            f"Invalid taxonomy_level '{taxonomy_level}'. "
            f"Valid: {', '.join(_TAXONOMY_LEVELS)}"
        )
    if taxonomy_domain not in _TAXONOMY_DOMAINS:
        raise ValueError(
            f"Invalid taxonomy_domain '{taxonomy_domain}'. "
            f"Valid: {', '.join(_TAXONOMY_DOMAINS)}"
        )

    item = Item(
        name=name,
        taxonomy_level=taxonomy_level,
        taxonomy_domain=taxonomy_domain,
        item_type=item_type,
    )
    session.add(item)
    session.flush()
    return item


def _resolve_institution(session: Session, short_name: str) -> Institution:
    """Look up institution by short_name, raise ValueError if not found."""
    stmt = select(Institution).where(Institution.short_name == short_name)
    inst = session.scalars(stmt).first()
    if inst is None:
        raise ValueError(f"Institution '{short_name}' not found.")
    return inst


def create_evaluation_template(
    session: Session,
    *,
    institution_short_name: str,
    name: str,
    description: str = "",
) -> EvaluationTemplate:
    """Create a new evaluation template with duplicate validation."""
    inst = _resolve_institution(session, institution_short_name)

    # Check for duplicate (same name + institution)
    stmt = select(EvaluationTemplate).where(
        EvaluationTemplate.institution_id == inst.id,
        EvaluationTemplate.name == name,
    )
    if session.scalars(stmt).first() is not None:
        raise ValueError(
            f"Duplicate: template '{name}' already exists for {institution_short_name}."
        )

    tmpl = EvaluationTemplate(
        institution_id=inst.id,
        name=name,
        description=description,
    )
    session.add(tmpl)
    session.flush()
    return tmpl


def add_evaluation_item(
    session: Session,
    *,
    template_id: int,
    item_id: int,
    amount: int,
    points_per_item: int,
) -> EvaluationItem:
    """Add an item to an evaluation template."""
    tmpl = session.get(EvaluationTemplate, template_id)
    if tmpl is None:
        raise ValueError(f"Template with id={template_id} not found.")

    item = session.get(Item, item_id)
    if item is None:
        raise ValueError(f"Item with id={item_id} not found.")

    ei = EvaluationItem(
        evaluation_id=template_id,
        item_id=item_id,
        total_amount=amount,
        points_per_item=points_per_item,
    )
    session.add(ei)
    session.flush()
    return ei


def remove_evaluation_item(
    session: Session,
    *,
    evaluation_item_id: int,
    template_id: int | None = None,
) -> bool:
    """Remove an evaluation item link. Returns True if deleted, False if not found.

    If template_id is provided, validates the item belongs to that template.
    """
    ei = session.get(EvaluationItem, evaluation_item_id)
    if ei is None:
        return False
    if template_id is not None and ei.evaluation_id != template_id:
        raise ValueError(
            f"EvaluationItem id={evaluation_item_id} does not belong to "
            f"template id={template_id}."
        )
    session.delete(ei)
    session.flush()
    return True


def rename_evaluation_template(
    session: Session,
    *,
    template_id: int,
    new_name: str,
) -> EvaluationTemplate:
    """Rename an evaluation template with duplicate validation."""
    tmpl = session.get(EvaluationTemplate, template_id)
    if tmpl is None:
        raise ValueError(f"Template with id={template_id} not found.")

    # Check for duplicate (same name + institution)
    stmt = select(EvaluationTemplate).where(
        EvaluationTemplate.institution_id == tmpl.institution_id,
        EvaluationTemplate.name == new_name,
        EvaluationTemplate.id != tmpl.id,
    )
    if session.scalars(stmt).first() is not None:
        inst = session.get(Institution, tmpl.institution_id)
        inst_name = inst.short_name if inst else "unknown"
        raise ValueError(
            f"Duplicate: template '{new_name}' already exists for {inst_name}."
        )

    tmpl.name = new_name
    session.flush()
    return tmpl


def create_course(
    session: Session,
    *,
    institution_short_name: str,
    code: str,
    name: str,
    lectures_per_week: int = 3,
    hours_per_lecture: int = 2,
) -> Course:
    """Create a new course with duplicate validation."""
    inst = _resolve_institution(session, institution_short_name)

    # Check for duplicate (same code + institution)
    stmt = select(Course).where(
        Course.institution_id == inst.id,
        Course.code == code,
    )
    if session.scalars(stmt).first() is not None:
        raise ValueError(
            f"Duplicate: course '{code}' already exists for {institution_short_name}."
        )

    c = Course(
        institution_id=inst.id,
        code=code,
        name=name,
        lectures_per_week=lectures_per_week,
        hours_per_lecture=hours_per_lecture,
    )
    session.add(c)
    session.flush()
    return c
