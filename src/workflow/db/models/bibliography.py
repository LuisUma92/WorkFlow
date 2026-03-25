"""
Unified bibliography models — stored in the global workflow.db.

Ported from PRISMAreview's Django Bib_entries and related models,
rewritten as SQLAlchemy 2.0 mapped classes on GlobalBase.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from workflow.db.base import GlobalBase


# ── Enum / lookup tables ───────────────────────────────────────────────────


class IsnType(GlobalBase):
    """ISN type lookup (isbn, issn, isan, ismn, isrn, iswc)."""

    __tablename__ = "isn_type"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(6), unique=True)

    bib_entries: Mapped[list["BibEntry"]] = relationship(back_populates="isn_type")

    def __repr__(self) -> str:
        return f"<IsnType {self.code}>"


class AuthorType(GlobalBase):
    """Author role lookup (author, editor, translator, …)."""

    __tablename__ = "author_type"

    id: Mapped[int] = mapped_column(primary_key=True)
    type_of_author: Mapped[str] = mapped_column(String(20), unique=True)

    bib_author_links: Mapped[list["BibAuthor"]] = relationship(
        back_populates="author_type"
    )

    def __repr__(self) -> str:
        return f"<AuthorType {self.type_of_author}>"


class ReferencedDatabase(GlobalBase):
    """External database / repository source (e.g. PubMed, Scopus)."""

    __tablename__ = "referenced_database"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(200), default=None)
    proxy: Mapped[str | None] = mapped_column(String(400), default=None)
    aliases: Mapped[str | None] = mapped_column(String(5000), default=None)

    urls: Mapped[list["BibUrl"]] = relationship(back_populates="database")

    def __repr__(self) -> str:
        return f"<ReferencedDatabase {self.name}>"


# ── Core entities ──────────────────────────────────────────────────────────


class Author(GlobalBase):
    """Unified author record, unique on (first_name, last_name)."""

    __tablename__ = "author"
    __table_args__ = (
        UniqueConstraint("first_name", "last_name", name="uq_author_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(200))
    alias: Mapped[str | None] = mapped_column(String(80), default=None)
    affiliation: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    bib_links: Mapped[list["BibAuthor"]] = relationship(back_populates="author")

    def __repr__(self) -> str:
        return f"<Author {self.last_name}, {self.first_name}>"


class BibEntry(GlobalBase):
    """
    Full BibLaTeX entry — all standard fields plus workflow-specific metadata.
    Unique on (title, year, volume).
    """

    __tablename__ = "bib_entry"
    __table_args__ = (UniqueConstraint("title", "year", "volume", name="uq_bib_entry"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    # ── BibLaTeX type & key ──
    entry_type: Mapped[str | None] = mapped_column(String(100), default=None)
    bibkey: Mapped[str | None] = mapped_column(String(200), default=None)

    # ── Institutions / publishers ──
    institution: Mapped[str | None] = mapped_column(String(200), default=None)
    organization: Mapped[str | None] = mapped_column(String(200), default=None)
    publisher: Mapped[str | None] = mapped_column(String(200), default=None)

    # ── Titles ──
    title: Mapped[str | None] = mapped_column(String(500), default=None)
    indextitle: Mapped[str | None] = mapped_column(String(500), default=None)
    booktitle: Mapped[str | None] = mapped_column(String(500), default=None)
    maintitle: Mapped[str | None] = mapped_column(String(500), default=None)
    journaltitle: Mapped[str | None] = mapped_column(String(200), default=None)
    issuetitle: Mapped[str | None] = mapped_column(String(500), default=None)
    eventtitle: Mapped[str | None] = mapped_column(String(500), default=None)
    reprinttitle: Mapped[str | None] = mapped_column(String(500), default=None)

    # ── Series / volume / issue ──
    series: Mapped[str | None] = mapped_column(String(200), default=None)
    volume: Mapped[str | None] = mapped_column(String(20), default=None)
    number: Mapped[str | None] = mapped_column(String(20), default=None)
    part: Mapped[str | None] = mapped_column(String(20), default=None)
    issue: Mapped[str | None] = mapped_column(String(20), default=None)
    volumes: Mapped[str | None] = mapped_column(String(20), default=None)

    # ── Edition / version / state ──
    edition: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    version: Mapped[str | None] = mapped_column(String(50), default=None)
    pubstate: Mapped[str | None] = mapped_column(String(100), default=None)

    # ── Pages ──
    pages: Mapped[str | None] = mapped_column(String(20), default=None)
    pagetotal: Mapped[str | None] = mapped_column(String(20), default=None)
    pagination: Mapped[str | None] = mapped_column(String(200), default=None)

    # ── Dates ──
    publication_date: Mapped[date | None] = mapped_column(Date, default=None)
    month: Mapped[str | None] = mapped_column(String(10), default=None)
    year: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    eventdate: Mapped[date | None] = mapped_column(Date, default=None)
    urldate: Mapped[date | None] = mapped_column(Date, default=None)

    # ── Location / venue ──
    location: Mapped[str | None] = mapped_column(String(100), default=None)
    venue: Mapped[str | None] = mapped_column(String(200), default=None)

    # ── Electronic identifiers ──
    doi: Mapped[str | None] = mapped_column(Text, default=None)
    eid: Mapped[str | None] = mapped_column(Text, default=None)
    eprint: Mapped[str | None] = mapped_column(Text, default=None)
    eprinttype: Mapped[str | None] = mapped_column(Text, default=None)

    # ── Notes / misc ──
    addendum: Mapped[str | None] = mapped_column(Text, default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    howpublished: Mapped[str | None] = mapped_column(Text, default=None)
    language: Mapped[str | None] = mapped_column(String(200), default=None)

    # ── ISN ──
    isn: Mapped[str | None] = mapped_column(String(200), default=None)
    isn_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("isn_type.id"), default=None
    )

    # ── Content / file ──
    abstract_text: Mapped[str | None] = mapped_column(Text, default=None)
    annotation: Mapped[str | None] = mapped_column(Text, default=None)
    file_path: Mapped[str | None] = mapped_column(Text, default=None)
    library: Mapped[str | None] = mapped_column(String(500), default=None)

    # ── BibLaTeX control fields ──
    label: Mapped[str | None] = mapped_column(String(500), default=None)
    shorthand: Mapped[str | None] = mapped_column(String(500), default=None)
    shorthandintro: Mapped[str | None] = mapped_column(Text, default=None)
    execute_task: Mapped[str | None] = mapped_column(Text, default=None)
    keywords: Mapped[str | None] = mapped_column(Text, default=None)
    options: Mapped[str | None] = mapped_column(Text, default=None)
    ids: Mapped[str | None] = mapped_column(String(500), default=None)

    # ── Timestamps ──
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    # ── Relationships ──
    isn_type: Mapped["IsnType | None"] = relationship(back_populates="bib_entries")
    author_links: Mapped[list["BibAuthor"]] = relationship(back_populates="bib_entry")
    urls: Mapped[list["BibUrl"]] = relationship(back_populates="bib_entry")
    tag_links: Mapped[list["BibEntryTag"]] = relationship(back_populates="bib_entry")
    content_links: Mapped[list["BibContent"]] = relationship(  # pyright: ignore[reportUndefinedVariable]
        back_populates="bib_entry"
    )
    general_project_links: Mapped[list["GeneralProjectBib"]] = relationship(  # pyright: ignore[reportUndefinedVariable]
        back_populates="bib_entry"
    )

    def __repr__(self) -> str:
        title_short = (self.title or "")[:60]
        return f"<BibEntry ({self.year}) {title_short}>"


# ── Association / junction tables ──────────────────────────────────────────


class BibAuthor(GlobalBase):
    """Links Author to BibEntry with a role and first-author flag."""

    __tablename__ = "bib_author"
    __table_args__ = (
        UniqueConstraint(
            "author_id",
            "bib_entry_id",
            "author_type_id",
            name="uq_bib_author_role",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bib_entry_id: Mapped[int] = mapped_column(ForeignKey("bib_entry.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("author.id"))
    author_type_id: Mapped[int] = mapped_column(ForeignKey("author_type.id"))
    first_author: Mapped[bool] = mapped_column(Boolean, default=False)

    bib_entry: Mapped["BibEntry"] = relationship(back_populates="author_links")
    author: Mapped["Author"] = relationship(back_populates="bib_links")
    author_type: Mapped["AuthorType"] = relationship(back_populates="bib_author_links")


class BibUrl(GlobalBase):
    """One URL per (BibEntry, ReferencedDatabase) pair."""

    __tablename__ = "bib_url"
    __table_args__ = (
        UniqueConstraint("bib_entry_id", "database_id", name="uq_bib_url_per_database"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bib_entry_id: Mapped[int] = mapped_column(ForeignKey("bib_entry.id"))
    database_id: Mapped[int] = mapped_column(ForeignKey("referenced_database.id"))
    url_string: Mapped[str] = mapped_column(String(500))
    main_url: Mapped[bool] = mapped_column(Boolean, default=False)

    bib_entry: Mapped["BibEntry"] = relationship(back_populates="urls")
    database: Mapped["ReferencedDatabase"] = relationship(back_populates="urls")

    def __repr__(self) -> str:
        return f"<BibUrl {self.url_string[:60]}>"


# ── Keyword / tag tables ───────────────────────────────────────────────────


class BibKeyword(GlobalBase):
    """Keyword list used for systematic review searches."""

    __tablename__ = "bib_keyword"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_list: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    def __repr__(self) -> str:
        return f"<BibKeyword {self.keyword_list[:50]}>"


class BibTag(GlobalBase):
    """Free-form tag that can be applied to bibliography entries."""

    __tablename__ = "bib_tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    tag: Mapped[str] = mapped_column(String(200), unique=True)

    entry_links: Mapped[list["BibEntryTag"]] = relationship(back_populates="bib_tag")

    def __repr__(self) -> str:
        return f"<BibTag {self.tag}>"


class BibEntryTag(GlobalBase):
    """Many-to-many between BibEntry and BibTag."""

    __tablename__ = "bib_entry_tag"
    __table_args__ = (
        UniqueConstraint("bib_entry_id", "bib_tag_id", name="uq_entry_tag"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bib_entry_id: Mapped[int] = mapped_column(ForeignKey("bib_entry.id"))
    bib_tag_id: Mapped[int] = mapped_column(ForeignKey("bib_tag.id"))

    bib_entry: Mapped["BibEntry"] = relationship(back_populates="tag_links")
    bib_tag: Mapped["BibTag"] = relationship(back_populates="entry_links")
