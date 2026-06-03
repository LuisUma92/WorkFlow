"""Phase-3 calculated-bibkey recompute-keys tests.

Coverage:
- dry-run reports changes but writes nothing (no DB mutation, no backup).
- fill-missing default: NULL bibkey → calculated; existing key → untouched.
- --all mode: every entry recalculated.
- collision: two distinct works with same base key get a/b suffixes.
- backup file created on a real file-based run.
- idempotency: second run of same mode yields 0 changes.
- _surname_for_entry: first_author flag honored; fallback; anon when no authors.
- CLI: recompute-keys command (table + JSON output, --dry-run, --all).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.bibliography import Author, BibAuthor, BibEntry
from workflow.prisma.cli import prisma
from workflow.prisma.importer import import_bib_text
from workflow.prisma.recompute import (
    BibkeyChange,
    apply_recompute,
    backup_database,
    compute_recompute_plan,
    _surname_for_entry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enable_fk(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def _make_file_engine(db_path: Path):
    """Create a GlobalBase engine backed by a real file (for backup tests)."""
    engine = create_engine(f"sqlite:///{db_path}")
    event.listen(engine, "connect", _enable_fk)
    GlobalBase.metadata.create_all(engine)
    return engine


BIB_KNUTH = textwrap.dedent("""\
    @book{,
      title     = {The Art of Computer Programming},
      author    = {Knuth, Donald E.},
      year      = {1997},
      volume    = {3},
      edition   = {3},
      publisher = {Addison-Wesley},
    }
""")

BIB_EINSTEIN = textwrap.dedent("""\
    @article{,
      title   = {On the Electrodynamics},
      author  = {Einstein, Albert},
      year    = {1905},
      volume  = {17},
    }
""")

BIB_WITH_EXPLICIT_KEY = textwrap.dedent("""\
    @article{existingKey2020,
      title   = {Explicit Key Article},
      author  = {Smith, John},
      year    = {2020},
    }
""")


# ---------------------------------------------------------------------------
# _surname_for_entry — unit tests (no DB)
# ---------------------------------------------------------------------------


class TestSurnameForEntry:
    """Verify surname extraction logic against ORM objects."""

    def _make_entry_with_author(
        self,
        last_name: str,
        name_prefix: str | None = None,
        first_author: bool = True,
    ) -> BibEntry:
        """Build a lightweight BibEntry + BibAuthor + Author without persisting."""
        author = Author()
        author.first_name = "Test"
        author.last_name = last_name
        author.name_prefix = name_prefix

        link = BibAuthor()
        link.first_author = first_author
        link.author = author

        entry = BibEntry()
        entry.author_links = [link]
        return entry

    def test_first_author_flag_honored(self):
        """The BibAuthor flagged first_author=True is used as the source."""
        author_a = Author()
        author_a.first_name = "Alice"
        author_a.last_name = "Alpha"
        author_a.name_prefix = None

        author_b = Author()
        author_b.first_name = "Bob"
        author_b.last_name = "Beta"
        author_b.name_prefix = None

        link_a = BibAuthor()
        link_a.first_author = False
        link_a.author = author_a

        link_b = BibAuthor()
        link_b.first_author = True
        link_b.author = author_b

        entry = BibEntry()
        entry.author_links = [link_a, link_b]

        last_name, prefix = _surname_for_entry(entry)
        assert last_name == "Beta"
        assert prefix is None

    def test_fallback_to_first_link_when_none_flagged(self):
        """When no link has first_author=True, the first link is used."""
        entry = self._make_entry_with_author("Fallback", first_author=False)
        last_name, prefix = _surname_for_entry(entry)
        assert last_name == "Fallback"

    def test_name_prefix_returned(self):
        """Von-particle (name_prefix) is included in the result."""
        entry = self._make_entry_with_author("Beethoven", name_prefix="van")
        last_name, prefix = _surname_for_entry(entry)
        assert last_name == "Beethoven"
        assert prefix == "van"

    def test_anon_when_no_authors(self):
        """An entry with no author links yields (None, None)."""
        entry = BibEntry()
        entry.author_links = []
        assert _surname_for_entry(entry) == (None, None)


# ---------------------------------------------------------------------------
# compute_recompute_plan — fill_missing_only (default)
# ---------------------------------------------------------------------------


class TestFillMissingOnly:
    def test_null_bibkey_gets_calculated(self, global_session):
        """An entry with NULL bibkey receives a calculated key."""
        import_bib_text(global_session, BIB_KNUTH)
        # Force bibkey to NULL to simulate missing.
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.title == "The Art of Computer Programming")
        ).scalar_one()
        entry.bibkey = None
        global_session.flush()

        changes = compute_recompute_plan(global_session, fill_missing_only=True)
        assert len(changes) == 1
        assert changes[0].new_bibkey == "knuth1997V03E03"
        assert changes[0].old_bibkey is None

    def test_existing_key_untouched(self, global_session):
        """An entry with an existing bibkey is NOT in the change plan."""
        import_bib_text(global_session, BIB_WITH_EXPLICIT_KEY)
        changes = compute_recompute_plan(global_session, fill_missing_only=True)
        assert all(c.old_bibkey != "existingKey2020" for c in changes)

    def test_mixed_entries(self, global_session):
        """Only NULL-bibkey entries appear in the plan; keyed entries are skipped."""
        import_bib_text(global_session, BIB_WITH_EXPLICIT_KEY)
        import_bib_text(global_session, BIB_KNUTH)
        # Set the Knuth entry key to NULL.
        knuth = global_session.execute(
            select(BibEntry).where(BibEntry.title == "The Art of Computer Programming")
        ).scalar_one()
        knuth.bibkey = None
        global_session.flush()

        changes = compute_recompute_plan(global_session, fill_missing_only=True)
        assert len(changes) == 1
        assert changes[0].new_bibkey == "knuth1997V03E03"


# ---------------------------------------------------------------------------
# compute_recompute_plan — recompute all
# ---------------------------------------------------------------------------


class TestRecomputeAll:
    def test_all_mode_recalculates_every_entry(self, global_session):
        """--all mode produces changes for entries whose existing key differs."""
        import_bib_text(global_session, BIB_WITH_EXPLICIT_KEY)
        changes = compute_recompute_plan(global_session, fill_missing_only=False)
        # existingKey2020 ≠ smith2020 → change expected
        assert len(changes) == 1
        assert changes[0].old_bibkey == "existingKey2020"
        assert changes[0].new_bibkey == "smith2020"

    def test_already_correct_key_produces_no_change(self, global_session):
        """If the existing key already matches the calculated one, no change emitted."""
        import_bib_text(global_session, BIB_KNUTH)
        # Force the correct calculated key on the entry.
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.title == "The Art of Computer Programming")
        ).scalar_one()
        entry.bibkey = "knuth1997V03E03"
        global_session.flush()

        changes = compute_recompute_plan(global_session, fill_missing_only=False)
        assert not any(c.entry_id == entry.id for c in changes)


# ---------------------------------------------------------------------------
# Collision disambiguation
# ---------------------------------------------------------------------------


class TestCollisionDisambiguation:
    def test_two_works_same_base_key_get_suffixes(self, global_session):
        """Two distinct works producing the same base key get a/b suffixes."""
        bib_a = textwrap.dedent("""\
            @article{,
              title  = {Collision Work One},
              author = {Clash, Test},
              year   = {2000},
            }
        """)
        bib_b = textwrap.dedent("""\
            @article{fakeKey,
              title  = {Collision Work Two},
              author = {Clash, Test},
              year   = {2000},
            }
        """)
        import_bib_text(global_session, bib_a)  # clash2000
        import_bib_text(global_session, bib_b)  # stored as fakeKey

        # Force fakeKey entry to NULL so both are targets in fill_missing plan.
        entry_b = global_session.execute(
            select(BibEntry).where(BibEntry.title == "Collision Work Two")
        ).scalar_one()
        entry_b.bibkey = None
        global_session.flush()

        changes = compute_recompute_plan(global_session, fill_missing_only=True)
        new_keys = {c.new_bibkey for c in changes}
        assert "clash2000a" in new_keys

    def test_all_mode_collision_between_two_entries(self, global_session):
        """--all mode: two entries that share the same calculated base key."""
        bib_a = textwrap.dedent("""\
            @article{keyA,
              title  = {Coll All Work One},
              author = {Alltest, Foo},
              year   = {2001},
            }
        """)
        bib_b = textwrap.dedent("""\
            @article{keyB,
              title  = {Coll All Work Two},
              author = {Alltest, Foo},
              year   = {2001},
            }
        """)
        import_bib_text(global_session, bib_a + bib_b)

        changes = compute_recompute_plan(global_session, fill_missing_only=False)
        new_keys = [c.new_bibkey for c in changes]
        # One should be alltest2001, the other alltest2001a
        assert "alltest2001" in new_keys
        assert "alltest2001a" in new_keys


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_fill_missing_idempotent_on_second_run(self, global_session):
        """Running fill-missing twice yields 0 changes on the second run."""
        import_bib_text(global_session, BIB_KNUTH)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.title == "The Art of Computer Programming")
        ).scalar_one()
        entry.bibkey = None
        global_session.flush()

        changes1 = compute_recompute_plan(global_session, fill_missing_only=True)
        apply_recompute(global_session, changes1)
        global_session.flush()

        changes2 = compute_recompute_plan(global_session, fill_missing_only=True)
        assert changes2 == []

    def test_all_mode_idempotent_on_second_run(self, global_session):
        """Running --all twice: second run yields 0 changes."""
        import_bib_text(global_session, BIB_EINSTEIN)

        changes1 = compute_recompute_plan(global_session, fill_missing_only=False)
        apply_recompute(global_session, changes1)
        global_session.flush()

        changes2 = compute_recompute_plan(global_session, fill_missing_only=False)
        assert changes2 == []


# ---------------------------------------------------------------------------
# Dry-run: no writes, no backup
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_no_db_mutation(self, global_session):
        """Dry-run plan returns changes but does NOT mutate the DB."""
        import_bib_text(global_session, BIB_KNUTH)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.title == "The Art of Computer Programming")
        ).scalar_one()
        entry.bibkey = None
        global_session.flush()

        changes = compute_recompute_plan(global_session, fill_missing_only=True)
        assert len(changes) == 1

        # Simulate dry-run: do NOT call apply_recompute.
        # Verify bibkey still NULL.
        global_session.expire_all()
        entry_after = global_session.execute(
            select(BibEntry).where(BibEntry.title == "The Art of Computer Programming")
        ).scalar_one()
        assert entry_after.bibkey is None


# ---------------------------------------------------------------------------
# Backup — file-based engine
# ---------------------------------------------------------------------------


class TestBackupDatabase:
    def test_backup_creates_file(self, tmp_path):
        """backup_database copies the SQLite file to a timestamped .bak file."""
        db_file = tmp_path / "test.db"
        engine = _make_file_engine(db_file)
        # create_all already ran in _make_file_engine; ensure file exists.
        GlobalBase.metadata.create_all(engine)

        backup = backup_database(engine)
        assert backup is not None
        assert backup.exists()
        assert backup.name.startswith("test.db.bak-")
        engine.dispose()

    def test_backup_returns_none_for_in_memory(self, global_engine):
        """In-memory engine returns None from backup_database."""
        result = backup_database(global_engine)
        assert result is None

    def test_backup_is_readable_copy(self, tmp_path):
        """The backup is a valid copy of the original DB file."""
        db_file = tmp_path / "workflow.db"
        engine = _make_file_engine(db_file)

        backup = backup_database(engine)
        assert backup is not None
        # Sizes must match (shutil.copy2 is a byte-perfect copy).
        assert backup.stat().st_size == db_file.stat().st_size
        engine.dispose()


# ---------------------------------------------------------------------------
# CLI: recompute-keys
# ---------------------------------------------------------------------------


@pytest.fixture
def runner():
    return CliRunner()


class TestCliRecomputeKeys:
    def test_dry_run_reports_but_does_not_write(self, runner, global_engine):
        """--dry-run shows changes but leaves DB unchanged."""
        bib = textwrap.dedent("""\
            @book{,
              title     = {Dry Run Book},
              author    = {Dryrun, Test},
              year      = {2010},
              edition   = {2},
              publisher = {Pub},
            }
        """)
        with Session(global_engine) as s:
            import_bib_text(s, bib)
            entry = s.execute(
                select(BibEntry).where(BibEntry.title == "Dry Run Book")
            ).scalar_one()
            entry.bibkey = None
            s.commit()

        result = runner.invoke(
            prisma,
            ["bib", "recompute-keys", "--dry-run"],
            obj={"engine": global_engine},
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "dryrun2010E02" in result.output

        # DB still NULL after dry-run.
        with Session(global_engine) as s:
            e = s.execute(
                select(BibEntry).where(BibEntry.title == "Dry Run Book")
            ).scalar_one()
        assert e.bibkey is None

    def test_fill_missing_default_cli(self, runner, global_engine):
        """Default (fill-missing) mode assigns key to NULL entry."""
        with Session(global_engine) as s:
            import_bib_text(s, BIB_KNUTH)
            e = s.execute(
                select(BibEntry).where(BibEntry.title == "The Art of Computer Programming")
            ).scalar_one()
            e.bibkey = None
            s.commit()

        result = runner.invoke(
            prisma,
            ["bib", "recompute-keys"],
            obj={"engine": global_engine},
            catch_exceptions=False,
        )
        assert result.exit_code == 0

        with Session(global_engine) as s:
            e = s.execute(
                select(BibEntry).where(BibEntry.title == "The Art of Computer Programming")
            ).scalar_one()
        assert e.bibkey == "knuth1997V03E03"

    def test_all_flag_recalculates_existing(self, runner, global_engine):
        """--all --yes rewrites the explicit key to the calculated one."""
        with Session(global_engine) as s:
            import_bib_text(s, BIB_WITH_EXPLICIT_KEY)

        result = runner.invoke(
            prisma,
            ["bib", "recompute-keys", "--all", "--yes"],
            obj={"engine": global_engine},
            catch_exceptions=False,
        )
        assert result.exit_code == 0

        with Session(global_engine) as s:
            e = s.execute(
                select(BibEntry).where(BibEntry.title == "Explicit Key Article")
            ).scalar_one()
        assert e.bibkey == "smith2020"

    def test_json_output(self, runner, global_engine):
        """--json returns valid JSON with expected keys."""
        with Session(global_engine) as s:
            import_bib_text(s, BIB_WITH_EXPLICIT_KEY)

        result = runner.invoke(
            prisma,
            ["bib", "recompute-keys", "--all", "--json", "--yes"],
            obj={"engine": global_engine},
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "changes" in data
        assert "count" in data
        assert "dry_run" in data
        assert data["dry_run"] is False
        assert data["count"] >= 1

    def test_dry_run_json_no_backup(self, runner, global_engine):
        """--dry-run --json: backup is null."""
        with Session(global_engine) as s:
            import_bib_text(s, BIB_EINSTEIN)

        result = runner.invoke(
            prisma,
            ["bib", "recompute-keys", "--dry-run", "--json"],
            obj={"engine": global_engine},
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["backup"] is None

    def test_no_changes_message(self, runner, global_engine):
        """With no entries that need changes, a no-change message is shown."""
        result = runner.invoke(
            prisma,
            ["bib", "recompute-keys"],
            obj={"engine": global_engine},
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "No changes" in result.output

    def test_help_text_present(self, runner):
        """The recompute-keys command appears in bib help output."""
        result = runner.invoke(prisma, ["bib", "--help"])
        assert result.exit_code == 0
        assert "recompute-keys" in result.output

    # --- FIX 1: --all confirmation guard ---

    def test_all_without_yes_and_input_n_aborts(self, runner, global_engine):
        """--all without --yes prompts; answering 'n' aborts with nonzero exit."""
        with Session(global_engine) as s:
            import_bib_text(s, BIB_WITH_EXPLICIT_KEY)
            before = s.execute(
                select(BibEntry).where(BibEntry.title == "Explicit Key Article")
            ).scalar_one()
            before_key = before.bibkey  # preserve for assertion

        result = runner.invoke(
            prisma,
            ["bib", "recompute-keys", "--all"],
            obj={"engine": global_engine},
            input="n\n",
            catch_exceptions=False,
        )
        assert result.exit_code != 0

        # DB must be unchanged.
        with Session(global_engine) as s:
            e = s.execute(
                select(BibEntry).where(BibEntry.title == "Explicit Key Article")
            ).scalar_one()
        assert e.bibkey == before_key

    def test_all_without_yes_and_input_y_applies(self, runner, global_engine):
        """--all without --yes prompts; answering 'y' applies changes."""
        with Session(global_engine) as s:
            import_bib_text(s, BIB_WITH_EXPLICIT_KEY)

        result = runner.invoke(
            prisma,
            ["bib", "recompute-keys", "--all"],
            obj={"engine": global_engine},
            input="y\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0

        with Session(global_engine) as s:
            e = s.execute(
                select(BibEntry).where(BibEntry.title == "Explicit Key Article")
            ).scalar_one()
        assert e.bibkey == "smith2020"

    def test_json_all_without_yes_raises(self, runner, global_engine):
        """--json --all without --yes raises ClickException (no prompt in JSON mode)."""
        with Session(global_engine) as s:
            import_bib_text(s, BIB_WITH_EXPLICIT_KEY)

        result = runner.invoke(
            prisma,
            ["bib", "recompute-keys", "--all", "--json"],
            obj={"engine": global_engine},
            catch_exceptions=False,
        )
        assert result.exit_code != 0
        assert "--yes" in result.output or "requires --yes" in result.output

    def test_json_all_with_yes_works(self, runner, global_engine):
        """--json --all --yes skips prompt and returns valid JSON."""
        with Session(global_engine) as s:
            import_bib_text(s, BIB_WITH_EXPLICIT_KEY)

        result = runner.invoke(
            prisma,
            ["bib", "recompute-keys", "--all", "--json", "--yes"],
            obj={"engine": global_engine},
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] >= 1

    # --- FIX 2: backup failure aborts ---

    def test_backup_failure_aborts_no_db_change(
        self, runner, global_engine, monkeypatch
    ):
        """If backup_database raises OSError, command aborts before any DB write."""
        with Session(global_engine) as s:
            import_bib_text(s, BIB_WITH_EXPLICIT_KEY)
            before_key = s.execute(
                select(BibEntry).where(BibEntry.title == "Explicit Key Article")
            ).scalar_one().bibkey

        def _fail_backup(engine):
            raise OSError("disk full")

        monkeypatch.setattr(
            "workflow.prisma.cli.backup_database", _fail_backup
        )

        result = runner.invoke(
            prisma,
            ["bib", "recompute-keys", "--yes"],
            obj={"engine": global_engine},
            catch_exceptions=False,
        )
        assert result.exit_code != 0
        assert "backup failed" in result.output.lower() or "DB backup" in result.output

        # DB must be unchanged.
        with Session(global_engine) as s:
            e = s.execute(
                select(BibEntry).where(BibEntry.title == "Explicit Key Article")
            ).scalar_one()
        assert e.bibkey == before_key


# ---------------------------------------------------------------------------
# apply_recompute — unit
# ---------------------------------------------------------------------------


class TestApplyRecompute:
    def test_apply_sets_bibkey(self, global_session):
        """apply_recompute sets the bibkey column on the matching entry."""
        import_bib_text(global_session, BIB_KNUTH)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.title == "The Art of Computer Programming")
        ).scalar_one()
        entry.bibkey = None
        global_session.flush()

        change = BibkeyChange(
            entry_id=entry.id,
            title=entry.title,
            old_bibkey=None,
            new_bibkey="knuth1997V03E03",
        )
        apply_recompute(global_session, [change])
        global_session.flush()

        global_session.expire(entry)
        assert entry.bibkey == "knuth1997V03E03"

    def test_apply_empty_list_is_noop(self, global_session):
        """apply_recompute with empty changes list raises no error."""
        apply_recompute(global_session, [])  # must not raise
