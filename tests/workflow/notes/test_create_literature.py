"""Tests for Wave D: `workflow notes create --type literature --bibkey`.

Covers:
- bibkey → file created at <vault>/notes/literature/<YYYYMMDD>-lit-<key>.md
- frontmatter: type=literature, prisma_review_record_id=null, prisma_keyword_id=null, origin=manual
- body: NO ## PRISMA rationale section; HAS ## Bib block
- --origin reading-list → frontmatter origin: reading-list
- idempotent re-run → created=false, file unchanged
- --dry-run → no file written, reports intended path
- --json → {"note_path","bibkey","created"}
- ambiguous bibkey (2 entries same key) → ClickException mentioning --bib-entry-id
- --bib-entry-id resolves ambiguous bibkey
- unsafe bibkey → ClickException, no file
- --type with non-literature value → Click usage error (exit 2)

CLI tests inject the in-memory engine via ``obj={"engine": global_engine}`` so the
command reuses the same DB the ``global_session`` fixture writes to (the live file DB
that ``get_engine_from_ctx`` would otherwise open is empty). This mirrors the Wave C2
``TestAcceptAllToNoteCLI`` pattern.
"""

from __future__ import annotations

import json

import yaml
from click.testing import CliRunner
from sqlalchemy.orm import Session

from workflow.db.models.bibliography import BibEntry
from workflow.notes.cli import notes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(session: Session, bibkey: str = "smith2020test") -> BibEntry:
    """Insert a minimal BibEntry and flush."""
    entry = BibEntry(
        bibkey=bibkey,
        entry_type="article",
        title="A Test Article About Science",
        year=2020,
        volume="1",
        journaltitle="Journal of Testing",
        doi="10.1234/test.2020",
    )
    session.add(entry)
    session.flush()
    return entry


def _extract_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from a markdown string."""
    lines = content.split("\n")
    assert lines[0] == "---", "Expected frontmatter opening ---"
    end = lines.index("---", 1)
    fm_text = "\n".join(lines[1:end])
    return yaml.safe_load(fm_text)


def _invoke(global_engine, args, *, catch_exceptions=False):
    """Run `notes <args>` reusing the in-memory engine from global_session."""
    runner = CliRunner()
    return runner.invoke(
        notes,
        args,
        obj={"engine": global_engine},
        catch_exceptions=catch_exceptions,
    )


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCreateLiteratureCLI:

    def test_creates_file_at_expected_path(self, global_session, global_engine, tmp_path):
        """bibkey → file created under notes/literature/ with correct name prefix."""
        entry = _make_entry(global_session)
        global_session.commit()

        result = _invoke(
            global_engine,
            ["create", "--bibkey", entry.bibkey, "--vault-root", str(tmp_path)],
        )

        assert result.exit_code == 0, result.output
        lit_dir = tmp_path / "notes" / "literature"
        files = list(lit_dir.glob(f"*-lit-{entry.bibkey}.md"))
        assert len(files) == 1, f"Expected 1 file, found: {files}"

    def test_frontmatter_defaults(self, global_session, global_engine, tmp_path):
        """Created note has type=literature, prisma ids=null, origin=manual."""
        entry = _make_entry(global_session)
        global_session.commit()

        _invoke(
            global_engine,
            ["create", "--bibkey", entry.bibkey, "--vault-root", str(tmp_path)],
        )

        lit_dir = tmp_path / "notes" / "literature"
        note_file = next(lit_dir.glob(f"*-lit-{entry.bibkey}.md"))
        content = note_file.read_text(encoding="utf-8")
        fm = _extract_frontmatter(content)

        assert fm["type"] == "literature"
        assert fm["prisma_review_record_id"] is None
        assert fm["prisma_keyword_id"] is None
        assert fm["origin"] == "manual"

    def test_body_no_prisma_rationale_has_bib_block(self, global_session, global_engine, tmp_path):
        """Body omits ## PRISMA rationale and includes ## Bib block."""
        entry = _make_entry(global_session)
        global_session.commit()

        _invoke(
            global_engine,
            ["create", "--bibkey", entry.bibkey, "--vault-root", str(tmp_path)],
        )

        lit_dir = tmp_path / "notes" / "literature"
        note_file = next(lit_dir.glob(f"*-lit-{entry.bibkey}.md"))
        content = note_file.read_text(encoding="utf-8")

        assert "## PRISMA rationale" not in content
        assert "## Bib block" in content

    def test_origin_override(self, global_session, global_engine, tmp_path):
        """--origin reading-list → frontmatter origin: reading-list."""
        entry = _make_entry(global_session)
        global_session.commit()

        _invoke(
            global_engine,
            ["create", "--bibkey", entry.bibkey, "--origin", "reading-list",
             "--vault-root", str(tmp_path)],
        )

        lit_dir = tmp_path / "notes" / "literature"
        note_file = next(lit_dir.glob(f"*-lit-{entry.bibkey}.md"))
        content = note_file.read_text(encoding="utf-8")
        fm = _extract_frontmatter(content)
        assert fm["origin"] == "reading-list"

    def test_idempotent_rerun(self, global_session, global_engine, tmp_path):
        """Second invocation returns exists: <path> and does not overwrite file."""
        entry = _make_entry(global_session)
        global_session.commit()

        args = ["create", "--bibkey", entry.bibkey, "--vault-root", str(tmp_path)]

        _invoke(global_engine, args)

        lit_dir = tmp_path / "notes" / "literature"
        note_file = next(lit_dir.glob(f"*-lit-{entry.bibkey}.md"))
        original_mtime = note_file.stat().st_mtime
        original_content = note_file.read_text(encoding="utf-8")

        result2 = _invoke(global_engine, args)

        assert result2.exit_code == 0, result2.output
        assert "exists:" in result2.output
        assert note_file.read_text(encoding="utf-8") == original_content
        assert note_file.stat().st_mtime == original_mtime

    def test_dry_run_no_file_written(self, global_session, global_engine, tmp_path):
        """--dry-run reports path but does not write the file."""
        entry = _make_entry(global_session)
        global_session.commit()

        result = _invoke(
            global_engine,
            ["create", "--bibkey", entry.bibkey, "--vault-root", str(tmp_path), "--dry-run"],
        )

        assert result.exit_code == 0, result.output
        lit_dir = tmp_path / "notes" / "literature"
        assert not lit_dir.exists() or not list(lit_dir.glob(f"*-lit-{entry.bibkey}.md"))

    def test_json_output_shape(self, global_session, global_engine, tmp_path):
        """--json produces {note_path, bibkey, created} object."""
        entry = _make_entry(global_session)
        global_session.commit()

        result = _invoke(
            global_engine,
            ["create", "--bibkey", entry.bibkey, "--vault-root", str(tmp_path), "--json"],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "note_path" in data
        assert data["bibkey"] == entry.bibkey
        assert data["created"] is True

    def test_ambiguous_bibkey_raises_click_exception(self, global_session, global_engine, tmp_path):
        """Two entries with same bibkey → ClickException mentioning --bib-entry-id."""
        bibkey = "dup2020test"
        entry1 = BibEntry(
            bibkey=bibkey, entry_type="article", title="First Dup", year=2020, volume="1",
        )
        entry2 = BibEntry(
            bibkey=bibkey, entry_type="article", title="Second Dup", year=2020, volume="2",
        )
        global_session.add_all([entry1, entry2])
        global_session.commit()

        result = _invoke(
            global_engine,
            ["create", "--bibkey", bibkey, "--vault-root", str(tmp_path)],
            catch_exceptions=True,
        )

        assert result.exit_code != 0
        assert "--bib-entry-id" in result.output

    def test_bib_entry_id_resolves_ambiguous(self, global_session, global_engine, tmp_path):
        """--bib-entry-id selects one entry when bibkey is ambiguous."""
        bibkey = "dup2020resolve"
        entry1 = BibEntry(
            bibkey=bibkey, entry_type="article", title="Resolve First", year=2020, volume="1",
        )
        entry2 = BibEntry(
            bibkey=bibkey, entry_type="article", title="Resolve Second", year=2020, volume="2",
        )
        global_session.add_all([entry1, entry2])
        global_session.commit()

        result = _invoke(
            global_engine,
            ["create", "--bibkey", bibkey, "--bib-entry-id", str(entry1.id),
             "--vault-root", str(tmp_path)],
        )

        assert result.exit_code == 0, result.output
        lit_dir = tmp_path / "notes" / "literature"
        files = list(lit_dir.glob(f"*-lit-{bibkey}.md"))
        assert len(files) == 1

    def test_unsafe_bibkey_raises_click_exception(self, global_session, global_engine, tmp_path):
        """A bibkey with path-traversal chars → ClickException, no file."""
        unsafe_key = "../evil"
        entry = BibEntry(
            bibkey=unsafe_key, entry_type="article", title="Evil", year=2020, volume="1",
        )
        global_session.add(entry)
        global_session.commit()

        result = _invoke(
            global_engine,
            ["create", "--bibkey", unsafe_key, "--vault-root", str(tmp_path)],
            catch_exceptions=True,
        )

        assert result.exit_code != 0
        lit_dir = tmp_path / "notes" / "literature"
        assert not lit_dir.exists() or not list(lit_dir.iterdir())

    def test_type_non_literature_rejected(self, global_engine, tmp_path):
        """--type with a value other than 'literature' → Click usage error exit 2."""
        result = _invoke(
            global_engine,
            ["create", "--bibkey", "any2020", "--type", "permanent",
             "--vault-root", str(tmp_path)],
            catch_exceptions=True,
        )
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Service regression tests (origin threading, added per Wave D spec)
# ---------------------------------------------------------------------------


class TestAcceptToNoteOriginRegression:
    """Regression suite confirming origin threading does not break Wave C behaviour."""

    def test_origin_override_wins_even_with_record(self, global_session, tmp_path):
        """accept_to_note(origin='manual') with a ReviewRecord → origin: manual in frontmatter."""
        from workflow.db.models.bibliography import BibKeyword, ReviewRecord
        from workflow.prisma.accept_to_note import accept_to_note

        entry = _make_entry(global_session, bibkey="override2020test")
        kw = BibKeyword(keyword_list="override kw")
        global_session.add(kw)
        global_session.flush()
        record = ReviewRecord(
            keyword_id=kw.id,
            bib_entry_id=entry.id,
            included=1,
        )
        global_session.add(record)
        global_session.commit()

        result = accept_to_note(
            global_session,
            bibkey=entry.bibkey,
            review_record_id=record.id,
            vault_root=tmp_path,
            origin="manual",
        )

        content = result.content
        fm = _extract_frontmatter(content)
        assert fm["origin"] == "manual", f"Expected 'manual', got {fm['origin']!r}"

    def test_origin_none_auto_derives_prisma_when_record_present(self, global_session, tmp_path):
        """accept_to_note(origin=None) with a ReviewRecord → origin: prisma (auto-derive)."""
        from workflow.db.models.bibliography import BibKeyword, ReviewRecord
        from workflow.prisma.accept_to_note import accept_to_note

        entry = _make_entry(global_session, bibkey="autoderived2020test")
        kw = BibKeyword(keyword_list="autoderive kw")
        global_session.add(kw)
        global_session.flush()
        record = ReviewRecord(
            keyword_id=kw.id,
            bib_entry_id=entry.id,
            included=1,
        )
        global_session.add(record)
        global_session.commit()

        result = accept_to_note(
            global_session,
            bibkey=entry.bibkey,
            review_record_id=record.id,
            vault_root=tmp_path,
            origin=None,
        )

        content = result.content
        fm = _extract_frontmatter(content)
        assert fm["origin"] == "prisma", f"Expected 'prisma', got {fm['origin']!r}"
