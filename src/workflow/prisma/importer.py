"""BibTeX → DB import for PRISMA systematic review (P2).

Parses .bib files with ``bibtexparser`` and inserts BibEntry / Author /
BibAuthor / BibUrl / ReferencedDatabase rows into ``workflow.db``.
Uses per-item savepoint rollback on IntegrityError for dedup.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import bibtexparser
from bibtexparser.bparser import BibTexParser
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from workflow.bibliography import dialect as _dialect
from workflow.db.models.bibliography import (
    Author,
    AuthorType,
    BibAuthor,
    BibEntry,
    BibUrl,
    ReferencedDatabase,
)

__all__ = ["ImportResult", "import_bib_file", "import_bib_text", "MAX_BIB_SIZE_BYTES"]


MAX_BIB_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB hard cap on input

_ALLOWED_URL_SCHEMES: frozenset[str] = frozenset({"http", "https", "ftp"})

EntryStatus = Literal["created", "skipped"]

TRANSLATED_BIB_KEYS: dict[str, str] = {
    "entry_type": "ENTRYTYPE",
    "bibkey": "ID",
    # BibTeX → BibLaTeX field aliases — derived from canonical map (ADR-0019).
    # Keys are BibLaTeX model column names; values are BibTeX raw field names.
    **{biblatex: bibtex for bibtex, biblatex in _dialect.BIBTEX_TO_BIBLATEX.items()},
    # Importer-private struct keys (not in the dialect alias map)
    "publication_date": "date",
    "urldate": "urldate",
    "abstract_text": "abstract",
    "file_path": "file",
}

# Raw biblatex ``date`` field → stored verbatim (ADR-0019 P2.2).
# Separate from TRANSLATED_BIB_KEYS because it needs special dual handling:
# the verbatim literal goes to BibEntry.date; year/month are derived from it.
_RAW_DATE_BIB_FIELD: str = "date"

_DATE_BIB_FIELDS: frozenset[str] = frozenset({"publication_date", "urldate"})

_STRING_BIB_FIELDS: frozenset[str] = frozenset(
    {
        # BibLaTeX-native spellings that can also appear as raw fields when a
        # .bib is already in biblatex format (ADR-0019 P1).
        "journaltitle",
        "notes",
        # Other direct-pass string fields
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
        # BibLaTeX dialect additions (ADR-0019 P2.2)
        "chapter",
        "type",
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


def _parse_date(val: str) -> date | None:
    """Parse BibLaTeX date strings (YYYY, YYYY-MM, YYYY-MM-DD).

    Also accepts EDTF ranges like ``2010/2015`` or ``2010-03/2015``; in that
    case the *first* component (before ``/``) is parsed and returned.
    """
    # Strip EDTF range: take only the start component.
    first_component = val.split("/")[0].strip()
    parts = first_component.split("-")
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day)
    except (ValueError, IndexError):
        return None


def _split_authors(
    author_string: str,
) -> list[tuple[str, str, str | None, str | None]]:
    """Split BibTeX author string into ``(first, last, prefix, suffix)`` tuples.

    Supports forms:
    - ``"Last, First"``         → prefix/suffix None
    - ``"von Last, Jr, First"`` → prefix="von", suffix="Jr"
    - ``"First Last"``          → prefix/suffix None
    - ``"{Corporate Name}"``    → first="", prefix/suffix None

    *prefix* captures the von-particle (lowercase word(s) before Last in
    the ``Last, First`` form).  *suffix* captures the Jr-token in the
    three-part ``Last, Jr, First`` BibTeX form.

    Returns empty list for empty/whitespace input.
    """
    out: list[tuple[str, str, str | None, str | None]] = []
    for raw in author_string.split(" and "):
        token = raw.strip()
        if not token:
            continue
        if token.startswith("{") and token.endswith("}"):
            # Corporate name — entire string is the last_name
            name = _strip_braces(token).strip()
            if name:
                out.append(("", name, None, None))
            continue
        cleaned = _strip_braces(token).strip()
        comma_parts = [p.strip() for p in cleaned.split(",")]
        if len(comma_parts) >= 3:
            # BibTeX "von Last, Jr, First" form
            last_part = comma_parts[0]
            suffix = comma_parts[1] or None
            first = ", ".join(comma_parts[2:]).strip()
            # Split von prefix from last name (lowercase leading words)
            last, prefix = _extract_von(last_part)
            out.append((first, last, prefix or None, suffix))
        elif len(comma_parts) == 2:
            # "Last, First" or "von Last, First"
            last_part = comma_parts[0]
            first = comma_parts[1].strip()
            last, prefix = _extract_von(last_part)
            out.append((first, last, prefix or None, None))
        elif " " in cleaned:
            # "First Last" — no comma.  Split on the first space so everything
            # to the right forms the last-name token, then run _extract_von on
            # it to capture a lowercase leading particle (e.g. "van Beethoven").
            first, last_token = cleaned.split(" ", 1)
            last, prefix = _extract_von(last_token.strip())
            out.append((first.strip(), last, prefix or None, None))
        else:
            out.append(("", cleaned, None, None))
    return out


def _extract_von(last_part: str) -> tuple[str, str]:
    """Return ``(last_name, von_prefix)`` from a BibTeX last-name token.

    Lowercase leading words are treated as the von-particle (e.g. "von der
    Heide" → last="Heide", prefix="von der").  If no lowercase prefix exists
    the whole string is the last name and prefix is "".
    """
    words = last_part.strip().split()
    prefix_words: list[str] = []
    for word in words[:-1]:  # keep at least the last word as last_name
        if word and word[0].islower():
            prefix_words.append(word)
        else:
            break
    if prefix_words:
        prefix = " ".join(prefix_words)
        last = " ".join(words[len(prefix_words):])
    else:
        prefix = ""
        last = last_part.strip()
    return last, prefix


_IGNORED_BIB_KEYS: frozenset[str] = frozenset(
    {"ENTRYTYPE", "ID", "url", _RAW_DATE_BIB_FIELD, *_AUTHOR_FIELDS, *TRANSLATED_BIB_KEYS.values()}
)


def _assign_direct(out: dict[str, object], key: str, val: object) -> None:
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


def _assign_translated(out: dict[str, object], model_key: str, raw_val: object) -> None:
    cleaned = _clean(raw_val)
    if cleaned is None:
        return
    if model_key in _DATE_BIB_FIELDS:
        parsed = _parse_date(cleaned)
        if parsed is not None:
            out[model_key] = parsed
    else:
        out[model_key] = cleaned


def _parse_fields(raw: dict[str, object]) -> dict[str, object]:
    """Map a ``bibtexparser`` entry to a BibEntry kwarg dict.

    Collision rule (ADR-0019): if a raw entry contains *both* a BibTeX alias
    (e.g. ``journal``) and its BibLaTeX target (e.g. ``journaltitle``), the
    BibLaTeX-native value wins and a ``UserWarning`` is emitted — matching the
    semantics of :func:`workflow.bibliography.dialect.to_biblatex`.

    Raw ``date`` field (ADR-0019 P2.2): when present the verbatim literal is
    stored in ``BibEntry.date``; ``year`` and ``month`` are derived from the
    *first* EDTF component (before any ``/``) if not already set by a
    dedicated ``year``/``month`` field in the entry.
    """
    out: dict[str, object] = {}
    # Set of model_keys that are also BibLaTeX-native raw field names (the 5 alias targets).
    _alias_model_keys: frozenset[str] = frozenset(_dialect.BIBTEX_TO_BIBLATEX.values())
    for model_key, bib_key in TRANSLATED_BIB_KEYS.items():
        if bib_key not in raw:
            continue
        # For the 5 bibtex-alias entries, model_key IS the biblatex-native field name.
        # If the raw entry also has model_key as a direct key, the native value wins.
        if model_key in _alias_model_keys and model_key in raw:
            # Both bibtex alias and biblatex-native present — prefer native, warn.
            warnings.warn(
                f"BibTeX field {bib_key!r} conflicts with already-present biblatex "
                f"field {model_key!r}; keeping existing biblatex value.",
                UserWarning,
                stacklevel=4,
            )
            _assign_translated(out, model_key, raw[model_key])
        else:
            _assign_translated(out, model_key, raw[bib_key])
    for key, val in raw.items():
        if key in _IGNORED_BIB_KEYS:
            continue
        _assign_direct(out, key, val)

    # Handle raw ``date`` → verbatim + derived year/month (ADR-0019 P2.2).
    _apply_raw_date(raw, out)

    return out


def _apply_raw_date(raw: dict[str, object], out: dict[str, object]) -> None:
    """Store verbatim biblatex ``date`` and derive year/month from it.

    Only fills ``year``/``month`` in *out* when they are not already present
    (explicit ``year=`` / ``month=`` fields take priority).
    """
    raw_date_val = raw.get(_RAW_DATE_BIB_FIELD)
    if raw_date_val is None:
        return
    cleaned_date = _clean(raw_date_val)
    if not cleaned_date:
        return
    out["date"] = cleaned_date
    first_component = cleaned_date.split("/")[0].strip()
    parts = first_component.split("-")
    if "year" not in out:
        try:
            out["year"] = int(parts[0])
        except (ValueError, IndexError):
            pass
    if "month" not in out and len(parts) > 1:
        out["month"] = parts[1]


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


def _upsert_author(
    session: Session,
    first_name: str,
    last_name: str,
    name_prefix: str | None = None,
    name_suffix: str | None = None,
) -> Author:
    existing = session.scalars(
        select(Author).where(
            Author.first_name == first_name, Author.last_name == last_name
        )
    ).first()
    if existing:
        return existing
    a = Author(
        first_name=first_name,
        last_name=last_name,
        name_prefix=name_prefix,
        name_suffix=name_suffix,
    )
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
    for idx, (first, last, prefix, suffix) in enumerate(_split_authors(author_string)):
        author = _upsert_author(session, first, last, prefix, suffix)
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


def _is_safe_url(url: str) -> bool:
    try:
        scheme = urlparse(url).scheme.lower()
    except ValueError:
        return False
    return scheme in _ALLOWED_URL_SCHEMES


def _process_url(
    session: Session,
    bib_entry: BibEntry,
    url_string: str,
    database_name: str | None,
) -> None:
    if not _is_safe_url(url_string):
        return
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


def _process_entry(
    session: Session, raw: dict[str, object], database_name: str | None
) -> EntryStatus:
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
        val = raw.get(afield)
        if isinstance(val, str) and val:
            _process_authors(session, entry, val, afield)

    url_raw = raw.get("url")
    url = _clean(url_raw) if url_raw is not None else None
    if url:
        _process_url(session, entry, url, database_name)

    return "created"


def _infer_database_name(path: Path) -> str | None:
    stem = path.stem
    if "-" in stem:
        return stem.split("-", 1)[0]
    return None


def import_bib_text(
    session: Session,
    text: str,
    *,
    database_name: str | None = None,
) -> ImportResult:
    """Parse biblatex *text* and insert rows into the session.

    Commits the session on completion. Raises ``ValueError`` if the
    encoded text exceeds ``MAX_BIB_SIZE_BYTES``. Per-entry errors are
    isolated by savepoint and collected into the result rather than raised.
    """
    size = len(text.encode("utf-8"))
    if size > MAX_BIB_SIZE_BYTES:
        raise ValueError(
            f"bib text too large ({size} bytes > {MAX_BIB_SIZE_BYTES} cap)"
        )

    # Accept biblatex-only entry types (@online, @report, @thesis, …).
    # bibtexparser's default parser silently drops "non-standard" types.
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parsed = bibtexparser.loads(text, parser=parser)

    created = 0
    skipped = 0
    errors: list[str] = []
    statuses: list[tuple[str, str]] = []

    for raw in parsed.entries:
        bibkey = raw.get("ID", "<no-id>")
        entry_savepoint = session.begin_nested()
        try:
            status = _process_entry(session, raw, database_name)
            entry_savepoint.commit()
            if status == "created":
                created += 1
            else:
                skipped += 1
            statuses.append((bibkey, status))
        except Exception as exc:  # noqa: BLE001 — per-entry isolation
            entry_savepoint.rollback()
            label = type(exc).__name__
            errors.append(f"{bibkey}: {label}")
            statuses.append((bibkey, f"error: {label}"))

    session.commit()
    return ImportResult(
        created=created,
        skipped=skipped,
        errors=tuple(errors),
        statuses=tuple(statuses),
    )


def import_bib_file(
    session: Session,
    path: str | Path,
    database_name: str | None = None,
) -> ImportResult:
    """Parse a .bib file and insert rows into the session.

    Commits the session on completion. Raises ``FileNotFoundError`` if
    path does not exist and ``ValueError`` if the file exceeds
    ``MAX_BIB_SIZE_BYTES``. Delegates to ``import_bib_text`` after reading
    the file. Per-entry errors are isolated by savepoint and collected into
    the result rather than raised.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"bib file not found: {path}")

    size = p.stat().st_size
    if size > MAX_BIB_SIZE_BYTES:
        raise ValueError(
            f"bib file too large ({size} bytes > {MAX_BIB_SIZE_BYTES} cap)"
        )

    text = p.read_text(encoding="utf-8")

    if database_name is None:
        database_name = _infer_database_name(p)

    return import_bib_text(session, text, database_name=database_name)
