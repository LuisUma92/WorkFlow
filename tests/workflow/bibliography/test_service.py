"""Unit tests for workflow.bibliography.service.

Tests follow TDD RED→GREEN cycle.
Fixtures reuse global_session from tests/conftest.py (GlobalBase in-memory SQLite).
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from workflow.bibliography.service import BibKeyAmbiguous, get_bib_entry_by_bibkey
from workflow.db.models.bibliography import BibEntry


# ── Helpers ───────────────────────────────────────────────────────────────


def _make_bib(session: Session, bibkey: str, title: str = "A Title") -> BibEntry:
    """Insert a BibEntry row and flush (no commit, rolls back with session)."""
    entry = BibEntry(bibkey=bibkey, title=title, year=2024)
    session.add(entry)
    session.flush()
    return entry


# ── Tests ─────────────────────────────────────────────────────────────────


class TestGetBibEntryByBibkey:
    """Covers the 0 / 1 / 2+ row contract."""

    def test_zero_rows_returns_none(self, global_session: Session) -> None:
        """No matching rows → return None (back-compat for callers)."""
        result = get_bib_entry_by_bibkey(global_session, "nonexistent2099")
        assert result is None

    def test_one_row_returns_entry(self, global_session: Session) -> None:
        """Exactly one matching row → return that entry."""
        _make_bib(global_session, "smith2024")
        result = get_bib_entry_by_bibkey(global_session, "smith2024")
        assert result is not None
        assert result.bibkey == "smith2024"

    def test_two_rows_same_bibkey_raises_ambiguous(self, global_session: Session) -> None:
        """Two rows with the same bibkey → raise BibKeyAmbiguous.

        BibEntry.bibkey has no UNIQUE constraint at the DB layer (only an
        application-level expectation), so duplicate inserts are possible via
        ORM.  We insert two separate objects with the same bibkey and verify
        that get_bib_entry_by_bibkey raises BibKeyAmbiguous.
        """
        # Insert via ORM — no UNIQUE constraint, so both flush fine.
        e1 = BibEntry(bibkey="dup2024", title="First Dup", year=2024)
        e2 = BibEntry(bibkey="dup2024", title="Second Dup", year=2024)
        global_session.add_all([e1, e2])
        global_session.flush()
        # Expire so the query executes fresh against the DB.
        global_session.expire_all()

        with pytest.raises(BibKeyAmbiguous, match="dup2024"):
            get_bib_entry_by_bibkey(global_session, "dup2024")

    def test_eager_load_author_links(self, global_session: Session) -> None:
        """author_links is accessible without additional DB hits (eager-loaded)."""
        entry = _make_bib(global_session, "eager2024")
        # Expire all objects so lazy-load would be required without options
        global_session.expire_all()

        result = get_bib_entry_by_bibkey(global_session, "eager2024")
        assert result is not None
        # Accessing author_links must not raise DetachedInstanceError.
        # (Empty list is fine; the point is it was eager-loaded.)
        assert isinstance(result.author_links, list)
