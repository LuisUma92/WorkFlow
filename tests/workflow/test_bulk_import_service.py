"""TDD tests for workflow.topic.bulk_import — import engine.

Coverage targets:
1. success path — correct created counts + rows persisted
2. idempotency — 2nd run skips all, children still attach
3. dry_run — counts computed but NO rows persisted
4. unknown discipline_area → DisciplineAreaNotFound raised
5. invalid concept domain → RowError captured, others still created
6. validate_schema / load_yaml edge cases
7. discipline_area_override replaces file value
8. in-file parent_code resolves for concepts
"""
from __future__ import annotations

import textwrap

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.db.models.knowledge import Concept, Content, DisciplineArea, Topic
from workflow.topic.bulk_import import (
    ImportSchemaError,
    import_hierarchy,
    load_yaml,
    validate_schema,
)
from workflow.topic.import_types import ImportResult
from workflow.topic.service import DisciplineAreaNotFound


# ── Helpers ───────────────────────────────────────────────────────────────────


def _seed_da(session: Session, code: str = "FS01") -> DisciplineArea:
    area = DisciplineArea(
        code=code,
        name=f"Area {code}",
        discipline_num=1,
        topic_num=1,
        area_initials=code[:2],
    )
    session.add(area)
    session.commit()
    return area


def _minimal_data(da_code: str = "FS01") -> dict:
    """2 topics, 3 contents total, 3 concepts total."""
    return {
        "discipline_area_code": da_code,
        "topics": [
            {
                "name": "Cinemática",
                "serial": 1,
                "contents": [
                    {
                        "name": "Posición",
                        "concepts": [
                            {
                                "code": "fs01-kin-001",
                                "label": "Vector posición",
                                "domain": "Información",
                            }
                        ],
                    },
                    {
                        "name": "Velocidad",
                        "concepts": [
                            {
                                "code": "fs01-kin-002",
                                "label": "Velocidad media",
                                "domain": "Procedimiento Mental",
                            }
                        ],
                    },
                ],
            },
            {
                "name": "Dinámica",
                "serial": 2,
                "contents": [
                    {
                        "name": "Fuerza",
                        "concepts": [
                            {
                                "code": "fs01-dyn-001",
                                "label": "Segunda ley de Newton",
                                "domain": "Información",
                            }
                        ],
                    },
                ],
            },
        ],
    }


# ── 1. Success path ───────────────────────────────────────────────────────────


def test_success_creates_correct_counts(global_session):
    _seed_da(global_session)
    result = import_hierarchy(global_session, _minimal_data())

    assert isinstance(result, ImportResult)
    assert result.created_topics == 2
    assert result.created_contents == 3
    assert result.created_concepts == 3
    assert result.skipped == 0
    assert result.errors == ()
    assert result.dry_run is False


def test_success_rows_are_persisted(global_engine):
    """After import rows must be readable in a fresh session."""
    with Session(global_engine) as s1:
        _seed_da(s1)
        import_hierarchy(s1, _minimal_data())

    with Session(global_engine) as s2:
        topics = list(s2.scalars(select(Topic)).all())
        contents = list(s2.scalars(select(Content)).all())
        concepts = list(s2.scalars(select(Concept)).all())

    assert len(topics) == 2
    assert len(contents) == 3
    assert len(concepts) == 3


def test_success_persisted_topic_name(global_engine):
    with Session(global_engine) as s1:
        _seed_da(s1)
        import_hierarchy(s1, _minimal_data())

    with Session(global_engine) as s2:
        topic = s2.scalars(
            select(Topic).where(Topic.serial_number == 1)
        ).first()
        assert topic is not None
        assert topic.name == "Cinemática"


# ── 2. Idempotency ────────────────────────────────────────────────────────────


def test_idempotency_second_run_all_skipped(global_engine):
    with Session(global_engine) as s1:
        _seed_da(s1)
        import_hierarchy(s1, _minimal_data())

    with Session(global_engine) as s2:
        result2 = import_hierarchy(s2, _minimal_data())

    assert result2.created_topics == 0
    assert result2.created_contents == 0
    assert result2.created_concepts == 0
    assert result2.skipped == 2 + 3 + 3  # topics + contents + concepts
    assert result2.errors == ()


def test_idempotency_children_still_attached(global_engine):
    """After two runs concepts are still linked to their content."""
    with Session(global_engine) as s1:
        _seed_da(s1)
        import_hierarchy(s1, _minimal_data())

    with Session(global_engine) as s2:
        import_hierarchy(s2, _minimal_data())

    with Session(global_engine) as s3:
        concepts = list(s3.scalars(select(Concept)).all())
        assert len(concepts) == 3


# ── 3. dry_run ────────────────────────────────────────────────────────────────


def test_dry_run_returns_correct_counts(global_session):
    _seed_da(global_session)
    result = import_hierarchy(global_session, _minimal_data(), dry_run=True)

    assert result.created_topics == 2
    assert result.created_contents == 3
    assert result.created_concepts == 3
    assert result.dry_run is True


def test_dry_run_no_rows_persisted(global_engine):
    with Session(global_engine) as s1:
        _seed_da(s1)
        import_hierarchy(s1, _minimal_data(), dry_run=True)

    with Session(global_engine) as s2:
        topics = list(s2.scalars(select(Topic)).all())
        contents = list(s2.scalars(select(Content)).all())
        concepts = list(s2.scalars(select(Concept)).all())

    assert topics == []
    assert contents == []
    assert concepts == []


# ── 4. Unknown discipline_area ────────────────────────────────────────────────


def test_unknown_da_code_raises_before_writes(global_session):
    _seed_da(global_session)
    with pytest.raises(DisciplineAreaNotFound, match="BADCODE"):
        import_hierarchy(
            global_session,
            _minimal_data(),
            discipline_area_override="BADCODE",
        )


def test_unknown_da_no_rows_created_on_raise(global_engine):
    with Session(global_engine) as s1:
        _seed_da(s1)

    with Session(global_engine) as s2:
        with pytest.raises(DisciplineAreaNotFound):
            import_hierarchy(s2, _minimal_data(), discipline_area_override="NOPE")

    with Session(global_engine) as s3:
        assert list(s3.scalars(select(Topic)).all()) == []


# ── 5. Invalid domain → RowError ─────────────────────────────────────────────


def test_invalid_domain_skipped_as_error(global_session):
    """A concept with an invalid domain is captured as a RowError; others persist."""
    _seed_da(global_session)
    data = {
        "discipline_area_code": "FS01",
        "topics": [
            {
                "name": "Óptica",
                "serial": 10,
                "contents": [
                    {
                        "name": "Luz",
                        "concepts": [
                            {
                                "code": "fs01-opt-bad",
                                "label": "Bad domain",
                                "domain": "INVALID_DOMAIN",
                            },
                            {
                                "code": "fs01-opt-002",
                                "label": "Reflexión",
                                "domain": "Información",
                            },
                        ],
                    }
                ],
            }
        ],
    }
    result = import_hierarchy(global_session, data)

    assert result.has_errors
    assert len(result.errors) == 1
    assert result.errors[0].entity == "concept"
    assert result.errors[0].row == "fs01-opt-bad"
    # Good concept still created
    assert result.created_concepts == 1


# ── 6. validate_schema & load_yaml edge cases ─────────────────────────────────


def test_validate_schema_missing_topics():
    with pytest.raises(ImportSchemaError, match="topics"):
        validate_schema({"discipline_area_code": "FS01"})


def test_validate_schema_missing_discipline_area_code():
    with pytest.raises(ImportSchemaError, match="discipline_area_code"):
        validate_schema({"topics": []})


def test_validate_schema_topic_missing_name():
    with pytest.raises(ImportSchemaError, match="name"):
        validate_schema({
            "discipline_area_code": "FS01",
            "topics": [{"serial": 1, "contents": []}],
        })


def test_validate_schema_topic_missing_serial():
    with pytest.raises(ImportSchemaError, match="serial"):
        validate_schema({
            "discipline_area_code": "FS01",
            "topics": [{"name": "T", "contents": []}],
        })


def test_validate_schema_content_missing_name():
    with pytest.raises(ImportSchemaError, match="name"):
        validate_schema({
            "discipline_area_code": "FS01",
            "topics": [
                {"name": "T", "serial": 1, "contents": [{"concepts": []}]},
            ],
        })


def test_validate_schema_concept_missing_code():
    with pytest.raises(ImportSchemaError, match="code"):
        validate_schema({
            "discipline_area_code": "FS01",
            "topics": [
                {
                    "name": "T", "serial": 1,
                    "contents": [
                        {"name": "C", "concepts": [{"label": "L", "domain": "Información"}]},
                    ],
                }
            ],
        })


def test_validate_schema_concept_missing_domain():
    with pytest.raises(ImportSchemaError, match="domain"):
        validate_schema({
            "discipline_area_code": "FS01",
            "topics": [
                {
                    "name": "T", "serial": 1,
                    "contents": [
                        {"name": "C", "concepts": [{"code": "x-001", "label": "L"}]},
                    ],
                }
            ],
        })


def test_load_yaml_parses_valid_file(tmp_path):
    yaml_file = tmp_path / "valid.yaml"
    yaml_file.write_text(textwrap.dedent("""\
        discipline_area_code: FS01
        topics: []
    """))
    data = load_yaml(yaml_file)
    assert data["discipline_area_code"] == "FS01"
    assert data["topics"] == []


def test_load_yaml_raises_on_bad_yaml(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("key: [\nunot_closed")
    with pytest.raises(ImportSchemaError, match="YAML parse error"):
        load_yaml(bad)


def test_load_yaml_raises_on_non_dict(tmp_path):
    list_yaml = tmp_path / "list.yaml"
    list_yaml.write_text("- item1\n- item2\n")
    with pytest.raises(ImportSchemaError, match="mapping"):
        load_yaml(list_yaml)


# ── 7. discipline_area_override ───────────────────────────────────────────────


def test_discipline_area_override_used(global_session):
    """Override the file's discipline_area_code with a different code."""
    area = DisciplineArea(
        code="QU01",
        name="Química",
        discipline_num=2,
        topic_num=1,
        area_initials="QU",
    )
    global_session.add(area)
    global_session.commit()

    data = {
        "discipline_area_code": "WRONG",
        "topics": [
            {
                "name": "Estequiometría",
                "serial": 1,
                "contents": [{"name": "Mol", "concepts": []}],
            }
        ],
    }
    result = import_hierarchy(global_session, data, discipline_area_override="QU01")
    assert result.created_topics == 1


# ── 8. Concept parent_code within same file ───────────────────────────────────


def test_infile_parent_concept_resolves(global_session):
    """A concept whose parent is defined earlier in the same file must resolve."""
    _seed_da(global_session)
    data = {
        "discipline_area_code": "FS01",
        "topics": [
            {
                "name": "Mecánica",
                "serial": 5,
                "contents": [
                    {
                        "name": "Energía",
                        "concepts": [
                            {
                                "code": "fs01-mec-001",
                                "label": "Trabajo",
                                "domain": "Información",
                            },
                            {
                                "code": "fs01-mec-002",
                                "label": "Potencia",
                                "domain": "Procedimiento Mental",
                                "parent_code": "fs01-mec-001",
                            },
                        ],
                    }
                ],
            }
        ],
    }
    result = import_hierarchy(global_session, data)
    assert result.created_concepts == 2
    assert result.errors == ()

    parent = global_session.scalars(
        select(Concept).where(Concept.code == "fs01-mec-001")
    ).first()
    child = global_session.scalars(
        select(Concept).where(Concept.code == "fs01-mec-002")
    ).first()
    assert parent is not None
    assert child is not None
    assert child.parent_id == parent.id


# ── 9. Genuine DB error aborts the run cleanly (ADR-0018) ─────────────────────


def test_flush_db_error_aborts_run_without_partial_commit(global_engine, monkeypatch):
    """A genuine flush-time DB error (not an app-level row error) must propagate
    and abort the whole run — the engine must NOT swallow it into a RowError and
    keep using a poisoned session. import_hierarchy never reaches commit(), so
    nothing from the run is persisted.

    (App-level row errors like a bad domain ARE collected; that is covered by
    test_invalid_domain_*. This guards the DB-integrity path specifically.)
    """
    import workflow.topic.bulk_import as bi
    from sqlalchemy.exc import SQLAlchemyError

    real_add = bi.add_concept

    def flaky_add(session, *, code, label, content_id, domain,
                  parent_code=None, description=None):
        if code == "bad-001":
            # Bogus content_id → FK violation raised at flush() (FK pragma on).
            session.add(Concept(code=code, label=label,
                                content_id=10_000_000, domain=domain))
            return None
        return real_add(
            session, code=code, label=label, content_id=content_id,
            domain=domain, parent_code=parent_code, description=description,
        )

    monkeypatch.setattr(bi, "add_concept", flaky_add)

    data = {
        "discipline_area_code": "FS01",
        "topics": [{
            "name": "T", "serial": 1,
            "contents": [{
                "name": "C",
                "concepts": [
                    {"code": "good-001", "label": "g1", "domain": "Información"},
                    {"code": "bad-001", "label": "b", "domain": "Información"},
                    {"code": "good-002", "label": "g2", "domain": "Información"},
                ],
            }],
        }],
    }

    with Session(global_engine) as s1:
        _seed_da(s1)
        with pytest.raises(SQLAlchemyError):
            import_hierarchy(s1, data)

    # Whole run aborted (no commit reached) → nothing persisted.
    with Session(global_engine) as s2:
        codes = set(s2.scalars(select(Concept.code)).all())
    assert codes == set()
