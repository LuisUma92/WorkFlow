"""Tests for `exercise sync --json/--dry-run/--status` and `exercise list --concept`.

Covers tasks/requests/2026-07-03-exercise-composability-flags.md acceptance criteria:
1. `sync --json` emits {"synced","skipped","errors","dropped_concepts","invalid_status","dry_run"}.
2. `sync --dry-run` parses/reports but writes nothing to the DB.
3. `sync --status <enum>` only syncs files whose parsed status matches.
4. `list --concept <code>` filters via ExerciseConcept M2M; unknown code exits 2.

TDD RED -> GREEN.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.engine import _enable_fk_pragma
from workflow.db.models.exercises import Exercise, ExerciseConcept
from workflow.db.models.knowledge import Concept, Content, DisciplineArea, MainTopic, Topic
from workflow.exercise.cli import exercise


# ── Shared fixtures ─────────────────────────────────────────────────────────


def _seed_concept_chain(session: Session, code: str = "test-concept") -> Concept:
    import hashlib

    suffix = hashlib.sha1(code.encode()).hexdigest()[:6].upper()
    area = DisciplineArea(
        name=f"Test Area {code}",
        code=f"T{suffix}",
        dewey="000",
        discipline_num=1,
        topic_num=1,
        area_initials="TA",
    )
    session.add(area)
    session.flush()
    main_topic = MainTopic(
        name=f"Test Topic {code}", code=f"T{suffix}-001", discipline_area_id=area.id
    )
    session.add(main_topic)
    session.flush()
    subtopic = Topic(name=f"Sub Topic {code}", serial_number=1, discipline_area_id=area.id)
    session.add(subtopic)
    session.flush()
    content = Content(name="Test Content", topic_id=subtopic.id)
    session.add(content)
    session.flush()
    concept = Concept(
        code=code,
        label=code.replace("-", " ").title(),
        domain="Información",
        content_id=content.id,
    )
    session.add(concept)
    session.flush()
    return concept


@pytest.fixture()
def db_engine():
    import workflow.db.models.exercises  # noqa: F401
    import workflow.db.models.knowledge  # noqa: F401
    import workflow.db.models.bibliography  # noqa: F401
    import workflow.db.models.notes  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk_pragma)
    GlobalBase.metadata.create_all(engine)
    return engine


@pytest.fixture()
def runner():
    return CliRunner()


TEX_TEMPLATE = """\
% ---
% id: {ex_id}
% type: essay
% difficulty: easy
% taxonomy_level: Recordar
% taxonomy_domain: Información
% tags: []
% concepts: [{concepts}]
% status: {status}
% ---
\\question{{Stem for {ex_id}.}}{{Solution for {ex_id}.}}
"""


def _make_tex(
    path: Path, ex_id: str, status: str = "complete", concepts: str = ""
) -> Path:
    path.write_text(
        TEX_TEMPLATE.format(ex_id=ex_id, concepts=concepts, status=status),
        encoding="utf-8",
    )
    return path


# ── sync --json ──────────────────────────────────────────────────────────────


class TestSyncJson:
    def test_json_report_has_required_keys(self, runner, tmp_path, db_engine):
        _make_tex(tmp_path / "ex001.tex", "cj-001")

        result = runner.invoke(
            exercise, ["sync", str(tmp_path), "--json"], obj={"engine": db_engine}
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        for key in (
            "synced",
            "skipped",
            "errors",
            "dropped_concepts",
            "invalid_status",
            "dry_run",
        ):
            assert key in data, f"Missing key: {key}"

    def test_json_synced_count_reflects_new_file(self, runner, tmp_path, db_engine):
        _make_tex(tmp_path / "ex002.tex", "cj-002")

        result = runner.invoke(
            exercise, ["sync", str(tmp_path), "--json"], obj={"engine": db_engine}
        )
        data = json.loads(result.output)
        assert data["synced"] == 1
        assert data["dry_run"] is False

    def test_json_dropped_concepts_structured(self, runner, tmp_path, db_engine):
        _make_tex(tmp_path / "ex003.tex", "cj-003", concepts="ghost-code")

        result = runner.invoke(
            exercise, ["sync", str(tmp_path), "--json"], obj={"engine": db_engine}
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert len(data["dropped_concepts"]) == 1
        entry = data["dropped_concepts"][0]
        assert entry["file"] == "ex003.tex"
        assert "ghost-code" in entry["codes"]

    def test_json_output_is_clean_stdout_no_extra_lines(self, runner, tmp_path, db_engine):
        """--json emits a single JSON object; no human log lines mixed in."""
        _make_tex(tmp_path / "ex004.tex", "cj-004")

        result = runner.invoke(
            exercise, ["sync", str(tmp_path), "--json"], obj={"engine": db_engine}
        )
        assert result.exit_code == 0, result.output
        # Must parse as a single JSON value from the full stdout.
        json.loads(result.output)


# ── sync --dry-run ───────────────────────────────────────────────────────────


class TestSyncDryRun:
    def test_dry_run_writes_nothing_to_db(self, runner, tmp_path, db_engine):
        _make_tex(tmp_path / "ex005.tex", "cj-005")

        result = runner.invoke(
            exercise, ["sync", str(tmp_path), "--dry-run"], obj={"engine": db_engine}
        )
        assert result.exit_code == 0, result.output

        with Session(db_engine) as session:
            count = len(session.scalars(select(Exercise)).all())
        assert count == 0

    def test_dry_run_json_reports_would_be_synced_count(self, runner, tmp_path, db_engine):
        _make_tex(tmp_path / "ex006.tex", "cj-006")

        result = runner.invoke(
            exercise,
            ["sync", str(tmp_path), "--dry-run", "--json"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["synced"] == 1
        assert data["dry_run"] is True

        with Session(db_engine) as session:
            count = len(session.scalars(select(Exercise)).all())
        assert count == 0

    def test_dry_run_does_not_persist_concept_links_either(
        self, runner, tmp_path, db_engine
    ):
        with Session(db_engine) as session:
            _seed_concept_chain(session, "dr-concept")
            session.commit()

        _make_tex(tmp_path / "ex007.tex", "cj-007", concepts="dr-concept")

        runner.invoke(
            exercise, ["sync", str(tmp_path), "--dry-run"], obj={"engine": db_engine}
        )

        with Session(db_engine) as session:
            assert len(session.scalars(select(ExerciseConcept)).all()) == 0
            assert len(session.scalars(select(Exercise)).all()) == 0


# ── sync --status ────────────────────────────────────────────────────────────


class TestSyncStatusFilter:
    def test_status_filter_only_syncs_matching_files(self, runner, tmp_path, db_engine):
        _make_tex(tmp_path / "ex008.tex", "cj-008", status="complete")
        _make_tex(tmp_path / "ex009.tex", "cj-009", status="placeholder")

        result = runner.invoke(
            exercise,
            ["sync", str(tmp_path), "--status", "complete", "--json"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["synced"] == 1

        with Session(db_engine) as session:
            repo_ids = {
                ex.exercise_id for ex in session.scalars(select(Exercise)).all()
            }
        assert "cj-008" in repo_ids
        assert "cj-009" not in repo_ids

    def test_status_filter_excludes_non_matching_from_sync(
        self, runner, tmp_path, db_engine
    ):
        _make_tex(tmp_path / "ex010.tex", "cj-010", status="placeholder")

        result = runner.invoke(
            exercise,
            ["sync", str(tmp_path), "--status", "complete", "--json"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["synced"] == 0

        with Session(db_engine) as session:
            assert session.scalars(select(Exercise)).first() is None


# ── list --concept ───────────────────────────────────────────────────────────


class TestListConceptFilter:
    def _seed_exercise_with_concept(
        self, session: Session, exercise_id: str, concept: Concept
    ) -> Exercise:
        import hashlib

        ex = Exercise(
            exercise_id=exercise_id,
            source_path=f"/fake/{exercise_id}.tex",
            file_hash=hashlib.sha256(exercise_id.encode()).hexdigest(),
            status="complete",
            type="essay",
            difficulty="medium",
            taxonomy_level="Usar-Aplicar",
            taxonomy_domain="Procedimiento Mental",
            tags="[]",
        )
        session.add(ex)
        session.flush()
        session.add(ExerciseConcept(exercise_id=ex.id, concept_id=concept.id))
        session.commit()
        return ex

    def test_concept_filter_returns_matching_only(self, runner, db_engine):
        with Session(db_engine) as session:
            concept = _seed_concept_chain(session, "lc-concept-a")
            other_concept = _seed_concept_chain(session, "lc-concept-b")
            self._seed_exercise_with_concept(session, "lc-ex-001", concept)
            self._seed_exercise_with_concept(session, "lc-ex-002", other_concept)

        result = runner.invoke(
            exercise,
            ["list", "--concept", "lc-concept-a", "--json"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        ids = [d["id"] for d in data]
        assert "lc-ex-001" in ids
        assert "lc-ex-002" not in ids

    def test_unknown_concept_code_exits_2(self, runner, db_engine):
        result = runner.invoke(
            exercise,
            ["list", "--concept", "nonexistent-code", "--json"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 2, result.output
        assert "nonexistent-code" in result.output

    def test_concept_filter_composes_with_type_filter(self, runner, db_engine):
        with Session(db_engine) as session:
            concept = _seed_concept_chain(session, "lc-concept-c")
            self._seed_exercise_with_concept(session, "lc-ex-003", concept)

        result = runner.invoke(
            exercise,
            ["list", "--concept", "lc-concept-c", "--type", "essay", "--json"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["id"] == "lc-ex-003"
