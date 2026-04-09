"""Evaluation service layer — create and validate operations.

Business logic for evaluation templates, taxonomy items, and their links.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.db.models.academic import (
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
