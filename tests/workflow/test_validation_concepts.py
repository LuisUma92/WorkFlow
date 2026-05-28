"""ITEP-0012.3 — check_concepts_against_db + --strict-concepts CLI flag tests."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.engine import init_global_db
from workflow.db.models.knowledge import DisciplineArea, MainTopic, Topic, Content
from workflow.db.models.knowledge import Concept
from workflow.validation.cli import validate
from workflow.validation.schemas import (
    NoteFrontmatter,
    check_concepts_against_db,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def engine():
    """In-memory SQLite engine with all GlobalBase tables."""
    import workflow.db.models.bibliography  # noqa: F401
    import workflow.db.models.academic  # noqa: F401
    import workflow.db.models.project  # noqa: F401
    import workflow.db.models.notes  # noqa: F401
    import workflow.db.models.exercises  # noqa: F401

    eng = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture()
def seeded_session(session):
    """Seed two DisciplineAreas + MainTopics, Topic+Content chain under da1, and one Concept.

    Post-Phase-4B: Topic is rooted at DisciplineArea, not MainTopic.
    mt1 and mt2 belong to *different* DisciplineAreas so that the
    discipline-area mismatch check (the new strict semantics) fires
    when the note declares mt2 but the concept belongs to da1/mt1.
    """
    da1 = DisciplineArea(
        code="FI0006",
        name="Fisica",
        discipline_num=1,
        topic_num=6,
        area_initials="FI",
    )
    da2 = DisciplineArea(
        code="FI0007",
        name="Termo",
        discipline_num=1,
        topic_num=7,
        area_initials="FI",
    )
    session.add_all([da1, da2])
    session.flush()

    mt1 = MainTopic(code="FI0006", name="Mecanica", discipline_area_id=da1.id)
    mt2 = MainTopic(code="FI0007", name="Termo", discipline_area_id=da2.id)
    session.add_all([mt1, mt2])
    session.flush()

    # Topic is rooted at da1 (discipline_area_id), not main_topic_id
    tp = Topic(discipline_area_id=da1.id, name="Cinematica", serial_number=1)
    session.add(tp)
    session.flush()

    ct = Content(topic_id=tp.id, name="Movimiento rectilineo")
    session.add(ct)
    session.flush()

    c = Concept(code="forces", label="Forces", content_id=ct.id, domain="Información")
    session.add(c)
    session.commit()
    return {"da1": da1, "da2": da2, "mt1": mt1, "mt2": mt2, "concept": c}


def _make_fm(concepts=(), main_topic=None):
    return NoteFrontmatter(
        id="test-note",
        title="Test Note",
        concepts=tuple(concepts),
        main_topic=main_topic,
    )


# ── check_concepts_against_db unit tests ─────────────────────────────────


def test_validate_concepts_no_concepts_field_clean(session, seeded_session):
    fm = _make_fm(concepts=[])
    issues = check_concepts_against_db(fm, session, strict=False)
    assert issues == []


def test_validate_concepts_unknown_code_warns(session, seeded_session):
    fm = _make_fm(concepts=["nonexistent"])
    issues = check_concepts_against_db(fm, session, strict=False)
    assert len(issues) == 1
    assert issues[0]["severity"] == "warning"
    assert "nonexistent" in issues[0]["message"]


def test_validate_concepts_unknown_code_strict_errors(session, seeded_session):
    fm = _make_fm(concepts=["nonexistent"])
    issues = check_concepts_against_db(fm, session, strict=True)
    assert len(issues) == 1
    assert issues[0]["severity"] == "error"
    assert "nonexistent" in issues[0]["message"]


def test_validate_concepts_known_code_clean(session, seeded_session):
    fm = _make_fm(concepts=["forces"])
    issues = check_concepts_against_db(fm, session, strict=False)
    assert issues == []


def test_validate_concepts_main_topic_mismatch_strict_errors(session, seeded_session):
    """Concept belongs to da1 but note declares mt2 (da2) → discipline-area mismatch error under strict.

    Post-Phase-4B: the strict check compares concept.discipline_area vs note.main_topic.discipline_area_id.
    mt2 belongs to da2; concept 'forces' belongs to da1 → mismatch.
    """
    fm = _make_fm(concepts=["forces"], main_topic="FI0007")
    issues = check_concepts_against_db(fm, session, strict=True)
    errors = [i for i in issues if i["severity"] == "error"]
    assert len(errors) >= 1
    # Error message should mention the concept or a DA code
    msg = errors[0]["message"]
    assert "forces" in msg or "FI0006" in msg or "discipline_area" in msg


def test_validate_concepts_no_main_topic_mismatch_check_skipped(
    session, seeded_session
):
    """When note has no main_topic, mt-mismatch check is skipped silently."""
    fm = _make_fm(concepts=["forces"], main_topic=None)
    issues = check_concepts_against_db(fm, session, strict=True)
    # Only unknown-code issues are possible; forces IS known so should be clean
    assert issues == []


# ── CLI flag wiring tests ─────────────────────────────────────────────────


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_global_db(tmp_path_factory, monkeypatch):
    """Redirect the global DB to a throwaway dir for every test.

    The engine resolves its path from ``WORKFLOW_DATA_DIR`` (see
    ``engine._default_global_path``), not ``XDG_DATA_HOME`` — setting the wrong
    var lets ``init_global_db()`` hit the real ``~/01-U/workflow/workflow.db``.
    """
    base = tmp_path_factory.mktemp("val_concepts_db")
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(base))


def _seed_global():
    """Seed a single-DA/MT chain for CLI tests.

    Post-Phase-4B: Topic is rooted at DisciplineArea, not MainTopic.
    """
    engine = init_global_db()
    with Session(engine) as session:
        da = DisciplineArea(
            code="FI0006",
            name="Fisica",
            discipline_num=1,
            topic_num=6,
            area_initials="FI",
        )
        session.add(da)
        session.flush()
        mt = MainTopic(code="FI0006", name="Mecanica", discipline_area_id=da.id)
        session.add(mt)
        session.flush()
        # Topic rooted at DisciplineArea (Phase 4B)
        tp = Topic(discipline_area_id=da.id, name="Cinematica", serial_number=1)
        session.add(tp)
        session.flush()
        ct = Content(topic_id=tp.id, name="Movimiento rectilineo")
        session.add(ct)
        session.flush()
        c = Concept(code="forces", label="Forces", content_id=ct.id, domain="Información")
        session.add(c)
        session.commit()
        return mt.id


def _write_note(path: Path, **fm_extra) -> None:
    lines = ["---", "id: n-1", "title: T"]
    for k, v in fm_extra.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        elif isinstance(v, str):
            lines.append(f"{k}: {v!r}")
        else:
            lines.append(f"{k}: {v}")
    lines += ["---", "", "body"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_validate_notes_cli_strict_concepts_propagates(runner, tmp_path):
    """--strict-concepts causes exit 1 on a note with unknown concept code."""
    _seed_global()
    _write_note(tmp_path / "a.md", concepts=["totally-unknown"])
    result = runner.invoke(validate, ["notes", str(tmp_path), "--strict-concepts"])
    assert result.exit_code == 1
    assert "totally-unknown" in result.output


def test_strict_concepts_orthogonal_to_strict_main_topic(runner, tmp_path):
    """Both flags can be set independently; each gates its own check."""
    _seed_global()
    # Note with known concept but unknown main_topic
    _write_note(tmp_path / "a.md", concepts=["forces"], main_topic="XX9999")
    # --strict-main-topic alone → error on main_topic; concept is clean
    r1 = runner.invoke(validate, ["notes", str(tmp_path), "--strict-main-topic"])
    assert r1.exit_code == 1
    assert "XX9999" in r1.output

    # --strict-concepts alone → concept is known, no errors
    r2 = runner.invoke(validate, ["notes", str(tmp_path), "--strict-concepts"])
    assert r2.exit_code == 0
