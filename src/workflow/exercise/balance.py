"""Taxonomy x concept balance report for assembled exams.

Computes a read-only balance matrix over an already-produced
``SelectionResult`` (see ``workflow.exercise.selector``) without touching
``ExamDocument`` (``workflow.exercise.exam_builder``) — additive only, per
tasks/requests/2026-07-04-build-exam-balanceo.md acceptance criterion #7.

Two axes:
- Taxonomy: one row per slot in ``selection.selected`` (no new query — the
  slot dict already carries level/domain/count/points_per_item).
- Concepts: resolved via the ``ExerciseConcept`` M2M table. ``total_concepts``
  is scoped to the exercise **pool** passed to ``select_exercises`` (not the
  whole DB — locked decision in the request doc); ``distinct_covered`` is
  scoped to the exercises actually selected.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.db.models.exercises import Exercise, ExerciseConcept
from workflow.exercise.selector import SelectionResult


@dataclass(frozen=True)
class BalanceRow:
    """One taxonomy slot's contribution to the balance matrix."""

    taxonomy_level: str
    taxonomy_domain: str
    count: int
    points: float


@dataclass(frozen=True)
class ConceptCoverage:
    """Concept coverage summary: pool-wide total vs. selected-exercise coverage."""

    total_concepts: int
    distinct_covered: int


@dataclass(frozen=True)
class BalanceReport:
    """Full balance report: taxonomy matrix + concept coverage + warnings."""

    matrix: tuple[BalanceRow, ...]
    concept_coverage: ConceptCoverage
    warnings: tuple[str, ...]


def _distinct_concept_ids(session: Session, exercise_db_ids: list[int]) -> set[int]:
    """Distinct concept ids linked (via ExerciseConcept) to the given exercise PKs."""
    if not exercise_db_ids:
        return set()
    rows = session.execute(
        select(ExerciseConcept.concept_id).where(
            ExerciseConcept.exercise_id.in_(exercise_db_ids)
        )
    ).all()
    return {row[0] for row in rows}


def compute_balance(
    selection: SelectionResult,
    pool: Sequence[Exercise],
    session: Session,
) -> BalanceReport:
    """Compute a taxonomy x concept balance report.

    ``pool`` is the same exercise pool passed to ``select_exercises`` — it
    scopes the ``total_concepts`` denominator (locked decision: pool-wide,
    not whole-DB). ``session`` is used for a single ``ExerciseConcept`` query
    per axis; no writes are performed.
    """
    matrix = tuple(
        BalanceRow(
            taxonomy_level=slot.taxonomy_level,
            taxonomy_domain=slot.taxonomy_domain,
            count=len(exercises),
            points=slot.points_per_item * len(exercises),
        )
        for slot, exercises in selection.selected.items()
    )

    pool_ids = [ex.id for ex in pool if ex.id is not None]
    selected_ids = [
        ex.id
        for exercises in selection.selected.values()
        for ex in exercises
        if ex.id is not None
    ]

    coverage = ConceptCoverage(
        total_concepts=len(_distinct_concept_ids(session, pool_ids)),
        distinct_covered=len(_distinct_concept_ids(session, selected_ids)),
    )

    return BalanceReport(
        matrix=matrix,
        concept_coverage=coverage,
        warnings=tuple(selection.warnings),
    )


def coverage_ratio(report: BalanceReport) -> float:
    """distinct_covered / total_concepts. Vacuously 1.0 when total_concepts is 0."""
    total = report.concept_coverage.total_concepts
    if total == 0:
        return 1.0
    return report.concept_coverage.distinct_covered / total


def to_dict(report: BalanceReport) -> dict:
    """JSON-serializable form: {matrix, concept_coverage, warnings}."""
    return {
        "matrix": [
            {
                "taxonomy_level": row.taxonomy_level,
                "taxonomy_domain": row.taxonomy_domain,
                "count": row.count,
                "points": row.points,
            }
            for row in report.matrix
        ],
        "concept_coverage": {
            "total_concepts": report.concept_coverage.total_concepts,
            "distinct_covered": report.concept_coverage.distinct_covered,
        },
        "warnings": list(report.warnings),
    }


_CSV_FIELDNAMES = ("taxonomy_level", "taxonomy_domain", "count", "points")


def to_csv_string(report: BalanceReport) -> str:
    """CSV form: one row per slot, columns taxonomy_level,taxonomy_domain,count,points."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    for row in report.matrix:
        writer.writerow(
            {
                "taxonomy_level": row.taxonomy_level,
                "taxonomy_domain": row.taxonomy_domain,
                "count": row.count,
                "points": row.points,
            }
        )
    return buf.getvalue()


def write_csv(report: BalanceReport, path: Path) -> None:
    """Write the CSV form of the report to ``path``."""
    Path(path).write_text(to_csv_string(report), encoding="utf-8")


def format_human_table(report: BalanceReport) -> str:
    """Human-readable table for stderr — matrix rows + concept coverage + warnings."""
    lines: list[str] = ["Balance report:"]
    lines.append(f"{'level':<16} {'domain':<24} {'count':>5} {'points':>8}")
    for row in report.matrix:
        lines.append(
            f"{row.taxonomy_level:<16} {row.taxonomy_domain:<24} "
            f"{row.count:>5} {row.points:>8.1f}"
        )
    ratio = coverage_ratio(report)
    lines.append(
        "Concept coverage: "
        f"{report.concept_coverage.distinct_covered}/"
        f"{report.concept_coverage.total_concepts} ({ratio:.0%})"
    )
    for warn in report.warnings:
        lines.append(f"[WARN] {warn}")
    return "\n".join(lines)


__all__ = [
    "BalanceRow",
    "ConceptCoverage",
    "BalanceReport",
    "compute_balance",
    "coverage_ratio",
    "to_dict",
    "to_csv_string",
    "write_csv",
    "format_human_table",
]
