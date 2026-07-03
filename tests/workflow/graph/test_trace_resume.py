"""Tests for `workflow graph trace` and `workflow graph resume` (Wave 3 D3)."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.notes import Note, NoteEdge
from workflow.graph.cli import graph
from workflow.graph.analysis import directed_bfs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _enable_fk(dbapi_conn, _cr):
    c = dbapi_conn.cursor()
    c.execute("PRAGMA foreign_keys=ON")
    c.close()


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    event.listen(eng, "connect", _enable_fk)
    GlobalBase.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_note(session: Session, zettel_id: str, title: str = "") -> Note:
    n = Note(
        filename=f"{zettel_id}.md",
        reference=zettel_id,
        zettel_id=zettel_id,
        title=title or zettel_id,
        note_type="permanent",
        source_format="md",
    )
    session.add(n)
    session.flush()
    return n


def _make_edge(
    session: Session,
    source: Note,
    target: Note,
    rel_type: str = "continuation",
) -> NoteEdge:
    e = NoteEdge(
        source_id=source.id,
        target_id=target.id,
        target_zettel_id=target.zettel_id,
        edge_class="structural",
        relation_type=rel_type,
        weight=1.0,
    )
    session.add(e)
    session.flush()
    return e


# ---------------------------------------------------------------------------
# Pure unit tests for directed_bfs helper in analysis.py
# ---------------------------------------------------------------------------


def test_directed_bfs_follows_forward_adjacency():
    """directed_bfs from A reaches B and C in a chain A→B→C."""
    adj = {"A": ["B"], "B": ["C"]}
    result = directed_bfs("A", adj, max_depth=10, node_budget=100)
    assert "A" in result
    assert "B" in result
    assert "C" in result


def test_directed_bfs_max_depth_bound():
    """directed_bfs stops at max_depth hops."""
    adj = {"A": ["B"], "B": ["C"], "C": ["D"]}
    result = directed_bfs("A", adj, max_depth=2, node_budget=100)
    assert "A" in result and result["A"] == 0
    assert "B" in result and result["B"] == 1
    assert "C" in result and result["C"] == 2
    assert "D" not in result


def test_directed_bfs_node_budget_bound():
    """directed_bfs stops when node_budget is hit."""
    adj = {"A": ["B", "C", "D", "E"]}
    result = directed_bfs("A", adj, max_depth=10, node_budget=3)
    assert len(result) <= 3


def test_directed_bfs_no_cross_edges():
    """directed_bfs does not follow reverse edges."""
    # In A→B, starting from B should not reach A
    adj = {"A": ["B"]}  # only A→B, no B→A
    result = directed_bfs("B", adj, max_depth=10, node_budget=100)
    assert "B" in result
    assert "A" not in result


# ---------------------------------------------------------------------------
# CLI: trace command
# ---------------------------------------------------------------------------


def test_trace_cli_finds_ancestors(tmp_path, engine, session):
    """graph trace returns ancestors (parents) of a note along structural edges."""
    # Build chain: A (derived_from) → B (derived_from) → C (root)
    root = _make_note(session, "rootCCCCCCCC", "Root C")
    mid = _make_note(session, "midBBBBBBBB", "Mid B")
    leaf = _make_note(session, "leafAAAAAAAA", "Leaf A")
    _make_edge(session, mid, root)   # mid derived from root
    _make_edge(session, leaf, mid)   # leaf derived from mid
    session.commit()

    runner = CliRunner()
    with patch("workflow.graph.cli.init_global_db", return_value=engine):
        result = runner.invoke(
            graph,
            ["trace", "leafAAAAAAAA", "--json"],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    ancestor_ids = {n["zettel_id"] for n in data["nodes"]}
    assert "midBBBBBBBB" in ancestor_ids
    assert "rootCCCCCCCC" in ancestor_ids


def test_trace_cli_max_depth(tmp_path, engine, session):
    """--max-depth 1 only returns the immediate parent."""
    root = _make_note(session, "rootCCCCCCCC")
    mid = _make_note(session, "midBBBBBBBB")
    leaf = _make_note(session, "leafAAAAAAAA")
    _make_edge(session, mid, root)
    _make_edge(session, leaf, mid)
    session.commit()

    runner = CliRunner()
    with patch("workflow.graph.cli.init_global_db", return_value=engine):
        result = runner.invoke(
            graph,
            ["trace", "leafAAAAAAAA", "--max-depth", "1", "--json"],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    ancestor_ids = {n["zettel_id"] for n in data["nodes"]}
    assert "midBBBBBBBB" in ancestor_ids
    assert "rootCCCCCCCC" not in ancestor_ids


def test_resume_cli_finds_descendants(tmp_path, engine, session):
    """graph resume returns descendants (children) of a note."""
    root = _make_note(session, "rootCCCCCCCC")
    child1 = _make_note(session, "childAAAAAAAA")
    child2 = _make_note(session, "childBBBBBBBB")
    _make_edge(session, child1, root)   # child1 derived from root
    _make_edge(session, child2, root)   # child2 derived from root
    session.commit()

    runner = CliRunner()
    with patch("workflow.graph.cli.init_global_db", return_value=engine):
        result = runner.invoke(
            graph,
            ["resume", "rootCCCCCCCC", "--json"],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    descendant_ids = {n["zettel_id"] for n in data["nodes"]}
    assert "childAAAAAAAA" in descendant_ids
    assert "childBBBBBBBB" in descendant_ids


def test_trace_cli_not_found(tmp_path, engine, session):
    """trace with unknown zettel_id exits nonzero."""
    session.commit()
    runner = CliRunner()
    with patch("workflow.graph.cli.init_global_db", return_value=engine):
        result = runner.invoke(graph, ["trace", "unknownAAAA"])
    assert result.exit_code != 0


def test_resume_cli_text_output(tmp_path, engine, session):
    """graph resume without --json prints human-readable output."""
    root = _make_note(session, "rootCCCCCCCC", "Root Note")
    child = _make_note(session, "childAAAAAAAA", "Child Note")
    _make_edge(session, child, root)
    session.commit()

    runner = CliRunner()
    with patch("workflow.graph.cli.init_global_db", return_value=engine):
        result = runner.invoke(
            graph,
            ["resume", "rootCCCCCCCC"],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, result.output
    assert "childAAAAAAAA" in result.output or "Child Note" in result.output
