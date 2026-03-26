"""Tests for workflow.exercise.selector — Exercise selection engine."""

from __future__ import annotations

from workflow.db.models.exercises import Exercise
from workflow.exercise.selector import ExerciseSlot, SelectionResult, select_exercises


def _make_exercise(
    exercise_id: str,
    taxonomy_level: str = "Recordar",
    taxonomy_domain: str = "Información",
    status: str = "complete",
    difficulty: str = "medium",
) -> Exercise:
    ex = Exercise(
        exercise_id=exercise_id,
        source_path=f"/fake/{exercise_id}.tex",
        file_hash="abc123",
        status=status,
        taxonomy_level=taxonomy_level,
        taxonomy_domain=taxonomy_domain,
        difficulty=difficulty,
    )
    return ex


# ── Basic selection ──────────────────────────────────────────────────────


def test_select_fills_single_slot():
    slot = ExerciseSlot(
        taxonomy_level="Recordar",
        taxonomy_domain="Información",
        count=2,
        points_per_item=10.0,
    )
    pool = [
        _make_exercise("ex-001", "Recordar", "Información"),
        _make_exercise("ex-002", "Recordar", "Información"),
        _make_exercise("ex-003", "Recordar", "Información"),
    ]
    result = select_exercises([slot], pool)

    assert isinstance(result, SelectionResult)
    assert len(result.unfilled) == 0
    assert slot in result.selected
    assert len(result.selected[slot]) == 2


def test_select_fills_multiple_slots():
    slot_a = ExerciseSlot("Recordar", "Información", count=1, points_per_item=5.0)
    slot_b = ExerciseSlot(
        "Comprender", "Procedimiento Mental", count=1, points_per_item=10.0
    )
    pool = [
        _make_exercise("ex-001", "Recordar", "Información"),
        _make_exercise("ex-002", "Comprender", "Procedimiento Mental"),
        _make_exercise("ex-003", "Comprender", "Procedimiento Mental"),
    ]
    result = select_exercises([slot_a, slot_b], pool)

    assert len(result.unfilled) == 0
    assert len(result.selected[slot_a]) == 1
    assert len(result.selected[slot_b]) == 1


def test_select_no_duplicate_across_slots():
    """The same exercise must not fill two slots."""
    slot_a = ExerciseSlot("Recordar", "Información", count=1, points_per_item=5.0)
    slot_b = ExerciseSlot("Recordar", "Información", count=1, points_per_item=5.0)
    pool = [
        _make_exercise("ex-001", "Recordar", "Información"),
        _make_exercise("ex-002", "Recordar", "Información"),
    ]
    result = select_exercises([slot_a, slot_b], pool)

    all_ids = [
        ex.exercise_id for exercises in result.selected.values() for ex in exercises
    ]
    assert len(all_ids) == len(set(all_ids)), "Duplicate exercise selected across slots"


def test_select_unfilled_when_pool_too_small():
    slot = ExerciseSlot("Recordar", "Información", count=5, points_per_item=10.0)
    pool = [
        _make_exercise("ex-001", "Recordar", "Información"),
        _make_exercise("ex-002", "Recordar", "Información"),
    ]
    result = select_exercises([slot], pool)

    assert slot in result.unfilled
    assert len(result.warnings) > 0
    # Only 2 exercises available but 5 requested — slot still partially filled
    assert len(result.selected.get(slot, [])) == 2


def test_select_only_complete_exercises():
    slot = ExerciseSlot("Recordar", "Información", count=2, points_per_item=10.0)
    pool = [
        _make_exercise("ex-001", "Recordar", "Información", status="complete"),
        _make_exercise("ex-002", "Recordar", "Información", status="in_progress"),
        _make_exercise("ex-003", "Recordar", "Información", status="placeholder"),
        _make_exercise("ex-004", "Recordar", "Información", status="complete"),
    ]
    result = select_exercises([slot], pool)

    selected = result.selected.get(slot, [])
    assert all(ex.status == "complete" for ex in selected)
    assert len(selected) == 2


def test_select_empty_pool():
    slot = ExerciseSlot("Recordar", "Información", count=3, points_per_item=10.0)
    result = select_exercises([slot], [])

    assert slot in result.unfilled
    assert len(result.warnings) > 0
    assert result.selected.get(slot, []) == []


def test_select_exact_count():
    """When pool has exactly N exercises, selects exactly N."""
    slot = ExerciseSlot("Recordar", "Información", count=3, points_per_item=10.0)
    pool = [
        _make_exercise("ex-001", "Recordar", "Información"),
        _make_exercise("ex-002", "Recordar", "Información"),
        _make_exercise("ex-003", "Recordar", "Información"),
    ]
    result = select_exercises([slot], pool)

    assert len(result.unfilled) == 0
    assert len(result.selected[slot]) == 3


def test_select_ignores_wrong_taxonomy():
    """Exercises with mismatching taxonomy are not selected."""
    slot = ExerciseSlot("Recordar", "Información", count=2, points_per_item=10.0)
    pool = [
        _make_exercise("ex-001", "Comprender", "Información"),
        _make_exercise("ex-002", "Recordar", "Procedimiento Mental"),
        _make_exercise("ex-003", "Recordar", "Información"),
    ]
    result = select_exercises([slot], pool)

    selected = result.selected.get(slot, [])
    assert len(selected) == 1
    assert selected[0].exercise_id == "ex-003"
    assert slot in result.unfilled


def test_select_duplicate_slots_same_taxonomy():
    """Two identical slots should not share exercises."""
    slot1 = ExerciseSlot(
        taxonomy_level="Usar-Aplicar",
        taxonomy_domain="Procedimiento Mental",
        count=1,
        points_per_item=5.0,
    )
    slot2 = ExerciseSlot(
        taxonomy_level="Usar-Aplicar",
        taxonomy_domain="Procedimiento Mental",
        count=1,
        points_per_item=10.0,
    )

    pool = [
        _make_exercise(
            "ex-1",
            taxonomy_level="Usar-Aplicar",
            taxonomy_domain="Procedimiento Mental",
        ),
        _make_exercise(
            "ex-2",
            taxonomy_level="Usar-Aplicar",
            taxonomy_domain="Procedimiento Mental",
        ),
    ]

    result = select_exercises([slot1, slot2], pool)
    # Both slots should be filled with different exercises
    all_selected = []
    for exs in result.selected.values():
        all_selected.extend(exs)
    ids = [e.exercise_id for e in all_selected]
    assert len(ids) == len(set(ids))  # no duplicates
