"""Tests for P2.5 — target resolution pass (target_zettel_id → target_id).

RED phase: fail until resolve_edge_targets() + `notes edges resolve` exist.
"""
from __future__ import annotations

import json

from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.models.notes import Note, NoteEdge
from workflow.notes.cli import notes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _note(session: Session, zettel_id: str) -> Note:
    n = Note(filename=f"{zettel_id}.md", reference=zettel_id, zettel_id=zettel_id)
    session.add(n)
    session.flush()
    return n


def _unresolved_edge(session: Session, src: Note, target_zettel_id: str) -> NoteEdge:
    edge = NoteEdge(
        source_id=src.id,
        target_id=None,
        target_zettel_id=target_zettel_id,
        edge_class="structural",
        relation_type="continuation",
    )
    session.add(edge)
    session.flush()
    return edge


def _resolved_edge(session: Session, src: Note, tgt: Note) -> NoteEdge:
    edge = NoteEdge(
        source_id=src.id,
        target_id=tgt.id,
        target_zettel_id=tgt.zettel_id,
        edge_class="structural",
        relation_type="continuation",
    )
    session.add(edge)
    session.flush()
    return edge


# ---------------------------------------------------------------------------
# Unit: resolve_edge_targets
# ---------------------------------------------------------------------------


def test_resolve_empty_db(global_session):
    from workflow.notes.resolve import ResolveReport, resolve_edge_targets

    report = resolve_edge_targets(global_session)
    assert isinstance(report, ResolveReport)
    assert report.resolved == 0
    assert report.unresolved == 0


def test_resolve_fills_target_id(global_session):
    """Unresolved edge whose target zettel_id exists in Note is resolved."""
    from workflow.notes.resolve import resolve_edge_targets

    src = _note(global_session, "resolve-src-000")
    tgt = _note(global_session, "resolve-tgt-000")
    edge = _unresolved_edge(global_session, src, "resolve-tgt-000")

    report = resolve_edge_targets(global_session)

    assert report.resolved == 1
    assert report.unresolved == 0
    global_session.refresh(edge)
    assert edge.target_id == tgt.id


def test_resolve_counts_unresolved(global_session):
    """Edge pointing to a zettel_id not yet in Note stays unresolved."""
    from workflow.notes.resolve import resolve_edge_targets

    src = _note(global_session, "resolve-missing0")
    _unresolved_edge(global_session, src, "not-in-db-00000")

    report = resolve_edge_targets(global_session)

    assert report.resolved == 0
    assert report.unresolved == 1


def test_resolve_mixed(global_session):
    """Two edges: one resolvable, one not."""
    from workflow.notes.resolve import resolve_edge_targets

    src = _note(global_session, "resolve-mixsrc00")
    tgt = _note(global_session, "resolve-mixtgt00")
    edge_ok = _unresolved_edge(global_session, src, "resolve-mixtgt00")
    edge_missing = _unresolved_edge(global_session, src, "nonexistent0000")

    report = resolve_edge_targets(global_session)

    assert report.resolved == 1
    assert report.unresolved == 1
    global_session.refresh(edge_ok)
    global_session.refresh(edge_missing)
    assert edge_ok.target_id == tgt.id
    assert edge_missing.target_id is None


def test_resolve_skips_already_resolved(global_session):
    """Edges with target_id already set are not touched."""
    from workflow.notes.resolve import resolve_edge_targets

    src = _note(global_session, "resolve-already0")
    tgt = _note(global_session, "resolve-alrtgt00")
    edge = _resolved_edge(global_session, src, tgt)

    report = resolve_edge_targets(global_session)

    assert report.resolved == 0
    assert report.unresolved == 0
    global_session.refresh(edge)
    assert edge.target_id == tgt.id  # unchanged


def test_resolve_idempotent(global_session):
    """Running resolve twice produces the same result."""
    from workflow.notes.resolve import resolve_edge_targets

    src = _note(global_session, "resolve-idem-000")
    _note(global_session, "resolve-idemtgt0")
    _unresolved_edge(global_session, src, "resolve-idemtgt0")

    r1 = resolve_edge_targets(global_session)
    r2 = resolve_edge_targets(global_session)

    assert r1.resolved == 1
    assert r2.resolved == 0  # already resolved on second pass


def test_resolve_dry_run_does_not_mutate(global_session):
    """dry_run=True reports what would be resolved but does not update target_id."""
    from workflow.notes.resolve import resolve_edge_targets

    src = _note(global_session, "resolve-dryrun00")
    _note(global_session, "resolve-drytgt00")
    edge = _unresolved_edge(global_session, src, "resolve-drytgt00")

    report = resolve_edge_targets(global_session, dry_run=True)

    assert report.resolved == 1
    global_session.refresh(edge)
    assert edge.target_id is None  # NOT mutated


def test_resolve_dry_run_survives_commit(global_engine):
    """dry_run=True + subsequent commit must not persist any target_id change.

    Pins the invariant: even if a caller commits after dry_run, no rows change.
    """
    from sqlalchemy import select

    from workflow.notes.resolve import resolve_edge_targets

    with Session(global_engine) as session:
        src = _note(session, "resolve-drcmt-00")
        _note(session, "resolve-drcmtt0")
        edge = _unresolved_edge(session, src, "resolve-drcmtt0")
        session.commit()
        edge_id = edge.id

    with Session(global_engine) as session:
        resolve_edge_targets(session, dry_run=True)
        session.commit()  # intentional: simulates caller error

    with Session(global_engine) as session:
        reloaded = session.get(NoteEdge, edge_id)
        assert reloaded.target_id is None


# ---------------------------------------------------------------------------
# CLI: notes edges resolve
# ---------------------------------------------------------------------------


def test_cli_resolve_no_edges(global_engine):
    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "resolve"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "resolved" in result.output.lower()


def test_cli_resolve_resolves_edge(global_engine, global_session):
    src = _note(global_session, "cliresolve-src0")
    _note(global_session, "cliresolve-tgt0")
    _unresolved_edge(global_session, src, "cliresolve-tgt0")
    global_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "resolve"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "1" in result.output


def test_cli_resolve_dry_run(global_engine, global_session):
    src = _note(global_session, "clidryrun-src00")
    _note(global_session, "clidryrun-tgt00")
    _unresolved_edge(global_session, src, "clidryrun-tgt00")
    global_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "resolve", "--dry-run"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "dry" in result.output.lower()


def test_cli_resolve_json(global_engine, global_session):
    src = _note(global_session, "clijson-src0000")
    _note(global_session, "clijson-tgt0000")
    _unresolved_edge(global_session, src, "clijson-tgt0000")
    global_session.commit()

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["edges", "resolve", "--json"],
        obj={"engine": global_engine},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["resolved"] == 1
    assert data["unresolved"] == 0
    assert data["dry_run"] is False
