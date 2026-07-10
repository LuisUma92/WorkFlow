"""Tests for check_graph_against_db (Wave 2 / ITEP-0013 P3 MUST).

TDD RED → GREEN:
  WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest tests/workflow/test_validation_graph.py -q
"""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from click.testing import CliRunner
from sqlalchemy.orm import Session

from workflow.db.models.notes import Note, NoteEdge


# ---------------------------------------------------------------------------
# Helpers (mirror test_dag.py conventions)
# ---------------------------------------------------------------------------


def _note(session: Session, zettel_id: str, title: str | None = None) -> Note:
    n = Note(
        filename=f"{zettel_id}.md",
        reference=zettel_id,
        zettel_id=zettel_id,
        title=title or zettel_id,
    )
    session.add(n)
    session.flush()
    return n


def _struct_edge(
    session: Session,
    src: Note,
    tgt: Note,
    relation_type: str = "continuation",
) -> NoteEdge:
    e = NoteEdge(
        source_id=src.id,
        target_id=tgt.id,
        target_zettel_id=tgt.zettel_id,
        edge_class="structural",
        relation_type=relation_type,
    )
    session.add(e)
    session.flush()
    return e


def _unresolved_edge(
    session: Session,
    src: Note,
    target_zettel_id: str,
    relation_type: str = "continuation",
) -> NoteEdge:
    e = NoteEdge(
        source_id=src.id,
        target_id=None,
        target_zettel_id=target_zettel_id,
        edge_class="structural",
        relation_type=relation_type,
    )
    session.add(e)
    session.flush()
    return e


# ---------------------------------------------------------------------------
# Unit: check_graph_against_db(session)
# ---------------------------------------------------------------------------


def test_graph_clean_no_issues(global_session):
    """Connected A→B graph with no anomalies returns no issues."""
    from workflow.validation.schemas import check_graph_against_db

    a = _note(global_session, "grclean-aaaaaa")
    b = _note(global_session, "grclean-bbbbbb")
    _struct_edge(global_session, a, b)

    issues = check_graph_against_db(global_session)
    # B has incoming edge from A — not an orphan.
    # No cycles, no unresolved, no self-edge, no duplicates.
    assert issues == []


def test_graph_cycle_is_error(global_session):
    """A→B→A structural cycle is reported as severity='error'."""
    from workflow.validation.schemas import check_graph_against_db

    a = _note(global_session, "grcycle-aaaaaa")
    b = _note(global_session, "grcycle-bbbbbb")
    _struct_edge(global_session, a, b)
    _struct_edge(global_session, b, a, relation_type="refines")

    issues = check_graph_against_db(global_session)
    errors = [i for i in issues if i["severity"] == "error"]
    assert len(errors) >= 1
    assert any("cycle" in i["message"].lower() for i in errors)


def test_graph_cycle_returns_note_ids(global_session):
    """Cycle error messages contain the participating note IDs."""
    from workflow.validation.schemas import check_graph_against_db

    a = _note(global_session, "grcycleid-aaaaa")
    b = _note(global_session, "grcycleid-bbbbb")
    _struct_edge(global_session, a, b)
    _struct_edge(global_session, b, a, relation_type="synthesis")

    issues = check_graph_against_db(global_session)
    errors = [i for i in issues if i["severity"] == "error"]
    cycle_msg = " ".join(i["message"] for i in errors)
    assert str(a.id) in cycle_msg or str(b.id) in cycle_msg


def test_graph_unresolved_edge_is_warning(global_session):
    """NoteEdge with target_id=None is reported as severity='warning'."""
    from workflow.validation.schemas import check_graph_against_db

    a = _note(global_session, "grunres-aaaaaa")
    _unresolved_edge(global_session, a, "notexist-abc00")

    issues = check_graph_against_db(global_session)
    warnings = [i for i in issues if i["severity"] == "warning"]
    assert any("notexist-abc00" in i["message"] for i in warnings)


def test_graph_unresolved_multiple(global_session):
    """Multiple unresolved edges each generate a warning."""
    from workflow.validation.schemas import check_graph_against_db

    a = _note(global_session, "grunresm-aaaaa")
    _unresolved_edge(global_session, a, "missing-one00")
    _unresolved_edge(global_session, a, "missing-two00", relation_type="refines")

    issues = check_graph_against_db(global_session)
    msgs = [i["message"] for i in issues if i["severity"] == "warning"]
    targets = {m for m in msgs if "missing-" in m}
    assert len(targets) == 2


def test_graph_orphan_note_is_warning(global_session):
    """Note with zero structural edges (in or out) is reported as orphan warning."""
    from workflow.validation.schemas import check_graph_against_db

    # A and B are connected — not orphans.
    a = _note(global_session, "grorphan-aaaaa")
    b = _note(global_session, "grorphan-bbbbb")
    _struct_edge(global_session, a, b)

    # C has no structural edges → orphan.
    c = _note(global_session, "grorphan-ccccc")

    issues = check_graph_against_db(global_session)
    warnings = [i for i in issues if i["severity"] == "warning"]
    orphan_warns = [i for i in warnings if "orphan" in i["message"].lower()]
    assert len(orphan_warns) >= 1
    assert any(str(c.id) in i["message"] for i in orphan_warns)
    # A and B are not orphans.
    assert not any(str(a.id) in i["message"] for i in orphan_warns)
    assert not any(str(b.id) in i["message"] for i in orphan_warns)


def test_graph_no_orphan_when_only_incoming(global_session):
    """A note that is only a target (no outgoing edges) is NOT an orphan."""
    from workflow.validation.schemas import check_graph_against_db

    a = _note(global_session, "grorpinc-aaaaa")
    b = _note(global_session, "grorpinc-bbbbb")
    _struct_edge(global_session, a, b)  # b has incoming, a has outgoing

    issues = check_graph_against_db(global_session)
    orphan_warns = [
        i for i in issues
        if i["severity"] == "warning" and "orphan" in i["message"].lower()
    ]
    assert orphan_warns == []


def test_graph_self_edge_is_warning(global_session):
    """NoteEdge where target_zettel_id matches source note's own zettel_id → warning."""
    from workflow.validation.schemas import check_graph_against_db

    a = _note(global_session, "grself-aaaaaaa")
    # Self-reference by zettel_id with target_id=None (DB CHECK doesn't catch this).
    self_e = NoteEdge(
        source_id=a.id,
        target_id=None,
        target_zettel_id=a.zettel_id,   # same as source
        edge_class="structural",
        relation_type="continuation",
    )
    global_session.add(self_e)
    global_session.flush()

    issues = check_graph_against_db(global_session)
    warnings = [i for i in issues if i["severity"] == "warning"]
    self_warns = [i for i in warnings if "self" in i["message"].lower()]
    assert len(self_warns) >= 1
    assert any(a.zettel_id in i["message"] for i in self_warns)


def test_graph_no_issues_empty_db(global_session):
    """Empty DB returns no issues (not even orphan warnings for zero notes)."""
    from workflow.validation.schemas import check_graph_against_db

    issues = check_graph_against_db(global_session)
    assert issues == []


def test_graph_warnings_do_not_cause_error_severity(global_session):
    """An unresolved edge produces only warnings, no errors."""
    from workflow.validation.schemas import check_graph_against_db

    a = _note(global_session, "grwarnonly-aaaa")
    _unresolved_edge(global_session, a, "ghost-00000000")

    issues = check_graph_against_db(global_session)
    errors = [i for i in issues if i["severity"] == "error"]
    assert errors == []
    assert any(i["severity"] == "warning" for i in issues)


# ---------------------------------------------------------------------------
# CLI: validate notes --graph
# ---------------------------------------------------------------------------


def _write_note_file(path: Path, zettel_id: str = "noteid-aaaaa") -> None:
    body = dedent(f"""\
        ---
        id: {zettel_id}
        title: Test Note
        type: permanent
        ---

        body text
    """)
    path.write_text(body, encoding="utf-8")


def test_validate_notes_graph_flag_clean(global_engine, tmp_path):
    """--graph on empty vault exits 0 (no issues)."""
    from workflow.validation.cli import validate

    runner = CliRunner()
    _write_note_file(tmp_path / "n.md")
    result = runner.invoke(
        validate,
        ["notes", str(tmp_path), "--graph"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0


def test_validate_notes_graph_flag_cycle_exits_1(global_engine, global_session, tmp_path):
    """--graph with a structural cycle exits 1."""
    from workflow.validation.cli import validate

    a = _note(global_session, "clicycle-aaaaa")
    b = _note(global_session, "clicycle-bbbbb")
    _struct_edge(global_session, a, b)
    _struct_edge(global_session, b, a, relation_type="refines")
    global_session.commit()

    runner = CliRunner()
    _write_note_file(tmp_path / "n.md")
    result = runner.invoke(
        validate,
        ["notes", str(tmp_path), "--graph"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert "cycle" in result.output.lower()


def test_validate_notes_graph_flag_warning_exits_0(global_engine, global_session, tmp_path):
    """--graph with only warnings (unresolved edge) still exits 0."""
    from workflow.validation.cli import validate

    a = _note(global_session, "cliwarn-aaaaaa")
    _unresolved_edge(global_session, a, "ghost-neverex0")
    global_session.commit()

    runner = CliRunner()
    _write_note_file(tmp_path / "n.md")
    result = runner.invoke(
        validate,
        ["notes", str(tmp_path), "--graph"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "warning" in result.output.lower() or "ghost-neverex0" in result.output


def test_validate_notes_graph_not_set_no_graph_check(global_engine, global_session, tmp_path):
    """Without --graph, cycles in DB do NOT affect exit code (validation is file-only)."""
    from workflow.validation.cli import validate

    # Create a cycle in DB but do NOT pass --graph.
    a = _note(global_session, "nograph-aaaaaa")
    b = _note(global_session, "nograph-bbbbbb")
    _struct_edge(global_session, a, b)
    _struct_edge(global_session, b, a, relation_type="synthesis")
    global_session.commit()

    runner = CliRunner()
    _write_note_file(tmp_path / "n.md")
    result = runner.invoke(
        validate,
        ["notes", str(tmp_path)],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    # No --graph: cycle is not checked, exit 0.
    assert result.exit_code == 0
