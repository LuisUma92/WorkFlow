"""Regression tests for GeneralDirectory values (ITEP-0008 Phase C, finding 2)."""

from __future__ import annotations

from itep.structure import GeneralDirectory


def test_general_directory_lectures() -> None:
    """GeneralDirectory.LEC must be '0000AL-Lectures' (not 00AA-Lectures)."""
    assert GeneralDirectory.LEC == "0000AL-Lectures"


def test_general_directory_images() -> None:
    """GeneralDirectory.IMG must be '0000II-ImagesFigures'."""
    assert GeneralDirectory.IMG == "0000II-ImagesFigures"


def test_general_directory_library() -> None:
    """GeneralDirectory.BIB must be '0000BB-Library'."""
    assert GeneralDirectory.BIB == "0000BB-Library"


def test_general_directory_examples() -> None:
    """GeneralDirectory.EXE must be '0000EE-ExamplesExercises'."""
    assert GeneralDirectory.EXE == "0000EE-ExamplesExercises"
