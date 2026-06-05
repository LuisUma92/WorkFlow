"""Tests for Wave C1: accept_to_note service + CLI.

Covers:
- bibkey → file created at expected path with correct frontmatter keys
- origin=prisma when keyword/record given; origin=manual when not
- ## PRISMA rationale section: include_rationale + RationaleOption labels
- ## PRISMA rationale absent when no record
- bib block round-trips through import_bib_text without error
- idempotent: second call returns created=False, file unchanged
- dry_run: returns content, writes nothing
- ambiguous bibkey (two BibEntry rows same bibkey) → BibKeyAmbiguous raised; CLI non-zero
- --json shape via CliRunner
"""

from __future__ import annotations

import pytest
import yaml
from click.testing import CliRunner
from sqlalchemy.orm import Session

from workflow.db.models.bibliography import (
    BibEntry,
    BibKeyword,
    RationaleOption,
    ReviewRationale,
    ReviewRecord,
)
from workflow.bibliography.service import BibKeyAmbiguous
from workflow.prisma.accept_to_note import accept_to_note
from workflow.prisma.cli import prisma
from workflow.prisma.importer import import_bib_text


# ---------------------------------------------------------------------------
# Fixtures / helpers
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


def _make_keyword(session: Session, text: str = "machine learning") -> BibKeyword:
    kw = BibKeyword(keyword_list=text)
    session.add(kw)
    session.flush()
    return kw


def _make_rationale_option(session: Session, label: str) -> RationaleOption:
    opt = RationaleOption(rationale_argument=label)
    session.add(opt)
    session.flush()
    return opt


def _make_review_record(
    session: Session,
    keyword: BibKeyword,
    entry: BibEntry,
    rationale_text: str | None = None,
    rationale_options: list[RationaleOption] | None = None,
) -> ReviewRecord:
    record = ReviewRecord(
        keyword_id=keyword.id,
        bib_entry_id=entry.id,
        included=1,
        include_rationale=rationale_text,
    )
    session.add(record)
    session.flush()
    for opt in (rationale_options or []):
        link = ReviewRationale(
            review_record_id=record.id,
            rationale_option_id=opt.id,
        )
        session.add(link)
    session.flush()
    return record


def _extract_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from a markdown string."""
    lines = content.split("\n")
    assert lines[0] == "---", "Expected frontmatter opening ---"
    end = lines.index("---", 1)
    fm_text = "\n".join(lines[1:end])
    return yaml.safe_load(fm_text)


def _extract_bib_block(content: str) -> str:
    """Extract content between ```bib and ``` fences."""
    in_block = False
    bib_lines: list[str] = []
    for line in content.split("\n"):
        if line.strip() == "```bib":
            in_block = True
            continue
        if in_block and line.strip() == "```":
            break
        if in_block:
            bib_lines.append(line)
    return "\n".join(bib_lines)


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestAcceptToNoteService:

    def test_creates_file_at_expected_path(self, global_session, tmp_path):
        """bibkey resolves → file created under notes/literature/."""
        entry = _make_entry(global_session)
        global_session.commit()

        result = accept_to_note(
            global_session,
            bibkey=entry.bibkey,
            vault_root=tmp_path,
        )

        assert result.created is True
        assert result.bibkey == entry.bibkey
        assert result.note_path.exists()
        assert result.note_path.parent == tmp_path / "notes" / "literature"
        assert f"-lit-{entry.bibkey}.md" in result.note_path.name

    def test_frontmatter_keys_present(self, global_session, tmp_path):
        """All required frontmatter keys must be present in the generated note."""
        entry = _make_entry(global_session)
        global_session.commit()

        result = accept_to_note(
            global_session,
            bibkey=entry.bibkey,
            vault_root=tmp_path,
        )

        fm = _extract_frontmatter(result.content)
        required_keys = {
            "id", "title", "type", "bibkey",
            "prisma_review_record_id", "prisma_keyword_id",
            "main_topic_id", "concepts", "tags", "created", "origin",
        }
        assert required_keys.issubset(set(fm.keys()))
        assert fm["type"] == "literature"
        assert fm["main_topic_id"] is None
        assert fm["concepts"] == []
        assert fm["tags"] == []

    def test_unsafe_bibkey_rejected(self, global_session, tmp_path):
        """A bibkey with path separators/traversal must raise, not write."""
        entry = _make_entry(global_session, bibkey="../../etc/passwd")
        global_session.commit()

        with pytest.raises(ValueError, match="unsafe"):
            accept_to_note(
                global_session,
                bibkey=entry.bibkey,
                vault_root=tmp_path,
            )
        assert not (tmp_path / "notes").exists()

    def test_origin_manual_without_keyword(self, global_session, tmp_path):
        """No keyword → origin: manual in frontmatter."""
        entry = _make_entry(global_session)
        global_session.commit()

        result = accept_to_note(
            global_session,
            bibkey=entry.bibkey,
            vault_root=tmp_path,
        )

        fm = _extract_frontmatter(result.content)
        assert fm["origin"] == "manual"
        assert fm["prisma_review_record_id"] is None
        assert fm["prisma_keyword_id"] is None

    def test_origin_prisma_with_keyword(self, global_session, tmp_path):
        """With keyword_id → origin: prisma; prisma_keyword_id populated."""
        entry = _make_entry(global_session)
        kw = _make_keyword(global_session)
        record = _make_review_record(global_session, kw, entry)
        global_session.commit()

        result = accept_to_note(
            global_session,
            bibkey=entry.bibkey,
            keyword_id=kw.id,
            vault_root=tmp_path,
        )

        fm = _extract_frontmatter(result.content)
        assert fm["origin"] == "prisma"
        assert fm["prisma_keyword_id"] == kw.id
        assert fm["prisma_review_record_id"] == record.id

    def test_rationale_section_present_with_keyword(self, global_session, tmp_path):
        """keyword_id → ## PRISMA rationale section with free text + option labels."""
        entry = _make_entry(global_session)
        kw = _make_keyword(global_session, "deep learning")
        opt1 = _make_rationale_option(global_session, "Addresses research question")
        opt2 = _make_rationale_option(global_session, "High quality study")
        record = _make_review_record(
            global_session, kw, entry,
            rationale_text="Strong empirical evidence.",
            rationale_options=[opt1, opt2],
        )
        global_session.commit()

        result = accept_to_note(
            global_session,
            bibkey=entry.bibkey,
            keyword_id=kw.id,
            vault_root=tmp_path,
        )

        assert "## PRISMA rationale" in result.content
        assert "Strong empirical evidence." in result.content
        assert "Addresses research question" in result.content
        assert "High quality study" in result.content
        assert f"review record {record.id}" in result.content
        assert "deep learning" in result.content

    def test_rationale_section_absent_without_keyword(self, global_session, tmp_path):
        """No keyword → ## PRISMA rationale section must not appear."""
        entry = _make_entry(global_session)
        global_session.commit()

        result = accept_to_note(
            global_session,
            bibkey=entry.bibkey,
            vault_root=tmp_path,
        )

        assert "## PRISMA rationale" not in result.content

    def test_bib_block_round_trips(self, global_session, tmp_path):
        """The ```bib block re-imports via import_bib_text without error."""
        entry = _make_entry(global_session, bibkey="roundtrip2021")
        global_session.commit()

        result = accept_to_note(
            global_session,
            bibkey=entry.bibkey,
            vault_root=tmp_path,
        )

        bib_text = _extract_bib_block(result.content)
        assert bib_text.strip(), "bib block should not be empty"

        # Round-trip in a fresh session context (reuses the same global engine)
        import_bib_text(global_session, bib_text)
        # If import_bib_text doesn't raise, the round-trip is confirmed.

    def test_idempotent_second_call(self, global_session, tmp_path):
        """Second call returns created=False and does not overwrite the file."""
        entry = _make_entry(global_session)
        global_session.commit()

        result1 = accept_to_note(
            global_session,
            bibkey=entry.bibkey,
            vault_root=tmp_path,
        )
        assert result1.created is True

        # Overwrite with sentinel to detect if file is touched
        result1.note_path.write_text("SENTINEL", encoding="utf-8")

        result2 = accept_to_note(
            global_session,
            bibkey=entry.bibkey,
            vault_root=tmp_path,
        )
        assert result2.created is False
        assert result2.note_path.read_text(encoding="utf-8") == "SENTINEL"

    def test_dry_run_writes_nothing(self, global_session, tmp_path):
        """dry_run=True returns content but does not write the file."""
        entry = _make_entry(global_session)
        global_session.commit()

        result = accept_to_note(
            global_session,
            bibkey=entry.bibkey,
            vault_root=tmp_path,
            dry_run=True,
        )

        assert result.content, "content should not be empty"
        assert not result.note_path.exists(), "file must NOT be written in dry_run mode"
        assert result.created is False

    def test_ambiguous_bibkey_raises(self, global_session, tmp_path):
        """Two BibEntry rows with the same bibkey → BibKeyAmbiguous raised."""
        # Insert two distinct entries sharing the same bibkey
        e1 = BibEntry(bibkey="dup2022", entry_type="article", title="Dup Title One",
                      year=2022, volume="1")
        e2 = BibEntry(bibkey="dup2022", entry_type="article", title="Dup Title Two",
                      year=2022, volume="2")
        global_session.add_all([e1, e2])
        global_session.commit()

        with pytest.raises(BibKeyAmbiguous):
            accept_to_note(global_session, bibkey="dup2022", vault_root=tmp_path)

    def test_bib_entry_id_disambiguates(self, global_session, tmp_path):
        """--bib-entry-id bypasses ambiguous-bibkey lookup."""
        e1 = BibEntry(bibkey="dup2023", entry_type="article", title="Disamb One",
                      year=2023, volume="1")
        e2 = BibEntry(bibkey="dup2023", entry_type="article", title="Disamb Two",
                      year=2023, volume="2")
        global_session.add_all([e1, e2])
        global_session.commit()

        # Direct id lookup never goes through bibkey → no exception
        result = accept_to_note(
            global_session,
            bib_entry_id=e1.id,
            vault_root=tmp_path,
        )
        assert result.created is True
        assert "dup2023" in result.note_path.name

    def test_missing_entry_raises_value_error(self, global_session, tmp_path):
        """Non-existent bibkey raises ValueError."""
        with pytest.raises(ValueError, match="No BibEntry found"):
            accept_to_note(
                global_session,
                bibkey="nonexistent9999",
                vault_root=tmp_path,
            )


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestAcceptToNoteCLI:

    def _make_engine(self, global_engine):
        return global_engine

    def test_cli_creates_file(self, global_session, global_engine, tmp_path):
        """CLI happy path creates file and prints path."""
        entry = _make_entry(global_session)
        global_session.commit()

        runner = CliRunner()
        result = runner.invoke(
            prisma,
            ["bib", "accept-to-note", entry.bibkey, "--vault-root", str(tmp_path)],
            obj={"engine": global_engine},
        )

        assert result.exit_code == 0, result.output
        assert "Created:" in result.output
        note_path = tmp_path / "notes" / "literature"
        assert any(note_path.iterdir())

    def test_cli_idempotent_exit_nonzero(self, global_session, global_engine, tmp_path):
        """Second invocation → exit code 1, skipped message on stderr."""
        entry = _make_entry(global_session, bibkey="cli_idem2020")
        global_session.commit()

        runner = CliRunner()
        runner.invoke(
            prisma,
            ["bib", "accept-to-note", entry.bibkey, "--vault-root", str(tmp_path)],
            obj={"engine": global_engine},
        )
        result2 = runner.invoke(
            prisma,
            ["bib", "accept-to-note", entry.bibkey, "--vault-root", str(tmp_path)],
            obj={"engine": global_engine},
        )
        assert result2.exit_code != 0

    def test_cli_dry_run_no_file(self, global_session, global_engine, tmp_path):
        """--dry-run prints content and writes no file."""
        entry = _make_entry(global_session, bibkey="cli_dry2020")
        global_session.commit()

        runner = CliRunner()
        result = runner.invoke(
            prisma,
            ["bib", "accept-to-note", entry.bibkey, "--vault-root", str(tmp_path), "--dry-run"],
            obj={"engine": global_engine},
        )

        assert result.exit_code == 0, result.output
        assert "---" in result.output  # frontmatter fences
        lit_dir = tmp_path / "notes" / "literature"
        assert not lit_dir.exists() or not any(lit_dir.iterdir())

    def test_cli_json_shape(self, global_session, global_engine, tmp_path):
        """--json emits {note_path, bibkey, created}."""
        import json as _json

        entry = _make_entry(global_session, bibkey="cli_json2020")
        global_session.commit()

        runner = CliRunner()
        result = runner.invoke(
            prisma,
            ["bib", "accept-to-note", entry.bibkey, "--vault-root", str(tmp_path), "--json"],
            obj={"engine": global_engine},
        )

        assert result.exit_code == 0, result.output
        data = _json.loads(result.output)
        assert set(data.keys()) == {"note_path", "bibkey", "created"}
        assert data["bibkey"] == entry.bibkey
        assert data["created"] is True

    def test_cli_ambiguous_bibkey_error(self, global_session, global_engine, tmp_path):
        """Ambiguous bibkey yields non-zero exit and names the conflicting ids."""
        e1 = BibEntry(bibkey="cli_dup2022", entry_type="article",
                      title="CLI Dup One", year=2022, volume="1")
        e2 = BibEntry(bibkey="cli_dup2022", entry_type="article",
                      title="CLI Dup Two", year=2022, volume="2")
        global_session.add_all([e1, e2])
        global_session.commit()

        runner = CliRunner()
        result = runner.invoke(
            prisma,
            ["bib", "accept-to-note", "cli_dup2022", "--vault-root", str(tmp_path)],
            obj={"engine": global_engine},
        )

        assert result.exit_code != 0
        assert "cli_dup2022" in result.output
        # Both ids should appear in the error
        assert str(e1.id) in result.output
        assert str(e2.id) in result.output

    def test_cli_no_bibkey_or_id_error(self, global_engine, tmp_path):
        """Neither BIBKEY nor --bib-entry-id → non-zero with helpful message."""
        runner = CliRunner()
        result = runner.invoke(
            prisma,
            ["bib", "accept-to-note", "--vault-root", str(tmp_path)],
            obj={"engine": global_engine},
        )
        assert result.exit_code != 0
        assert "bib-entry-id" in result.output.lower() or "bibkey" in result.output.lower()

    def test_cli_review_record_id_option(self, global_session, global_engine, tmp_path):
        """--review-record-id resolves ReviewRecord and emits PRISMA section."""
        entry = _make_entry(global_session, bibkey="cli_rr2021")
        kw = _make_keyword(global_session, "neural networks")
        record = _make_review_record(
            global_session, kw, entry,
            rationale_text="Directly relevant.",
        )
        global_session.commit()

        runner = CliRunner()
        result = runner.invoke(
            prisma,
            [
                "bib", "accept-to-note", entry.bibkey,
                "--review-record-id", str(record.id),
                "--vault-root", str(tmp_path),
            ],
            obj={"engine": global_engine},
        )

        assert result.exit_code == 0, result.output
        note_files = list((tmp_path / "notes" / "literature").iterdir())
        assert len(note_files) == 1
        content = note_files[0].read_text(encoding="utf-8")
        assert "## PRISMA rationale" in content
        assert "Directly relevant." in content


# ---------------------------------------------------------------------------
# Integration: frontmatter validates (requires parallel validator change)
# ---------------------------------------------------------------------------


class TestFrontmatterIntegration:

    def test_frontmatter_passes_validator(self, global_session, tmp_path):
        """Generated frontmatter dict passes validate_note_frontmatter with zero errors."""
        from workflow.validation.schemas import validate_note_frontmatter

        entry = _make_entry(global_session, bibkey="val_test2020")
        global_session.commit()

        result = accept_to_note(
            global_session,
            bibkey=entry.bibkey,
            vault_root=tmp_path,
        )

        fm = _extract_frontmatter(result.content)
        _model, errors = validate_note_frontmatter(fm)
        assert errors == [], f"Validation errors: {errors}"
