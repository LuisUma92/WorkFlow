"""Backward-compat shim. Engine moved to workflow.importer.engine (followup #8)."""
from workflow.importer.engine import (  # noqa: F401
    ImportSchemaError,
    add_concept,
    add_content,
    add_topic,
    import_hierarchy,
    load_yaml,
    validate_schema,
)

__all__ = ["ImportSchemaError", "load_yaml", "validate_schema", "import_hierarchy"]
