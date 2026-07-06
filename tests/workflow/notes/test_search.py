"""Tests for workflow.notes.search — FTS5 vault search (ADR-0021, Wave 1 F2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db import migrations
from workflow.db.base import GlobalBase
from workflow.notes.cli import notes
from workflow.notes.search import SearchQueryError, search_notes
from workflow.notes.sync import rebuild_fts_index, sync_vault


def _enable_fk(dbapi_conn, _record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def migrated_engine():
    """In-memory GlobalBase engine with all migrations applied (incl. 0017)."""
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk)
    GlobalBase.metadata.create_all(engine)
    migrations.upgrade(engine, "global")
    return engine


@pytest.fixture
def migrated_session(migrated_engine):
    with Session(migrated_engine) as session:
        yield session


def _write_note(vault: Path, zettel_id: str, title: str, body: str) -> Path:
    path = vault / f"{zettel_id}.md"
    path.write_text(
        f"---\nid: {zettel_id}\ntitle: {title}\ntype: permanent\n---\n{body}\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# search_notes()
# ---------------------------------------------------------------------------


def test_search_returns_matching_note_with_snippet_and_rank(tmp_path, migrated_session):
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_note(vault, "gauss-law", "Gauss's Law", "Gauss law states that flux equals charge.")
    _write_note(vault, "other-note", "Unrelated", "Something about thermodynamics.")

    sync_vault(vault, migrated_session)
    migrated_session.commit()

    results = search_notes("gauss", migrated_session)

    assert len(results) == 1
    r = results[0]
    assert r["zettel_id"] == "gauss-law"
    assert r["title"] == "Gauss's Law"
    assert "rank" in r and r["rank"] is not None
    assert "<b>" in r["snippet"] or "Gauss" in r["snippet"]


def test_search_nonexistent_term_returns_empty_list(tmp_path, migrated_session):
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_note(vault, "n1", "Some Note", "Body text about optics.")
    sync_vault(vault, migrated_session)
    migrated_session.commit()

    results = search_notes("nonexistent-term-xyz", migrated_session)
    assert results == []


def test_search_blank_query_returns_empty_list(migrated_session):
    assert search_notes("", migrated_session) == []
    assert search_notes("   ", migrated_session) == []


def test_search_query_with_fts5_special_chars_does_not_raise(tmp_path, migrated_session):
    """Hyphens/colons/quotes are FTS5 operator syntax but must be safe input
    here — sanitization quotes each word into a literal phrase token."""
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_note(vault, "n1", "Some Note", "Body text.")
    sync_vault(vault, migrated_session)
    migrated_session.commit()

    # None of these must raise; a no-match query returns an empty list.
    assert search_notes('"unterminated quote', migrated_session) == []
    assert search_notes("note: xyz", migrated_session) == []
    assert search_notes("-excluded-term", migrated_session) == []


def test_search_raises_when_note_fts_table_absent(global_session):
    """A pre-migration (or migration-less test) session raises a clean error,
    never a raw sqlite3.OperationalError."""
    with pytest.raises(SearchQueryError):
        search_notes("gauss", global_session)


def test_search_respects_limit(tmp_path, migrated_session):
    vault = tmp_path / "vault"
    vault.mkdir()
    for i in range(5):
        _write_note(vault, f"note-{i}", f"Title {i}", "shared keyword appears here.")
    sync_vault(vault, migrated_session)
    migrated_session.commit()

    results = search_notes("keyword", migrated_session, limit=2)
    assert len(results) == 2


def test_search_path_is_vault_relative(tmp_path, migrated_session):
    vault = tmp_path / "vault"
    (vault / "sub").mkdir(parents=True)
    _write_note(vault / "sub", "nested-note", "Nested", "unique-search-token here.")
    sync_vault(vault, migrated_session)
    migrated_session.commit()

    results = search_notes("unique-search-token", migrated_session, vault_root=vault)
    assert len(results) == 1
    assert results[0]["path"] == str(Path("sub") / "nested-note.md")


# ---------------------------------------------------------------------------
# sync FTS hook + rebuild-index
# ---------------------------------------------------------------------------


def test_sync_vault_populates_fts_row_per_note(tmp_path, migrated_session):
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_note(vault, "n1", "Alpha", "alpha body content.")

    report = sync_vault(vault, migrated_session)
    migrated_session.commit()

    assert report.fts_indexed == 1
    rows = migrated_session.connection().exec_driver_sql(
        "SELECT rowid FROM note_fts"
    ).fetchall()
    assert len(rows) == 1


def test_sync_vault_rerun_is_upsert_not_duplicate(tmp_path, migrated_session):
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_note(vault, "n1", "Alpha", "alpha body content.")

    sync_vault(vault, migrated_session)
    migrated_session.commit()
    sync_vault(vault, migrated_session)
    migrated_session.commit()

    rows = migrated_session.connection().exec_driver_sql(
        "SELECT rowid FROM note_fts"
    ).fetchall()
    assert len(rows) == 1


def test_rebuild_fts_index_reproduces_same_row_count(tmp_path, migrated_session):
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_note(vault, "n1", "Alpha", "alpha body.")
    _write_note(vault, "n2", "Beta", "beta body.")

    sync_vault(vault, migrated_session)
    migrated_session.commit()
    incremental_count = migrated_session.connection().exec_driver_sql(
        "SELECT COUNT(*) FROM note_fts"
    ).fetchone()[0]

    rebuilt = rebuild_fts_index(vault, migrated_session)

    rebuilt_count = migrated_session.connection().exec_driver_sql(
        "SELECT COUNT(*) FROM note_fts"
    ).fetchone()[0]

    assert rebuilt == incremental_count
    assert rebuilt_count == incremental_count


def test_sync_without_migration_is_noop_for_fts(tmp_path, global_session):
    """sync_vault against a non-migrated session must not raise — fts_indexed stays 0."""
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_note(vault, "n1", "Alpha", "alpha body.")

    report = sync_vault(vault, global_session)
    assert report.fts_indexed == 0


# ---------------------------------------------------------------------------
# CLI: notes search / notes sync --rebuild-index
# ---------------------------------------------------------------------------


def test_cli_search_json_shape(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_note(vault, "cli-gauss", "Gauss's Law", "Gauss law flux content.")

    env = {"WORKFLOW_VAULT_ROOT": str(vault), "WORKFLOW_DATA_DIR": str(data_dir)}
    runner = CliRunner()
    sync_result = runner.invoke(notes, ["sync"], env=env, catch_exceptions=False)
    assert sync_result.exit_code == 0

    result = runner.invoke(
        notes, ["search", "gauss", "--json"], env=env, catch_exceptions=False
    )
    assert result.exit_code == 0

    import json

    data = json.loads(result.output)
    assert set(data.keys()) == {"query", "results"}
    assert data["query"] == "gauss"
    assert len(data["results"]) == 1
    result_keys = set(data["results"][0].keys())
    assert result_keys == {"note_id", "zettel_id", "title", "path", "snippet", "rank"}


def test_cli_search_no_results_exits_zero(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    env = {"WORKFLOW_VAULT_ROOT": str(vault), "WORKFLOW_DATA_DIR": str(data_dir)}
    runner = CliRunner()
    runner.invoke(notes, ["sync"], env=env, catch_exceptions=False)

    result = runner.invoke(
        notes, ["search", "nonexistent-term-xyz", "--json"], env=env,
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    import json
    data = json.loads(result.output)
    assert data["results"] == []


def test_cli_sync_rebuild_index_flag(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_note(vault, "cli-rebuild", "Rebuild Me", "rebuild content token.")

    env = {"WORKFLOW_VAULT_ROOT": str(vault), "WORKFLOW_DATA_DIR": str(data_dir)}
    runner = CliRunner()
    result = runner.invoke(
        notes, ["sync", "--rebuild-index", "--json"], env=env, catch_exceptions=False
    )
    assert result.exit_code == 0
    import json
    data = json.loads(result.output)
    assert data["fts_rebuilt"] == 1


def test_cli_search_accented_query_matches_unaccented_title(tmp_path):
    """remove_diacritics=2 tokenizer: 'teoria' finds 'teoría' and vice versa."""
    vault = tmp_path / "vault"
    vault.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_note(vault, "teoria-note", "Teoría de Campos", "cuerpo sobre teoria de campos.")

    env = {"WORKFLOW_VAULT_ROOT": str(vault), "WORKFLOW_DATA_DIR": str(data_dir)}
    runner = CliRunner()
    runner.invoke(notes, ["sync"], env=env, catch_exceptions=False)

    result = runner.invoke(
        notes, ["search", "teoria", "--json"], env=env, catch_exceptions=False
    )
    assert result.exit_code == 0
    import json
    data = json.loads(result.output)
    assert len(data["results"]) == 1
