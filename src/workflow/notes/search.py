"""workflow.notes.search — vault full-text search (ADR-0021, Wave 1 Phase 2).

Queries the ``note_fts`` FTS5 table (see migration
``0017_note_fts_and_alias``) via SQLite's ``bm25()`` ranking function and
``snippet()`` highlighter. The index is derived-only: ``.md`` files remain
truth (ADR-0010); a missing or stale ``note_fts`` table is always fully
recoverable via ``workflow.notes.sync.rebuild_fts_index``.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from workflow.vault.paths import resolve_vault_root

__all__ = ["SearchQueryError", "search_notes"]

# note_fts column order: title(0), aliases(1), body(2) — snippet() needs the
# 0-based column index of the field to highlight (body reads best as a preview).
_BODY_COLUMN_INDEX = 2

_SEARCH_SQL = (
    "SELECT n.id, n.zettel_id, n.title, n.filename, "
    f"snippet(note_fts, {_BODY_COLUMN_INDEX}, '<b>', '</b>', '...', 10) AS snippet, "
    "bm25(note_fts) AS rank "
    "FROM note_fts JOIN note n ON n.id = note_fts.rowid "
    "WHERE note_fts MATCH ? "
    "ORDER BY rank "
    "LIMIT ?"
)


class SearchQueryError(Exception):
    """Raised for a malformed FTS5 MATCH query, or a missing note_fts index."""


def _table_exists(session: Session, table: str) -> bool:
    row = session.connection().exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _relative_path(filename: str, vault_root: Path) -> str:
    """Best-effort vault-relative path; falls back to the raw filename."""
    try:
        return str(Path(filename).resolve().relative_to(vault_root.resolve()))
    except ValueError:
        return filename


def _sanitize_fts_query(raw: str) -> str:
    """Turn free-text user input into a safe FTS5 MATCH query.

    FTS5's bareword query syntax treats ``-`` as a NOT-prefix operator and
    ``:`` as a column filter — both common in plain search terms (zettel_ids,
    hyphenated slugs, "note: xyz") and both liable to blow up as a MATCH
    syntax error (e.g. ``no such column``) rather than "no results". Each
    whitespace-separated word is instead double-quoted (any embedded ``"``
    doubled per FTS5's own escaping rule) into a phrase token; consecutive
    quoted phrases combine with FTS5's implicit AND. This makes every plain
    multi-word query literal and syntax-error-proof, at the cost of not
    exposing FTS5's boolean/NEAR operators to the CLI (out of scope here —
    this module is a body/title/alias phrase search, not a query-language
    frontend).
    """
    words = raw.split()
    return " ".join('"' + w.replace('"', '""') + '"' for w in words)


def search_notes(
    query: str,
    session: Session,
    *,
    limit: int = 20,
    vault_root: Path | None = None,
) -> list[dict]:
    """Full-text search notes by title/aliases/body via FTS5 bm25() ranking.

    Args:
        query: Plain free-text search terms (space-separated words). Each
            word is treated as a literal phrase token internally (see
            ``_sanitize_fts_query``) — FTS5 boolean/NEAR operator syntax is
            not exposed here, so hyphens, colons, and quotes in a query are
            always safe, never a syntax error.
        session: Active SQLAlchemy session bound to the global DB.
        limit: Max results to return (default 20).
        vault_root: Override vault root for path-relativization (default
            ``resolve_vault_root()``).

    Returns:
        A list of dicts, ranked ascending by ``rank`` (SQLite bm25()
        convention: lower is more relevant): ``{"note_id", "zettel_id",
        "title", "path", "snippet", "rank"}``. Empty list (not an error) when
        nothing matches or ``query`` is blank.

    Raises:
        SearchQueryError: the ``note_fts`` table doesn't exist yet (index
            never built — run ``workflow notes sync --rebuild-index``), or
            ``query`` is not valid FTS5 MATCH syntax.
    """
    if not query or not query.strip():
        return []

    if not _table_exists(session, "note_fts"):
        raise SearchQueryError(
            "note_fts index not found — run `workflow notes sync "
            "--rebuild-index` first."
        )

    root = vault_root if vault_root is not None else resolve_vault_root()
    fts_query = _sanitize_fts_query(query)
    if not fts_query:
        return []

    try:
        rows = session.connection().exec_driver_sql(
            _SEARCH_SQL, (fts_query, limit)
        ).fetchall()
    except OperationalError as exc:
        raise SearchQueryError(f"invalid search query {query!r}: {exc}") from exc

    return [
        {
            "note_id": row[0],
            "zettel_id": row[1],
            "title": row[2],
            "path": _relative_path(row[3], root),
            "snippet": row[4],
            "rank": row[5],
        }
        for row in rows
    ]
