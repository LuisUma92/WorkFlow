"""Tests for workflow.lecture.eval_builder — TDD Phase 5c."""

from __future__ import annotations

import pytest

from workflow.lecture.eval_builder import EvalSpec, build_eval_spec, evaluation_template_to_slots
from workflow.exercise.selector import ExerciseSlot


class TestEvaluationTemplateToSlots:
    def test_single_item(self):
        items = [
            {
                "taxonomy_level": "Usar-Aplicar",
                "taxonomy_domain": "Procedimiento Mental",
                "total_amount": 3,
                "points_per_item": 5.0,
            }
        ]
        slots = evaluation_template_to_slots(items)
        assert len(slots) == 1
        assert slots[0].count == 3
        assert slots[0].points_per_item == 5.0

    def test_single_item_taxonomy_fields(self):
        items = [
            {
                "taxonomy_level": "Recordar",
                "taxonomy_domain": "Información",
                "total_amount": 2,
                "points_per_item": 3.0,
            }
        ]
        slots = evaluation_template_to_slots(items)
        assert slots[0].taxonomy_level == "Recordar"
        assert slots[0].taxonomy_domain == "Información"

    def test_multiple_items(self):
        items = [
            {
                "taxonomy_level": "Recordar",
                "taxonomy_domain": "Información",
                "total_amount": 5,
                "points_per_item": 2.0,
            },
            {
                "taxonomy_level": "Usar-Aplicar",
                "taxonomy_domain": "Procedimiento Mental",
                "total_amount": 3,
                "points_per_item": 10.0,
            },
        ]
        slots = evaluation_template_to_slots(items)
        assert len(slots) == 2

    def test_multiple_items_order_preserved(self):
        items = [
            {
                "taxonomy_level": "A",
                "taxonomy_domain": "X",
                "total_amount": 1,
                "points_per_item": 1.0,
            },
            {
                "taxonomy_level": "B",
                "taxonomy_domain": "Y",
                "total_amount": 2,
                "points_per_item": 2.0,
            },
        ]
        slots = evaluation_template_to_slots(items)
        assert slots[0].taxonomy_level == "A"
        assert slots[1].taxonomy_level == "B"

    def test_empty_items(self):
        slots = evaluation_template_to_slots([])
        assert slots == []

    def test_returns_exercise_slots(self):
        items = [
            {
                "taxonomy_level": "Recordar",
                "taxonomy_domain": "Información",
                "total_amount": 1,
                "points_per_item": 5.0,
            }
        ]
        slots = evaluation_template_to_slots(items)
        assert isinstance(slots[0], ExerciseSlot)


class TestBuildEvalSpec:
    def test_basic(self):
        items = [
            {
                "taxonomy_level": "Recordar",
                "taxonomy_domain": "Información",
                "total_amount": 5,
                "points_per_item": 4.0,
            }
        ]
        spec = build_eval_spec("Parcial 1", items, institution="UCR")
        assert spec.title == "Parcial 1"
        assert spec.total_points == 20.0
        assert spec.institution == "UCR"

    def test_total_points_multiple_items(self):
        items = [
            {
                "taxonomy_level": "A",
                "taxonomy_domain": "B",
                "total_amount": 2,
                "points_per_item": 5.0,
            },
            {
                "taxonomy_level": "C",
                "taxonomy_domain": "D",
                "total_amount": 3,
                "points_per_item": 10.0,
            },
        ]
        spec = build_eval_spec("Test", items)
        assert spec.total_points == 40.0  # 2*5 + 3*10

    def test_returns_eval_spec(self):
        spec = build_eval_spec("My Exam", [])
        assert isinstance(spec, EvalSpec)

    def test_default_institution_empty(self):
        spec = build_eval_spec("Test", [])
        assert spec.institution == ""

    def test_slots_match_items(self):
        items = [
            {
                "taxonomy_level": "Recordar",
                "taxonomy_domain": "Información",
                "total_amount": 3,
                "points_per_item": 2.0,
            }
        ]
        spec = build_eval_spec("Exam", items)
        assert len(spec.slots) == 1
        assert spec.slots[0].count == 3

    def test_empty_items_zero_points(self):
        spec = build_eval_spec("Empty", [])
        assert spec.total_points == 0.0
        assert len(spec.slots) == 0

    def test_spec_is_frozen(self):
        spec = build_eval_spec("Frozen", [])
        with pytest.raises(Exception):
            spec.title = "Changed"  # type: ignore[misc]


class TestEvaluationTemplateInputValidation:
    def test_missing_key_raises_error(self):
        """Missing required keys in template items should raise clear error."""
        items = [{"taxonomy_level": "Recordar"}]  # missing taxonomy_domain, total_amount, points_per_item
        with pytest.raises((ValueError, KeyError)):
            evaluation_template_to_slots(items)

    def test_missing_total_amount_raises_error(self):
        """Item missing total_amount key raises an error."""
        items = [
            {
                "taxonomy_level": "Recordar",
                "taxonomy_domain": "Información",
                "points_per_item": 5.0,
                # missing total_amount
            }
        ]
        with pytest.raises((ValueError, KeyError)):
            evaluation_template_to_slots(items)

    def test_missing_points_per_item_raises_error(self):
        """Item missing points_per_item key raises an error."""
        items = [
            {
                "taxonomy_level": "Recordar",
                "taxonomy_domain": "Información",
                "total_amount": 2,
                # missing points_per_item
            }
        ]
        with pytest.raises((ValueError, KeyError)):
            evaluation_template_to_slots(items)
