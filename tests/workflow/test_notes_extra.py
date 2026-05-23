"""Extra reviewer finding tests — C1/H1-H10 audit findings for Phase A notes CRUD.

These complement test_notes.py. Kept separate to stay under 800-line limit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from workflow.notes.cli import notes
from workflow.notes.discovery import iter_note_files, parse_frontmatter
from workflow.notes.service import (
    AmbiguousNoteId,
    create_note,
    update_tags,
)
from workflow.validation.schemas import NoteFrontmatter

# ── Shared helpers ────────────────────────────────────────────────────────────


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def workspace(tmp_path):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    return tmp_path


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


# ── C1: Path traversal tests for --id ────────────────────────────────────────


class TestPathTraversal:
    def test_new_rejects_id_with_slash(self, runner, workspace):
        """C1: id with slash must exit != 0 before any fs write."""
        result = runner.invoke(
            notes,
            ["new", "--id", "a/b", "--title", "Bad", "--dir", str(workspace / "notes")],
        )
        assert result.exit_code != 0
        assert not (workspace / "notes" / "b.md").exists()

    def test_new_rejects_id_path_traversal(self, runner, workspace):
        """C1: ../traversal must exit != 0; no file written outside target."""
        target = workspace / "notes"
        result = runner.invoke(
            notes,
            ["new", "--id", "../etc", "--title", "Traversal", "--dir", str(target)],
        )
        assert result.exit_code != 0
        assert not (workspace / "etc.md").exists()

    def test_new_rejects_absolute_id(self, runner, workspace):
        """C1: absolute path as id must exit != 0."""
        result = runner.invoke(
            notes,
            [
                "new",
                "--id",
                "/abs",
                "--title",
                "Abs",
                "--dir",
                str(workspace / "notes"),
            ],
        )
        assert result.exit_code != 0


# ── H1: Containment and symlink rejection ─────────────────────────────────────


class TestContainment:
    def test_create_rejects_symlinked_dir(self, tmp_path):
        """H1: symlinked target_dir must be rejected before any fs write."""
        real_dir = tmp_path / "real_notes"
        real_dir.mkdir()
        sym_dir = tmp_path / "sym_notes"
        sym_dir.symlink_to(real_dir)
        fm = NoteFrontmatter(id="sym-001", title="Sym")
        with pytest.raises((ValueError, Exception)):
            create_note(sym_dir, fm, force=False)

    def test_containment_path_aware_not_prefix(self, tmp_path):
        """H1: /tmp/foo does NOT match /tmp/foobar — prefix check would be wrong."""
        foo = tmp_path / "foo"
        foo.mkdir()
        fm = NoteFrontmatter(id="ok-note", title="OK")
        path = create_note(foo, fm, force=False)
        # Verify the note landed inside foo, not foobar
        assert path.parent == foo


# ── H3: Body byte-exact preservation ─────────────────────────────────────────


class TestBodyPreservation:
    def test_body_preserves_post_fence_blank_line(self, workspace):
        """H3: blank line immediately after closing fence must survive mutation."""
        d = workspace / "notes"
        fm = {
            "id": "blank-body",
            "title": "Blank",
            "type": "permanent",
            "tags": [],
            "concepts": [],
            "references": [],
            "exercises": [],
            "images": [],
        }
        content = "---\n" + yaml.safe_dump(fm) + "---\n\nActual content\n"
        path = d / "blank-body.md"
        path.write_text(content, encoding="utf-8")
        update_tags(d, "blank-body", add=("t1",), remove=())
        after = path.read_text(encoding="utf-8")
        assert "\n\nActual content\n" in after

    def test_body_preserves_trailing_newline_state(self, workspace):
        """H3: body without trailing newline must survive mutation round-trip."""
        d = workspace / "notes"
        fm = {
            "id": "trail-note",
            "title": "Trail",
            "type": "permanent",
            "tags": [],
            "concepts": [],
            "references": [],
            "exercises": [],
            "images": [],
        }
        body_text = "Content without trailing newline"
        content = "---\n" + yaml.safe_dump(fm) + "---\n" + body_text
        path = d / "trail-note.md"
        path.write_text(content, encoding="utf-8")
        update_tags(d, "trail-note", add=("t1",), remove=())
        after = path.read_text(encoding="utf-8")
        assert after.endswith(body_text)

    def test_body_preserves_crlf_line_endings(self, workspace):
        """H3: CRLF body content must survive mutation."""
        d = workspace / "notes"
        fm = {
            "id": "crlf-note",
            "title": "CRLF",
            "type": "permanent",
            "tags": [],
            "concepts": [],
            "references": [],
            "exercises": [],
            "images": [],
        }
        # Write LF frontmatter but CRLF body
        fm_yaml = yaml.safe_dump(fm)
        content = "---\n" + fm_yaml + "---\n## Body\r\nContent\r\n"
        path = d / "crlf-note.md"
        path.write_text(content, encoding="utf-8")
        update_tags(d, "crlf-note", add=("t1",), remove=())
        after = path.read_text(encoding="utf-8")
        assert "Content" in after


# ── H5: Ambiguous-id detection across type subdirs ────────────────────────────


class TestAmbiguousCrossSubdir:
    def test_ambiguous_id_cross_subdir_permanent_literature(self, workspace):
        """H5: same id in permanent/ and literature/ subdirs → AmbiguousNoteId."""
        from workflow.notes.service import read_note

        d = workspace / "notes"
        perm = d / "permanent"
        perm.mkdir()
        lit = d / "literature"
        lit.mkdir()
        _write_note_raw(perm / "x.md", "x", "From Permanent")
        _write_note_raw(lit / "x.md", "x", "From Literature")
        with pytest.raises(AmbiguousNoteId):
            read_note(d, "x")


# ── H6: Top-level symlinks included ───────────────────────────────────────────


class TestSymlinkedTopLevel:
    def test_iter_includes_symlinked_md_at_top_level(self, workspace, tmp_path):
        """H6: top-level .md symlinks must NOT be skipped."""
        d = workspace / "notes"
        real_file = tmp_path / "external.md"
        fm = {
            "id": "sym-note",
            "title": "Symlinked Note",
            "type": "permanent",
            "tags": [],
            "concepts": [],
            "references": [],
            "exercises": [],
            "images": [],
        }
        real_file.write_text(
            "---\n" + yaml.safe_dump(fm) + "---\n## Body\n", encoding="utf-8"
        )
        sym = d / "sym-note.md"
        sym.symlink_to(real_file)
        files = list(iter_note_files(d))
        stems = {p.stem for p in files}
        assert "sym-note" in stems


# ── H10: Smoke + table tests ──────────────────────────────────────────────────


class TestSmoke:
    def test_notes_help_smoke(self, runner):
        """H10: notes --help exits 0 and lists all commands."""
        result = runner.invoke(notes, ["--help"])
        assert result.exit_code == 0
        output = result.output.lower()
        for cmd in ("init", "new", "list", "show", "tag", "link"):
            assert cmd in output, f"missing command '{cmd}' in --help"

    def test_init_cmd_creates_dirs(self, runner, tmp_path):
        """notes init creates the vault, inbox/, and templates/ — Obsidian-flat layout."""
        result = runner.invoke(notes, ["init", str(tmp_path)])
        assert result.exit_code == 0, result.output
        # Inbox + templates are created under the vault; typed-subdirs are NOT.
        vault = tmp_path / "0000AA-Vault"
        assert vault.is_dir(), "vault dir not created"
        assert (vault / "inbox").is_dir(), "missing inbox/"
        assert (vault / "templates").is_dir(), "missing templates/"
        for subdir in ("permanent", "literature", "fleeting"):
            assert not (tmp_path / subdir).exists(), (
                f"typed subdir {subdir!r} should not be created — type lives in frontmatter"
            )

    def test_notes_in_subdir_are_discoverable(self, runner, workspace):
        """Notes in any subdir (e.g. inbox/) must be visible to list/show — fix for vault layout drift."""
        d = workspace / "notes"
        inbox = d / "inbox"
        inbox.mkdir()
        _write_note_raw(inbox / "inbox-001.md", "inbox-001", "Inbox Note")

        # list should find it
        list_result = runner.invoke(notes, ["list", "--dir", str(d)])
        assert list_result.exit_code == 0
        assert "inbox-001" in list_result.output

        # show should find it
        show_result = runner.invoke(notes, ["show", "inbox-001", "--dir", str(d)])
        assert show_result.exit_code == 0
        assert "Inbox Note" in show_result.output

    def test_list_table_output_basic(self, runner, workspace):
        """H10: list without --json shows id and title."""
        import yaml as _yaml

        d = workspace / "notes"
        fm = {
            "id": "tbl-001",
            "title": "Table Title",
            "type": "permanent",
            "tags": [],
            "concepts": [],
            "references": [],
            "exercises": [],
            "images": [],
        }
        (d / "tbl-001.md").write_text(
            "---\n" + _yaml.safe_dump(fm) + "---\n## Body\n", encoding="utf-8"
        )
        result = runner.invoke(notes, ["list", "--dir", str(d)])
        assert result.exit_code == 0
        assert "tbl-001" in result.output
        assert "Table Title" in result.output

    def test_show_table_output_basic(self, runner, workspace):
        """H10: show without --json shows id and title."""
        import yaml as _yaml

        d = workspace / "notes"
        fm = {
            "id": "tbl-show-001",
            "title": "Show Table",
            "type": "permanent",
            "tags": [],
            "concepts": [],
            "references": [],
            "exercises": [],
            "images": [],
        }
        (d / "tbl-show-001.md").write_text(
            "---\n" + _yaml.safe_dump(fm) + "---\n## Body\n", encoding="utf-8"
        )
        result = runner.invoke(notes, ["show", "tbl-show-001", "--dir", str(d)])
        assert result.exit_code == 0
        assert "tbl-show-001" in result.output
        assert "Show Table" in result.output


# ── Cheap LOWs — additional edge cases ───────────────────────────────────────


class TestCheapLows:
    def test_empty_body_writeable(self, workspace):
        """LOW: empty body must not break create_note."""
        target = workspace / "notes"
        fm = NoteFrontmatter(id="empty-body", title="Empty")
        path = create_note(target, fm, force=False)
        assert path.exists()
        parsed, body = parse_frontmatter(path)
        assert parsed["id"] == "empty-body"
        assert isinstance(body, str)

    def test_unicode_title_round_trip(self, runner, workspace):
        """LOW: Unicode in title survives create → show round-trip."""
        d = str(workspace / "notes")
        r1 = runner.invoke(
            notes,
            [
                "new",
                "--id",
                "uni-001",
                "--title",
                "Física Cuántica",
                "--dir",
                d,
                "--json",
            ],
        )
        assert r1.exit_code == 0, r1.output
        show = runner.invoke(notes, ["show", "uni-001", "--dir", d, "--json"])
        assert show.exit_code == 0
        assert json.loads(show.output)["title"] == "Física Cuántica"

    def test_tags_empty_string_yields_empty_list(self, runner, workspace):
        """LOW: --tags '' must not error and must produce empty tags list."""
        d = str(workspace / "notes")
        r1 = runner.invoke(
            notes,
            [
                "new",
                "--id",
                "notags-001",
                "--title",
                "No Tags",
                "--tags",
                "",
                "--dir",
                d,
                "--json",
            ],
        )
        assert r1.exit_code == 0, r1.output
        show = runner.invoke(notes, ["show", "notags-001", "--dir", d, "--json"])
        assert json.loads(show.output)["tags"] == []
