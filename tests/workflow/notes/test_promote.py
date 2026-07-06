"""Tests for `workflow notes promote REF` (Wave 1 Phase 1).

LOCKED contract (2026-07-05 user gate, ★d — amends ITEP-0011):
- FLIP-ONLY: sets note_type in DB AND updates frontmatter `type:` in the .md
  (file-as-truth — both must change, FILE FIRST then sync). NEVER moves or
  renames the file (flat-layout: type is metadata, directories not semantic).
- Allowed: fleeting→permanent AND literature→permanent.
- anything→same-type = error; permanent→anything = error (no demote).
- Re-promote of an already-permanent note → explicit ClickException exit 1.
- --json → exactly {"reference", "from", "to", "note_path"}.
- REF resolved the same way `notes show` does (frontmatter id lookup).
"""

from __future__ import annotations

import json

import yaml
from click.testing import CliRunner
from sqlalchemy import select

from workflow.db.models.notes import Note
from workflow.notes.cli import notes
from workflow.notes.sync import sync_note_files


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoke(global_engine, vault, args, *, catch_exceptions=False):
    runner = CliRunner()
    return runner.invoke(
        notes,
        args,
        obj={"engine": global_engine},
        env={"WORKFLOW_VAULT_ROOT": str(vault)},
        catch_exceptions=catch_exceptions,
    )


def _seed_note(
    vault, session, *, zid, note_type, extra_fm: str = "", body: str = "Body.\n"
):
    """Write a note file flat in the vault and register it in the DB."""
    path = vault / f"{zid}-seed.md"
    fm = f"id: {zid}\ntitle: Seed {zid}\ntype: {note_type}\n{extra_fm}".rstrip()
    path.write_text(f"---\n{fm}\n---\n{body}", encoding="utf-8")
    sync_note_files([path], session)
    session.commit()
    return path


def _read_fm(path):
    text = path.read_text(encoding="utf-8")
    end = text.index("\n---", 3)
    return yaml.safe_load(text[4:end])


def _db_type(session, zid):
    note = session.scalars(select(Note).where(Note.zettel_id == zid)).first()
    assert note is not None
    session.refresh(note)
    return note.note_type


# ---------------------------------------------------------------------------
# Allowed transitions
# ---------------------------------------------------------------------------


class TestPromoteAllowed:
    def test_literature_to_permanent_flips_file_and_db(
        self, global_engine, global_session, tmp_path
    ):
        vault = tmp_path / "vault"
        vault.mkdir()
        path = _seed_note(
            vault, global_session, zid="litnote12345", note_type="literature"
        )

        result = _invoke(global_engine, vault, ["promote", "litnote12345"])
        assert result.exit_code == 0, result.output

        assert _read_fm(path)["type"] == "permanent"
        assert _db_type(global_session, "litnote12345") == "permanent"

    def test_fleeting_to_permanent_allowed(
        self, global_engine, global_session, tmp_path
    ):
        vault = tmp_path / "vault"
        vault.mkdir()
        path = _seed_note(
            vault, global_session, zid="fleetnote123", note_type="fleeting"
        )

        result = _invoke(global_engine, vault, ["promote", "fleetnote123"])
        assert result.exit_code == 0, result.output
        assert _read_fm(path)["type"] == "permanent"
        assert _db_type(global_session, "fleetnote123") == "permanent"

    def test_file_never_moved_or_renamed(
        self, global_engine, global_session, tmp_path
    ):
        vault = tmp_path / "vault"
        vault.mkdir()
        path = _seed_note(
            vault, global_session, zid="staysput1234", note_type="literature"
        )

        result = _invoke(global_engine, vault, ["promote", "staysput1234"])
        assert result.exit_code == 0, result.output
        assert path.exists(), "promote must NEVER move/rename the file"
        assert list(vault.rglob("*.md")) == [path]

    def test_body_and_extra_frontmatter_preserved(
        self, global_engine, global_session, tmp_path
    ):
        """Flip must not drop bibkey/origin or alter the body (raw round-trip)."""
        vault = tmp_path / "vault"
        vault.mkdir()
        path = _seed_note(
            vault, global_session, zid="preserve1234", note_type="literature",
            extra_fm="bibkey: smith2020\norigin: manual",
            body="Reading notes here.\n",
        )

        result = _invoke(global_engine, vault, ["promote", "preserve1234"])
        assert result.exit_code == 0, result.output

        fm = _read_fm(path)
        assert fm["type"] == "permanent"
        assert fm["bibkey"] == "smith2020"
        assert fm["origin"] == "manual"
        assert "Reading notes here." in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Forbidden transitions
# ---------------------------------------------------------------------------


class TestPromoteForbidden:
    def test_already_permanent_is_explicit_error(
        self, global_engine, global_session, tmp_path
    ):
        vault = tmp_path / "vault"
        vault.mkdir()
        path = _seed_note(
            vault, global_session, zid="alreadyperm1", note_type="permanent"
        )
        before = path.read_text(encoding="utf-8")

        result = _invoke(global_engine, vault, ["promote", "alreadyperm1"])
        assert result.exit_code == 1
        assert "permanent" in (result.stderr + result.output).lower()
        assert path.read_text(encoding="utf-8") == before
        assert _db_type(global_session, "alreadyperm1") == "permanent"

    def test_repromote_after_promote_errors(
        self, global_engine, global_session, tmp_path
    ):
        vault = tmp_path / "vault"
        vault.mkdir()
        _seed_note(
            vault, global_session, zid="twicepromote", note_type="literature"
        )

        first = _invoke(global_engine, vault, ["promote", "twicepromote"])
        assert first.exit_code == 0, first.output
        second = _invoke(global_engine, vault, ["promote", "twicepromote"])
        assert second.exit_code == 1

    def test_missing_note_errors(self, global_engine, global_session, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _invoke(global_engine, vault, ["promote", "nosuchnote12"])
        assert result.exit_code == 1

    def test_invalid_reference_characters_rejected(
        self, global_engine, global_session, tmp_path
    ):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _invoke(global_engine, vault, ["promote", "../evil"])
        assert result.exit_code == 2

    def test_hand_edited_unrecognized_type_rejected(
        self, global_engine, global_session, tmp_path
    ):
        """A note whose on-disk `type:` is neither promotable nor permanent
        (e.g. hand-edited `type: reference`) must be an explicit error, not a
        silent promote — covers promote.py:89-93.

        Note.note_type has a DB CHECK constraint restricted to
        permanent|literature|fleeting, so the DB row is seeded with a valid
        type first and the file is hand-edited afterwards (bypassing sync) —
        promote_note resolves the note via the file (file-as-truth), not the
        DB row, so this reproduces a genuinely unrecognized on-disk type.
        """
        vault = tmp_path / "vault"
        vault.mkdir()
        path = _seed_note(
            vault, global_session, zid="weirdtype123", note_type="fleeting"
        )
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "type: fleeting", "type: reference"
            ),
            encoding="utf-8",
        )
        before = path.read_text(encoding="utf-8")

        result = _invoke(global_engine, vault, ["promote", "weirdtype123"])
        assert result.exit_code == 1
        assert "reference" in (result.stderr + result.output).lower()
        assert path.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# JSON contract
# ---------------------------------------------------------------------------


class TestPromoteJson:
    def test_json_exact_key_set(self, global_engine, global_session, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        path = _seed_note(
            vault, global_session, zid="jsonpromote1", note_type="literature"
        )

        result = _invoke(
            global_engine, vault, ["promote", "jsonpromote1", "--json"]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert set(data.keys()) == {"reference", "from", "to", "note_path"}
        assert data["reference"] == "jsonpromote1"
        assert data["from"] == "literature"
        assert data["to"] == "permanent"
        assert data["note_path"] == str(path)


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------


class TestPromoteService:
    def test_promote_result_is_frozen(self, global_session, tmp_path):
        import dataclasses

        from workflow.notes.promote import PromoteResult, promote_note

        vault = tmp_path / "vault"
        vault.mkdir()
        _seed_note(
            vault, global_session, zid="svcpromote12", note_type="fleeting"
        )

        result = promote_note(
            global_session, "svcpromote12", vault_root=vault,
        )
        assert isinstance(result, PromoteResult)
        assert result.from_type == "fleeting"
        assert result.to_type == "permanent"
        try:
            result.to_type = "x"
        except dataclasses.FrozenInstanceError:
            pass
        else:
            raise AssertionError("PromoteResult must be frozen")

    def test_same_type_raises_promote_error(self, global_session, tmp_path):
        import pytest

        from workflow.notes.promote import PromoteError, promote_note

        vault = tmp_path / "vault"
        vault.mkdir()
        _seed_note(
            vault, global_session, zid="svcperm12345", note_type="permanent"
        )
        with pytest.raises(PromoteError):
            promote_note(global_session, "svcperm12345", vault_root=vault)
