"""Tests for `workflow notes link --relation --target` (Wave 3 D2)."""
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
# Tests: --relation appends to frontmatter
# ---------------------------------------------------------------------------


def test_link_relation_structural_appends(tmp_path):
    """--relation continuation creates a derived_from entry in the relations block."""
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
    relations = fm.get("relations", {})
    derived = relations.get("derived_from", [])
    assert any(
        e.get("id") == "noteBBBBBBBB" and e.get("type") == "continuation"
        for e in derived
    ), f"Expected continuation edge in derived_from, got: {derived}"


def test_link_relation_associative_appends(tmp_path):
    """--relation supports creates a links entry in the relations block."""
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
    relations = fm.get("relations", {})
    links = relations.get("links", [])
    assert any(
        e.get("id") == "noteCCCCCCCC" and e.get("type") == "supports"
        for e in links
    ), f"Expected supports edge in links, got: {links}"


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
    derived = fm.get("relations", {}).get("derived_from", [])
    matching = [e for e in derived if e.get("id") == "noteDDDDDDDD" and e.get("type") == "refines"]
    assert len(matching) == 1, f"Expected exactly 1 entry, got: {matching}"


def test_link_relation_remove_deletes_entry(tmp_path):
    """--remove deletes an existing relation entry."""
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
    assert any(
        e.get("id") == "noteEEEEEEEE"
        for e in fm_before.get("relations", {}).get("derived_from", [])
    )

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
    remaining = fm_after.get("relations", {}).get("derived_from", [])
    assert not any(e.get("id") == "noteEEEEEEEE" for e in remaining), \
        f"Entry should have been removed, got: {remaining}"


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
