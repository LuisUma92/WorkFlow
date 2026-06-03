"""Backward-compat shim. Moved to workflow.importer.formatters (followup #8)."""
from workflow.importer.formatters import (  # noqa: F401
    format_import_json,
    format_import_table,
)

__all__ = ["format_import_json", "format_import_table"]
