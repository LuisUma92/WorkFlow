"""Bulk import engine for `workflow topic import`.

Loads a YAML file describing the full DisciplineArea → Topic → Content → Concept
hierarchy and persists it atomically (or rolls back on dry_run).

Public API
----------
load_yaml(path) -> dict
validate_schema(data) -> None   # raises ImportSchemaError
import_hierarchy(session, data, *, discipline_area_override=None, dry_run=False) -> ImportResult
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.concept.service import ConceptError, DuplicateCode, add_concept
from workflow.content.service import (
    ContentServiceError,
    DuplicateContent,
    add_content,
)
from workflow.db.models.knowledge import (
    Content,
    DisciplineArea,
    Topic,
)
from workflow.topic.import_types import ImportResult, RowError
from workflow.topic.service import (
    DisciplineAreaNotFound,
    DuplicateTopic,
    TopicError,
    add_topic,
)

__all__ = [
    "ImportSchemaError",
    "load_yaml",
    "validate_schema",
    "import_hierarchy",
]


# ── Schema error ─────────────────────────────────────────────────────────────


class ImportSchemaError(Exception):
    """Raised for malformed structure or YAML parse errors (CLI → exit 1)."""


# ── YAML loading ─────────────────────────────────────────────────────────────


def load_yaml(path: str | Path) -> dict:
    """Load and parse a YAML file.

    Returns:
        Parsed YAML as a dict.

    Raises:
        ImportSchemaError: on YAML parse error or if the top-level value is not a dict.
    """
    try:
        with open(path) as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ImportSchemaError(f"YAML parse error in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ImportSchemaError(
            f"{path}: top-level value must be a mapping, got {type(data).__name__}"
        )
    return data


# ── Schema validation ─────────────────────────────────────────────────────────


def validate_schema(data: dict) -> None:  # noqa: C901 (complexity OK for validation)
    """Validate the bulk-import YAML structure.

    Raises:
        ImportSchemaError: with a descriptive message on the first violation.
    """
    if not isinstance(data.get("discipline_area_code"), str):
        raise ImportSchemaError(
            "'discipline_area_code' is required and must be a string."
        )

    topics = data.get("topics")
    if not isinstance(topics, list):
        raise ImportSchemaError("'topics' is required and must be a list.")

    for ti, topic in enumerate(topics):
        _check_str(topic, "name", f"topics[{ti}]")
        if not isinstance(topic.get("serial"), int):
            raise ImportSchemaError(
                f"topics[{ti}]: 'serial' is required and must be an int."
            )
        contents = topic.get("contents")
        if not isinstance(contents, list):
            raise ImportSchemaError(
                f"topics[{ti}]: 'contents' is required and must be a list."
            )

        for ci, content in enumerate(contents):
            _check_str(content, "name", f"topics[{ti}].contents[{ci}]")
            concepts = content.get("concepts")
            if not isinstance(concepts, list):
                raise ImportSchemaError(
                    f"topics[{ti}].contents[{ci}]: 'concepts' is required and must be a list."
                )

            for ki, concept in enumerate(concepts):
                ctx = f"topics[{ti}].contents[{ci}].concepts[{ki}]"
                _check_str(concept, "code", ctx)
                _check_str(concept, "label", ctx)
                _check_str(concept, "domain", ctx)
                parent_code = concept.get("parent_code")
                if parent_code is not None and not isinstance(parent_code, str):
                    raise ImportSchemaError(
                        f"{ctx}: 'parent_code' must be a string or null."
                    )


def _check_str(mapping: Any, key: str, ctx: str) -> None:
    if not isinstance(mapping.get(key), str):
        raise ImportSchemaError(f"{ctx}: '{key}' is required and must be a string.")


# ── Import engine ─────────────────────────────────────────────────────────────


# ── Private helpers (reduce cyclomatic complexity of import_hierarchy) ─────────


class _Counters:
    """Mutable accumulator for import run statistics."""

    __slots__ = ("topics", "contents", "concepts", "skipped", "errors")

    def __init__(self) -> None:
        self.topics = 0
        self.contents = 0
        self.concepts = 0
        self.skipped = 0
        self.errors: list[RowError] = []


def _import_concept(
    session: Session,
    concept_data: dict,
    content_id: int,
    counters: _Counters,
) -> None:
    k_code: str = concept_data["code"]
    try:
        add_concept(
            session,
            code=k_code,
            label=concept_data["label"],
            content_id=content_id,
            domain=concept_data["domain"],
            parent_code=concept_data.get("parent_code"),
            description=concept_data.get("description") or None,
        )
        session.flush()
        counters.concepts += 1
    except DuplicateCode:
        counters.skipped += 1
    except ConceptError as exc:
        # ConceptError is the base for ContentNotFound / ParentNotFound. These
        # app-level validation errors are raised BEFORE the row is added to the
        # session, so the session stays clean and we record + continue. A genuine
        # DB error from flush() is deliberately NOT caught: it propagates and
        # aborts the whole run (no poisoned-session cascade). See ADR-0018.
        counters.errors.append(RowError("concept", k_code, str(exc)))


def _import_content(
    session: Session,
    content_data: dict,
    topic_id: int,
    counters: _Counters,
) -> None:
    c_name: str = content_data["name"]
    try:
        content = add_content(session, topic_id=topic_id, name=c_name)
        session.flush()
        content_id = content.id
        counters.contents += 1
    except DuplicateContent:
        existing = session.scalars(
            select(Content).where(
                Content.topic_id == topic_id,
                Content.name == c_name,
            )
        ).first()
        if existing is None:
            counters.errors.append(RowError("content", c_name, "Duplicate but lookup failed."))
            return
        content_id = existing.id
        counters.skipped += 1
    except ContentServiceError as exc:
        counters.errors.append(RowError("content", c_name, str(exc)))
        return

    for concept_data in content_data["concepts"]:
        _import_concept(session, concept_data, content_id, counters)


def _import_topic(
    session: Session,
    topic_data: dict,
    da_code: str,
    da_id: int,
    counters: _Counters,
) -> None:
    t_name: str = topic_data["name"]
    serial: int = topic_data["serial"]
    try:
        topic = add_topic(
            session,
            name=t_name,
            discipline_area_code=da_code,
            serial_number=serial,
        )
        session.flush()
        topic_id = topic.id
        counters.topics += 1
    except DuplicateTopic:
        existing = session.scalars(
            select(Topic).where(
                Topic.discipline_area_id == da_id,
                Topic.serial_number == serial,
            )
        ).first()
        if existing is None:
            counters.errors.append(RowError("topic", t_name, "Duplicate but lookup failed."))
            return
        topic_id = existing.id
        counters.skipped += 1
    except TopicError as exc:
        counters.errors.append(RowError("topic", t_name, str(exc)))
        return

    for content_data in topic_data["contents"]:
        _import_content(session, content_data, topic_id, counters)


# ── Public engine ─────────────────────────────────────────────────────────────


def import_hierarchy(
    session: Session,
    data: dict,
    *,
    discipline_area_override: str | None = None,
    dry_run: bool = False,
) -> ImportResult:
    """Walk the YAML data dict and persist the full hierarchy.

    Steps:
    1. validate_schema(data)
    2. Resolve DisciplineArea — raises DisciplineAreaNotFound before any write.
    3. Walk topics → contents → concepts, accumulating counters and RowErrors.
    4. dry_run → rollback; else commit. Return ImportResult.

    Raises:
        ImportSchemaError:        malformed data (before any writes).
        DisciplineAreaNotFound:   unknown DA code (before any writes, CLI → exit 2).
    """
    validate_schema(data)

    da_code: str = discipline_area_override or data["discipline_area_code"]
    da = session.scalars(
        select(DisciplineArea).where(DisciplineArea.code == da_code)
    ).first()
    if da is None:
        raise DisciplineAreaNotFound(f"DisciplineArea code {da_code!r} not found.")

    counters = _Counters()
    for topic_data in data["topics"]:
        _import_topic(session, topic_data, da_code, da.id, counters)

    result = ImportResult(
        created_topics=counters.topics,
        created_contents=counters.contents,
        created_concepts=counters.concepts,
        skipped=counters.skipped,
        errors=tuple(counters.errors),
        dry_run=dry_run,
    )

    if dry_run:
        session.rollback()
    else:
        session.commit()

    return result
