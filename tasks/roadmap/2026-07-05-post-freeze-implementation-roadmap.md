# Post-freeze implementation roadmap — window opens nov 2026

_Snapshot 2026-07-05. Synthesizes the audit's open-by-design findings
(`tasks/audit/2026-07-05-tasks-adr-completeness-audit.md` Summary), the four
proposed ADRs written 2026-07-05 (ITEP-0014, ITEP-0015, 0021, 0022), and the
approved-but-unplanned harvest-loop spec
(`docs/superpowers/specs/2026-07-05-fleeting-harvest-design.md`) into one
dependency-ordered execution sequence for the dev-freeze exit. Freeze runs
until the candidatura exam (nov 2026); this file is the entry point for that
first post-freeze sprint planning session — it is not itself a plan (no TDD
phases), just the ordering + evidence + entry criteria a plan will consume._

**Scoring rule (binding, director decision 2026-07-05):**
`prioridad = urgencia × uso`, plus hard dependency ordering — a later wave is
not "more important than" an earlier one, it is *blocked by* it. Do not
reorder without re-running the dependency check below.

---

## Wave dependency diagram

```text
Wave 0 — Harvest loop (D1-D3)
   │  unblocks: concept ingestion from 313 unindexed fleeting notes
   ▼
Wave 1 — Daily-use surfaces
   ITEP-0015 (editor-first authoring) ──┐
   0021 (FTS5 search)  ─────────────────┤  both consume Wave 0's sync passes
   │
   ▼
Wave 2 — Scale + research entities
   ITEP-0014 (fm_hash spike, optimization only, not a gate)
   0022 (ResearchQuestion entity) ── consumes Wave 0 ingestion pattern
                                     + Wave 1 capture UX
   │
   ▼
Wave 3 — Bibliography + review pipelines
   bibliography-dialect-compat remainder (P2/P3 of ADR-0019)
   │
   ▼
   PRISMA C0 rewrite + Wave C remainder ── depends partially on Wave 3

Wave 4 — Platform evolution (parallel track, ADR-gated, schedule last)
   graphify/graph evolution strategy (independent of Waves 0-3)
   convention engine / batch transform R4 (independent, largest effort)

Stretch (not a wave): `workflow synth` ── gated on Waves 0-2 populated data
```

---

## Wave 0 — Semantic-layer ingestion (first, unblocks everything knowledge-side)

### 1. Harvest loop D1–D3

- **Source**: `docs/superpowers/specs/2026-07-05-fleeting-harvest-design.md`
  (Status: Approved, approach B, user-approved 2026-07-05); companion guide
  `docs/wiki/Fleeting-Monolith-Flow.md`.
- **What remains** (evidence): nothing designed remains open — the spec is
  implementation-ready. Concretely un-shipped:
  - D1: `lectures split --sync/--no-sync` — `src/workflow/lecture/cli.py:90-119`
    calls only `split_notes_file` (`src/workflow/lecture/note_splitter.py:35-133`),
    zero DB interaction today. Needs a new `sync_note_files(paths, session, ...)`
    entry point factored out of `sync_vault`'s Pass 2–5 loop
    (`src/workflow/notes/sync.py:366-449`) — `sync_vault` itself untouched.
  - D2: zero new code — one operational run of existing `workflow notes sync
    <vault_root>` over the whole vault. ~~Blocked on the `essay` enum fix~~
    **UNBLOCKED**: the enum fix shipped 2026-07-05 (`4283e17`, Exercise.type
    value-keyed + migration 0016 auto-applied; live vault verified — `graph
    stats` exits 0). D2 can run at any time, even during the freeze
    (ops-only, no dev).
  - D3: new command `workflow concept harvest [--notes DIR|FILE...] [--out
    PATH.yaml] [--json]` — read-only against the DB (`resolve_concepts`
    partition known/unknown), never writes; emits a skyfolding-delta YAML.
    Reuses `_parse_md` (frontmatter parsing), `add_concept`/`import_hierarchy`
    (`src/workflow/concept/service.py:201-257`, ADR-0018) as the sole
    concept-creation path.
- **Effort**: M (D1 requires an extraction refactor of `sync.py`'s pass loop
  plus new CLI flag + tests; D2 is ops-only; D3 is a new module, self-contained,
  no schema change).
- **Hard dependencies**: none pending — the `essay` enum fix shipped `4283e17`
  (2026-07-05). ITEP-0012's 2026-07-04 slug-only amendment (already locked —
  D3 must not violate it, and doesn't by design).
- **Entry criteria**: ready NOW for D2 (ops-only; may run during the freeze);
  D1/D3 start at freeze-exit.
- **Urgencia × uso**: highest in the whole roadmap — 313 vault notes with
  hand-written semantic frontmatter currently produce **0 NoteConcept / 0
  Tag·NoteTag / 0 NoteEdge rows** (verified count in the spec, §1). Every
  downstream feature in Waves 1–2 (FTS ranking by concept, RQ↔note linking,
  editor pickers backed by real data) reads this layer — it is the one true
  blocking dependency for the rest of the roadmap, not just first by
  convenience.

## Wave 1 — Daily-use surfaces

### 2. ITEP-0015 — Editor-first authoring tooling

- **Source**: `docs/ADR/ITEP-0015-editor-first-authoring-tooling.md`
  (Status: Proposed, 2026-05-22).
- **What remains**: everything — this is a design-only ADR, zero code shipped
  (confirmed by audit: "Proposed... no overlap confirmed" against existing
  nvim-plugin pickers). Concrete surface: `workflow notes enums [--json]` CLI
  introspection endpoint (`src/workflow/notes/cli.py`), `workflow notes new-id`,
  `note_alias` table + migration, 7 new nvim keymaps (`<prefix>er/ec/ei/eI/eb/ek/en`),
  `:WorkflowValidate` on `BufWritePost`.
- **Effort**: L (new DB table + migration, CLI surface, 5+ new Lua files,
  test gate asserting CLI/ORM enum parity per the ADR's own MUST rule).
- **Hard dependencies**: **ITEP-0013 P2.1 (NoteEdge model) already shipped**
  (per `fafdfc2`/F5 and the audit's ITEP-0013 → Implemented bump) — the ADR's
  own gate ("ships only after ITEP-0013 P2.1 lands") is now satisfied. Also
  overlaps/extends the D1–D3 tooling from Wave 0 (concept-harvest UX and the
  editor's concept picker should share the same resolve path) — sequence
  after Wave 0, not strictly blocked by it at the schema level.
- **Entry criteria**: ready now at freeze-exit (its own ADR gate is already
  cleared); sequenced second only because Wave 0 populates the data these
  pickers browse.
- **Urgencia × uso**: high daily-use friction (users hand-type 14-char
  `zettel_id` strings and 9-value `relation_type` enums today) but strictly
  a UX layer over data Wave 0 makes real — sequencing after Wave 0 avoids
  building pickers over empty tables.

### 3. ADR-0021 — Vault FTS5 search

- **Source**: `docs/ADR/0021-vault-full-text-search.md` (Status: Proposed,
  2026-07-05, originates from the 2026-07-05 council evaluation).
- **What remains**: everything — placeholder ADR, "No code is written by this
  ADR." Concrete surface: `note_fts` FTS5 virtual table (external-content vs
  contentless tradeoff explicitly left open), `workflow notes search <query>
  [--json]` ranked via `bm25()`, `:WorkflowNoteSearch` Telescope picker,
  index refresh wired into `notes sync`'s existing per-note passes (no new
  top-level write command — sync remains the single writer).
- **Effort**: M (one new virtual table, one CLI command, one picker; the ADR
  itself flags the index-freshness cost as coupled to sync's re-parse
  decision, see next item).
- **Hard dependencies**: **soft** coupling only, per the ADR's own
  Consequences section — "this ADR does not require ITEP-0014 as a
  precondition, only notes the coupling." Real hard dependency: the
  per-note sync passes touched/refactored in Wave 0 D1 (`sync_note_files`)
  are the natural place to also update `note_fts`, so building FTS after
  that refactor avoids a second touch of the same code path.
- **Entry criteria**: ready once Wave 0's `sync_note_files` extraction
  lands (not because FTS *needs* it architecturally, but because building
  the FTS write-hook into the pre-refactor `sync_vault` loop means
  redoing that hook after D1 anyway).
- **Urgencia × uso**: vault has 313 notes and **zero search surface**
  (verified: no FTS table/index/query path anywhere in `workflow.db`,
  `latexzettel`, or `nvim-plugin`) — high daily-use gap, medium urgency
  since tag/concept/graph discovery is a working (if slower) substitute
  today.

## Wave 2 — Scale + research entities

### 4. ITEP-0014 — `fm_hash` incremental-sync spike

- **Source**: `docs/ADR/ITEP-0014-incremental-sync-via-content-hash.md`
  (Status: Proposed, 2026-05-22, "placeholder... Implementation MUST NOT
  begin before" 3 named gates).
- **What remains**: everything, by design — this ADR is explicitly a
  benchmark-gated placeholder, not a committed feature. Its own gate #3
  ("ITEP-0013 ships") is now satisfied (Implemented per the audit), but
  gates #1 (vault-size-justifies-the-optimization benchmark) and #2 (4 open
  questions: hash scope, split hashes, dry-run contract, concurrent-write
  races) are still unresolved.
- **Effort**: S for the spike/benchmark itself; M if the benchmark says
  "yes, build it" (schema migration `ALTER TABLE note ADD COLUMN fm_hash`,
  skip-gate logic in the sync loop `sync --force`/`--rebuild-edges` bypass).
- **Hard dependencies**: none blocking the spike itself. It becomes an
  **optimization**, not a gate, for ADR-0021 (FTS re-index piggybacks on the
  same hash-skip decision if it exists, per 0021's Consequences section) —
  do not block Wave 1 item 3 on this.
- **Entry criteria**: ready once sync is running on a cadence (weekly,
  post-Wave-0 harvest loop in steady use) so a realistic corpus/benchmark
  exists to justify the optimization — this is the "vault size justifies it"
  gate made concrete.
- **Urgencia × uso**: low urgency today (current sync is 10-50ms per the
  ADR's own numbers, on a <1000-note vault); relevant once weekly harvest +
  FTS indexing make full-rescan sync a real recurring cost. Correctly
  sequenced last among the notes-layer items.

### 5. ADR-0022 — ResearchQuestion entity

- **Source**: `docs/ADR/0022-research-question-entity.md` (Status: Proposed,
  2026-07-05, one of "only two true schema-level gaps" per the 2026-07-05
  council evaluation, the other being 0021).
- **What remains**: everything — new `ResearchQuestion` GlobalBase entity
  (`id, code, question_text, status, created_date, closed_date, main_topic_id`),
  `NoteResearchQuestion` M2M table (mirrors `NoteConcept`, adds `stance`
  enum `supports|contradicts|contextualizes`), `workflow notes question
  add|list|link` CLI (Click group + service + formatter split, following
  `workflow.evaluation`/`workflow.concept` precedent), new frontmatter key
  `questions:` ingested by `notes sync` as an additional pass alongside
  `_sync_note_concepts`.
- **Effort**: M (one new entity + M2M table + migration + CLI group + a new
  sync pass + slug-only resolver distinct from but modeled on
  `resolve_concepts`).
- **Hard dependencies**: ITEP-0012 slug-only referencing discipline (extends
  to `ResearchQuestion.code` — the ADR is explicit this is not optional),
  ITEP-0013 (note relation graph — Implemented), PRISMA-0005. Practically:
  depends on Wave 0's ingestion pattern (`_sync_note_concepts`-style pass is
  the template to follow, "not to reuse directly") and Wave 1's capture UX
  (editor pickers for `questions:` frontmatter, once ITEP-0015 ships, close
  the authoring loop the same way concept pickers do).
- **Entry criteria**: ready once Wave 0 ships (concrete sync-pass pattern to
  clone) and Wave 1's ITEP-0015 is at least partially landed (frontmatter
  authoring ergonomics) — sequencing this after Wave 1 avoids building a
  third hand-authored frontmatter key with no editor support.
- **Urgencia × uso**: feeds the stated pipeline vision (reading → notes →
  research questions → frameworks) at its explicit missing link — but is
  new-entity work with no existing partial implementation to build on,
  correctly scheduled behind the two items that are pure UX/perf work over
  already-decided schema.

## Wave 3 — Bibliography + review pipelines

### 6. Bibliography dialect remainder

- **Source**: `tasks/requests/2026-06-01-bibliography-dialect-biblatex-bibtex-compat.md`
  (Status: open, P2 — audit confirms "genuinely still open... the one true
  remaining bibliography-dialect gap").
- **What actually remains** (much of ADR-0019 shipped — do not re-plan the
  whole request): P1 (alias map / `to_biblatex()`/`to_bibtex()` translators)
  and P3 (exporter round-trip, biblatex↔bibtex downgrade) status needs
  re-verification against live code before planning — the request's own
  acceptance criteria are unchecked in the file, but `src/workflow/bibliography/
  dialect.py`, `render.py`, `inheritance.py` all exist per the audit (ADR-0019
  row: "✅ resolved... dialect.py, render.py, inheritance.py exist"). **Action
  before planning**: grep `dialect.py` for `BIBTEX_TO_BIBLATEX`/`to_biblatex`/
  `to_bibtex` and the exporter's downgrade logic to establish which of
  P1/P2/P3 are actually done vs the request file's stale unchecked boxes —
  this roadmap does not re-derive that; flag it as the first action item for
  whoever picks this up.
- **P2 schema work** (if not yet done): `date` verbatim EDTF column, `chapter`,
  `type` entry subtype, `name_prefix`/`name_suffix` on `Author`, `bibkey`
  promoted to unique identity (migration must reconcile existing null/dup
  bibkeys first — ITEP-0010 forward-only migration discipline).
- **Effort**: S–M depending on the re-verification outcome above (could be
  "P3 exporter only" = S, or "full P1-P3" = M).
- **Hard dependencies**: none blocking from Waves 0–2; coordinates with
  PRISMA-0005 dedup logic per the request's own implementation notes (bibkey
  identity change touches PRISMA dedup).
- **Entry criteria**: ready now — no upstream Wave gate; sequenced here
  because it feeds Wave 3 item 7 (citation-accurate synthesis needs a stable
  bibliography dialect) and is otherwise independent.
- **Urgencia × uso**: P2 severity "recurring-friction" per the request's own
  frontmatter; feeds citation-accurate note synthesis directly.

### 7. PRISMA C0 request rewrite + Wave C remainder

- **Source**: `tasks/requests/2026-06-03-prisma-to-literature-note.md`
  (Status: open, P2 — audit: "genuinely still partially open... Wave D
  shipped per plan, but request itself carries no closure annotation").
- **What remains**: the request **already is** a C0 rewrite (done 2026-06-04,
  reconciled against the truth-source audit) and is marked
  "Implementation-ready" with a plan (`tasks/plans/2026-06-04-wave-c-prisma-to-
  note-plan.md`). Audit's own disposition: "writing the C0 request rewrite is
  substantive new content generation... explicitly scheduled post-freeze...
  left open and tracked" — **the C0 rewrite work described in the roadmap
  brief is already done**; what's open is P1 (`workflow prisma bib
  accept-to-note` CLI), P2 (screening-transition hook, itself marked
  "deferred" in-request), P3 (`:WorkflowPrismaAcceptToNote` nvim command).
  `blocked_by: []` in the request's own frontmatter — "B1 stdin + A5 renderer
  have both landed."
- **Effort**: M (P1 CLI + tests is the bulk; P3 nvim command is S once P1
  exists; P2 explicitly deferred by the request itself, not this roadmap).
- **Hard dependencies**: none remaining per the request's own `blocked_by: []`
  — B1 (stdin import) and A5 (shared `render.entry_to_biblatex`) both shipped.
  Soft dependency: item 6 above, since P1's bib-block emission reuses the
  same renderer/dialect module that item 6 may touch.
- **Entry criteria**: ready now for P1/P3; P2 stays deferred per the request
  until "the interactive screening CLI matures" (no timeline given —
  re-evaluate at Wave 3 planning time, don't assume it unblocks itself).
- **Urgencia × uso**: P2, "recurring-friction" — closes the one currently
  fully-manual handoff point between PRISMA screening and the Zettelkasten.

**[FLAG — contradicts the given framing]**: the roadmap brief describes item
7 as needing a "C0 request rewrite... pending." The request file itself
shows the C0 rewrite already happened (2026-06-04, marked
implementation-ready). What's actually pending is the P1/P3 *implementation*
work, not another rewrite pass. Not reordering — just correcting the
characterization so whoever plans this doesn't schedule a rewrite that's
already done.

## Wave 4 — Platform evolution (ADR-first, schedule last intake)

### 8. Graphify / graph evolution strategy

- **Source**: `tasks/requests/2026-07-03-graphify-ideas.md` (Status: open, P1
  in its own frontmatter — but director's locked ordering places it in
  Wave 4; see flag below). Audit: "genuinely open/untracked... not referenced
  by any roadmap yet — orphaned by design (very new, same-day)."
- **What remains**: everything at the strategy level, but the request's own
  "Findings — 2026-07-03" section already narrows the real gap
  considerably: the graphify skill already supports incremental `--update`,
  `merge-graphs`, and a manifest-based file index
  (`graphify-out/manifest.json` with `ast_hash`/`semantic_hash` per file) —
  the request's proposed `{path, sha256, last_graph_update}` refinement is
  "not something new," per the request's own live-verification note. The
  **actual distilled gap** (§ "Gap real destilado"): (a) scope-merge — adding
  `tests/`, `share/`, `data/` to an existing graph while preserving
  IDs/communities instead of regenerating (this part is **already done** per
  primer.md: "Graphify scope-merge DONE: 7047 nodos/10625 links/551
  comunidades" as of 2026-07-05 — verify this closes part of the request
  before planning further work here); (b) `last_graph_update` + manifest
  entry tags for CI; (c) deterministic metrics (fan-in/out, community
  coupling, centrality) — **blocked**: networkx confirmed NOT installed
  (neither uv env nor system python, per the request's own verification),
  pydeps/pyan/tree_sitter-python binding also absent.
- **Effort**: L (metrics work needs a `networkx` dependency decision first —
  `uv add networkx` — then CI pipeline wiring; scope-merge is already
  substantially shipped).
- **Hard dependencies**: a `networkx`-or-alternative dependency decision
  (none of the request's candidate tools are currently installed) — this is
  the concrete decision gate, more granular than "needs an ADR" but
  functionally the same blocker.
- **Entry criteria**: ready to re-scope now that scope-merge is done —
  re-verify against the request's own acceptance criteria before writing new
  work; the remaining ask is narrower than the original request text
  suggests.
- **Urgencia × uso**: tooling-side, low urgency relative to Waves 0-3 (no
  user-facing knowledge-layer feature depends on it); large potential
  leverage for CI-integrated architectural drift detection, but gated on a
  dependency decision no one has made yet.

**[FLAG — contradicts the given framing]**: the request's own frontmatter
priority is P1, and the audit does not mark it low-priority — the Wave 4
placement here is a *director scheduling decision* (stated as such in the
task brief: "low urgency, tooling-side"), not a finding from the source
docs. Flagging per instructions, not reordering.

### 9. Convention engine / batch transform (R4, marco)

- **Source**: `tasks/requests/2026-07-03-convention-engine-batch-transform.md`
  (Status: open, P3, explicitly `blocked_by: ["ADR pending (post-candidatura)",
  "candidatura exam (nov 2026)"]` in its own frontmatter — the only request in
  this roadmap that names the exam date itself as a blocker).
- **What remains**: everything, by explicit design — "this marco request
  exists so the next gap harvest does NOT re-mine the same 54 gaps." Proposal
  is a **one-page ADR first**, deciding: (1) conventions-as-data storage
  (YAML in `data/conventions/` vs DB table) covering at minimum exercise
  fragment layout + `\ifthenelse` guard, `\exa[área]{id}` format, status enum,
  Moodle category-style, weekly naming offsets, note→tex fragment mapping;
  (2) a transform runner (`workflow transform <name> --glob <pattern>
  [--dry-run]` or per-domain verbs) sharing one engine; (3) which historical
  transforms become built-in, using the 54-gap corpus from the 2026-07-03
  harvest as the acceptance-test checklist.
- **Effort**: L (ADR alone is nontrivial — it must reconcile 3 root causes:
  no transform surface, conventions not SSOT, non-composable interface;
  implementation replays ≥3 historical transforms as a acceptance gate).
- **Hard dependencies**: explicitly gated on the candidatura exam date itself
  (not just other work) — "no calendar pressure [before the exam], a
  half-implemented engine during freeze is worse than none." Also
  soft-depends on the validators/flags shipped in the pre-candidatura window
  staying stable ("prerequisites, not substitutes").
- **Entry criteria**: ADR accepted, post-exam — do not start design work
  before the freeze lifts; largest-leverage, largest-effort item in the
  roadmap, correctly scheduled last.
- **Urgencia × uso**: highest historical recurrence (54 de-duplicated gaps,
  3 agents, apr–jul 2026; the costliest single incident was silent-drift
  status-field normalization across 11,301 files) but the director's own
  scoring rule for the *pre-candidatura* window was "prevention > transformation"
  — post-freeze, transformation becomes the higher-leverage item precisely
  because prevention (validators) is now in place and stable.

---

## Stretch / derived — `workflow synth`

Not a wave; explicitly gated. Both ADR-0022 (ResearchQuestion, Consequences
section: "Feeds a future `workflow synth` command... this ADR does not
design `synth`, only ensures the RQ substrate it needs will exist") and the
fleeting-harvest design's own scope line ("Out of scope... `workflow synth`")
agree: `synth` is explicitly premature before Waves 0-2 populate real data.
Council 2026-07-05 confirmed this directly. Do not schedule `synth` design
work inside this roadmap's waves — revisit only after Wave 2 ships and the
concept/RQ/note graph has nonzero real content to query over.

---

## Durante el freeze se permite (reminder, not a wave)

Only the following are in-scope **before** nov 2026, per the locked freeze
rules already in force (see `tasks/roadmap/2026-07-03-pre-candidatura-window-
roadmap.md` for the pre-candidatura window itself, now closed):

- Capture discipline per `docs/wiki/Fleeting-Monolith-Flow.md` — writing
  monoliths, running `lectures split` (pre-D1: split-only, no sync yet),
  hand-authoring skyfolding YAMLs. This produces the very backlog Wave 0
  will ingest — keep capturing, do not build the harvest tooling early.
- Skyfolding imports (`workflow import <area>-contents-skyfolding.yml`) —
  the (a) skyfolding-first concept lifecycle continues normally; it is
  orthogonal to the (b) harvest-later tooling this roadmap plans.
- Bug fixes de producción — standard exception, unrelated to any wave above.

Everything else described in this file (D1-D3 code, ITEP-0015/0021/0022/0014
implementation, bibliography/PRISMA remainder, graphify metrics, convention
engine) is **post-freeze only**.

---

## Contradictions found against the given ordering (flagged, not reordered)

1. **Item 7 (PRISMA)**: the brief frames it as needing a "C0 request rewrite
   pending" — the source request shows the C0 rewrite already happened
   (2026-06-04) and the request is marked "Implementation-ready." What's
   actually pending is P1/P3 implementation, not another rewrite. See flag
   inline above.
2. **Item 8 (graphify)**: the source request's own frontmatter priority is
   P1, not "low urgency" — the audit treats it as correctly open-by-design
   with no priority downgrade. Wave 4 placement is the director's explicit
   scheduling call ("low urgency, tooling-side" — stated in the task brief
   itself), not a finding from the source docs. Flagging per instructions.
3. **Item 8 scope-merge sub-part**: per `primer.md` (2026-07-05), the
   "scope-merge" piece of the graphify request (adding `tests/`, `share/`,
   `data/` to the existing graph) is **already done** ("Graphify scope-merge
   DONE: 7047 nodos/10625 links/551 comunidades"). The request itself
   predates that work finishing. Whoever plans item 8 should re-scope
   against current state, not the request's original framing.
4. **Item 6 (bibliography)**: the roadmap brief says "establish what
   actually remains open — much of ADR-0019 shipped." Confirmed true by the
   audit (dialect.py/render.py/inheritance.py all exist), but the request
   file's own acceptance-criteria checkboxes are all unchecked with no
   progress-log update since 2026-06-01 — there is a genuine **documentation
   gap** here (code likely ahead of the request's tracked status, same
   pattern the audit found and fixed elsewhere) that this roadmap does not
   resolve; flagged as the first action item under Wave 3 item 6 above.
</content>
