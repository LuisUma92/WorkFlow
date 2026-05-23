"""Tests for DAG cycle detection on structural NoteEdges (P2.4).

RED phase: fail until dag.py + `notes edges check` command exist.
"""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from sqlalchemy.orm import Session

from workflow.db.models.notes import Note, NoteEdge
from workflow.notes.cli import notes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_note(session: Session, zettel_id: str) -> Note:
    note = Note(filename=f"{zettel_id}.md", reference=zettel_id, zettel_id=zettel_id)
    session.add(note)
    session.flush()
    return note


def _add_structural_edge(session: Session, src: Note, tgt: Note, relation_type: str = "continuation") -> NoteEdge:
    edge = NoteEdge(
        source_id=src.id,
        target_id=tgt.id,
        target_zettel_id=tgt.zettel_id,
        edge_class="structural",
        relation_type=relation_type,
    )
    session.add(edge)
    session.flush()
    return edge


def _add_associative_edge(session: Session, src: Note, tgt_zettel_id: str) -> NoteEdge:
    edge = NoteEdge(
        source_id=src.id,
        target_zettel_id=tgt_zettel_id,
        edge_class="associative",
        relation_type="see_also",
    )
    session.add(edge)
    session.flush()
    return edge


# ---------------------------------------------------------------------------
# Unit: detect_structural_cycles(session) service function
# ---------------------------------------------------------------------------


def test_detect_cycles_empty_db(global_session):
    from workflow.notes.dag import detect_structural_cycles
    assert detect_structural_cycles(global_session) == []


def test_detect_cycles_no_cycle_linear(global_session):
    """A→B→C (linear chain) has no cycle."""
    from workflow.notes.dag import detect_structural_cycles
    a = _make_note(global_session, "daglinear-a000")
    b = _make_note(global_session, "daglinear-b000")
    c = _make_note(global_session, "daglinear-c000")
    _add_structural_edge(global_session, a, b)
    _add_structural_edge(global_session, b, c)
    assert detect_structural_cycles(global_session) == []


def test_detect_cycles_no_cycle_branching(global_session):
    """A→B, A→C, B→D, C→D (diamond, no cycle)."""
    from workflow.notes.dag import detect_structural_cycles
    a = _make_note(global_session, "dagdiamond-a00")
    b = _make_note(global_session, "dagdiamond-b00")
    c = _make_note(global_session, "dagdiamond-c00")
    d = _make_note(global_session, "dagdiamond-d00")
    _add_structural_edge(global_session, a, b)
    _add_structural_edge(global_session, a, c)
    _add_structural_edge(global_session, b, d)
    _add_structural_edge(global_session, c, d)
    assert detect_structural_cycles(global_session) == []


def test_detect_cycles_simple_cycle(global_session):
    """A→B→A — two-node cycle."""
    from workflow.notes.dag import detect_structural_cycles
    a = _make_note(global_session, "dagcycle2a-0000")
    b = _make_note(global_session, "dagcycle2b-0000")
    _add_structural_edge(global_session, a, b, relation_type="continuation")
    _add_structural_edge(global_session, b, a, relation_type="refines")
    cycles = detect_structural_cycles(global_session)
    assert len(cycles) >= 1
    # Every returned cycle is a list of note ids; first == last (closed path)
    for cycle in cycles:
        assert isinstance(cycle, list)
        assert len(cycle) >= 2
        assert cycle[0] == cycle[-1]
    # The cycle must include both a.id and b.id
    all_ids = {nid for cycle in cycles for nid in cycle}
    assert a.id in all_ids
    assert b.id in all_ids


def test_detect_cycles_three_node_cycle(global_session):
    """A→B→C→A — three-node cycle."""
    from workflow.notes.dag import detect_structural_cycles
    a = _make_note(global_session, "dagcycle3a-0000")
    b = _make_note(global_session, "dagcycle3b-0000")
    c = _make_note(global_session, "dagcycle3c-0000")
    _add_structural_edge(global_session, a, b)
    _add_structural_edge(global_session, b, c)
    _add_structural_edge(global_session, c, a)
    cycles = detect_structural_cycles(global_session)
    assert len(cycles) >= 1
    all_ids = {nid for cycle in cycles for nid in cycle}
    assert a.id in all_ids
    assert b.id in all_ids
    assert c.id in all_ids


def test_detect_cycles_excludes_unresolved_edges(global_session):
    """Edges with target_id=None are excluded from cycle detection."""
    from workflow.notes.dag import detect_structural_cycles
    a = _make_note(global_session, "dagunresolved-0")
    # Edge pointing to an unresolved target (target_id=None)
    unresolved = NoteEdge(
        source_id=a.id,
        target_id=None,
        target_zettel_id="notyet-in-db-000",
        edge_class="structural",
        relation_type="continuation",
    )
    global_session.add(unresolved)
    global_session.flush()
    assert detect_structural_cycles(global_session) == []


def test_detect_cycles_excludes_associative_edges(global_session):
    """Associative edges that form a 'cycle' are ignored — only structural edges checked."""
    from workflow.notes.dag import detect_structural_cycles
    a = _make_note(global_session, "dagassoc-a00000")
    b = _make_note(global_session, "dagassoc-b00000")
    # Associative "cycle" — must not be reported
    _add_associative_edge(global_session, a, b.zettel_id)
    _add_associative_edge(global_session, b, a.zettel_id)
    assert detect_structural_cycles(global_session) == []


def test_detect_cycles_deep_chain_no_crash(global_session):
    """Linear chain of 1200 nodes must not raise RecursionError."""
    from workflow.notes.dag import detect_structural_cycles

    # Build 1200-node linear chain: n0 → n1 → ... → n1199 (no cycle)
    prev_note = _make_note(global_session, f"deepchain-{0:04d}")
    for i in range(1, 1200):
        cur = _make_note(global_session, f"deepchain-{i:04d}")
        _add_structural_edge(global_session, prev_note, cur)
        prev_note = cur

    result = detect_structural_cycles(global_session)
    assert result == []


# ---------------------------------------------------------------------------
# CLI: notes edges check
# ---------------------------------------------------------------------------


def test_edges_check_no_cycles(global_engine):
    """Empty DB → exits 0, reports 'no cycles'."""
    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "check"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "no cycle" in result.output.lower()


def test_edges_check_reports_cycle(global_engine, global_session):
    """DB with cycle → exits non-zero (or reports cycle count)."""
    a = _make_note(global_session, "clichecycle-a00")
    b = _make_note(global_session, "clichecycle-b00")
    _add_structural_edge(global_session, a, b)
    _add_structural_edge(global_session, b, a)
    global_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "check"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    # Exit 1 when cycles found; output mentions cycle
    assert result.exit_code == 1
    assert "cycle" in result.output.lower()


def test_edges_check_json_no_cycles(global_engine):
    """--json with no cycles returns {cycles: []}."""
    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "check", "--json"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == {"cycles": []}


def test_edges_check_json_with_cycles(global_engine, global_session):
    """--json with cycles returns {cycles: [[...]]}."""
    a = _make_note(global_session, "jsoncycle-a0000")
    b = _make_note(global_session, "jsoncycle-b0000")
    _add_structural_edge(global_session, a, b)
    _add_structural_edge(global_session, b, a)
    global_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "check", "--json"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert "cycles" in data
    assert len(data["cycles"]) >= 1
    # Each cycle is a non-empty list of ints
    for cycle in data["cycles"]:
        assert isinstance(cycle, list)
        assert all(isinstance(n, int) for n in cycle)
