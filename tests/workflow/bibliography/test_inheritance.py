"""Unit tests for biblatex crossref/xdata inheritance (Wave A — A4-5)."""

from __future__ import annotations

from workflow.bibliography.inheritance import (
    GLOBAL_NOINHERIT,
    inherit_crossref,
    inherit_xdata,
)


# ---------------------------------------------------------------------------
# crossref field remapping
# ---------------------------------------------------------------------------


def test_book_to_inbook_title_becomes_booktitle():
    parent = {"title": "The Book", "subtitle": "A Sub", "titleaddon": "addon"}
    inherited = inherit_crossref("book", "inbook", parent)
    assert inherited["booktitle"] == "The Book"
    assert inherited["booksubtitle"] == "A Sub"
    assert inherited["booktitleaddon"] == "addon"
    assert "title" not in inherited


def test_mvbook_to_book_title_becomes_maintitle():
    inherited = inherit_crossref("mvbook", "book", {"title": "Multi Vol"})
    assert inherited["maintitle"] == "Multi Vol"
    assert "title" not in inherited
    assert "booktitle" not in inherited


def test_mvbook_to_inbook_maintitle_wins_over_booktitle():
    """More specific mvbook rule (later) overrides the book→inbook rule."""
    inherited = inherit_crossref("mvbook", "inbook", {"title": "MV"})
    assert inherited["maintitle"] == "MV"
    assert "booktitle" not in inherited


def test_periodical_to_article_title_becomes_journaltitle():
    inherited = inherit_crossref("periodical", "article", {"title": "J. Phys."})
    assert inherited["journaltitle"] == "J. Phys."


def test_collection_to_incollection_title_becomes_booktitle():
    inherited = inherit_crossref("collection", "incollection", {"title": "Coll"})
    assert inherited["booktitle"] == "Coll"


# ---------------------------------------------------------------------------
# global same-name inheritance + noinherit + drop
# ---------------------------------------------------------------------------


def test_unmapped_field_inherited_same_name():
    inherited = inherit_crossref("book", "inbook", {"publisher": "ACME"})
    assert inherited["publisher"] == "ACME"


def test_noinherit_fields_excluded():
    parent = {"title": "T", "crossref": "x", "label": "L", "options": "o"}
    inherited = inherit_crossref("book", "inbook", parent)
    assert "crossref" not in inherited
    assert "label" not in inherited
    assert "options" not in inherited


def test_dropped_fields_not_inherited():
    parent = {"title": "T", "shorttitle": "ST", "sorttitle": "SO"}
    inherited = inherit_crossref("book", "inbook", parent)
    assert "shorttitle" not in inherited
    assert "sorttitle" not in inherited
    # but title is still remapped
    assert inherited["booktitle"] == "T"


def test_global_noinherit_contains_pointer_fields():
    for f in ("crossref", "xref", "xdata", "related", "ids"):
        assert f in GLOBAL_NOINHERIT


# ---------------------------------------------------------------------------
# xdata plain copy
# ---------------------------------------------------------------------------


def test_xdata_copies_fields_verbatim():
    parent = {"author": "Doe", "publisher": "ACME", "note": "shared"}
    inherited = inherit_xdata(parent)
    assert inherited == parent


def test_xdata_excludes_noinherit():
    parent = {"author": "Doe", "crossref": "p", "label": "L"}
    inherited = inherit_xdata(parent)
    assert inherited == {"author": "Doe"}
