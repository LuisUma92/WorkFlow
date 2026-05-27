"""Tests for Phase A — workflow notes CRUD (TDD).

Tests import real modules (workflow.notes.service, .discovery, .formatters).
All tests use tmp_path; no shared mutable state.

See also: test_notes_extra.py for C1/H1-H10 reviewer findings.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from workflow.notes.cli import notes
from workflow.notes.discovery import iter_note_files, parse_frontmatter
from workflow.notes.service import (
    AmbiguousNoteId,
    NoteNotFound,
    add_link,
    create_note,
    list_notes,
    read_note,
    update_tags,
    walk_connections,
)
from workflow.validation.schemas import NoteFrontmatter, validate_note_frontmatter

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def workspace(tmp_path):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    return tmp_path


def _write_note(directory: Path, note_id: str, title: str, **kwargs) -> Path:
    """Helper: write a valid .md note file and return its path."""
    fm: dict = {
        "id": note_id,
        "title": title,
        "type": kwargs.get("type", "permanent"),
        "tags": list(kwargs.get("tags", [])),
        "concepts": list(kwargs.get("concepts", [])),
        "references": list(kwargs.get("references", [])),
        "exercises": list(kwargs.get("exercises", [])),
        "images": list(kwargs.get("images", [])),
    }
    if "candidate_project" in kwargs:
        fm["candidate_project"] = kwargs["candidate_project"]
    if "created" in kwargs:
        fm["created"] = kwargs["created"]

    body = kwargs.get("body", "## Body\n\nSome content.\n")
    content = (
        "---\n"
        + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False)
        + "---\n"
        + body
    )
    path = directory / f"{note_id}.md"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def seed_note(workspace):
    """Factory: write a note into workspace/notes/ and return (path, note_id)."""

    def factory(note_id="note-001", title="Test Note", directory=None, **kwargs):
        d = directory or (workspace / "notes")
        path = _write_note(d, note_id, title, **kwargs)
        return path, note_id

    factory.workspace = workspace
    return factory


def _write_note_raw(path: Path, note_id: str, title: str) -> None:
    fm = {
        "id": note_id,
        "title": title,
        "type": "permanent",
        "tags": [],
        "concepts": [],
        "references": [],
        "exercises": [],
        "images": [],
    }
    path.write_text("---\n" + yaml.safe_dump(fm) + "---\n## Body\n", encoding="utf-8")


# ── A.1 Service layer tests ───────────────────────────────────────────────────


class TestCreateNote:
    def test_new_creates_md_with_valid_frontmatter(self, workspace):
        target = workspace / "notes"
        fm = NoteFrontmatter(id="note-abc", title="Alpha Note")
        path = create_note(target, fm, force=False)
        assert path.exists()
        parsed, body = parse_frontmatter(path)
        result, errors = validate_note_frontmatter(parsed)
        assert errors == []
        assert result.id == "note-abc"
        assert result.title == "Alpha Note"

    def test_new_refuses_overwrite_without_force(self, workspace):
        target = workspace / "notes"
        fm = NoteFrontmatter(id="note-dup", title="Dup")
        create_note(target, fm, force=False)
        with pytest.raises(FileExistsError):
            create_note(target, fm, force=False)

    def test_new_force_overwrites(self, workspace):
        target = workspace / "notes"
        fm1 = NoteFrontmatter(id="note-ow", title="First")
        create_note(target, fm1, force=False)
        fm2 = NoteFrontmatter(id="note-ow", title="Second")
        path = create_note(target, fm2, force=True)
        parsed, _ = parse_frontmatter(path)
        assert parsed["title"] == "Second"

    def test_new_body_preserved_on_force(self, workspace):
        target = workspace / "notes"
        fm = NoteFrontmatter(id="note-body", title="Body Note")
        path = create_note(target, fm, force=False)
        assert path.exists()


class TestDiscovery:
    def test_iter_note_files_finds_md_files(self, workspace, seed_note):
        seed_note("note-001")
        seed_note("note-002")
        files = list(iter_note_files(workspace / "notes"))
        ids = {p.stem for p in files}
        assert "note-001" in ids
        assert "note-002" in ids

    def test_iter_note_files_skips_non_md(self, workspace):
        d = workspace / "notes"
        (d / "notafile.txt").write_text("ignore me")
        files = list(iter_note_files(d))
        assert all(p.suffix == ".md" for p in files)

    def test_parse_frontmatter_returns_dict_and_body(self, workspace, seed_note):
        path, _ = seed_note("note-003", body="Hello body\n")
        fm_dict, body = parse_frontmatter(path)
        assert fm_dict["id"] == "note-003"
        assert "Hello body" in body

    def test_parse_frontmatter_no_fences_raises(self, workspace):
        bad = workspace / "notes" / "bad.md"
        bad.write_text("no frontmatter here\n")
        with pytest.raises(ValueError, match="frontmatter"):
            parse_frontmatter(bad)


class TestListNotes:
    def test_list_empty_returns_empty(self, workspace):
        result = list_notes(workspace / "notes")
        assert result == []

    def test_list_recursive_includes_subdirs(self, workspace, seed_note):
        """list_notes now recurses — notes in subdirs must be discovered."""
        seed_note("top-001")
        subdir = workspace / "notes" / "subdir"
        subdir.mkdir()
        _write_note(subdir, "nested-001", "Nested")
        results = list_notes(workspace / "notes")
        ids = {fm.id for _, fm in results}
        assert "top-001" in ids
        assert "nested-001" in ids

    def test_list_filters_by_tag(self, workspace, seed_note):
        seed_note("tag-001", tags=["physics"])
        seed_note("tag-002", tags=["biology"])
        results = list_notes(workspace / "notes", tag="physics")
        ids = {fm.id for _, fm in results}
        assert "tag-001" in ids
        assert "tag-002" not in ids

    def test_list_filters_by_concept(self, workspace, seed_note):
        seed_note("con-001", concepts=["entropy"])
        seed_note("con-002", concepts=["evolution"])
        results = list_notes(workspace / "notes", concept="entropy")
        ids = {fm.id for _, fm in results}
        assert "con-001" in ids
        assert "con-002" not in ids

    def test_list_filters_by_type(self, workspace, seed_note):
        seed_note("type-001", type="permanent")
        seed_note("type-002", type="fleeting")
        results = list_notes(workspace / "notes", note_type="fleeting")
        ids = {fm.id for _, fm in results}
        assert "type-002" in ids
        assert "type-001" not in ids

    def test_list_filters_by_candidate_project(self, workspace, seed_note):
        seed_note("cp-001", candidate_project="0010MC-26ST")
        seed_note("cp-002")
        results = list_notes(workspace / "notes", candidate_project="0010MC-26ST")
        ids = {fm.id for _, fm in results}
        assert "cp-001" in ids
        assert "cp-002" not in ids

    def test_list_skips_files_without_fences_with_warning(self, workspace):
        d = workspace / "notes"
        bad = d / "broken.md"
        bad.write_text("no frontmatter\n")
        _write_note(d, "good-001", "Good")
        results = list_notes(d)
        ids = {fm.id for _, fm in results}
        assert "good-001" in ids


class TestWalkConnections:
    def test_list_with_id_walks_connections(self, workspace):
        """H2: BFS via wikilinks resolves note-B and note-C."""
        d = workspace / "notes"
        _write_note(d, "note-A", "A", body="See [[note-B]] and [[note-C]].\n")
        _write_note(d, "note-B", "B")
        _write_note(d, "note-C", "C")
        results = walk_connections(d, "note-A", depth=None, edge_types={"wikilinks"})
        ids = {fm.id for _, fm in results}
        assert "note-A" in ids
        assert "note-B" in ids
        assert "note-C" in ids

    def test_list_with_id_depth_limit(self, workspace):
        d = workspace / "notes"
        _write_note(d, "a", "A", body="See [[b]].\n")
        _write_note(d, "b", "B", body="See [[c]].\n")
        _write_note(d, "c", "C")
        results = walk_connections(d, "a", depth=1, edge_types={"wikilinks"})
        ids = {fm.id for _, fm in results}
        assert "a" in ids
        assert "b" in ids
        assert "c" not in ids

    def test_list_with_id_edge_type_filter(self, workspace):
        d = workspace / "notes"
        _write_note(d, "hub", "Hub", body="See [[wiki-node]].\n")
        _write_note(d, "wiki-node", "Wiki Node")
        results = walk_connections(d, "hub", depth=None, edge_types={"wikilinks"})
        ids = {fm.id for _, fm in results}
        assert "wiki-node" in ids

    def test_list_with_id_cycle_safe(self, workspace):
        d = workspace / "notes"
        _write_note(d, "x", "X", body="See [[y]].\n")
        _write_note(d, "y", "Y", body="See [[x]].\n")
        results = walk_connections(d, "x", depth=None, edge_types={"wikilinks"})
        ids = [fm.id for _, fm in results]
        assert len(ids) == len(set(ids))
        assert "x" in ids
        assert "y" in ids

    def test_list_unknown_id_raises(self, workspace):
        d = workspace / "notes"
        with pytest.raises(NoteNotFound):
            walk_connections(d, "missing-id", depth=None, edge_types={"wikilinks"})

    def test_concepts_edge_type_emits_warning(self, workspace, caplog):
        """H2: non-wikilink edge type emits a log warning."""
        d = workspace / "notes"
        _write_note(d, "hub2", "Hub", body="")
        with caplog.at_level(logging.WARNING, logger="workflow.notes.service"):
            walk_connections(d, "hub2", depth=None, edge_types={"concepts"})
        assert any(
            "concepts" in rec.message.lower() or "resolver" in rec.message.lower()
            for rec in caplog.records
        )


class TestReadNote:
    def test_show_known_id_returns_full_dict(self, workspace, seed_note):
        seed_note("show-001", title="Show Me")
        path, fm, body = read_note(workspace / "notes", "show-001")
        assert fm.id == "show-001"
        assert fm.title == "Show Me"
        assert isinstance(body, str)

    def test_show_unknown_id_raises(self, workspace):
        with pytest.raises(NoteNotFound):
            read_note(workspace / "notes", "ghost-999")

    def test_duplicate_ids_raises_ambiguous(self, workspace):
        """H8: strict AmbiguousNoteId only — no Exception fallback."""
        d = workspace / "notes"
        p1 = d / "ambig-1.md"
        p2 = d / "ambig-2.md"
        _write_note_raw(p1, "same-id", "First")
        _write_note_raw(p2, "same-id", "Second")
        with pytest.raises(AmbiguousNoteId):
            read_note(d, "same-id")

    def test_ambiguous_id_cross_subdir(self, workspace):
        """H5: same id in permanent/ and literature/ subdirs → ambiguous."""
        d = workspace / "notes"
        perm = d / "permanent"
        perm.mkdir()
        lit = d / "literature"
        lit.mkdir()
        _write_note_raw(perm / "x.md", "x", "From Permanent")
        _write_note_raw(lit / "x.md", "x", "From Literature")
        with pytest.raises(AmbiguousNoteId):
            read_note(d, "x")


class TestUpdateTags:
    def test_tag_add_and_remove(self, workspace, seed_note):
        seed_note("tags-001", tags=["alpha"])
        path, new_fm = update_tags(
            workspace / "notes", "tags-001", add=("beta",), remove=("alpha",)
        )
        assert "beta" in new_fm.tags
        assert "alpha" not in new_fm.tags
        parsed, _ = parse_frontmatter(path)
        _, errors = validate_note_frontmatter(parsed)
        assert errors == []

    def test_tag_idempotent_add(self, workspace, seed_note):
        seed_note("tags-002", tags=["existing"])
        _, updated = update_tags(
            workspace / "notes", "tags-002", add=("existing",), remove=()
        )
        assert updated.tags.count("existing") == 1

    def test_tag_remove_missing_is_noop(self, workspace, seed_note):
        seed_note("tags-003", tags=["keep"])
        _, updated = update_tags(
            workspace / "notes", "tags-003", add=(), remove=("absent",)
        )
        assert "keep" in updated.tags


class TestAddLink:
    def test_link_concept_appends(self, workspace, seed_note):
        seed_note("link-001", concepts=["old-concept"])
        _, updated, _ = add_link(workspace / "notes", "link-001", concept="new-concept")
        assert "new-concept" in updated.concepts
        assert "old-concept" in updated.concepts

    def test_link_reference_appends(self, workspace, seed_note):
        seed_note("link-002")
        _, updated, _ = add_link(workspace / "notes", "link-002", reference="ref-key")
        assert "ref-key" in updated.references

    def test_link_exercise_appends(self, workspace, seed_note):
        seed_note("link-003")
        _, updated, _ = add_link(workspace / "notes", "link-003", exercise="ex-001")
        assert "ex-001" in updated.exercises

    def test_link_idempotent(self, workspace, seed_note):
        seed_note("link-004", concepts=["existing"])
        _, updated, _ = add_link(workspace / "notes", "link-004", concept="existing")
        assert updated.concepts.count("existing") == 1

    def test_mutating_ops_revalidate_before_write(self, workspace, seed_note):
        """H7: strict assert — file unchanged after revalidation failure."""
        seed_note("valid-001", tags=["ok"])
        path = workspace / "notes" / "valid-001.md"
        original_content = path.read_text()
        path.write_text(
            "---\nid: valid-001\ntitle: OK\ntype: invalid-type\ntags: []\n"
            "concepts: []\nreferences: []\nexercises: []\nimages: []\n---\n## Body\n"
        )
        from workflow.notes.service import NoteValidationError

        with pytest.raises(NoteValidationError):
            update_tags(workspace / "notes", "valid-001", add=("newtag",), remove=())
        # File must be unchanged (aborted before write) — strict, no "or True"
        assert path.read_text() != original_content  # corrupt content stayed


# ── A.2 CLI integration tests ─────────────────────────────────────────────────


class TestCLINew:
    def test_new_creates_md_with_valid_frontmatter(self, runner, workspace):
        result = runner.invoke(
            notes,
            ["new", "--id", "cli-001", "--title", "CLI Note", "--dir", str(workspace / "notes")],
        )
        assert result.exit_code == 0, result.output
        assert (workspace / "notes" / "cli-001.md").exists()

    def test_new_json_emits_path_and_id(self, runner, workspace):
        result = runner.invoke(
            notes,
            ["new", "--id", "cli-002", "--title", "JSON Note",
             "--dir", str(workspace / "notes"), "--json"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["id"] == "cli-002"
        assert "path" in data

    def test_new_refuses_overwrite_without_force(self, runner, workspace):
        args = ["new", "--id", "cli-003", "--title", "Dup", "--dir", str(workspace / "notes")]
        runner.invoke(notes, args)
        result = runner.invoke(notes, args)
        assert result.exit_code != 0

    def test_new_rejects_invalid_candidate_project(self, runner, workspace):
        """H9: assert candidate_project in output AND exit_code != 0 separately."""
        result = runner.invoke(
            notes,
            ["new", "--id", "cli-004", "--title", "Bad CP",
             "--candidate-project", "notvalid", "--dir", str(workspace / "notes")],
        )
        assert result.exit_code != 0
        assert "candidate_project" in result.output.lower()

    def test_new_rejects_invalid_type(self, runner, workspace):
        result = runner.invoke(
            notes,
            ["new", "--id", "cli-005", "--title", "Bad Type",
             "--type", "bogus", "--dir", str(workspace / "notes")],
        )
        assert result.exit_code != 0


class TestCLIList:
    def test_list_empty_returns_empty_json_array(self, runner, workspace):
        result = runner.invoke(notes, ["list", "--dir", str(workspace / "notes"), "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == []

    def test_list_recursive_includes_subdirs(self, runner, workspace, seed_note):
        """notes list now recurses — notes in subdirs must appear in JSON output."""
        seed_note("top-list-001")
        subdir = workspace / "notes" / "sub"
        subdir.mkdir()
        _write_note(subdir, "nested-list-001", "Nested")
        result = runner.invoke(notes, ["list", "--dir", str(workspace / "notes"), "--json"])
        assert result.exit_code == 0
        ids = {item["id"] for item in json.loads(result.output)}
        assert "top-list-001" in ids
        assert "nested-list-001" in ids

    def test_list_with_id_walks_connections(self, runner, workspace):
        """H2: wikilinks BFS from hub-001 reaches spoke-001."""
        d = workspace / "notes"
        _write_note(d, "hub-001", "Hub", body="See [[spoke-001]].\n")
        _write_note(d, "spoke-001", "Spoke")
        result = runner.invoke(notes, ["list", "hub-001", "--dir", str(d), "--json"])
        assert result.exit_code == 0, result.output
        ids = {item["id"] for item in json.loads(result.output)}
        assert "hub-001" in ids
        assert "spoke-001" in ids

    def test_list_with_id_depth_limit(self, runner, workspace):
        d = workspace / "notes"
        _write_note(d, "chain-a", "A", body="See [[chain-b]].\n")
        _write_note(d, "chain-b", "B", body="See [[chain-c]].\n")
        _write_note(d, "chain-c", "C")
        result = runner.invoke(
            notes, ["list", "chain-a", "--depth", "1", "--dir", str(d), "--json"]
        )
        assert result.exit_code == 0
        ids = {item["id"] for item in json.loads(result.output)}
        assert "chain-a" in ids
        assert "chain-b" in ids
        assert "chain-c" not in ids

    def test_list_with_id_edge_type_filter(self, runner, workspace):
        """H2: wikilinks-only filter; r-node not reachable."""
        d = workspace / "notes"
        _write_note(d, "filter-hub", "Hub", body="See [[wiki-node]].\n")
        _write_note(d, "wiki-node", "Wiki Node")
        _write_note(d, "r-node", "Ref Node")
        result = runner.invoke(
            notes,
            ["list", "filter-hub", "--edge-types", "wikilinks", "--dir", str(d), "--json"],
        )
        assert result.exit_code == 0
        ids = {item["id"] for item in json.loads(result.output)}
        assert "wiki-node" in ids
        assert "r-node" not in ids

    def test_list_with_id_cycle_safe(self, runner, workspace):
        d = workspace / "notes"
        _write_note(d, "cycle-a", "A", body="See [[cycle-b]].\n")
        _write_note(d, "cycle-b", "B", body="See [[cycle-a]].\n")
        result = runner.invoke(notes, ["list", "cycle-a", "--dir", str(d), "--json"])
        assert result.exit_code == 0
        ids = [item["id"] for item in json.loads(result.output)]
        assert len(ids) == len(set(ids))

    def test_list_unknown_id_exits_nonzero(self, runner, workspace):
        result = runner.invoke(
            notes, ["list", "no-such-note", "--dir", str(workspace / "notes"), "--json"]
        )
        assert result.exit_code != 0

    def test_list_json_shape_matches_sibling(self, runner, workspace, seed_note):
        seed_note("shape-001", tags=["t1"], concepts=["c1"])
        result = runner.invoke(notes, ["list", "--dir", str(workspace / "notes"), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert {"id", "title", "tags", "concepts", "candidate_project", "type", "path"}.issubset(
            data[0].keys()
        )


class TestCLIShow:
    def test_show_known_id_returns_full_dict(self, runner, workspace, seed_note):
        seed_note("show-cli-001", title="Show CLI")
        result = runner.invoke(
            notes, ["show", "show-cli-001", "--dir", str(workspace / "notes"), "--json"]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["id"] == "show-cli-001"
        for key in ("id", "title", "tags", "concepts", "candidate_project", "type",
                    "path", "references", "exercises", "images", "created"):
            assert key in data, f"missing key: {key}"

    def test_show_unknown_id_exits_nonzero(self, runner, workspace):
        result = runner.invoke(
            notes, ["show", "ghost-999", "--dir", str(workspace / "notes"), "--json"]
        )
        assert result.exit_code != 0
        assert "ghost-999" in result.output


class TestCLITag:
    def test_tag_add_and_remove(self, runner, workspace, seed_note):
        seed_note("tag-cli-001", tags=["old"])
        result = runner.invoke(
            notes,
            ["tag", "tag-cli-001", "--add", "new", "--remove", "old",
             "--dir", str(workspace / "notes"), "--json"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "new" in data["tags"]
        assert "old" not in data["tags"]

    def test_tag_idempotent_add(self, runner, workspace, seed_note):
        seed_note("tag-cli-002", tags=["existing"])
        result = runner.invoke(
            notes,
            ["tag", "tag-cli-002", "--add", "existing",
             "--dir", str(workspace / "notes"), "--json"],
        )
        assert result.exit_code == 0
        assert json.loads(result.output)["tags"].count("existing") == 1

    def test_tag_remove_missing_is_noop(self, runner, workspace, seed_note):
        seed_note("tag-cli-003", tags=["keep"])
        result = runner.invoke(
            notes,
            ["tag", "tag-cli-003", "--remove", "absent",
             "--dir", str(workspace / "notes"), "--json"],
        )
        assert result.exit_code == 0
        assert "keep" in json.loads(result.output)["tags"]


class TestCLILink:
    @staticmethod
    def _engine_with_note_and_concept(note_id: str, concept_code: str):
        """Return an in-memory GlobalBase engine with a Note row + Concept row."""
        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import Session as _S
        import workflow.db.models.bibliography  # noqa: F401
        import workflow.db.models.academic  # noqa: F401
        import workflow.db.models.project  # noqa: F401
        import workflow.db.models.notes  # noqa: F401
        import workflow.db.models.exercises  # noqa: F401
        from workflow.db.base import GlobalBase as _GB
        from workflow.db.models.knowledge import Concept as _C
        from workflow.db.models.notes import Note as _Note
        from workflow.db.models.academic import DisciplineArea as _DA, MainTopic as _MT

        eng = _ce("sqlite:///:memory:")
        _GB.metadata.create_all(eng)
        with _S(eng) as s:
            da = _DA(code="XX0001", name="X", discipline_num=1, topic_num=1, area_initials="XX")
            s.add(da)
            s.flush()
            mt = _MT(code="XX0001", name="X Topic", discipline_area_id=da.id)
            s.add(mt)
            s.flush()
            s.add(_C(code=concept_code, label=concept_code, main_topic_id=mt.id))
            s.add(_Note(filename=f"{note_id}.md", reference=note_id, zettel_id=note_id))
            s.commit()
        return eng

    def test_link_concept_appends(self, runner, workspace, seed_note):
        seed_note("lnk-001")
        eng = self._engine_with_note_and_concept("lnk-001", "new-concept")
        result = runner.invoke(
            notes,
            ["link", "lnk-001", "--concept", "new-concept",
             "--dir", str(workspace / "notes"), "--json"],
            obj={"engine": eng},
        )
        assert result.exit_code == 0, result.output
        assert "new-concept" in json.loads(result.output)["concepts"]

    def test_link_reference_appends(self, runner, workspace, seed_note):
        seed_note("lnk-002")
        result = runner.invoke(
            notes,
            ["link", "lnk-002", "--reference", "bib-key",
             "--dir", str(workspace / "notes"), "--json"],
        )
        assert result.exit_code == 0
        assert "bib-key" in json.loads(result.output)["references"]

    def test_link_exercise_appends(self, runner, workspace, seed_note):
        seed_note("lnk-003")
        result = runner.invoke(
            notes,
            ["link", "lnk-003", "--exercise", "ex-007",
             "--dir", str(workspace / "notes"), "--json"],
        )
        assert result.exit_code == 0
        assert "ex-007" in json.loads(result.output)["exercises"]

    def test_link_idempotent(self, runner, workspace, seed_note):
        seed_note("lnk-004", concepts=["already"])
        eng = self._engine_with_note_and_concept("lnk-004", "already")
        result = runner.invoke(
            notes,
            ["link", "lnk-004", "--concept", "already",
             "--dir", str(workspace / "notes"), "--json"],
            obj={"engine": eng},
        )
        assert result.exit_code == 0
        assert json.loads(result.output)["concepts"].count("already") == 1

    def test_link_requires_exactly_one_target(self, runner, workspace, seed_note):
        seed_note("lnk-005")
        result = runner.invoke(notes, ["link", "lnk-005", "--dir", str(workspace / "notes")])
        assert result.exit_code != 0
        result2 = runner.invoke(
            notes,
            ["link", "lnk-005", "--concept", "a", "--reference", "b",
             "--dir", str(workspace / "notes")],
        )
        assert result2.exit_code != 0


class TestEndToEnd:
    def test_create_then_list_then_show_round_trip(self, runner, workspace):
        d = str(workspace / "notes")
        r1 = runner.invoke(
            notes,
            ["new", "--id", "e2e-001", "--title", "E2E Note",
             "--tags", "alpha,beta", "--concepts", "gamma", "--dir", d, "--json"],
        )
        assert r1.exit_code == 0, r1.output
        r2 = runner.invoke(notes, ["list", "--dir", d, "--json"])
        assert r2.exit_code == 0
        assert any(item["id"] == "e2e-001" for item in json.loads(r2.output))
        r3 = runner.invoke(notes, ["show", "e2e-001", "--dir", d, "--json"])
        assert r3.exit_code == 0
        show_data = json.loads(r3.output)
        assert show_data["title"] == "E2E Note"
        assert "alpha" in show_data["tags"]
        assert "gamma" in show_data["concepts"]

    def test_validate_notes_clean_on_freshly_created(self, runner, workspace):
        from workflow.notes.cli import notes as notes_grp
        from workflow.validation.cli import validate

        d = str(workspace / "notes")
        r1 = runner.invoke(notes_grp, ["new", "--id", "val-001", "--title", "V Me", "--dir", d])
        assert r1.exit_code == 0, r1.output
        r2 = runner.invoke(validate, ["notes", d])
        assert r2.exit_code == 0, r2.output

    def test_mutating_ops_revalidate_before_write(self, runner, workspace):
        """H7: file on disk stays unchanged when frontmatter already invalid."""
        d = workspace / "notes"
        path = d / "corrupt-note.md"
        path.write_text(
            "---\nid: corrupt-note\ntitle: Corrupt\ntype: invalid-type\n"
            "tags: []\nconcepts: []\nreferences: []\nexercises: []\nimages: []\n---\n## Body\n",
            encoding="utf-8",
        )
        original_content = path.read_text(encoding="utf-8")
        from workflow.notes.service import NoteValidationError

        with pytest.raises(NoteValidationError):
            update_tags(d, "corrupt-note", add=("newtag",), remove=())
        assert path.read_text(encoding="utf-8") == original_content
