"""BibTeX → DB import for PRISMA systematic review (P2).

Parses .bib files with ``bibtexparser`` and inserts BibEntry / Author /
BibAuthor / BibUrl / ReferencedDatabase rows into ``workflow.db``.
Uses per-item savepoint rollback on IntegrityError for dedup.
"""

from __future__ import annotations

import itertools
import re
import warnings
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterator, Literal
from urllib.parse import urlparse

import bibtexparser
from bibtexparser.bparser import BibTexParser
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from workflow.bibliography import dialect as _dialect
from workflow.bibliography.bibkey import calculate_bibkey
from workflow.db.models.bibliography import (
    Author,
    AuthorType,
    BibAuthor,
    BibEntry,
    BibExtraField,
    BibUrl,
    ReferencedDatabase,
)

__all__ = [
    "ImportResult",
    "import_bib_file",
    "import_bib_text",
    "MAX_BIB_SIZE_BYTES",
    "MAX_EXTRA_VALUE_LEN",
    "MAX_EXTRA_FIELDS",
    "generate_bibkey_for_entry",
    "disambiguate_bibkey",
    "_BIBLATEX_FIELD_CATALOG",
]


MAX_BIB_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB hard cap on input

# Security caps for the EAV overflow table (ADR-0019 A1 / security finding #3).
MAX_EXTRA_VALUE_LEN: int = 10_000  # characters; values exceeding this are skipped
MAX_EXTRA_FIELDS: int = 100       # rows per bib_entry; entries beyond cap are dropped

_ALLOWED_URL_SCHEMES: frozenset[str] = frozenset({"http", "https", "ftp"})

# ---------------------------------------------------------------------------
# BibLaTeX field catalog — whitelist for the EAV overflow table (ADR-0019 A1).
# Source: tasks/plans/biblatex-fields-catalog.md (293 fields + 9 aliases).
# Only catalog-known fields may be stored; all others are silently dropped.
# ---------------------------------------------------------------------------

_BIBLATEX_FIELD_CATALOG: frozenset[str] = frozenset({
    # Name fields (24)
    "author", "editor", "translator", "editora", "editorb", "editorc",
    "annotator", "commentator", "conductor", "bookauthor", "authortype",
    "editortype", "editoratype", "editorbtype", "editorctype", "namea",
    "nameaddon", "moreauthor", "moreeditor", "moretranslator", "morelabelname",
    "savedauthor", "useauthor", "useeditor",
    # Title fields (25)
    "title", "subtitle", "titleaddon", "maintitle", "mainsubtitle",
    "maintitleaddon", "booktitle", "booksubtitle", "booktitleaddon",
    "journaltitle", "journalsubtitle", "journaltitleaddon", "issuetitle",
    "issuesubtitle", "issuetitleaddon", "eventtitle", "eventtitleaddon",
    "origtitle", "reprinttitle", "shorttitle", "indextitle", "indexsorttitle",
    "extratitle", "labeltitle", "extratitleyear",
    # Date/time fields (44)
    "date", "year", "month", "day", "season", "yeardivision",
    "endyear", "endmonth", "endday", "endseason", "endyeardivision",
    "eventdate", "eventyear", "eventmonth", "eventday", "eventseason",
    "eventyeardivision", "eventendyear", "eventendmonth", "eventendday",
    "eventendseason", "eventendyeardivision",
    "origdate", "origyear", "origmonth", "origday", "origseason",
    "origyeardivision", "origendyear", "origendmonth", "origendday",
    "origendseason", "origendyeardivision",
    "urldate", "urlyear", "urlmonth", "urlday", "urlseason", "urlyeardivision",
    "urlendyear", "urlendmonth", "urlendday", "urlendseason", "urlendyeardivision",
    "datepart", "dateunspecified",
    # Publication fields (10)
    "publisher", "location", "address", "institution", "organization",
    "school", "origlocation", "origpublisher", "venue", "place",
    # Identifier fields (19)
    "doi", "url", "urlraw", "isbn", "issn", "isrn", "eid", "eprint",
    "eprinttype", "eprintclass", "archiveprefix", "primaryclass",
    "pubmedid", "pubmed", "file", "pdf", "library", "gps", "articleid",
    # Pagination & structure fields (11)
    "pages", "pagetotal", "pagination", "bookpagination", "volume",
    "volumes", "number", "chapter", "part", "edition", "issue",
    # Series & cross-reference fields (10)
    "series", "shortseries", "crossref", "xref", "xdata", "related",
    "relatedtype", "relatedstring", "relatedoptions", "entrysetcount",
    # Miscellaneous fields (23)
    "note", "addendum", "pubstate", "language", "langid", "langidopts",
    "hyphenation", "keywords", "annotation", "annote", "abstract", "type",
    "subtype", "entrysubtype", "howpublished", "version", "foreword",
    "afterword", "introduction", "commentary", "comment", "key", "origlanguage",
    # Special/processing fields
    "useprefix", "gender", "sortname", "sortkey", "sortinit", "sortinithash",
    "label", "labelalpha", "labelnumber", "singletitle", "uniquename",
    "uniquetitle", "uniquework", "shorthand", "shorthandintro", "execute",
    "ids", "options", "presort", "entryset", "execute_task",
})

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
        # Promoted first-class columns (ADR-0019 A3)
        "subtitle",
        "titleaddon",
        "booksubtitle",
        "booktitleaddon",
        "mainsubtitle",
        "maintitleaddon",
        "origdate",
        "origlocation",
        "origpublisher",
        "pubmedid",
        "urlraw",
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

# First-class column names on BibEntry (derived at import time from the ORM table).
# Any field in _BIBLATEX_FIELD_CATALOG that is NOT in this set is an overflow candidate.
_BIBENTRY_COLUMNS: frozenset[str] = frozenset(
    col.name for col in BibEntry.__table__.columns
)


# ---------------------------------------------------------------------------
# Bibkey generation helpers (ADR-0019, Phase 2)
# ---------------------------------------------------------------------------

def generate_bibkey_for_entry(fields: dict[str, object], author_string: str) -> str:
    """Compute a calculated bibkey from parsed entry fields and the raw author string.

    Extracts the first author's ``last_name`` and ``name_prefix`` (von-particle)
    from :func:`_split_authors`, then delegates to
    :func:`~workflow.bibliography.bibkey.calculate_bibkey` with year, volume,
    edition, and entry_type from *fields*.

    Parameters
    ----------
    fields:
        The output of :func:`_parse_fields` (model-key → value mapping).
    author_string:
        Raw BibTeX ``author`` field value (may be empty or absent).

    Returns
    -------
    str
        Calculated bibkey string (never empty).
    """
    # Extract first author's surname + prefix from the raw author string.
    surname: str | None = None
    name_prefix: str | None = None
    if author_string:
        authors = _split_authors(author_string)
        if authors:
            _first_name, last, prefix, _suffix = authors[0]
            surname = last or None
            name_prefix = prefix

    return calculate_bibkey(
        surname=surname,
        year=fields.get("year"),  # type: ignore[arg-type]
        volume=fields.get("volume"),
        edition=fields.get("edition"),  # type: ignore[arg-type]
        entry_type=fields.get("entry_type"),  # type: ignore[arg-type]
        name_prefix=name_prefix,
    )


def _suffix_sequence() -> Iterator[str]:
    """Yield an unbounded bijective base-26 suffix sequence: a, b, …, z, aa, ab, …"""
    for length in itertools.count(1):
        for combo in itertools.product("abcdefghijklmnopqrstuvwxyz", repeat=length):
            yield "".join(combo)


def disambiguate_bibkey(candidate: str, taken: set[str]) -> str:
    """Append ``a``, ``b``, … to *candidate* until it is not in *taken*.

    Only appends a suffix when *candidate* already appears in *taken*.
    Uses an unbounded bijective base-26 sequence: a, b, …, z, aa, ab, …
    so there is no cap on the number of colliding distinct works.
    """
    if candidate not in taken:
        return candidate
    for suffix in _suffix_sequence():
        suffixed = f"{candidate}{suffix}"
        if suffixed not in taken:
            return suffixed
    return candidate  # unreachable; satisfies type checker


# Backward-compatible private alias — kept so existing tests and internal
# callers that reference ``_disambiguate_bibkey`` continue to work.
_disambiguate_bibkey = disambiguate_bibkey


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


def _persist_extra_fields(
    session: Session,
    bib_entry: BibEntry,
    raw: dict[str, object],
) -> None:
    """Store catalog-known biblatex fields that lack a first-class BibEntry column.

    Security constraints (finding #3):
    - Only fields in ``_BIBLATEX_FIELD_CATALOG`` are stored (whitelist).
    - ``value`` length is capped at ``MAX_EXTRA_VALUE_LEN``; over-length values are skipped.
    - At most ``MAX_EXTRA_FIELDS`` rows are written per entry; extras are silently dropped.

    Fields that are already handled as first-class columns, or that are in
    ``_IGNORED_BIB_KEYS``, are excluded from overflow storage.
    """
    # Determine which raw fields are overflow candidates.
    # A field qualifies when ALL of:
    #   1. it is in the biblatex catalog (whitelist)
    #   2. it does NOT have a first-class BibEntry column
    #   3. it is not in the ignored set (internal bibtexparser keys, author fields, etc.)
    count = 0
    for raw_field, raw_val in raw.items():
        if count >= MAX_EXTRA_FIELDS:
            break
        if raw_field in _IGNORED_BIB_KEYS:
            continue
        if raw_field not in _BIBLATEX_FIELD_CATALOG:
            continue  # not catalog-known → drop (security: no arbitrary keys)
        if raw_field in _BIBENTRY_COLUMNS:
            continue  # already stored as a first-class column
        cleaned = _clean(raw_val)
        if not cleaned:
            continue
        if len(cleaned) > MAX_EXTRA_VALUE_LEN:
            continue  # over-length → skip (security: cap value size)
        savepoint = session.begin_nested()
        try:
            session.add(BibExtraField(
                bib_entry_id=bib_entry.id,
                field=raw_field,
                value=cleaned,
            ))
            session.flush()
            savepoint.commit()
            count += 1
        except IntegrityError:  # UNIQUE(bib_entry_id, field) violation; skip silently
            savepoint.rollback()


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


def _resolve_bibkey(
    raw: dict[str, object],
    fields_dict: dict[str, object],
    *,
    recompute_bibkeys: bool,
    taken_bibkeys: set[str] | None,
) -> str:
    """Pick the bibkey: source ID verbatim, else a disambiguated calculated key.

    A sentinel ID from `_inject_keyless_ids` (key-less `.bib` entry) counts as
    missing, so the calculated path fires. `--recompute-bibkeys` forces it.
    """
    source_id = _clean(raw.get("ID"))
    if source_id and source_id.startswith(_KEYLESS_PREFIX):
        source_id = None
    if source_id and not recompute_bibkeys:
        return source_id

    author_string = raw.get("author", "")
    if not isinstance(author_string, str):
        author_string = ""
    bibkey = generate_bibkey_for_entry(fields_dict, author_string)
    if taken_bibkeys is not None:
        bibkey = _disambiguate_bibkey(bibkey, taken_bibkeys)
    return bibkey


def _process_entry(
    session: Session,
    raw: dict[str, object],
    database_name: str | None,
    *,
    recompute_bibkeys: bool = False,
    taken_bibkeys: set[str] | None = None,
) -> EntryStatus:
    fields_dict = _parse_fields(raw)
    new_bibkey = _resolve_bibkey(
        raw,
        fields_dict,
        recompute_bibkeys=recompute_bibkeys,
        taken_bibkeys=taken_bibkeys,
    )
    fields_dict["bibkey"] = new_bibkey

    entry = BibEntry(**fields_dict)

    savepoint = session.begin_nested()
    try:
        session.add(entry)
        session.flush()
        savepoint.commit()
    except IntegrityError:
        savepoint.rollback()
        return "skipped"

    # Track this key so later entries in the same batch can avoid collisions.
    # Use the pre-captured value to avoid relying on ORM attribute state post-flush.
    if taken_bibkeys is not None:
        taken_bibkeys.add(new_bibkey)

    # Persist overflow fields (catalog-known, no first-class column).
    _persist_extra_fields(session, entry, raw)

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


def _load_existing_bibkeys(session: Session) -> set[str]:
    """Return the set of all non-null bibkeys already in the DB."""
    rows = session.scalars(
        select(BibEntry.bibkey).where(BibEntry.bibkey.is_not(None))
    ).all()
    return set(rows)


# Sentinel citation key injected for key-less `.bib` entries (e.g. `@book{,`).
# bibtexparser silently DROPS entries with an empty key, so we give each one a
# unique placeholder before parsing, then treat it as "missing" in
# `_process_entry` → the calculated bibkey path fires (request P2.2).
_KEYLESS_PREFIX = "__keyless_"
# Anchored to line-start (re.MULTILINE) so patterns inside field values like
# `@misc{,` in an abstract or note are NOT matched — only real entry openers are.
_KEYLESS_OPEN_RE = re.compile(r"^([ \t]*)(@\w+\s*\{)(\s*,)", re.MULTILINE)


def _inject_keyless_ids(text: str) -> str:
    """Give every key-less entry (`@type{,`) a unique sentinel citation key."""
    counter = [0]

    def _repl(match: "re.Match[str]") -> str:
        key = f"{_KEYLESS_PREFIX}{counter[0]}__"
        counter[0] += 1
        return f"{match.group(1)}{match.group(2)}{key}{match.group(3)}"

    return _KEYLESS_OPEN_RE.sub(_repl, text)


def import_bib_text(
    session: Session,
    text: str,
    *,
    database_name: str | None = None,
    recompute_bibkeys: bool = False,
) -> ImportResult:
    """Parse biblatex *text* and insert rows into the session.

    Commits the session on completion. Raises ``ValueError`` if the
    encoded text exceeds ``MAX_BIB_SIZE_BYTES``. Per-entry errors are
    isolated by savepoint and collected into the result rather than raised.

    Parameters
    ----------
    recompute_bibkeys:
        When ``True``, ignore the source ``.bib`` entry ID and always
        compute the canonical bibkey from author/year/volume/edition/type.
        When ``False`` (default), source ID is kept verbatim; the
        calculated key is only used when the source ID is missing/empty.
    """
    size = len(text.encode("utf-8"))
    if size > MAX_BIB_SIZE_BYTES:
        raise ValueError(
            f"bib text too large ({size} bytes > {MAX_BIB_SIZE_BYTES} cap)"
        )

    # Inject sentinel keys so key-less entries survive parsing (request P2.2).
    text = _inject_keyless_ids(text)

    # Accept biblatex-only entry types (@online, @report, @thesis, …).
    # bibtexparser's default parser silently drops "non-standard" types.
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parsed = bibtexparser.loads(text, parser=parser)

    # Gather existing bibkeys once for collision disambiguation.
    taken_bibkeys: set[str] = _load_existing_bibkeys(session)

    created = 0
    skipped = 0
    errors: list[str] = []
    statuses: list[tuple[str, str]] = []

    for raw in parsed.entries:
        bibkey = raw.get("ID", "<no-id>")
        if isinstance(bibkey, str) and bibkey.startswith(_KEYLESS_PREFIX):
            bibkey = "<no-id>"
        entry_savepoint = session.begin_nested()
        try:
            status = _process_entry(
                session,
                raw,
                database_name,
                recompute_bibkeys=recompute_bibkeys,
                taken_bibkeys=taken_bibkeys,
            )
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
    *,
    recompute_bibkeys: bool = False,
) -> ImportResult:
    """Parse a .bib file and insert rows into the session.

    Commits the session on completion. Raises ``FileNotFoundError`` if
    path does not exist and ``ValueError`` if the file exceeds
    ``MAX_BIB_SIZE_BYTES``. Delegates to ``import_bib_text`` after reading
    the file. Per-entry errors are isolated by savepoint and collected into
    the result rather than raised.

    Parameters
    ----------
    recompute_bibkeys:
        Forwarded to :func:`import_bib_text`.  When ``True``, source ``.bib``
        IDs are ignored and bibkeys are always calculated from entry metadata.
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

    return import_bib_text(
        session, text, database_name=database_name, recompute_bibkeys=recompute_bibkeys
    )
