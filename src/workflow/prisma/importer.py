"""BibTeX → DB import for PRISMA systematic review (P2).

Parses .bib files with ``bibtexparser`` and inserts BibEntry / Author /
BibAuthor / BibUrl / ReferencedDatabase rows into ``workflow.db``.
Uses per-item savepoint rollback on IntegrityError for dedup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import bibtexparser
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from workflow.db.models.bibliography import (
    Author,
    AuthorType,
    BibAuthor,
    BibEntry,
    BibUrl,
    ReferencedDatabase,
)

__all__ = ["ImportResult", "import_bib_file"]


TRANSLATED_BIB_KEYS: dict[str, str] = {
    "entry_type": "ENTRYTYPE",
    "bibkey": "ID",
    "journaltitle": "journal",
    "notes": "note",
    "abstract_text": "abstract",
    "file_path": "file",
}

_STRING_BIB_FIELDS: frozenset[str] = frozenset(
    {
        "institution",
        "organization",
        "publisher",
        "title",
        "indextitle",
        "booktitle",
        "maintitle",
        "issuetitle",
        "eventtitle",
        "reprinttitle",
        "series",
        "volume",
        "number",
        "part",
        "issue",
        "volumes",
        "version",
        "pubstate",
        "pages",
        "pagetotal",
        "pagination",
        "month",
        "location",
        "venue",
        "doi",
        "eid",
        "eprint",
        "eprinttype",
        "addendum",
        "howpublished",
        "language",
        "isn",
        "annotation",
        "library",
        "label",
        "shorthand",
        "shorthandintro",
        "execute_task",
        "keywords",
        "options",
        "ids",
    }
)

_INT_BIB_FIELDS: frozenset[str] = frozenset({"year", "edition"})

_AUTHOR_FIELDS: tuple[str, ...] = ("author", "editor", "translator")


@dataclass(frozen=True)
class ImportResult:
    """Outcome of a .bib import run."""

    created: int = 0
    skipped: int = 0
    errors: tuple[str, ...] = ()
    statuses: tuple[tuple[str, str], ...] = field(default=())


def _strip_braces(s: str) -> str:
    return s.replace("{", "").replace("}", "")


def _clean(s: object | None) -> str | None:
    if s is None:
        return None
    v = _strip_braces(str(s)).strip()
    return v or None


def _split_authors(author_string: str) -> list[tuple[str, str]]:
    """Split BibTeX author string into ``(first_name, last_name)`` tuples.

    Supports forms: "Last, First", "First Last", "{Corporate Name}".
    Returns empty list for empty/whitespace input.
    """
    out: list[tuple[str, str]] = []
    for raw in author_string.split(" and "):
        token = raw.strip()
        if not token:
            continue
        if token.startswith("{") and token.endswith("}"):
            # Corporate name — entire string is the last_name
            name = _strip_braces(token).strip()
            if name:
                out.append(("", name))
            continue
        cleaned = _strip_braces(token).strip()
        if ", " in cleaned:
            last, first = cleaned.split(", ", 1)
            out.append((first.strip(), last.strip()))
        elif " " in cleaned:
            first, last = cleaned.split(" ", 1)
            out.append((first.strip(), last.strip()))
        else:
            out.append(("", cleaned))
    return out


_IGNORED_BIB_KEYS: frozenset[str] = frozenset(
    {"ENTRYTYPE", "ID", "url", *_AUTHOR_FIELDS, *TRANSLATED_BIB_KEYS.values()}
)


def _assign_direct(out: dict, key: str, val: object) -> None:
    """Populate ``out[key]`` from a 1:1 BibTeX field (string or int)."""
    cleaned = _clean(val)
    if cleaned is None:
        return
    if key in _STRING_BIB_FIELDS:
        out[key] = cleaned
    elif key in _INT_BIB_FIELDS:
        try:
            out[key] = int(cleaned)
        except ValueError:
            pass


def _parse_fields(raw: dict) -> dict:
    """Map a ``bibtexparser`` entry to a BibEntry kwarg dict."""
    out: dict = {}
    for model_key, bib_key in TRANSLATED_BIB_KEYS.items():
        if bib_key in raw:
            val = _clean(raw[bib_key])
            if val is not None:
                out[model_key] = val
    for key, val in raw.items():
        if key in _IGNORED_BIB_KEYS:
            continue
        _assign_direct(out, key, val)
    return out


def _get_or_create_author_type(session: Session, name: str) -> AuthorType:
    existing = session.scalars(
        select(AuthorType).where(AuthorType.type_of_author == name)
    ).first()
    if existing:
        return existing
    at = AuthorType(type_of_author=name)
    session.add(at)
    session.flush()
    return at


def _get_or_create_database(session: Session, name: str) -> ReferencedDatabase:
    existing = session.scalars(
        select(ReferencedDatabase).where(ReferencedDatabase.name == name)
    ).first()
    if existing:
        return existing
    db = ReferencedDatabase(name=name)
    session.add(db)
    session.flush()
    return db


def _upsert_author(session: Session, first_name: str, last_name: str) -> Author:
    existing = session.scalars(
        select(Author).where(
            Author.first_name == first_name, Author.last_name == last_name
        )
    ).first()
    if existing:
        return existing
    a = Author(first_name=first_name, last_name=last_name)
    savepoint = session.begin_nested()
    try:
        session.add(a)
        session.flush()
        savepoint.commit()
        return a
    except IntegrityError:
        savepoint.rollback()
        return session.scalars(
            select(Author).where(
                Author.first_name == first_name, Author.last_name == last_name
            )
        ).one()


def _process_authors(
    session: Session,
    bib_entry: BibEntry,
    author_string: str,
    author_type_name: str,
) -> None:
    at = _get_or_create_author_type(session, author_type_name)
    for idx, (first, last) in enumerate(_split_authors(author_string)):
        author = _upsert_author(session, first, last)
        savepoint = session.begin_nested()
        try:
            link = BibAuthor(
                bib_entry_id=bib_entry.id,
                author_id=author.id,
                author_type_id=at.id,
                first_author=(idx == 0 and author_type_name == "author"),
            )
            session.add(link)
            session.flush()
            savepoint.commit()
        except IntegrityError:
            savepoint.rollback()


def _process_url(
    session: Session,
    bib_entry: BibEntry,
    url_string: str,
    database_name: str | None,
) -> None:
    db = _get_or_create_database(session, database_name or "unknown")
    savepoint = session.begin_nested()
    try:
        session.add(
            BibUrl(
                bib_entry_id=bib_entry.id,
                database_id=db.id,
                url_string=url_string,
            )
        )
        session.flush()
        savepoint.commit()
    except IntegrityError:
        savepoint.rollback()


def _process_entry(session: Session, raw: dict, database_name: str | None) -> str:
    fields_dict = _parse_fields(raw)
    entry = BibEntry(**fields_dict)

    savepoint = session.begin_nested()
    try:
        session.add(entry)
        session.flush()
        savepoint.commit()
    except IntegrityError:
        savepoint.rollback()
        return "skipped"

    for afield in _AUTHOR_FIELDS:
        if afield in raw and raw[afield]:
            _process_authors(session, entry, raw[afield], afield)

    url = _clean(raw.get("url"))
    if url:
        _process_url(session, entry, url, database_name)

    return "created"


def _infer_database_name(path: Path) -> str | None:
    stem = path.stem
    if "-" in stem:
        return stem.split("-", 1)[0]
    return None


def import_bib_file(
    session: Session,
    path: str | Path,
    database_name: str | None = None,
) -> ImportResult:
    """Parse a .bib file and insert rows into the session.

    Commits the session on completion. Raises FileNotFoundError if path
    does not exist. Per-entry errors are collected into the result
    rather than raised.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"bib file not found: {path}")

    with p.open() as f:
        parsed = bibtexparser.load(f)

    if database_name is None:
        database_name = _infer_database_name(p)

    created = 0
    skipped = 0
    errors: list[str] = []
    statuses: list[tuple[str, str]] = []

    for raw in parsed.entries:
        bibkey = raw.get("ID", "<no-id>")
        try:
            status = _process_entry(session, raw, database_name)
            if status == "created":
                created += 1
            elif status == "skipped":
                skipped += 1
            statuses.append((bibkey, status))
        except Exception as exc:  # noqa: BLE001 — per-entry isolation
            session.rollback()
            msg = f"{bibkey}: {exc}"
            errors.append(msg)
            statuses.append((bibkey, f"error: {exc}"))

    session.commit()
    return ImportResult(
        created=created,
        skipped=skipped,
        errors=tuple(errors),
        statuses=tuple(statuses),
    )
