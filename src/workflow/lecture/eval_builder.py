"""Evaluation bridge — Phase 5c.

Bridges EvaluationTemplate (exam structure via Items) with the exercise bank
from Phase 4. Converts template item specs into ExerciseSlots for use with
the existing selector and exam_builder.

Pure domain logic — no DB or I/O dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

from workflow.exercise.selector import ExerciseSlot


@dataclass(frozen=True)
class EvalSpec:
    """Specification for building an evaluation from a template."""

    title: str
    slots: tuple[ExerciseSlot, ...]
    total_points: float
    institution: str


def evaluation_template_to_slots(
    template_items: list[dict],
) -> list[ExerciseSlot]:
    """Convert EvaluationTemplate items to ExerciseSlots.

    Each dict has: taxonomy_level, taxonomy_domain, total_amount, points_per_item
    (matching the EvaluationItem model fields).

    Returns one ExerciseSlot per item specification.
    """
    return [
        ExerciseSlot(
            taxonomy_level=item["taxonomy_level"],
            taxonomy_domain=item["taxonomy_domain"],
            count=item["total_amount"],
            points_per_item=item["points_per_item"],
        )
        for item in template_items
    ]


def build_eval_spec(
    template_name: str,
    items: list[dict],
    institution: str = "",
) -> EvalSpec:
    """Build an EvalSpec from template data.

    Calculates total points from items as sum of (total_amount * points_per_item).
    """
    slots = evaluation_template_to_slots(items)
    total_points = sum(
        item["total_amount"] * item["points_per_item"] for item in items
    )
    return EvalSpec(
        title=template_name,
        slots=tuple(slots),
        total_points=total_points,
        institution=institution,
    )


__all__ = ["EvalSpec", "evaluation_template_to_slots", "build_eval_spec"]
