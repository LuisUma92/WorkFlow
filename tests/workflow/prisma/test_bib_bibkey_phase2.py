"""Phase-2 calculated-bibkey tests (ADR-0019 P2.1–P2.4).

Coverage:
- P2.1  generate_bibkey_for_entry: first-author extraction, von-particle, anon fallback
- P2.2  Importer wiring: no-ID entry → calculated key; explicit-ID entry → kept verbatim
- P2.2  --recompute-bibkeys: explicit-ID entry → overridden with calculated key
- P2.2  Collision disambiguation: two distinct works with same base key → second gets 'a'
- P2.2  Dedup hit (same title/year/volume): single row, NOT disambiguated to a second row
- P2.3  recompute_bibkeys kwarg threads through import_bib_text / import_bib_file
- P2.4  CLI: prisma bib import --stdin --recompute-bibkeys end-to-end
"""

from __future__ import annotations

import json
import textwrap

import pytest
from click.testing import CliRunner
from sqlalchemy import select

from workflow.db.models.bibliography import BibEntry
from workflow.prisma.cli import prisma
from workflow.prisma.importer import (
    generate_bibkey_for_entry,
    import_bib_text,
)


# ---------------------------------------------------------------------------
# P2.1 — generate_bibkey_for_entry (unit, no DB)
# ---------------------------------------------------------------------------

class TestGenerateBibkeyForEntry:
    """Unit tests for generate_bibkey_for_entry."""

    def test_book_knuth_1997_vol3_ed3(self):
        fields = {"year": 1997, "volume": "3", "edition": 3, "entry_type": "book"}
        key = generate_bibkey_for_entry(fields, "Knuth, Donald E.")
        assert key == "knuth1997V03E03"

    def test_article_einstein_1905_vol17(self):
        fields = {"year": 1905, "volume": "17", "entry_type": "article"}
        key = generate_bibkey_for_entry(fields, "Einstein, Albert")
        assert key == "einstein1905V17"

    def test_von_particle_stripped(self):
        fields = {"year": 2001, "entry_type": "book"}
        key = generate_bibkey_for_entry(fields, "van Beethoven, Ludwig")
        # surname normalises to 'beethoven', book missing vol → no V, missing ed → E01
        assert key == "beethoven2001E01"

    def test_empty_author_string_yields_anon(self):
        fields = {"year": 2020, "entry_type": "article"}
        key = generate_bibkey_for_entry(fields, "")
        assert key.startswith("anon")

    def test_missing_author_field_yields_anon(self):
        fields = {"year": 2020, "entry_type": "article"}
        key = generate_bibkey_for_entry(fields, "")
        assert key.startswith("anon")

    def test_multiple_authors_uses_first(self):
        fields = {"year": 2010, "entry_type": "article", "volume": "5"}
        key = generate_bibkey_for_entry(fields, "Smith, Alice and Jones, Bob")
        assert key == "smith2010V05"

    def test_natural_order_author(self):
        """'First Last' natural-order author form is parsed correctly."""
        fields = {"year": 2015, "entry_type": "book"}
        key = generate_bibkey_for_entry(fields, "Alan Turing")
        assert key == "turing2015E01"


# ---------------------------------------------------------------------------
# P2.2 — wiring: no-ID entry → calculated key
# ---------------------------------------------------------------------------

class TestNoIdEntryGetsCalculatedKey:
    def test_missing_id_gets_calculated_bibkey(self, global_session):
        """Entry without a source ID receives the calculated bibkey."""
        bib = textwrap.dedent("""\
            @book{,
              title     = {The Art of Computer Programming},
              author    = {Knuth, Donald E.},
              year      = {1997},
              volume    = {3},
              edition   = {3},
              publisher = {Addison-Wesley},
            }
        """)
        result = import_bib_text(global_session, bib)
        assert result.created == 1
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.title == "The Art of Computer Programming")
        ).scalar_one()
        assert entry.bibkey == "knuth1997V03E03"

    def test_empty_id_gets_calculated_bibkey(self, global_session):
        """Entry with empty string ID also receives the calculated bibkey."""
        bib = textwrap.dedent("""\
            @article{,
              title   = {On the Origin of Species},
              author  = {Darwin, Charles},
              year    = {1859},
              volume  = {1},
            }
        """)
        result = import_bib_text(global_session, bib)
        assert result.created == 1
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.title == "On the Origin of Species")
        ).scalar_one()
        assert entry.bibkey == "darwin1859V01"


# ---------------------------------------------------------------------------
# P2.2 — wiring: explicit-ID entry → kept verbatim by default
# ---------------------------------------------------------------------------

class TestExplicitIdKeptByDefault:
    def test_source_id_is_kept_verbatim(self, global_session):
        bib = textwrap.dedent("""\
            @book{myCustomKey2023,
              title     = {Custom Key Book},
              author    = {Smith, Jane},
              year      = {2023},
              edition   = {1},
              publisher = {Publisher},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.title == "Custom Key Book")
        ).scalar_one()
        assert entry.bibkey == "myCustomKey2023"

    def test_source_id_kept_even_when_differs_from_calculated(self, global_session):
        bib = textwrap.dedent("""\
            @article{notCalculated2022,
              title   = {Explicit ID Article},
              author  = {Doe, John},
              year    = {2022},
              volume  = {7},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.title == "Explicit ID Article")
        ).scalar_one()
        assert entry.bibkey == "notCalculated2022"
        # sanity: calculated would have been something like doe2022V07
        assert entry.bibkey != "doe2022V07"


# ---------------------------------------------------------------------------
# P2.2 — recompute_bibkeys=True overrides source ID
# ---------------------------------------------------------------------------

class TestRecomputeBibkeys:
    def test_recompute_overrides_source_id(self, global_session):
        bib = textwrap.dedent("""\
            @book{arbitraryKey,
              title     = {Recomputed Book},
              author    = {Goldstein, Herbert},
              year      = {2001},
              edition   = {3},
              publisher = {Addison-Wesley},
            }
        """)
        import_bib_text(global_session, bib, recompute_bibkeys=True)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.title == "Recomputed Book")
        ).scalar_one()
        # Should be calculated, not "arbitraryKey"
        assert entry.bibkey == "goldstein2001E03"

    def test_recompute_false_keeps_source_id(self, global_session):
        bib = textwrap.dedent("""\
            @book{keepThisKey,
              title     = {Keep Key Book},
              author    = {Feynman, Richard},
              year      = {1965},
              edition   = {1},
              publisher = {Addison-Wesley},
            }
        """)
        import_bib_text(global_session, bib, recompute_bibkeys=False)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.title == "Keep Key Book")
        ).scalar_one()
        assert entry.bibkey == "keepThisKey"


# ---------------------------------------------------------------------------
# P2.2 — Collision disambiguation
# ---------------------------------------------------------------------------

class TestCollisionDisambiguation:
    def test_two_distinct_works_same_base_key_get_suffix(self, global_session):
        """Two DISTINCT works (different title/year/volume) whose base keys collide:
        the second receives the base key + 'a'.

        Uses two no-ID articles by the same author in the same year with no
        volume — both produce "tester1999".  Import in one batch so the
        in-batch disambiguation fires.
        """
        bib_art_a = textwrap.dedent("""\
            @article{,
              title  = {Same Key Article One},
              author = {Tester, Foo},
              year   = {1999},
            }
        """)
        bib_art_b = textwrap.dedent("""\
            @article{,
              title  = {Same Key Article Two},
              author = {Tester, Foo},
              year   = {1999},
            }
        """)
        # Both produce base key "tester1999"; second should get "tester1999a".
        combined = bib_art_a + bib_art_b
        result = import_bib_text(global_session, combined)
        assert result.created == 2

        entries = global_session.execute(
            select(BibEntry).where(BibEntry.title.like("Same Key Article%"))
        ).scalars().all()
        keys = {e.bibkey for e in entries}
        assert "tester1999" in keys
        assert "tester1999a" in keys

    def test_disambiguation_against_existing_db_key(self, global_engine):
        """Existing DB key causes new entry's calculated key to get 'a' suffix."""
        from sqlalchemy.orm import Session

        # Insert first entry in its own session so it's committed.
        bib_first = textwrap.dedent("""\
            @article{,
              title  = {DB Key Existing},
              author = {Existing, Key},
              year   = {2003},
            }
        """)
        with Session(global_engine) as s1:
            r = import_bib_text(s1, bib_first)
        assert r.created == 1

        # Now import a SECOND distinct work in a new session.
        bib_second = textwrap.dedent("""\
            @article{,
              title  = {DB Key New Distinct},
              author = {Existing, Key},
              year   = {2003},
            }
        """)
        with Session(global_engine) as s2:
            r2 = import_bib_text(s2, bib_second)
        assert r2.created == 1

        with Session(global_engine) as s3:
            entries = s3.execute(
                select(BibEntry).where(BibEntry.title.like("DB Key%"))
            ).scalars().all()
        keys = {e.bibkey for e in entries}
        assert "existing2003" in keys
        assert "existing2003a" in keys


# ---------------------------------------------------------------------------
# P2.2 — Dedup hit is NOT disambiguated
# ---------------------------------------------------------------------------

class TestDedupHitNotDisambiguated:
    def test_same_identity_dedup_not_disambiguated(self, global_engine):
        """Same title/year/volume → dedup skipped; only ONE row, no 'a' suffix."""
        from sqlalchemy.orm import Session

        bib = textwrap.dedent("""\
            @article{,
              title  = {Dedup Same Work},
              author = {Author, Same},
              year   = {2015},
              volume = {5},
            }
        """)
        with Session(global_engine) as s1:
            r1 = import_bib_text(s1, bib)
        assert r1.created == 1

        with Session(global_engine) as s2:
            r2 = import_bib_text(s2, bib)
        # Second import → skipped (dedup), NOT a new row with 'a' suffix
        assert r2.skipped == 1
        assert r2.created == 0

        with Session(global_engine) as s3:
            all_entries = s3.execute(
                select(BibEntry).where(BibEntry.title == "Dedup Same Work")
            ).scalars().all()
        assert len(all_entries) == 1


# ---------------------------------------------------------------------------
# P2.3 — Author-less entry → anon key
# ---------------------------------------------------------------------------

class TestAnonymousEntry:
    def test_authorless_entry_gets_anon_key(self, global_session):
        bib = textwrap.dedent("""\
            @article{,
              title  = {Authorless Article},
              year   = {2022},
              volume = {1},
            }
        """)
        import_bib_text(global_session, bib)
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.title == "Authorless Article")
        ).scalar_one()
        assert entry.bibkey.startswith("anon")


# ---------------------------------------------------------------------------
# P2.4 — CLI: --recompute-bibkeys end-to-end
# ---------------------------------------------------------------------------

class TestCliRecomputeBibkeys:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_recompute_bibkeys_flag_cli(self, runner, global_engine):
        """prisma bib import --stdin --recompute-bibkeys replaces source ID with calculated key."""
        bib = textwrap.dedent("""\
            @book{someArbitraryId,
              title     = {CLI Recompute Test Book},
              author    = {Dirac, Paul},
              year      = {1930},
              edition   = {1},
              publisher = {Oxford},
            }
        """)
        result = runner.invoke(
            prisma,
            ["bib", "import", "--stdin", "--recompute-bibkeys", "--json"],
            input=bib,
            obj={"engine": global_engine},
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] == 1

        from sqlalchemy.orm import Session
        with Session(global_engine) as s:
            entry = s.execute(
                select(BibEntry).where(BibEntry.title == "CLI Recompute Test Book")
            ).scalar_one()
        assert entry.bibkey == "dirac1930E01"
        assert entry.bibkey != "someArbitraryId"

    def test_default_import_keeps_source_id_cli(self, runner, global_engine):
        """Without --recompute-bibkeys the source ID is kept verbatim."""
        bib = textwrap.dedent("""\
            @article{keepThisSourceId,
              title   = {CLI Default ID Test},
              author  = {Euler, Leonhard},
              year    = {1748},
              volume  = {2},
            }
        """)
        result = runner.invoke(
            prisma,
            ["bib", "import", "--stdin", "--json"],
            input=bib,
            obj={"engine": global_engine},
            catch_exceptions=False,
        )
        assert result.exit_code == 0

        from sqlalchemy.orm import Session
        with Session(global_engine) as s:
            entry = s.execute(
                select(BibEntry).where(BibEntry.title == "CLI Default ID Test")
            ).scalar_one()
        assert entry.bibkey == "keepThisSourceId"

    def test_recompute_bibkeys_help_text(self, runner):
        """The --recompute-bibkeys flag appears in help output."""
        result = runner.invoke(prisma, ["bib", "import", "--help"])
        assert result.exit_code == 0
        assert "recompute-bibkeys" in result.output


# ---------------------------------------------------------------------------
# Reviewer-esquema P2 regression fixes
# ---------------------------------------------------------------------------

from workflow.prisma.importer import _disambiguate_bibkey, _inject_keyless_ids  # noqa: E402


class TestKeylessRegexFieldBodySafety:
    """FIX 1: _inject_keyless_ids must NOT corrupt field values that contain
    @type{, substrings (e.g. inside a note or abstract field)."""

    def test_keyless_regex_ignores_field_body_at_signs(self, global_session):
        """A valid keyed entry whose note field contains '@misc{,' verbatim must
        not have a sentinel key injected into the field value."""
        bib = textwrap.dedent("""\
            @article{myRealKey2024,
              title    = {Field Body At Sign Test},
              author   = {Author, Test},
              year     = {2024},
              note     = {See @book{,} balanced example},
            }
        """)
        result = import_bib_text(global_session, bib)
        assert result.created == 1
        entry = global_session.execute(
            select(BibEntry).where(BibEntry.title == "Field Body At Sign Test")
        ).scalar_one()
        # Source ID must be preserved verbatim — NOT replaced with a sentinel.
        assert entry.bibkey == "myRealKey2024"
        assert "__keyless_" not in (entry.bibkey or "")

    def test_inject_keyless_ids_does_not_touch_indented_field_values(self):
        """Unit: _inject_keyless_ids only matches line-start entry openers."""
        # A line that is NOT at line-start (i.e. indented field value fragment).
        text = "  note = {example: @book{ , some text},\n"
        result = _inject_keyless_ids(text)
        assert "__keyless_" not in result
        assert result == text  # unchanged

    def test_inject_keyless_ids_matches_real_keyless_entry(self):
        """Unit: a genuine keyless entry opener at line-start IS patched."""
        text = "@book{,\n  title = {X},\n}\n"
        result = _inject_keyless_ids(text)
        assert "__keyless_" in result
        # The @book{ opener must still be present.
        assert "@book{" in result


class TestDisambiguateBeyond26:
    """FIX 2: _disambiguate_bibkey must handle >26 collisions without RuntimeError."""

    def test_first_suffix_a_when_only_base_taken(self):
        """Sanity: only base key taken → returns base+'a'."""
        taken = {"smith2000"}
        assert _disambiguate_bibkey("smith2000", taken) == "smith2000a"

    def test_second_suffix_b_when_base_and_a_taken(self):
        """Base + 'a' both taken → returns base+'b'."""
        taken = {"smith2000", "smith2000a"}
        assert _disambiguate_bibkey("smith2000", taken) == "smith2000b"

    def test_no_suffix_when_candidate_not_taken(self):
        """Candidate not in taken → returned unchanged (no suffix appended)."""
        taken = {"other2000"}
        assert _disambiguate_bibkey("smith2000", taken) == "smith2000"

    def test_beyond_26_returns_aa(self):
        """27th collision yields 'aa' suffix — no RuntimeError raised."""
        base = "jones1990"
        taken = {base}
        for ch in "abcdefghijklmnopqrstuvwxyz":
            taken.add(f"{base}{ch}")
        # taken now has base + all 26 single-letter suffixes = 27 entries
        result = _disambiguate_bibkey(base, taken)
        assert result == f"{base}aa"

    def test_beyond_26_no_runtime_error(self):
        """Calling _disambiguate_bibkey with 26 suffixes taken must NOT raise."""
        base = "stress1111"
        taken = {base}
        for ch in "abcdefghijklmnopqrstuvwxyz":
            taken.add(f"{base}{ch}")
        # Must not raise RuntimeError
        result = _disambiguate_bibkey(base, taken)
        assert result.startswith(base)
        assert result != base
