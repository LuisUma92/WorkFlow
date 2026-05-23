# tests/latexzettel/test_api_imports.py
"""
Smoke tests: latexzettel API modules import cleanly post-shim-removal (LZK-0004).
"""
import importlib

import pytest


def test_api_modules_import_without_shim():
    # analysis requires numpy (optional dep); excluded here.
    # Remaining 6 modules cover the full post-shim import surface.
    from latexzettel.api import notes, render, markdown, sync, export, workflows

    for mod in (notes, render, markdown, sync, export, workflows):
        assert mod.__name__.startswith("latexzettel.api.")


def test_api_notes_public_symbols():
    from latexzettel.api import notes
    assert callable(getattr(notes, "create_note", None)), "create_note missing"


def test_api_workflows_public_symbols():
    from latexzettel.api import workflows
    assert callable(getattr(workflows, "list_recent_notes", None)), "list_recent_notes missing"


def test_api_analysis_requires_numpy():
    """analysis.py requires numpy; if not installed the error is ModuleNotFoundError."""
    try:
        from latexzettel.api import analysis  # noqa: F401
        import numpy  # noqa: F401
        # If both import fine, that's also acceptable
    except ModuleNotFoundError as e:
        assert "numpy" in str(e) or "analysis" in str(e)


def test_shim_orm_module_deleted():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("latexzettel.infra.orm")
