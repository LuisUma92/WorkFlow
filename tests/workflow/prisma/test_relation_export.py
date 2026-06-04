"""Round-trip export of biblatex relation fields (Wave A — A4-4).

After A4, crossref/xref/xdata/related live in the bib_relation table, not the
overflow. Default export (no --resolve-xref) must re-emit them verbatim so the
import→export round-trip stays lossless.
"""

from __future__ import annotations

import textwrap

import pytest
from click.testing import CliRunner
from sqlalchemy.orm import Session

from workflow.prisma.cli import prisma
from workflow.prisma.exporter import export_bib_entries
from workflow.prisma.importer import import_bib_text


def test_crossref_round_trips_biblatex(global_session):
    bib = textwrap.dedent("""\
        @book{rtparent, title = {RT Parent}, year = {2020}, volume = {1}}
        @inbook{rtchild, title = {RT Child}, year = {2021}, volume = {2},
                crossref = {rtparent}}
    """)
    import_bib_text(global_session, bib)
    out = export_bib_entries(global_session, dialect="biblatex")
    assert "crossref = {rtparent}," in out


def test_xdata_related_round_trip_biblatex(global_session):
    bib = textwrap.dedent("""\
        @article{multichild, title = {Multi Child}, year = {2022}, volume = {3},
                 xdata = {xa, xb}, related = {rp, rq}}
    """)
    import_bib_text(global_session, bib)
    out = export_bib_entries(global_session, dialect="biblatex")
    assert "xdata = {xa, xb}," in out
    assert "related = {rp, rq}," in out


def test_crossref_emitted_in_bibtex(global_session):
    bib = textwrap.dedent("""\
        @inbook{btchild, title = {BT Child}, year = {2023}, volume = {4},
                crossref = {btparent}}
    """)
    import_bib_text(global_session, bib)
    out = export_bib_entries(global_session, dialect="bibtex")
    assert "crossref = {btparent}," in out


def test_unresolved_relation_still_exported(global_session):
    """parent_id NULL (target missing) but parent_bibkey must still round-trip."""
    bib = textwrap.dedent("""\
        @inbook{uchild, title = {U Child}, year = {2024}, volume = {5},
                crossref = {ghostref}}
    """)
    import_bib_text(global_session, bib)
    out = export_bib_entries(global_session, dialect="biblatex")
    assert "crossref = {ghostref}," in out


# ---------------------------------------------------------------------------
# --resolve-xref inheritance (A4-5)
# ---------------------------------------------------------------------------


def test_resolve_crossref_inlines_booktitle_and_suppresses_pointer(global_session):
    bib = textwrap.dedent("""\
        @book{rxparent, title = {Parent Book}, year = {2030}, volume = {1},
              publisher = {ACME Press}}
        @inbook{rxchild, title = {Chapter One}, year = {2031}, volume = {2},
                crossref = {rxparent}}
    """)
    import_bib_text(global_session, bib)
    out = export_bib_entries(global_session, dialect="biblatex", resolve_xref=True)
    child_block = [b for b in out.split("\n\n") if "rxchild" in b][0]
    # parent title inherited as booktitle; parent publisher inherited same-name
    assert "booktitle = {Parent Book}," in child_block
    assert "publisher = {ACME Press}," in child_block
    # resolved pointer suppressed
    assert "crossref" not in child_block


def test_resolve_child_wins_over_parent(global_session):
    bib = textwrap.dedent("""\
        @book{cwparent, title = {Parent Title}, year = {2032}, volume = {1},
              publisher = {Parent Pub}}
        @inbook{cwchild, title = {Child Title}, year = {2033}, volume = {2},
                booktitle = {Child Booktitle}, crossref = {cwparent}}
    """)
    import_bib_text(global_session, bib)
    out = export_bib_entries(global_session, dialect="biblatex", resolve_xref=True)
    child_block = [b for b in out.split("\n\n") if "cwchild" in b][0]
    # child's own booktitle wins; parent's title does NOT overwrite it
    assert "booktitle = {Child Booktitle}," in child_block
    assert "Parent Title" not in child_block


def test_resolve_xdata_copies_field_verbatim(global_session):
    bib = textwrap.dedent("""\
        @misc{xdsrc, title = {XData Source}, year = {2034}, volume = {1},
              note = {shared note}}
        @article{xdtarget, title = {XData Target}, year = {2035}, volume = {2},
                 xdata = {xdsrc}}
    """)
    import_bib_text(global_session, bib)
    out = export_bib_entries(global_session, dialect="biblatex", resolve_xref=True)
    child_block = [b for b in out.split("\n\n") if "xdtarget" in b][0]
    # biblatex canonical column for note is ``notes`` (bibtex-aliased to note)
    assert "notes = {shared note}," in child_block
    assert "xdata" not in child_block


def test_resolve_keeps_xref_pointer(global_session):
    """xref does not trigger inheritance; the pointer field is preserved."""
    bib = textwrap.dedent("""\
        @book{xrparent, title = {XRef Parent}, year = {2036}, volume = {1}}
        @inbook{xrchild, title = {XRef Child}, year = {2037}, volume = {2},
                xref = {xrparent}}
    """)
    import_bib_text(global_session, bib)
    out = export_bib_entries(global_session, dialect="biblatex", resolve_xref=True)
    child_block = [b for b in out.split("\n\n") if "xrchild" in b][0]
    assert "xref = {xrparent}," in child_block


# ---------------------------------------------------------------------------
# CLI --resolve-xref flag (A4-6)
# ---------------------------------------------------------------------------


class TestResolveXrefCli:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def _seed(self, engine):
        bib = textwrap.dedent("""\
            @book{cliparent, title = {CLI Parent}, year = {2040}, volume = {1}}
            @inbook{clichild, title = {CLI Child}, year = {2041}, volume = {2},
                    crossref = {cliparent}}
        """)
        with Session(engine) as session:
            import_bib_text(session, bib)

    def test_export_without_flag_keeps_crossref(self, runner, global_engine):
        self._seed(global_engine)
        r = runner.invoke(
            prisma, ["bib", "export"],
            obj={"engine": global_engine}, catch_exceptions=False,
        )
        assert r.exit_code == 0
        assert "crossref = {cliparent}," in r.output

    def test_export_with_resolve_xref_inlines_and_suppresses(self, runner, global_engine):
        self._seed(global_engine)
        r = runner.invoke(
            prisma, ["bib", "export", "--resolve-xref"],
            obj={"engine": global_engine}, catch_exceptions=False,
        )
        assert r.exit_code == 0
        child_block = [b for b in r.output.split("\n\n") if "clichild" in b][0]
        assert "booktitle = {CLI Parent}," in child_block
        assert "crossref" not in child_block
