"""Tests for ADR ITEP-0009 Phase A: discipline taxonomy registry."""

from __future__ import annotations

import json

from click.testing import CliRunner

from workflow.db import taxonomy
from workflow.db.cli import db


def test_registry_has_ten_disciplines():
    assert sorted(taxonomy.DISCIPLINES.keys()) == list(range(10))


def test_registry_keys_have_human_names():
    for dd, name in taxonomy.DISCIPLINES.items():
        assert isinstance(name, str)
        assert name.strip() == name
        assert name


def test_hobby_threshold():
    assert taxonomy.is_hobby(3) is False
    assert taxonomy.is_hobby(4) is True
    assert taxonomy.is_hobby(9) is True


def test_discover_disciplines_matches_bundled_csvs():
    entries = taxonomy.discover_disciplines()
    assert len(entries) == 10
    by_dd = {e.dd: e for e in entries}
    assert by_dd[0].name == "Física"
    assert by_dd[0].csv_path is not None
    assert by_dd[0].csv_path.name == "00-PhysicsCodes.csv"
    assert by_dd[0].hobby is False
    assert by_dd[4].hobby is True


def test_discover_disciplines_handles_missing_dir(tmp_path):
    entries = taxonomy.discover_disciplines(tmp_path)
    assert len(entries) == 10
    assert all(e.csv_path is None for e in entries)


def test_discover_disciplines_partial_dir(tmp_path):
    (tmp_path / "00-PhysicsCodes.csv").write_text(
        "Rama,código,Dewey\n", encoding="utf-8"
    )
    (tmp_path / "03-TeachingCodes.csv").write_text(
        "Rama,código,Dewey\n", encoding="utf-8"
    )
    entries = {e.dd: e for e in taxonomy.discover_disciplines(tmp_path)}
    assert entries[0].csv_path is not None
    assert entries[1].csv_path is None
    assert entries[3].csv_path is not None


def test_cli_disciplines_list_table():
    runner = CliRunner()
    result = runner.invoke(db, ["disciplines", "list"])
    assert result.exit_code == 0, result.output
    assert "00" in result.output
    assert "Física" in result.output
    assert "09" in result.output


def test_cli_disciplines_list_json():
    runner = CliRunner()
    result = runner.invoke(db, ["disciplines", "list", "--json"])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)
    assert len(parsed) == 10
    first = parsed[0]
    assert set(first.keys()) == {"dd", "code_prefix", "name", "csv", "hobby"}
    assert first["dd"] == 0
    assert first["code_prefix"] == "00"
    assert first["hobby"] is False
    # DD>=4 are hobby
    assert next(e for e in parsed if e["dd"] == 4)["hobby"] is True


def test_cli_disciplines_list_data_dir_override(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        db,
        ["disciplines", "list", "--json", "--data-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert all(e["csv"] is None for e in parsed)


def test_cli_taxonomy_list_alias_still_works():
    """Deprecated `db taxonomy list` forwards to `disciplines list`."""
    runner = CliRunner()
    result = runner.invoke(db, ["taxonomy", "list", "--json"])
    assert result.exit_code == 0, result.output
    assert "[deprecated]" in result.output
    json_start = result.output.index("\n[\n") + 1
    parsed = json.loads(result.output[json_start:])
    assert isinstance(parsed, list) and len(parsed) == 10
