"""Tests for ITEP-0013 P2.2 — relations frontmatter parser + sync integration."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from sqlalchemy import select

from workflow.db.models.notes import Note, NoteEdge
from workflow.notes.edges import RelationEntry, parse_relations_frontmatter
from workflow.notes.sync import SyncReport, sync_vault


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_md(path: Path, frontmatter: str, body: str = "") -> Path:
    content = f"---\n{frontmatter.strip()}\n---\n{body}"
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# parse_relations_frontmatter — unit tests
# ---------------------------------------------------------------------------


def test_parse_relations_empty_returns_empty():
    assert parse_relations_frontmatter({}) == []


def test_parse_relations_no_relations_key():
    assert parse_relations_frontmatter({"id": "x", "title": "y"}) == []


def test_parse_relations_structural_derived_from():
    fm = {
        "relations": {
            "derived_from": [
                {"id": "ancestor-id", "type": "refines"},
            ]
        }
    }
    result = parse_relations_frontmatter(fm)
    assert len(result) == 1
    assert result[0] == RelationEntry(
        target_zettel_id="ancestor-id",
        relation_type="refines",
        edge_class="structural",
        weight=1.0,
        rationale=None,
    )


def test_parse_relations_associative_links():
    fm = {
        "relations": {
            "links": [
                {"id": "other-note", "type": "supports"},
            ]
        }
    }
    result = parse_relations_frontmatter(fm)
    assert len(result) == 1
    assert result[0].edge_class == "associative"
    assert result[0].relation_type == "supports"
    assert result[0].target_zettel_id == "other-note"


def test_parse_relations_weight_and_rationale():
    fm = {
        "relations": {
            "derived_from": [
                {"id": "src-synth0", "type": "synthesis", "weight": 0.75, "note": "merged two ideas"},
            ]
        }
    }
    result = parse_relations_frontmatter(fm)
    assert result[0].weight == 0.75
    assert result[0].rationale == "merged two ideas"


def test_parse_relations_invalid_structural_type_skipped():
    fm = {
        "relations": {
            "derived_from": [
                {"id": "tgt", "type": "supports"},   # "supports" is associative, not structural
            ]
        }
    }
    assert parse_relations_frontmatter(fm) == []


def test_parse_relations_invalid_associative_type_skipped():
    fm = {
        "relations": {
            "links": [
                {"id": "tgt", "type": "refines"},   # "refines" is structural, not associative
            ]
        }
    }
    assert parse_relations_frontmatter(fm) == []


def test_parse_relations_missing_id_skipped():
    fm = {
        "relations": {
            "derived_from": [
                {"type": "continuation"},   # no id
            ]
        }
    }
    assert parse_relations_frontmatter(fm) == []


def test_parse_relations_missing_type_skipped():
    fm = {
        "relations": {
            "derived_from": [
                {"id": "some-note"},   # no type
            ]
        }
    }
    assert parse_relations_frontmatter(fm) == []


def test_parse_relations_multiple_mixed():
    fm = {
        "relations": {
            "derived_from": [
                {"id": "ancestor001", "type": "continuation"},
                {"id": "ancestor002", "type": "refines", "weight": 0.5},
            ],
            "links": [
                {"id": "other-note0", "type": "see_also"},
            ],
        }
    }
    result = parse_relations_frontmatter(fm)
    assert len(result) == 3
    classes = [r.edge_class for r in result]
    assert classes.count("structural") == 2
    assert classes.count("associative") == 1


def test_parse_relations_non_dict_relations_skipped():
    """relations: not a dict → empty (defensive)."""
    assert parse_relations_frontmatter({"relations": "invalid"}) == []


def test_parse_relations_invalid_zettel_id_skipped():
    """target_zettel_id not matching NanoID regex is rejected."""
    fm = {
        "relations": {
            "derived_from": [
                {"id": "../../etc/passwd", "type": "continuation"},  # path traversal
                {"id": "short", "type": "continuation"},             # too short (<8 chars)
                {"id": "a" * 22, "type": "continuation"},            # too long (>21 chars)
            ]
        }
    }
    assert parse_relations_frontmatter(fm) == []


def test_parse_relations_nan_weight_defaults_to_one():
    """NaN/inf weight values are replaced with default 1.0."""
    fm = {
        "relations": {
            "derived_from": [
                {"id": "abcd1234", "type": "continuation", "weight": float("inf")},
            ]
        }
    }
    result = parse_relations_frontmatter(fm)
    assert result[0].weight == 1.0


def test_parse_relations_non_list_block_skipped():
    """derived_from: not a list → empty for that block."""
    fm = {"relations": {"derived_from": "not-a-list"}}
    assert parse_relations_frontmatter(fm) == []


# ---------------------------------------------------------------------------
# sync_vault integration — edges
# ---------------------------------------------------------------------------


def test_sync_creates_note_edges_from_derived_from(tmp_path, global_session):
    _write_md(tmp_path / "ancestor.md", "id: ancestor-note\ntitle: Ancestor\ntype: permanent")
    _write_md(
        tmp_path / "child.md",
        textwrap.dedent("""\
            id: child-note
            title: Child
            type: permanent
            relations:
              derived_from:
                - id: ancestor-note
                  type: refines
                  weight: 0.8
                  note: "refined the original"
        """),
    )

    report = sync_vault(tmp_path, global_session)

    assert report.edges_created == 1

    src = global_session.scalars(
        select(Note).where(Note.zettel_id == "child-note")
    ).first()
    tgt = global_session.scalars(
        select(Note).where(Note.zettel_id == "ancestor-note")
    ).first()
    edge = global_session.scalars(select(NoteEdge)).first()
    assert edge is not None
    assert edge.source_id == src.id
    assert edge.target_id == tgt.id
    assert edge.target_zettel_id == "ancestor-note"
    assert edge.edge_class == "structural"
    assert edge.relation_type == "refines"
    assert edge.weight == pytest.approx(0.8)
    assert edge.rationale == "refined the original"


def test_sync_creates_associative_edge_from_links(tmp_path, global_session):
    _write_md(tmp_path / "other.md", "id: other-note\ntitle: Other\ntype: permanent")
    _write_md(
        tmp_path / "main.md",
        textwrap.dedent("""\
            id: main-note
            title: Main
            type: permanent
            relations:
              links:
                - id: other-note
                  type: supports
        """),
    )

    sync_vault(tmp_path, global_session)

    edge = global_session.scalars(select(NoteEdge)).first()
    assert edge is not None
    assert edge.edge_class == "associative"
    assert edge.relation_type == "supports"


def test_sync_edge_unresolved_target_stored_with_null_id(tmp_path, global_session):
    """Edge to a note not yet in vault is stored with target_id=None."""
    _write_md(
        tmp_path / "note.md",
        textwrap.dedent("""\
            id: note-a
            title: Note A
            type: permanent
            relations:
              derived_from:
                - id: non-existent
                  type: continuation
        """),
    )

    sync_vault(tmp_path, global_session)

    edge = global_session.scalars(select(NoteEdge)).first()
    assert edge is not None
    assert edge.target_zettel_id == "non-existent"
    assert edge.target_id is None


def test_sync_edges_idempotent(tmp_path, global_session):
    _write_md(tmp_path / "anc.md", "id: anc-idem-00\ntitle: Anc\ntype: permanent")
    _write_md(
        tmp_path / "src.md",
        textwrap.dedent("""\
            id: src-idem-00
            title: Src
            type: permanent
            relations:
              derived_from:
                - id: anc-idem-00
                  type: continuation
        """),
    )

    sync_vault(tmp_path, global_session)
    report2 = sync_vault(tmp_path, global_session)

    assert report2.edges_created == 0
    assert len(global_session.scalars(select(NoteEdge)).all()) == 1


def test_sync_note_without_relations_unchanged(tmp_path, global_session):
    _write_md(tmp_path / "plain.md", "id: plain-00000\ntitle: Plain\ntype: permanent")
    report = sync_vault(tmp_path, global_session)
    assert report.edges_created == 0
    assert global_session.scalars(select(NoteEdge)).all() == []


def test_sync_dry_run_counts_parseable_edges(tmp_path, global_session):
    """dry_run edges_created counts parseable entries, not DB-delta (documented behaviour)."""
    _write_md(tmp_path / "anc.md", "id: anc12345678\ntitle: Anc\ntype: permanent")
    _write_md(
        tmp_path / "src.md",
        textwrap.dedent("""\
            id: src12345678
            title: Src
            type: permanent
            relations:
              derived_from:
                - id: anc12345678
                  type: continuation
        """),
    )
    report = sync_vault(tmp_path, global_session, dry_run=True)
    assert report.edges_created == 1   # parseable count, not idempotency-aware
    assert global_session.scalars(select(NoteEdge)).all() == []


def test_sync_dry_run_does_not_write_edges(tmp_path, global_session):
    _write_md(tmp_path / "anc.md", "id: anc-dry-000\ntitle: Anc\ntype: permanent")
    _write_md(
        tmp_path / "src.md",
        textwrap.dedent("""\
            id: src-dry-000
            title: Src
            type: permanent
            relations:
              derived_from:
                - id: anc-dry-000
                  type: continuation
        """),
    )
    sync_vault(tmp_path, global_session, dry_run=True)
    assert global_session.scalars(select(NoteEdge)).all() == []
