"""Workflow vault package — ITEP-0011 vault unification.

Public API:
    unify(...) -> UnifyReport
"""

from workflow.vault.unify import UnifyReport, unify

__all__ = ["UnifyReport", "unify"]
