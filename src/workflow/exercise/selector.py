"""Exercise selection engine.

Pure domain logic — selects exercises from a pool to satisfy evaluation
constraints. No DB or I/O dependencies.

See ADR-0009, ADR-0010.
"""

from __future__ import annotations

from dataclasses import dataclass

from workflow.db.models.exercises import Exercise


@dataclass(frozen=True)
class ExerciseSlot:
    """A slot in an exam that needs to be filled."""

    taxonomy_level: str
    taxonomy_domain: str
    count: int
    points_per_item: float


@dataclass(frozen=True)
class SelectionResult:
    """Result of selecting exercises for an exam."""

    selected: dict[ExerciseSlot, list[Exercise]]  # slot → chosen exercises
    unfilled: list[ExerciseSlot]  # slots that couldn't be fully filled
    warnings: list[str]


_DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}


def select_exercises(
    slots: list[ExerciseSlot],
    pool: list[Exercise],
) -> SelectionResult:
    """Select exercises from pool to fill slots.

    Rules:
    - Match by taxonomy_level AND taxonomy_domain
    - Only select exercises with status="complete"
    - Never select the same exercise twice across slots
    - If a slot can't be fully filled, add to unfilled list with warning
    - Prefer exercises with higher difficulty variety (easy → medium → hard)
    """

    # Filter pool to complete exercises only, sorted for variety
    eligible = [ex for ex in pool if ex.status == "complete"]
    eligible = sorted(
        eligible,
        key=lambda ex: _DIFFICULTY_ORDER.get(ex.difficulty or "medium", 1),
    )

    used_ids: set[str] = set()
    selected: dict[ExerciseSlot, list[Exercise]] = {}
    unfilled: list[ExerciseSlot] = []
    warnings: list[str] = []

    for slot in slots:
        candidates = [
            ex
            for ex in eligible
            if ex.taxonomy_level == slot.taxonomy_level
            and ex.taxonomy_domain == slot.taxonomy_domain
            and ex.exercise_id not in used_ids
        ]

        chosen = candidates[: slot.count]
        selected[slot] = chosen

        for ex in chosen:
            used_ids.add(ex.exercise_id)

        if len(chosen) < slot.count:
            unfilled.append(slot)
            warnings.append(
                f"Slot ({slot.taxonomy_level}, {slot.taxonomy_domain}): "
                f"requested {slot.count}, found {len(chosen)}."
            )

    return SelectionResult(
        selected=selected,
        unfilled=unfilled,
        warnings=warnings,
    )


__all__ = ["ExerciseSlot", "SelectionResult", "select_exercises"]
