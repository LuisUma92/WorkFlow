"""Concept package — ITEP-0012.

Re-exports the ``concept`` Click group for wiring into the root CLI.
"""

from workflow.concept.cli import concept  # noqa: F401

__all__ = ["concept"]
