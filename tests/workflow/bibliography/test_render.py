"""Tests for the relocated public render surface (Wave A — A5, ADR-0020).

The biblatex/bibtex rendering helpers were moved out of
``workflow.prisma.exporter`` into the foundation-layer module
``workflow.bibliography.render``. ``prisma.exporter`` keeps thin re-export
aliases so existing callers (and the dialect test suite) keep working.

These tests pin:
1. the new public API exists and renders correctly,
2. the ``prisma.exporter`` shim names are the *same objects* as the render
   functions (no divergent copies),
3. the foundation-layer boundary (ADR-0020): ``render`` must not import
   upward from ``workflow.prisma``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from workflow.bibliography import render
from workflow.db.models.bibliography import BibEntry


# ---------------------------------------------------------------------------
# Public API presence
# ---------------------------------------------------------------------------


def test_public_render_api_exported():
    """The four public render entry points are present and callable."""
    for name in (
        "entry_to_biblatex",
        "entry_to_bibtex",
        "biblatex_field_pairs",
        "bibtex_field_pairs",
    ):
        assert hasattr(render, name), f"render.{name} missing"
        assert callable(getattr(render, name))
        assert name in render.__all__


# ---------------------------------------------------------------------------
# Shim equivalence — exporter re-exports the SAME objects
# ---------------------------------------------------------------------------


def test_exporter_shim_reexports_same_objects():
    """``prisma.exporter`` private names alias the render functions exactly."""
    from workflow.prisma import exporter

    assert exporter._entry_to_biblatex is render.entry_to_biblatex
    assert exporter._entry_to_bibtex is render.entry_to_bibtex
    assert exporter._biblatex_field_pairs is render.biblatex_field_pairs
    assert exporter._bibtex_field_pairs is render.bibtex_field_pairs


# ---------------------------------------------------------------------------
# Rendering behaviour through the new public API
# ---------------------------------------------------------------------------


@pytest.fixture
def entry(global_session):
    e = BibEntry(
        entry_type="article",
        bibkey="render2040a",
        title="Render Module Test",
        year=2040,
        volume=3,
    )
    global_session.add(e)
    global_session.flush()
    return e


def test_entry_to_biblatex_renders_block(entry):
    block = render.entry_to_biblatex(entry)
    assert block.startswith("@article{render2040a,")
    assert "title = {Render Module Test}," in block
    assert block.rstrip().endswith("}")


def test_entry_to_bibtex_renders_block(entry):
    block = render.entry_to_bibtex(entry)
    assert block.startswith("@article{render2040a,")
    assert "title = {Render Module Test}," in block


def test_biblatex_field_pairs_returns_tuples(entry):
    pairs = render.biblatex_field_pairs(entry)
    assert ("title", "Render Module Test") in pairs
    assert all(isinstance(p, tuple) and len(p) == 2 for p in pairs)


# ---------------------------------------------------------------------------
# Foundation-layer boundary (ADR-0020): render must not import from prisma
# ---------------------------------------------------------------------------


def test_render_does_not_import_from_prisma():
    src = Path(render.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("workflow.prisma"), (
                f"render.py imports upward from {node.module} — violates ADR-0020"
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("workflow.prisma"), (
                    f"render.py imports {alias.name} — violates ADR-0020"
                )
