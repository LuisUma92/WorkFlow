# Roadmap — 100% biblatex compat + the two-workflow handoff (2026-06-03)

**Status: partially superseded (2026-07-05).** This roadmap carried no status field at all
prior to this note. Waves A/C/D/E are shipped elsewhere (see 2026-07-03 roadmap "Status of
prior roadmaps" table); **Wave B (bib-block stdin import) is now also shipped** — commit
`037e572` (2026-06-01), request `2026-06-01-literature-note-bib-block-import.md` closed
2026-07-05. Flagged for hygiene only per `tasks/audit/2026-07-05-tasks-adr-completeness-audit.md`
(Section A Finding #3 / Summary #2) — not urgent, this is a historical snapshot doc.

> Snapshot. Sequences the open bibliography + notes work against two hard constraints:
> **(1)** 100% biblatex compatibility (alternative normalized structures allowed if they
> keep the DB normalized); **(2)** two coexisting workflows that share one bibliography
> foundation. Security review of the new surfaces: `tasks/security/2026-06-03-roadmap-new-surfaces.md`.

## Architecture frame (the invariant everything serves)

```
                       ┌─────────────────────────────┐
                       │  bibliography foundation     │  ADR-0019, ADR-0020
                       │  BibEntry (biblatex-native)  │  ← Zotero .bib in/out
                       └──────────────┬──────────────┘
            ┌─────────────────────────┴─────────────────────────┐
   Zettelkasten (bottom-up)                          PRISMA projects (top-down)
   free reading → literature note                    PICO → search → screen
            │                                                   │
            └──────────────► literature note (.md) ◄────────────┘
                         (truth source; main_topic_id null
                          at creation — anchored later)
                                     │
                       fleeting / permanent notes (.md)
                       exercises / figures (.tex)
```

- **Notes are the truth source.** literature/fleeting/permanent = `.md`; exercises/figures = `.tex`.
- **Single handoff point** = the `included == 1` transition (PRISMA) and the free-read note
  creation (Zettelkasten). Both produce the *same* literature-note artifact. Build that
  artifact once; feed it from both sides.
- **Surface = Neovim.** Obsidian only inspects the vault (so frontmatter must stay
  Obsidian-legal — `aliases` already landed). Zotero interop = biblatex files only.

## Status of inputs

| Work | State |
|------|-------|
| ADR-0019 dialect P1–P3 | ✅ committed (dialect module, schema cols 0008/0012, exporter, `--dialect`) |
| Calculated bibkey P1–P3 | ✅ committed |
| v1.14 reviewer followups (10) | ✅ all closed |
| biblatex compliance | ~90% common / ~56% user-facing / 100% type storage (audit 2026-06-02) |
| literature-note bib-block import | 🟡 open — stdin + nvim |
| prisma-to-literature-note | 🔴 open but **NOT impl-ready** — 4 CRITICAL schema contradictions (audit 2026-06-03) |
| xdg-path-consolidation | 🟡 open, decisions locked |
| **Push** | ⚠️ several features committed, **not pushed** |

---

## Wave A — Close biblatex to 100% (foundation; both workflows depend)

**Insight (uses your "alternative structures if normalized" allowance):** do NOT chase 100%
with one first-class column per biblatex field (293 of them, most never queried). Split into:

- **A1 — overflow table `BibExtraField(bib_entry_id, field, value)`** — normalized EAV catch-all.
  Importer routes any *recognized biblatex field/alias* with no first-class column here;
  exporter re-emits them. **This single move makes storage 100% lossless** (round-trip
  guaranteed) while keeping the schema normalized. Queryable hot fields stay first-class;
  the long tail lives here. Migration `0013` (additive). UNIQUE(`bib_entry_id`,`field`).
- **A2 — 5 missing aliases** (cheap): `archiveprefix→eprinttype`, `primaryclass→eprintclass`,
  `hyphenation→langid`, `pdf→file`, `key→sortkey` into `dialect.BIBTEX_TO_BIBLATEX`. Importer-only.
- **A3 — promote high-value queryable fields to first-class columns** (incremental, not a blocker
  once A1 lands): `subtitle`/`titleaddon`/`booksubtitle` family, `origdate`/`origlocation`/
  `origpublisher`, `eprintclass`/`pubmedid`/`urlraw`. Each: column + dialect map + test. Move
  them *out* of `BibExtraField` as they graduate (back-compat: read both during transition).
- **A4 — cross-reference inheritance** (the one architecturally significant gap):
  normalized `BibRelation(child_id, parent_id, kind)` where `kind ∈ {crossref,xref,xdata,related}`.
  Store the *relationship*, not a copy. Export: emit the raw key; optional `--resolve-xref`
  flag inherits parent fields at render time (biber-style). Keeps normalization; no field copy.
- **A5 — promote the biblatex renderer** per ADR-0020: move `_entry_to_biblatex` /
  `_biblatex_field_pairs` from `prisma/exporter.py` → public `workflow.bibliography.render`.
  Both PRISMA and the note-generator (Wave C) share ONE renderer. Re-export shim in prisma.

A1+A2 ship first (storage hits 100%, lossless). A3/A4 are quality/queryability follow-ups.
Gate: round-trip test — import biblatex `.bib` → export `--dialect biblatex` is field-equivalent
**including** the long-tail fields now preserved via `BibExtraField`.

## Wave B — bib-block stdin import + nvim (small; unblocks C3)

**[CORRECTED 2026-07-05: SHIPPED — commit `037e572` (2026-06-01). B1 (`--stdin` on
`prisma bib import`) and B2 (`:WorkflowBibImport`) both landed same-day as the request;
request closed 2026-07-05 per audit.]**

- **B1** — factor `import_bib_file` → `read file` + `import_bib_text(session, text, …)`;
  add `--stdin` / `-` to `prisma bib import`. Zero change to parse/map/dedup/guards/`ImportResult`.
- **B2** — `:WorkflowBibImport`: extract first ```` ```bib ```` block, pipe to `--stdin --json`.
- Prereq for the generated note's ```` ```bib ```` block to be importable from inside nvim.

## Wave C — The handoff: PRISMA-accepted → literature note (keystone)

**Blocked until the request is corrected.** The 2026-06-03 audit found 4 CRITICAL schema
contradictions — fix the request file BEFORE any TDD:

- **C0 — rewrite request** per audit:
  1. No `Review` entity → use `ReviewRecord(keyword_id, bib_entry_id)`. Frontmatter
     `prisma_review_id` → `prisma_review_record_id` (D3); CLI `--review-id` →
     `--review-record-id`.
  2. Rationale: render `ReviewRecord.include_rationale` (free text) + join
     `ReviewRationale → RationaleOption.label` (controlled). `ReviewRationale` has no `.text`.
  3. Filter `included == 1` (tri-state SmallInteger, not bool).
  4. Frontmatter `source:` collides with `Note.source` relationship → rename `origin:`.
  5. Reuse `notes new --type literature` / `create_note` — do NOT duplicate the renderer.
  6. Extend the validator schema for new keys (`bibkey`, `prisma_keyword_id`, `origin`,
     `created`) — "no schema change" was false.
  7. `bibkey` is non-unique → add `--bib-entry-id` fallback selector; catch `BibKeyAmbiguous`.
  8. ITEP-0013 is **Accepted** (not Proposed); add `0020`, `ITEP-0012`, `ITEP-0013` to `adr_refs`.
- **C1** — `workflow prisma bib accept-to-note <BIBKEY|--bib-entry-id> [--keyword-id]
  [--vault-root] [--dry-run] [--json]`. Renders via the Wave A5 shared renderer; writes
  `<vault_root>/notes/literature/<YYYYMMDD>-lit-<bibkey>.md`; idempotent by file presence.
  PRISMA-rationale section emitted only when a keyword/record is given.
- **C2** — bulk `--all-accepted --keyword-id <id>` (one note per `included==1`; skip existing).
- **C3** — `:WorkflowPrismaAcceptToNote` (depends on C1 + B1 stdin).

## Wave D — Free-reading symmetric path (completes the Zettelkasten side)

- `workflow notes create --type literature --bibkey <key> [--origin manual]` — same template,
  `prisma_keyword_id: null`, no PRISMA-rationale section. Mostly falls out of C1 with the
  PRISMA section omitted. Closes the bottom-up entry point.

## Wave E — XDG path consolidation (infra hygiene; independent)

Locked decisions (platformdirs swap, explicit `db migrate-xdg`, relocate this machine's DB).
Schedule AFTER bibliography churn settles so migrations don't collide. P0 ADR amendment →
P1 `workflow.paths` → P2 config reader → P3 namespace collapse + migrator → P4 docs.
Also resolves the still-open template gap: `permanent.md` missing `main_topic`+`discipline_area`.

---

## Sequencing rationale

1. **Foundation before consumers.** A (bibliography 100% + shared renderer) underpins B, C, D.
   The renderer promotion (A5) is the literal dependency for the note-generator.
2. **Cheap-and-unblocking next.** B is tiny and unblocks C3 — do it right after A1/A2/A5.
3. **Keystone gated on correctness.** C cannot start as written — C0 (request fix) is mandatory;
   the audit is the spec for that rewrite.
4. **Symmetry last on the notes side.** D reuses C's machinery; trivial once C lands.
5. **Infra (E) is orthogonal** but touches migrations — fence it off from A's migration train.

## Decisions — LOCKED 2026-06-03 (user)

- **D1 — overflow table.** `BibExtraField` EAV overflow (A1) is the 100% mechanism.
  Avoid 200+ dead columns; first-class columns only for queryable hot fields.
- **D2 — xref store-only + opt-in resolve-on-export.** `BibRelation` stores the relation
  (normalized); inheritance resolved only via the `--resolve-xref` export flag, not at import.
- **D3 — PRISMA provenance key = `prisma_review_record_id`.** Frontmatter + CLI selector key
  in C0/C1 use `prisma_review_record_id` (per-record, ties the note to one screening decision).

## Push / hygiene reminder

Multiple features are **committed but not pushed** (dialect, calc-bibkey, followups). Before
new work: verify network state per the global push rules, then push `master`. Untracked stray
`tasks/audit/2026-06-03-prisma-to-literature-note-audit.md` should be committed with this roadmap.
