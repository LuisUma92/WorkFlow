"""ITEP-0012 — Concept service layer.

Pure functions; no Click. All side effects are session-local until caller commits.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from workflow.db.models.knowledge import (
    _TAXONOMY_DOMAINS,
    Concept,
    Content,
    DisciplineArea,
    MainTopic,
    Topic,
)
from workflow.db.models.notes import NoteConcept

__all__ = [
    "ConceptError",
    "DuplicateCode",
    "UnknownCode",
    "ParentNotFound",
    "MainTopicNotFound",
    "ContentNotFound",
    "HasReferences",
    "concept_main_topic",
    "concept_discipline_area",
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


class ContentNotFound(ConceptError):
    """No Content found for the given id."""


class HasReferences(ConceptError):
    """Concept is referenced by NoteConcept rows; use force=True to override."""


# ── Helpers ───────────────────────────────────────────────────────────────


def _get_concept_or_raise(session: Session, code: str) -> Concept:
    c = session.scalars(select(Concept).where(Concept.code == code)).first()
    if c is None:
        raise UnknownCode(f"Concept {code!r} not found.")
    return c


def _validate_domain(domain: str) -> None:
    if domain not in _TAXONOMY_DOMAINS:
        raise ConceptError(
            f"domain {domain!r} is invalid; must be one of {list(_TAXONOMY_DOMAINS)}"
        )


# ── Public API ────────────────────────────────────────────────────────────


def concept_main_topic(concept: Concept) -> "MainTopic | None":
    """Return the MainTopic associated with a Concept via its content chain.

    Deprecated: ``Concept.main_topic`` now always returns ``None`` because
    ``Topic.main_topic_id`` was removed in Phase 4B (Topic re-root). The
    concept→content→topic chain no longer carries a direct MainTopic FK.
    Use :func:`concept_discipline_area` instead to resolve the discipline area.

    Kept for back-compat; callers should migrate to ``concept_discipline_area``.
    """
    return concept.main_topic  # always None post-reroot


def concept_discipline_area(concept: Concept) -> "DisciplineArea | None":
    """Return the DisciplineArea for a Concept via content → topic → discipline_area.

    This is the recommended replacement for the deprecated
    :func:`concept_main_topic` after the Topic re-root (Phase 4B).

    Returns ``None`` if any link in the chain is missing (unloaded relationship
    or orphaned record). Callers must ensure the session is still open.
    """
    try:
        content: Content | None = concept.content
        if content is None:
            return None
        topic: Topic | None = content.topic
        if topic is None:
            return None
        return topic.discipline_area  # type: ignore[return-value]
    except Exception:
        return None


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
        c = session.scalars(select(Concept).where(Concept.code == code)).first()
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
    return session.scalars(select(Concept).where(Concept.code == code)).first()


def list_concepts(
    session: Session,
    *,
    main_topic_code: str | None = None,
) -> list[Concept]:
    """List concepts, optionally filtered by MainTopic.code."""
    if main_topic_code is not None:
        mt = session.scalars(
            select(MainTopic).where(MainTopic.code == main_topic_code)
        ).first()
        if mt is None:
            raise MainTopicNotFound(f"MainTopic {main_topic_code!r} not found.")
        # Post-Phase-4B: Topic is rooted at DisciplineArea; filter by the MT's DA.
        stmt = (
            select(Concept)
            .join(Content, Concept.content_id == Content.id)
            .join(Topic, Content.topic_id == Topic.id)
            .where(Topic.discipline_area_id == mt.discipline_area_id)
            .order_by(Concept.code)
        )
        return list(session.scalars(stmt).all())
    return list(session.scalars(select(Concept).order_by(Concept.code)).all())


def add_concept(
    session: Session,
    *,
    code: str,
    label: str,
    content_id: int,
    domain: str,
    parent_code: str | None = None,
    description: str | None = None,
) -> Concept:
    """Create and add a Concept to the session (not yet committed).

    Raises:
        ConceptError: code fails slug validation.
        ConceptError: domain is not a valid taxonomy domain.
        DuplicateCode: code already exists.
        ContentNotFound: content_id not found.
        ParentNotFound: parent_code not found.
        ConceptError: parent belongs to a different Content.
    """
    _validate_slug(code)
    _validate_domain(domain)

    existing = session.scalars(select(Concept).where(Concept.code == code)).first()
    if existing is not None:
        raise DuplicateCode(f"Concept {code!r} already exists (id={existing.id}).")

    content = session.get(Content, content_id)
    if content is None:
        raise ContentNotFound(f"Content id={content_id!r} not found.")

    parent_id: int | None = None
    if parent_code is not None:
        parent = session.scalars(
            select(Concept).where(Concept.code == parent_code)
        ).first()
        if parent is None:
            raise ParentNotFound(f"Parent concept {parent_code!r} not found.")
        if parent.content_id != content_id:
            raise ConceptError(
                f"Parent {parent_code!r} belongs to content_id="
                f"{parent.content_id}, but new concept targets "
                f"content_id={content_id}. Parent must be in the same Content."
            )
        # Cycle-safety: new concept doesn't have an id yet so no cycle possible
        parent_id = parent.id

    concept = Concept(
        code=code,
        label=label,
        content_id=content_id,
        domain=domain,
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

    nc_count = session.execute(
        select(func.count()).select_from(NoteConcept).where(
            NoteConcept.concept_id == concept.id
        )
    ).scalar_one()

    if nc_count > 0 and not force:
        raise HasReferences(
            f"Concept {code!r} is referenced by {nc_count} note(s). "
            "Use force=True to cascade-delete."
        )

    if force:
        # Delete NoteConcept rows
        session.execute(
            delete(NoteConcept).where(NoteConcept.concept_id == concept.id)
        )

        # Reparent children to grandparent (Q4 resolution)
        grandparent_id = concept.parent_id  # may be None
        session.execute(
            update(Concept)
            .where(Concept.parent_id == concept.id)
            .values(parent_id=grandparent_id)
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

    collision = session.scalars(select(Concept).where(Concept.code == new_code)).first()
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
    concepts = (
        list_concepts(session, main_topic_code=main_topic_code)
        if main_topic_code
        else list(session.scalars(select(Concept).order_by(Concept.code)).all())
    )

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
