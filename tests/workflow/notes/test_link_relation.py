"""Tests for `workflow notes link --relation --target` (Wave 3 D2, amended F3+F4).

Frontmatter schema is 9 FLAT keys (Obsidian Properties compatible) — see
``workflow.db.models.notes.FRONTMATTER_RELATION_KEYS``. A relation write
appends the target zettel_id to the flat key's list; removing the last id
of a relation type deletes the key from the file entirely.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from workflow.notes.cli import notes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_note(path: Path, zettel_id: str = "noteAAAAAAAA") -> Path:
    content = (
        f"---\n"
        f"id: {zettel_id}\n"
        f"title: Test Note\n"
        f"type: permanent\n"
        f"---\nBody text.\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def _read_fm(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    return yaml.safe_load(text[3:end]) or {}


# ---------------------------------------------------------------------------
# Tests: --relation appends to the flat frontmatter key
# ---------------------------------------------------------------------------


def test_link_relation_structural_appends(tmp_path):
    """--relation continuation creates a derived_from_continuation flat key."""
    note_path = _write_note(tmp_path / "noteAAAAAAAA.md")

    result = CliRunner().invoke(
        notes,
        [
            "link", "noteAAAAAAAA",
            "--relation", "continuation",
            "--target", "noteBBBBBBBB",
            "--dir", str(tmp_path),
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    fm = _read_fm(note_path)
    assert fm.get("derived_from_continuation") == ["noteBBBBBBBB"]
    assert "relations" not in fm


def test_link_relation_associative_appends(tmp_path):
    """--relation supports creates a links_supports flat key."""
    note_path = _write_note(tmp_path / "noteAAAAAAAA.md")

    CliRunner().invoke(
        notes,
        [
            "link", "noteAAAAAAAA",
            "--relation", "supports",
            "--target", "noteCCCCCCCC",
            "--dir", str(tmp_path),
        ],
        catch_exceptions=False,
    )

    fm = _read_fm(note_path)
    assert fm.get("links_supports") == ["noteCCCCCCCC"]
    assert "relations" not in fm


def test_link_relation_unknown_type_exits_2(tmp_path):
    """Unknown relation type produces a UsageError (exit code 2)."""
    _write_note(tmp_path / "noteAAAAAAAA.md")

    result = CliRunner().invoke(
        notes,
        [
            "link", "noteAAAAAAAA",
            "--relation", "INVALID_TYPE",
            "--target", "noteBBBBBBBB",
            "--dir", str(tmp_path),
        ],
    )
    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}: {result.output}"
    assert "INVALID_TYPE" in result.output or "valid" in result.output.lower()


def test_link_relation_bad_target_id_error(tmp_path):
    """Target zettel_id that doesn't match NanoID format produces an error."""
    _write_note(tmp_path / "noteAAAAAAAA.md")

    result = CliRunner().invoke(
        notes,
        [
            "link", "noteAAAAAAAA",
            "--relation", "continuation",
            "--target", "bad id!",  # invalid: spaces/special chars
            "--dir", str(tmp_path),
        ],
    )
    assert result.exit_code != 0, "Bad target id should fail"


def test_link_relation_duplicate_is_noop(tmp_path):
    """Linking the same (type, target) twice does not create a duplicate entry."""
    note_path = _write_note(tmp_path / "noteAAAAAAAA.md")

    runner = CliRunner()
    for _ in range(2):
        runner.invoke(
            notes,
            [
                "link", "noteAAAAAAAA",
                "--relation", "refines",
                "--target", "noteDDDDDDDD",
                "--dir", str(tmp_path),
            ],
            catch_exceptions=False,
        )

    fm = _read_fm(note_path)
    derived = fm.get("derived_from_refines", [])
    matching = [i for i in derived if i == "noteDDDDDDDD"]
    assert len(matching) == 1, f"Expected exactly 1 entry, got: {matching}"


def test_link_relation_remove_deletes_entry(tmp_path):
    """--remove deletes an existing relation entry; last id removed drops the key."""
    note_path = _write_note(tmp_path / "noteAAAAAAAA.md")
    runner = CliRunner()

    # Add first
    runner.invoke(
        notes,
        [
            "link", "noteAAAAAAAA",
            "--relation", "branches",
            "--target", "noteEEEEEEEE",
            "--dir", str(tmp_path),
        ],
        catch_exceptions=False,
    )

    fm_before = _read_fm(note_path)
    assert "noteEEEEEEEE" in fm_before.get("derived_from_branches", [])

    # Remove
    result = runner.invoke(
        notes,
        [
            "link", "noteAAAAAAAA",
            "--relation", "branches",
            "--target", "noteEEEEEEEE",
            "--remove",
            "--dir", str(tmp_path),
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    fm_after = _read_fm(note_path)
    assert "derived_from_branches" not in fm_after, (
        f"Key should be deleted entirely once its last id is removed, got: {fm_after}"
    )
    # And it must not survive as an empty list either — checked via raw text.
    assert "derived_from_branches" not in note_path.read_text(encoding="utf-8")


def test_link_relation_requires_target(tmp_path):
    """--relation without --target produces a UsageError."""
    _write_note(tmp_path / "noteAAAAAAAA.md")

    result = CliRunner().invoke(
        notes,
        [
            "link", "noteAAAAAAAA",
            "--relation", "continuation",
            "--dir", str(tmp_path),
        ],
    )
    assert result.exit_code != 0


def test_link_relation_short_target_id_error(tmp_path):
    """Target zettel_id shorter than 8 chars should fail (NanoID min length)."""
    _write_note(tmp_path / "noteAAAAAAAA.md")

    result = CliRunner().invoke(
        notes,
        [
            "link", "noteAAAAAAAA",
            "--relation", "continuation",
            "--target", "abc",  # too short
            "--dir", str(tmp_path),
        ],
    )
    assert result.exit_code != 0
