"""Tests for `notes edges list` and `notes edges show` CLI commands (P2.3).

RED phase: these tests MUST fail until the `edges` subgroup is wired into cli.py.
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


def _make_edge(
    session: Session,
    source_id: int,
    target_zettel_id: str,
    edge_class: str = "structural",
    relation_type: str = "continuation",
    weight: float = 1.0,
    rationale: str | None = None,
) -> NoteEdge:
    edge = NoteEdge(
        source_id=source_id,
        target_zettel_id=target_zettel_id,
        edge_class=edge_class,
        relation_type=relation_type,
        weight=weight,
        rationale=rationale,
    )
    session.add(edge)
    session.flush()
    return edge


# ---------------------------------------------------------------------------
# notes edges list
# ---------------------------------------------------------------------------


def test_edges_list_empty(global_engine):
    """Empty DB → 'No edges found.' message."""
    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "list"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "no edges" in result.output.lower()


def test_edges_list_returns_rows(global_engine, global_session):
    """Pre-seeded edges appear in table output."""
    src = _make_note(global_session, "abc123def456")
    _make_edge(global_session, src.id, "xyz789abc012", relation_type="refines")
    global_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "list"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "abc123def456" in result.output
    assert "xyz789abc012" in result.output
    assert "refines" in result.output


def test_edges_list_filter_source(global_engine, global_session):
    """--source filters by source note's zettel_id."""
    src_a = _make_note(global_session, "aaabbbcccddd")
    src_b = _make_note(global_session, "eeefffoooggg")
    _make_edge(global_session, src_a.id, "target001xxxxx", relation_type="refines")
    _make_edge(global_session, src_b.id, "target002xxxxx", relation_type="see_also")
    global_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "list", "--source", "aaabbbcccddd"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "target001xxxxx" in result.output
    assert "target002xxxxx" not in result.output


def test_edges_list_filter_edge_class(global_engine, global_session):
    """--edge-class filters correctly."""
    src = _make_note(global_session, "filterclass00")
    _make_edge(global_session, src.id, "tgt-struct-xxx", edge_class="structural", relation_type="continuation")
    _make_edge(global_session, src.id, "tgt-assoc-xxx", edge_class="associative", relation_type="see_also")
    global_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "list", "--edge-class", "structural"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "tgt-struct-xxx" in result.output
    assert "tgt-assoc-xxx" not in result.output


def test_edges_list_filter_relation_type(global_engine, global_session):
    """--relation-type filters correctly."""
    src = _make_note(global_session, "filterreltype0")
    _make_edge(global_session, src.id, "tgt-refines-xx", relation_type="refines")
    _make_edge(global_session, src.id, "tgt-see-also-x", relation_type="see_also")
    global_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "list", "--relation-type", "refines"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "tgt-refines-xx" in result.output
    assert "tgt-see-also-x" not in result.output


def test_edges_list_json_output(global_engine, global_session):
    """--json flag produces valid JSON array."""
    src = _make_note(global_session, "jsonlistsrc00")
    edge = _make_edge(
        global_session, src.id, "jsonlisttgt000",
        edge_class="associative", relation_type="supports", weight=0.8,
        rationale="test rationale",
    )
    global_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "list", "--json"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    item = data[0]
    assert item["id"] == edge.id
    assert item["source_id"] == src.id
    assert item["target_zettel_id"] == "jsonlisttgt000"
    assert item["edge_class"] == "associative"
    assert item["relation_type"] == "supports"
    assert abs(item["weight"] - 0.8) < 1e-6
    assert item["rationale"] == "test rationale"


def test_edges_list_source_null_zettel_id(global_engine, global_session):
    """Note without zettel_id still shows in list (src_label falls back to source_id)."""
    note = Note(filename="no-zettel.md", reference="no-zettel")  # zettel_id=None
    global_session.add(note)
    global_session.flush()
    _make_edge(global_session, note.id, "sometargetaaa", relation_type="see_also")
    global_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "list"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "sometargetaaa" in result.output
    # src label falls back to numeric id when zettel_id is None
    assert f"src={note.id}" in result.output


# ---------------------------------------------------------------------------
# notes edges show
# ---------------------------------------------------------------------------


def test_edges_show_existing(global_engine, global_session):
    """Show an existing edge by ID."""
    src = _make_note(global_session, "showsrc123456")
    edge = _make_edge(
        global_session, src.id, "showtgt123456",
        edge_class="structural", relation_type="continuation",
        rationale="because",
    )
    global_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "show", str(edge.id)],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "showtgt123456" in result.output
    assert "continuation" in result.output
    assert "because" in result.output


def test_edges_show_not_found(global_engine):
    """Non-existent edge ID exits with error."""
    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "show", "99999"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "error" in result.output.lower()


def test_edges_show_json(global_engine, global_session):
    """--json flag on show produces valid JSON object."""
    src = _make_note(global_session, "showjsonsrc00")
    edge = _make_edge(
        global_session, src.id, "showjsontgt000",
        edge_class="associative", relation_type="see_also",
    )
    global_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "show", str(edge.id), "--json"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == edge.id
    assert data["target_zettel_id"] == "showjsontgt000"
    assert data["relation_type"] == "see_also"
