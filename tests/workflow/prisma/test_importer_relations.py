"""Importer tests for biblatex relation fields → BibRelation (Wave A — A4).

crossref/xref/xdata/related are routed to the bib_relation table instead of
the bib_extra_field overflow. xdata/related are comma-separated lists (one row
per target). Parent resolution is a second pass so forward references resolve;
unresolved targets keep parent_bibkey with parent_id NULL (lossless).
"""

from __future__ import annotations

import textwrap

from workflow.db.models.bibliography import BibEntry, BibExtraField, BibRelation
from workflow.prisma.importer import import_bib_text


def _relations(session, child_bibkey: str) -> list[BibRelation]:
    child = session.query(BibEntry).filter_by(bibkey=child_bibkey).one()
    return list(child.relations)


def test_crossref_resolves_to_existing_parent(global_session):
    bib = textwrap.dedent("""\
        @book{bookparent, title = {Parent Book}, year = {2001}, volume = {1}}
        @inbook{chapchild, title = {Child Chapter}, year = {2002}, volume = {2},
                crossref = {bookparent}}
    """)
    import_bib_text(global_session, bib)
    rels = _relations(global_session, "chapchild")
    assert len(rels) == 1
    assert rels[0].kind == "crossref"
    assert rels[0].parent_bibkey == "bookparent"
    parent = global_session.query(BibEntry).filter_by(bibkey="bookparent").one()
    assert rels[0].parent_id == parent.id


def test_forward_reference_resolves(global_session):
    """Child appears before parent in the file; pass 2 still resolves it."""
    bib = textwrap.dedent("""\
        @inbook{fwchild, title = {Fwd Child}, year = {2003}, volume = {3},
                crossref = {fwparent}}
        @book{fwparent, title = {Fwd Parent}, year = {2004}, volume = {4}}
    """)
    import_bib_text(global_session, bib)
    rels = _relations(global_session, "fwchild")
    parent = global_session.query(BibEntry).filter_by(bibkey="fwparent").one()
    assert rels[0].parent_id == parent.id


def test_unresolved_parent_kept_lossless(global_session):
    bib = textwrap.dedent("""\
        @inbook{orphanchild, title = {Orphan}, year = {2005}, volume = {5},
                crossref = {missingparent}}
    """)
    import_bib_text(global_session, bib)
    rels = _relations(global_session, "orphanchild")
    assert len(rels) == 1
    assert rels[0].parent_bibkey == "missingparent"
    assert rels[0].parent_id is None


def test_xdata_multiple_targets_split(global_session):
    bib = textwrap.dedent("""\
        @misc{xd1, title = {XData One}, year = {2006}, volume = {6}}
        @misc{xd2, title = {XData Two}, year = {2007}, volume = {7}}
        @article{xdchild, title = {XData Child}, year = {2008}, volume = {8},
                 xdata = {xd1, xd2}}
    """)
    import_bib_text(global_session, bib)
    rels = sorted(_relations(global_session, "xdchild"), key=lambda r: r.parent_bibkey)
    assert [r.parent_bibkey for r in rels] == ["xd1", "xd2"]
    assert all(r.kind == "xdata" for r in rels)
    assert all(r.parent_id is not None for r in rels)


def test_related_multiple_targets_split(global_session):
    bib = textwrap.dedent("""\
        @article{relchild, title = {Related Child}, year = {2009}, volume = {9},
                 related = {ra, rb, rc}}
    """)
    import_bib_text(global_session, bib)
    rels = _relations(global_session, "relchild")
    assert {r.parent_bibkey for r in rels} == {"ra", "rb", "rc"}
    assert all(r.kind == "related" for r in rels)


def test_relation_fields_not_in_overflow(global_session):
    bib = textwrap.dedent("""\
        @inbook{nooverflow, title = {No Overflow}, year = {2010}, volume = {10},
                crossref = {someparent}, xref = {otherparent}}
    """)
    import_bib_text(global_session, bib)
    child = global_session.query(BibEntry).filter_by(bibkey="nooverflow").one()
    overflow_fields = {
        ef.field for ef in global_session.query(BibExtraField).filter_by(
            bib_entry_id=child.id
        )
    }
    assert "crossref" not in overflow_fields
    assert "xref" not in overflow_fields


def test_reimport_idempotent_no_duplicate_relations(global_session):
    bib = textwrap.dedent("""\
        @book{idemparent, title = {Idem Parent}, year = {2011}, volume = {11}}
        @inbook{idemchild, title = {Idem Child}, year = {2012}, volume = {12},
                crossref = {idemparent}}
    """)
    import_bib_text(global_session, bib)
    import_bib_text(global_session, bib)  # second import: entries skipped
    rels = _relations(global_session, "idemchild")
    assert len(rels) == 1
