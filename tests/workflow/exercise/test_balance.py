"""Tests for workflow.exercise.balance — taxonomy x concept balance report.

Covers tasks/requests/2026-07-04-build-exam-balanceo.md acceptance criteria:
1. `compute_balance` returns one matrix row per slot, count/points computed
   from the slot + selected exercises (fully-filled and under-filled slots).
2. `concept_coverage.total_concepts` is pool-scoped (not whole-DB);
   `distinct_covered` is scoped to selected exercises only.
3. Zero-concept exercises count as 0 toward coverage, not an error.
4. `--json` shape: matrix / concept_coverage / warnings.
5. CSV form: header + one row per slot.
6. `--fail-under` boundary: at threshold = pass, just below = fail (exit 2),
   exercised via the CLI in TestBuildExamBalanceoCli.

TDD RED -> GREEN.
"""

from __future__ import annotations

import csv
import io
import json

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.engine import _enable_fk_pragma
from workflow.db.models.exercises import Exercise, ExerciseConcept
from workflow.db.models.knowledge import Concept, Content, DisciplineArea, MainTopic, Topic
from workflow.exercise.balance import (
    BalanceReport,
    compute_balance,
    coverage_ratio,
    format_human_table,
    to_csv_string,
    to_dict,
)
from workflow.exercise.cli import exercise
from workflow.exercise.selector import ExerciseSlot, SelectionResult


# ── Shared fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def db_engine():
    import workflow.db.models.bibliography  # noqa: F401
    import workflow.db.models.exercises  # noqa: F401
    import workflow.db.models.knowledge  # noqa: F401
    import workflow.db.models.notes  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk_pragma)
    GlobalBase.metadata.create_all(engine)
    return engine


@pytest.fixture()
def runner():
    return CliRunner()


def _seed_concept(session: Session, code: str) -> Concept:
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


def _make_exercise(
    session: Session,
    exercise_id: str,
    taxonomy_level: str = "Recordar",
    taxonomy_domain: str = "Información",
    status: str = "complete",
) -> Exercise:
    ex = Exercise(
        exercise_id=exercise_id,
        source_path=f"/fake/{exercise_id}.tex",
        file_hash="abc123",
        status=status,
        taxonomy_level=taxonomy_level,
        taxonomy_domain=taxonomy_domain,
        difficulty="medium",
    )
    session.add(ex)
    session.flush()
    return ex


def _link_concept(session: Session, ex: Exercise, concept: Concept) -> None:
    session.add(ExerciseConcept(exercise_id=ex.id, concept_id=concept.id))
    session.flush()


# ── compute_balance: taxonomy matrix ────────────────────────────────────────


class TestComputeBalanceMatrix:
    def test_fully_filled_slot(self, db_engine):
        with Session(db_engine) as session:
            ex1 = _make_exercise(session, "ex-001")
            ex2 = _make_exercise(session, "ex-002")
            slot = ExerciseSlot("Recordar", "Información", count=2, points_per_item=10.0)
            selection = SelectionResult(
                selected={slot: [ex1, ex2]}, unfilled=[], warnings=[]
            )

            report = compute_balance(selection, pool=[ex1, ex2], session=session)

            assert isinstance(report, BalanceReport)
            assert len(report.matrix) == 1
            row = report.matrix[0]
            assert row.taxonomy_level == "Recordar"
            assert row.taxonomy_domain == "Información"
            assert row.count == 2
            assert row.points == 20.0

    def test_under_filled_slot(self, db_engine):
        with Session(db_engine) as session:
            ex1 = _make_exercise(session, "ex-003")
            slot = ExerciseSlot(
                "Usar-Aplicar", "Procedimiento Mental", count=3, points_per_item=5.0
            )
            selection = SelectionResult(
                selected={slot: [ex1]},
                unfilled=[slot],
                warnings=["Slot (Usar-Aplicar, Procedimiento Mental): requested 3, found 1."],
            )

            report = compute_balance(selection, pool=[ex1], session=session)

            row = report.matrix[0]
            assert row.count == 1
            assert row.points == 5.0
            assert report.warnings == (
                "Slot (Usar-Aplicar, Procedimiento Mental): requested 3, found 1.",
            )

    def test_multiple_slots_produce_one_row_each(self, db_engine):
        with Session(db_engine) as session:
            ex1 = _make_exercise(session, "ex-004")
            ex2 = _make_exercise(session, "ex-005", taxonomy_level="Comprender")
            slot1 = ExerciseSlot("Recordar", "Información", count=1, points_per_item=10.0)
            slot2 = ExerciseSlot("Comprender", "Información", count=1, points_per_item=8.0)
            selection = SelectionResult(
                selected={slot1: [ex1], slot2: [ex2]}, unfilled=[], warnings=[]
            )

            report = compute_balance(selection, pool=[ex1, ex2], session=session)

            assert len(report.matrix) == 2


# ── compute_balance: concept coverage ───────────────────────────────────────


class TestComputeBalanceConceptCoverage:
    def test_total_concepts_scoped_to_pool_not_selection(self, db_engine):
        with Session(db_engine) as session:
            c1 = _seed_concept(session, "concept-a")
            c2 = _seed_concept(session, "concept-b")
            ex1 = _make_exercise(session, "ex-006")
            ex2 = _make_exercise(session, "ex-007")  # in pool but NOT selected
            _link_concept(session, ex1, c1)
            _link_concept(session, ex2, c2)

            slot = ExerciseSlot("Recordar", "Información", count=1, points_per_item=10.0)
            selection = SelectionResult(selected={slot: [ex1]}, unfilled=[], warnings=[])

            report = compute_balance(selection, pool=[ex1, ex2], session=session)

            # total_concepts counts the whole POOL (c1 + c2 = 2)
            assert report.concept_coverage.total_concepts == 2
            # distinct_covered counts only SELECTED exercises (ex1 -> c1)
            assert report.concept_coverage.distinct_covered == 1

    def test_zero_concept_exercise_counts_as_zero_not_error(self, db_engine):
        with Session(db_engine) as session:
            ex1 = _make_exercise(session, "ex-008")  # no concept links at all
            slot = ExerciseSlot("Recordar", "Información", count=1, points_per_item=10.0)
            selection = SelectionResult(selected={slot: [ex1]}, unfilled=[], warnings=[])

            report = compute_balance(selection, pool=[ex1], session=session)

            assert report.concept_coverage.total_concepts == 0
            assert report.concept_coverage.distinct_covered == 0

    def test_distinct_covered_deduplicates_shared_concept(self, db_engine):
        with Session(db_engine) as session:
            c1 = _seed_concept(session, "concept-shared")
            ex1 = _make_exercise(session, "ex-009")
            ex2 = _make_exercise(session, "ex-010")
            _link_concept(session, ex1, c1)
            _link_concept(session, ex2, c1)

            slot = ExerciseSlot("Recordar", "Información", count=2, points_per_item=10.0)
            selection = SelectionResult(
                selected={slot: [ex1, ex2]}, unfilled=[], warnings=[]
            )

            report = compute_balance(selection, pool=[ex1, ex2], session=session)

            assert report.concept_coverage.total_concepts == 1
            assert report.concept_coverage.distinct_covered == 1


# ── coverage_ratio / --fail-under boundary ──────────────────────────────────


class TestCoverageRatio:
    def test_ratio_at_threshold_passes(self, db_engine):
        with Session(db_engine) as session:
            c1 = _seed_concept(session, "concept-r1")
            c2 = _seed_concept(session, "concept-r2")
            ex1 = _make_exercise(session, "ex-011")
            ex2 = _make_exercise(session, "ex-012")
            _link_concept(session, ex1, c1)
            _link_concept(session, ex2, c2)

            slot = ExerciseSlot("Recordar", "Información", count=2, points_per_item=10.0)
            selection = SelectionResult(
                selected={slot: [ex1, ex2]}, unfilled=[], warnings=[]
            )
            report = compute_balance(selection, pool=[ex1, ex2], session=session)

            assert coverage_ratio(report) == 1.0
            assert coverage_ratio(report) >= 0.9  # at/above threshold => "pass"

    def test_ratio_just_below_threshold_fails(self, db_engine):
        with Session(db_engine) as session:
            c1 = _seed_concept(session, "concept-b1")
            c2 = _seed_concept(session, "concept-b2")
            ex1 = _make_exercise(session, "ex-013")
            ex2 = _make_exercise(session, "ex-014")  # in pool, not selected
            _link_concept(session, ex1, c1)
            _link_concept(session, ex2, c2)

            slot = ExerciseSlot("Recordar", "Información", count=1, points_per_item=10.0)
            selection = SelectionResult(selected={slot: [ex1]}, unfilled=[], warnings=[])
            report = compute_balance(selection, pool=[ex1, ex2], session=session)

            ratio = coverage_ratio(report)
            assert ratio == 0.5
            assert ratio < 0.9  # below threshold => "fail"

    def test_ratio_vacuously_one_when_no_concepts_in_pool(self, db_engine):
        with Session(db_engine) as session:
            ex1 = _make_exercise(session, "ex-015")
            slot = ExerciseSlot("Recordar", "Información", count=1, points_per_item=10.0)
            selection = SelectionResult(selected={slot: [ex1]}, unfilled=[], warnings=[])
            report = compute_balance(selection, pool=[ex1], session=session)

            assert coverage_ratio(report) == 1.0


# ── formatters: JSON / CSV / human table ────────────────────────────────────


class TestFormatters:
    def test_to_dict_shape(self, db_engine):
        with Session(db_engine) as session:
            ex1 = _make_exercise(session, "ex-016")
            slot = ExerciseSlot("Recordar", "Información", count=1, points_per_item=10.0)
            selection = SelectionResult(
                selected={slot: [ex1]}, unfilled=[], warnings=["a warning"]
            )
            report = compute_balance(selection, pool=[ex1], session=session)

            data = to_dict(report)
            assert set(data.keys()) == {"matrix", "concept_coverage", "warnings"}
            assert data["matrix"] == [
                {
                    "taxonomy_level": "Recordar",
                    "taxonomy_domain": "Información",
                    "count": 1,
                    "points": 10.0,
                }
            ]
            assert data["concept_coverage"] == {"total_concepts": 0, "distinct_covered": 0}
            assert data["warnings"] == ["a warning"]
            # round-trips through json.dumps cleanly
            json.dumps(data)

    def test_to_csv_string_shape(self, db_engine):
        with Session(db_engine) as session:
            ex1 = _make_exercise(session, "ex-017")
            slot = ExerciseSlot("Recordar", "Información", count=1, points_per_item=10.0)
            selection = SelectionResult(selected={slot: [ex1]}, unfilled=[], warnings=[])
            report = compute_balance(selection, pool=[ex1], session=session)

            csv_text = to_csv_string(report)
            reader = csv.DictReader(io.StringIO(csv_text))
            rows = list(reader)
            assert reader.fieldnames == [
                "taxonomy_level",
                "taxonomy_domain",
                "count",
                "points",
            ]
            assert rows == [
                {
                    "taxonomy_level": "Recordar",
                    "taxonomy_domain": "Información",
                    "count": "1",
                    "points": "10.0",
                }
            ]

    def test_format_human_table_includes_coverage_and_warnings(self, db_engine):
        with Session(db_engine) as session:
            ex1 = _make_exercise(session, "ex-018")
            slot = ExerciseSlot("Recordar", "Información", count=1, points_per_item=10.0)
            selection = SelectionResult(
                selected={slot: [ex1]}, unfilled=[], warnings=["watch out"]
            )
            report = compute_balance(selection, pool=[ex1], session=session)

            table = format_human_table(report)
            assert "Recordar" in table
            assert "Concept coverage" in table
            assert "[WARN] watch out" in table


# ── ExamDocument unchanged (acceptance #7) ──────────────────────────────────


def test_exam_document_shape_unchanged():
    """ExamDocument keeps its existing fields — additive-only constraint."""
    from workflow.exercise.exam_builder import ExamDocument

    fields = set(ExamDocument.__dataclass_fields__.keys())
    assert fields == {"title", "content", "total_points", "exercise_count", "warnings"}


# ── CLI: build-exam --balanceo / --balanceo-csv / --json / --fail-under ────


TEX_TEMPLATE = """\
% ---
% id: {ex_id}
% type: essay
% difficulty: easy
% taxonomy_level: {level}
% taxonomy_domain: {domain}
% tags: []
% concepts: [{concepts}]
% status: complete
% ---
\\question{{Stem for {ex_id}.}}{{Solution for {ex_id}.}}
"""


def _seed_pool_exercise(
    session: Session,
    ex_id: str,
    level: str = "Recordar",
    domain: str = "Información",
    concept: Concept | None = None,
) -> Exercise:
    ex = _make_exercise(session, ex_id, taxonomy_level=level, taxonomy_domain=domain)
    if concept is not None:
        _link_concept(session, ex, concept)
    return ex


class TestBuildExamBalanceoCli:
    def test_balanceo_bare_prints_stderr_table_stdout_stays_tex(self, runner, db_engine):
        with Session(db_engine) as session:
            _seed_pool_exercise(session, "cli-001")
            session.commit()

        result = runner.invoke(
            exercise,
            ["build-exam", "-l", "Recordar", "-d", "Información", "--balanceo"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output
        assert r"\begin{questions}" in result.stdout
        assert "Balance report:" in result.stderr

    def test_balanceo_csv_writes_file(self, runner, db_engine, tmp_path):
        with Session(db_engine) as session:
            _seed_pool_exercise(session, "cli-002")
            session.commit()

        csv_path = tmp_path / "matriz.csv"
        result = runner.invoke(
            exercise,
            [
                "build-exam",
                "-l",
                "Recordar",
                "-d",
                "Información",
                "--balanceo-csv",
                str(csv_path),
            ],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output
        assert csv_path.exists()
        content = csv_path.read_text(encoding="utf-8")
        assert "taxonomy_level,taxonomy_domain,count,points" in content

    def test_balanceo_json_emits_documented_shape_to_stdout(self, runner, db_engine):
        with Session(db_engine) as session:
            _seed_pool_exercise(session, "cli-003")
            session.commit()

        result = runner.invoke(
            exercise,
            [
                "build-exam",
                "-l",
                "Recordar",
                "-d",
                "Información",
                "--balanceo",
                "--json",
            ],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert set(data.keys()) == {"matrix", "concept_coverage", "warnings"}

    def test_fail_under_below_threshold_exits_2(self, runner, db_engine):
        with Session(db_engine) as session:
            c1 = _seed_concept(session, "cli-concept-a")
            c2 = _seed_concept(session, "cli-concept-b")
            _seed_pool_exercise(session, "cli-004", concept=c1)
            _seed_pool_exercise(session, "cli-005", level="Comprender", concept=c2)
            session.commit()

        result = runner.invoke(
            exercise,
            [
                "build-exam",
                "-l",
                "Recordar",
                "-d",
                "Información",
                "--balanceo",
                "--json",
                "--fail-under",
                "0.9",
            ],
            obj={"engine": db_engine},
        )
        # pool has 2 concepts total; only 1 slot selected -> covered=1/2=0.5 < 0.9
        assert result.exit_code == 2, result.output

    def test_fail_under_at_threshold_exits_0(self, runner, db_engine):
        with Session(db_engine) as session:
            c1 = _seed_concept(session, "cli-concept-c")
            _seed_pool_exercise(session, "cli-006", concept=c1)
            session.commit()

        result = runner.invoke(
            exercise,
            [
                "build-exam",
                "-l",
                "Recordar",
                "-d",
                "Información",
                "--balanceo",
                "--json",
                "--fail-under",
                "1.0",
            ],
            obj={"engine": db_engine},
        )
        # single concept, fully covered -> ratio == 1.0 >= 1.0 threshold
        assert result.exit_code == 0, result.output

    def test_fail_under_without_balanceo_is_rejected(self, runner, db_engine):
        with Session(db_engine) as session:
            _seed_pool_exercise(session, "cli-007")
            session.commit()

        result = runner.invoke(
            exercise,
            [
                "build-exam",
                "-l",
                "Recordar",
                "-d",
                "Información",
                "--fail-under",
                "0.5",
            ],
            obj={"engine": db_engine},
        )
        assert result.exit_code != 0

    def test_no_balanceo_flags_behavior_unchanged(self, runner, db_engine):
        """Existing build-exam behavior (no balance flags) stays exactly as before."""
        with Session(db_engine) as session:
            _seed_pool_exercise(session, "cli-008")
            session.commit()

        result = runner.invoke(
            exercise,
            ["build-exam", "-l", "Recordar", "-d", "Información"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output
        assert "Balance report:" not in result.stderr
        assert r"\begin{questions}" in result.stdout

    def test_json_with_output_keeps_stdout_pure_json(self, runner, db_engine, tmp_path):
        """--json --output must not print the confirmation to stdout (ADR docstring contract)."""
        with Session(db_engine) as session:
            _seed_pool_exercise(session, "cli-009")
            session.commit()

        out_path = tmp_path / "exam.tex"
        result = runner.invoke(
            exercise,
            [
                "build-exam",
                "-l",
                "Recordar",
                "-d",
                "Información",
                "--balanceo",
                "--json",
                "--output",
                str(out_path),
            ],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert set(data.keys()) == {"matrix", "concept_coverage", "warnings"}
        assert out_path.exists()
