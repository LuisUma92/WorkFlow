"""Backward-compat shim. Moved to workflow.importer.types (followup #8)."""
from workflow.importer.types import ImportResult, RowError  # noqa: F401

__all__ = ["ImportResult", "RowError"]
