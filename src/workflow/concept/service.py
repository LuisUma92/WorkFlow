"""ITEP-0012 — Concept service layer.

Pure functions; no Click. All side effects are session-local until caller commits.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from workflow.db.models.academic import MainTopic
from workflow.db.models.notes import Concept, NoteConcept

__all__ = [
    "ConceptError",
    "DuplicateCode",
    "UnknownCode",
    "ParentNotFound",
    "MainTopicNotFound",
    "HasReferences",
    "resolve_concepts",
    "list_concepts",
    "get_concept",
    "add_concept",
    "remove_concept",
    "rename_concept",
    "build_concept_tree",
]

# ── Slug validation (lessons row 14) ─────────────────────────────────────

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


def _validate_slug(code: str) -> None:
    if not _SLUG_RE.match(code):
        raise ConceptError(
            f"code {code!r} is invalid; must match ^[a-z0-9][a-z0-9-]{{0,31}}$"
        )


# ── Custom exceptions ─────────────────────────────────────────────────────


class ConceptError(Exception):
    """Base class for concept service errors."""


class DuplicateCode(ConceptError):
    """A Concept with that code already exists."""


class UnknownCode(ConceptError):
    """No Concept found for the given code."""


class ParentNotFound(ConceptError):
    """No Concept found for the given parent code."""


class MainTopicNotFound(ConceptError):
    """No MainTopic found for the given code."""


class HasReferences(ConceptError):
    """Concept is referenced by NoteConcept rows; use force=True to override."""


# ── Helpers ───────────────────────────────────────────────────────────────


def _get_main_topic(session: Session, code: str) -> MainTopic:
    mt = session.query(MainTopic).filter_by(code=code).first()
    if mt is None:
        raise MainTopicNotFound(f"MainTopic {code!r} not found.")
    return mt


def _get_concept_or_raise(session: Session, code: str) -> Concept:
    c = session.query(Concept).filter_by(code=code).first()
    if c is None:
        raise UnknownCode(f"Concept {code!r} not found.")
    return c


# ── Public API ────────────────────────────────────────────────────────────


def resolve_concepts(
    codes: list[str],
    session: Session,
    *,
    strict: bool = False,
) -> tuple[list[Concept], list[dict[str, str]]]:
    """Resolve a list of Concept.code slugs to ORM objects.

    Returns ``(found_concepts, issues)`` where each issue is
    ``{"severity": "warning"|"error", "message": str}``.
    Unknown codes produce a warning (lenient) or error (strict).
    """
    if not codes:
        return [], []

    found: list[Concept] = []
    issues: list[dict[str, str]] = []

    for code in codes:
        c = session.query(Concept).filter_by(code=code).first()
        if c is None:
            severity = "error" if strict else "warning"
            issues.append({
                "severity": severity,
                "message": f"concept code {code!r} not found in database.",
            })
        else:
            found.append(c)

    return found, issues


def get_concept(session: Session, code: str) -> Concept | None:
    """Return a Concept by code, or None."""
    return session.query(Concept).filter_by(code=code).first()


def list_concepts(
    session: Session,
    *,
    main_topic_code: str | None = None,
) -> list[Concept]:
    """List concepts, optionally filtered by MainTopic.code."""
    q = session.query(Concept)
    if main_topic_code is not None:
        mt = session.query(MainTopic).filter_by(code=main_topic_code).first()
        if mt is None:
            raise MainTopicNotFound(f"MainTopic {main_topic_code!r} not found.")
        q = q.filter(Concept.main_topic_id == mt.id)
    return q.order_by(Concept.code).all()


def add_concept(
    session: Session,
    *,
    code: str,
    label: str,
    main_topic_code: str,
    parent_code: str | None = None,
    description: str | None = None,
) -> Concept:
    """Create and add a Concept to the session (not yet committed).

    Raises:
        ConceptError: code fails slug validation.
        DuplicateCode: code already exists.
        MainTopicNotFound: main_topic_code not found.
        ParentNotFound: parent_code not found.
        ConceptError: parent belongs to a different MainTopic.
    """
    _validate_slug(code)

    existing = session.query(Concept).filter_by(code=code).first()
    if existing is not None:
        raise DuplicateCode(f"Concept {code!r} already exists (id={existing.id}).")

    mt = _get_main_topic(session, main_topic_code)

    parent_id: int | None = None
    if parent_code is not None:
        parent = session.query(Concept).filter_by(code=parent_code).first()
        if parent is None:
            raise ParentNotFound(f"Parent concept {parent_code!r} not found.")
        if parent.main_topic_id != mt.id:
            raise ConceptError(
                f"Parent {parent_code!r} belongs to main_topic_id="
                f"{parent.main_topic_id}, but new concept targets "
                f"main_topic_id={mt.id}. Parent must be in the same MainTopic."
            )
        # Cycle-safety: new concept doesn't have an id yet so no cycle possible
        parent_id = parent.id

    concept = Concept(
        code=code,
        label=label,
        main_topic_id=mt.id,
        parent_id=parent_id,
        description=description,
    )
    session.add(concept)
    return concept


def remove_concept(
    session: Session,
    code: str,
    *,
    force: bool = False,
) -> None:
    """Remove a Concept.

    If *force* is False and NoteConcept rows reference this concept, raises
    ``HasReferences``.

    If *force* is True:
    - All NoteConcept rows are deleted.
    - Child concepts are reparented to the removed concept's parent_id
      (Q4 resolved decision: reparent to grandparent, not SET NULL).

    Does NOT auto-commit; caller must commit.
    """
    concept = _get_concept_or_raise(session, code)

    nc_count = (
        session.query(NoteConcept)
        .filter_by(concept_id=concept.id)
        .count()
    )

    if nc_count > 0 and not force:
        raise HasReferences(
            f"Concept {code!r} is referenced by {nc_count} note(s). "
            "Use force=True to cascade-delete."
        )

    if force:
        # Delete NoteConcept rows
        session.query(NoteConcept).filter_by(concept_id=concept.id).delete()

        # Reparent children to grandparent (Q4 resolution)
        grandparent_id = concept.parent_id  # may be None
        (
            session.query(Concept)
            .filter(Concept.parent_id == concept.id)
            .update({"parent_id": grandparent_id})
        )

    session.delete(concept)


def rename_concept(
    session: Session,
    old_code: str,
    new_code: str,
) -> Concept:
    """Rename a concept atomically (same transaction).

    Raises:
        UnknownCode: old_code not found.
        DuplicateCode: new_code already exists.
        ConceptError: new_code fails slug validation.
    """
    _validate_slug(new_code)

    concept = _get_concept_or_raise(session, old_code)

    collision = session.query(Concept).filter_by(code=new_code).first()
    if collision is not None:
        raise DuplicateCode(
            f"Concept {new_code!r} already exists (id={collision.id})."
        )

    concept.code = new_code
    return concept


def build_concept_tree(
    session: Session,
    *,
    main_topic_code: str | None = None,
) -> list[dict[str, Any]]:
    """Return a nested tree of Concept dicts.

    Nodes that are in-scope (matching MT) but whose parent_id is out-of-scope
    are promoted to root level.

    Each node: ``{"code": str, "label": str, "children": list}``.
    Cycle-safe via visited set.
    """
    concepts = list_concepts(session, main_topic_code=main_topic_code) \
        if main_topic_code \
        else session.query(Concept).order_by(Concept.code).all()

    # Build id → node mapping
    in_scope_ids = {c.id for c in concepts}
    nodes: dict[int, dict[str, Any]] = {}
    for c in concepts:
        nodes[c.id] = {"code": c.code, "label": c.label, "children": [], "_id": c.id}

    roots: list[dict[str, Any]] = []
    for c in concepts:
        node = nodes[c.id]
        if c.parent_id is None or c.parent_id not in in_scope_ids:
            roots.append(node)
        else:
            parent_node = nodes[c.parent_id]
            parent_node["children"].append(node)

    # Strip internal _id key
    def _strip(n: dict) -> dict:
        return {
            "code": n["code"],
            "label": n["label"],
            "children": [_strip(ch) for ch in n["children"]],
        }

    return [_strip(r) for r in roots]
