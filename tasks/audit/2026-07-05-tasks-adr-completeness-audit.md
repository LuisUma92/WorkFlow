# Tasks & ADR Completeness Audit — 2026-07-05

Scope: verify tasks/{roadmap,requests,plans} lifecycle truthfulness and docs/ADR implementation status against git history + live code + knowledge graph.

## Truth-sources

- **Git history** → `git log --oneline --all` — every cited commit hash in a request/plan/roadmap was verified present (e.g. `7257024`, `39e4d6f`, `037e572`, `87e3420`, `47a50ec`, `f0aa62d`, `14a0f21`, `7d8c385`, `e0a1a49`, `4bba8ab`, `c19afaa`, `3035684`, `1c908b9`).
- **Live code** → `src/workflow/**`, `src/itep/**`, `src/latexzettel/**`, `src/lectkit/**`, `nvim-plugin/**`, `share/latex/sty/**` — code wins over any doc or graph lag; symbol/flag/file presence checked via grep/Read (e.g. `src/workflow/exercise/cli.py:377` `--strict-concepts`, `src/workflow/prisma/cli.py:484` `recompute-keys`, `src/workflow/graph/cli.py:512-516` `neighbors --json`, `db/models/notes.py:273` `NoteEdge`).
- **ADR index** → `docs/ADR/INDEX.md` — cross-checked against each ADR file's own frontmatter `Status`.
- **Knowledge graph** → `graphify-out/graph.json` updated 2026-07-05 (7326 nodes / 11237 links; covers src+tests+docs+nvim-plugin+share+data; the incremental update also repaired a missing exam-module extraction gap from the 07-04 run). Used as a cross-reference aid only; live code remains authoritative.
- **Template conventions** → `data/templates/` (`request-template.md`, `plan-template.md`, `audit-template.md`) and the `tasks/` directory conventions in `CLAUDE.md` (date-prefixed `YYYY-MM-DD-<slug>[-<kind>].md` filenames).

<!-- Verdict legend:
     ✅ resolved — matches truth-source (or was fixed during this audit)
     ⚠️ open     — mismatch / gap that must be fixed
     ⚪ WIP-accepted — known deviation deliberately left; re-audit when stable
     ➖ (ADR sections only) — Proposed, correctly unshipped -->

---

## Section A: Roadmaps (`tasks/roadmap/`, 6 files)

| File | Verdict | Issue |
|---|---|---|
| 2026-05-27.md | ✅ resolved | frontmatter `status: completed`, no contradicting evidence found |
| 2026-05-29.md | ✅ resolved | `status: completed`; completion note cites 5 waves — spot-checked v1.14–v1.16 shipped |
| 2026-06-03-bibliography-and-two-workflow-roadmap.md | ⚠️ open | Waves A/C/D/E claimed shipped elsewhere (2026-07-03 roadmap); Wave B (bib-block stdin import) **is now also shipped** (commit `037e572`) but this roadmap has no closure annotation — file itself has no status field at all |
| 2026-06-06-note-graph-and-editor-tooling-roadmap.md | ✅ resolved | W1–W5 all cited with commits (`7d8c385`,`e0a1a49`,`4bba8ab`+`c19afaa`,`3035684`,`1c908b9`) — all verified present in `git log --all` |
| 2026-07-03-pre-candidatura-window-roadmap.md | ⚠️ open | Newest roadmap — 3 stale lines found (see Findings #1–#3 below); rest of table is accurate |
| route-map-post-itep-0011.md | ✅ resolved | frontmatter `status: completed` |

### Findings

1. **Bundle A/B falsely appear "in progress" via their own request files, but the roadmap correctly shows them planned — the request files are the stale artifact, not the roadmap** (see Section B, Findings #1–#2). Roadmap text itself ("Housekeeping done 2026-07-03") is accurate as of its own snapshot date; no fix needed in the roadmap file.
2. **Roadmap #14 line is stale**: `2026-07-03-pre-candidatura-window-roadmap.md` line "`#14 course add-practice | post-window P2 (surface decision needed; course --help unverified)`" — but `workflow course add-practice` **already shipped** 2026-05-27 (commit `87e3420`, request `2026-04-29-course-add-practice-quiz.md` closed same day, `tests/workflow/test_course_practices.py` exists). This is the exact case primer.md already flagged as stale — confirms it is still unfixed in the roadmap file. **OPEN.**
3. **2026-06-03-bibliography roadmap has no frontmatter/status marker at all** and its "Wave B open" claim is now also stale (Wave B shipped via `037e572`) — but that roadmap is a historical snapshot doc, not actively maintained; flagging for hygiene only, not urgent. **OPEN.**
4. The 2026-07-03 roadmap's own "Status of prior roadmaps" table is otherwise accurate (2026-06-06 W1–W5 commits all verified in git log).
5. `2026-07-04-build-exam-balanceo.md` (#17, closed same day as its own creation, commit `47a50ec` verified) postdates the 2026-07-03 roadmap snapshot — the roadmap's "post-window" disposition for #17 is just aged, not an error given the snapshot date.

---

## Section B: Requests (`tasks/requests/`, 37 files)

| File | Verdict | Issue |
|---|---|---|
| 2026-04-10-cli.md | ✅ resolved | closed_by ADR-0016, CLI verified (`workflow.evaluation.cli`) |
| 2026-04-22-wiki-single-vault-refactor.md | ✅ resolved | closed_by commits verified in git log |
| 2026-04-29-course-add-practice-quiz.md | ✅ resolved | closed_on 2026-05-27; CLI + tests verified; commit `87e3420` |
| 2026-04-29-evaluations-schema-migration.md | ✅ resolved | status completed, closed 2026-05-27 |
| 2026-04-29-exam-scaffold-moodle-xml.md | ✅ resolved | implementation files exist (`src/workflow/exam/scaffold.py`, `cli.py`) |
| 2026-04-29-exercise-list-json-filters.md | ✅ resolved | closed 2026-05-27 |
| 2026-04-29-exercise-register-existing-tex.md | ✅ resolved | closed 2026-05-27 |
| 2026-04-29-main-topic-discipline-area-fk.md | ✅ resolved | implementation `7d4a156` verified in git log |
| 2026-05-03-graph-export-tikz-filters.md | ✅ resolved | closed_by `4bba8ab`+`c19afaa` verified; PARTIAL note honestly documents scope reduction (mutex/--depth/--cluster still absent) |
| 2026-05-03-note-frontmatter-main-topic.md | ✅ resolved | closed_on 2026-06-05, pre-existing-implementation audit; **known prior stale case, now confirmed fixed in frontmatter** |
| 2026-05-03-notes-crud-subcommands.md | ✅ resolved | closed_on 2026-06-05 audit closure |
| 2026-05-04-zettelkasten-main-topic-bundle.md | ✅ resolved | id/title fields empty (template artifact) but status completed w/ resolution narrative — minor hygiene gap only |
| 2026-05-21-resuming.md | ✅ resolved | superseded by ITEP-0013, cross-linked |
| 2026-05-23-nvim-plugin-review-hardening.md | ✅ resolved | closed 2026-05-27, files exist |
| 2026-05-26-database-normalization.md | ✅ resolved | closed 2026-05-27, 8 commits cited, all verified in git log |
| 2026-05-27-topic-reroot-discipline-area.md | ✅ resolved | closed_by v1.11.0, module knowledge.py has MainTopicSyllabus/Topic.discipline_area_id |
| 2026-05-28-content-bib-link-cli.md | ⚠️ open | **No status/closure annotation at all** (legacy no-frontmatter format) despite feature being fully shipped: `content/bib_links.py` + `link-bib`/`bib-links`/`unlink-bib` CLI commands all present in `src/workflow/content/cli.py` |
| 2026-05-28-graph-neighbors-json.md | ✅ resolved | in-body "Status: RESOLVED — v1.16.0" marker (no YAML field, but present); `neighbors_cmd` verified |
| 2026-05-28-nvim-plugin-taxonomy-coverage.md | ✅ resolved | in-body Tier-2 update marker; nvim pickers (topics.lua, contents.lua, concepts.lua, graph_neighbors.lua) verified present |
| 2026-05-28-topic-content-cli-surface.md | ⚠️ open | **No status/closure annotation at all** despite `workflow topic add\|list\|show\|import` and `workflow content add\|list\|show` all shipped and verified in `src/workflow/topic/cli.py` + `content/cli.py` |
| 2026-05-29-bibliography-service-extraction.md | ✅ resolved | in-body "RESOLVED — v1.14.0" marker; `src/workflow/bibliography/service.py` exists |
| 2026-05-29-content-service-split.md | ✅ resolved | in-body "RESOLVED — v1.14.0" marker; `content/bib_links.py` split confirmed |
| 2026-05-29-nvim-plugin-plenary-harness.md | ✅ resolved | in-body "ALL PHASES DONE" marker; `nvim-plugin/tests/plenary/*.lua` specs present (5+ files) |
| 2026-05-29-v1.14.0-reviewer-esquema-followups.md | ✅ resolved | in-body "Status: completed (2026-06-03)" — all 10 items closed across 4 waves, commits verified (`dc5d603`,`07979b5`,`0903476`,`c12a7e0`,`8ac1089`,`02b7aaa`,`2b1789d`) |
| 2026-05-30-topic-content-concept-bulk-import.md | ✅ resolved | in-body "RESOLVED — v1.17.0"; `src/workflow/importer/engine.py` + ADR-0018 confirmed |
| 2026-06-01-bibliography-dialect-biblatex-bibtex-compat.md | ⚠️ open | genuinely still open (P2, no implementation listed) — but not orphaned: referenced by 2026-06-03 roadmap Wave A/C/D/E (mostly shipped under this umbrella) and by `2026-06-03-wave-a-biblatex-100-plan.md` |
| 2026-06-01-literature-note-bib-block-import.md | ⚠️ open | **STALE — feature already shipped.** `status: open`, no closed_on/closed_by, yet `workflow prisma bib import --stdin` (commit `037e572`) + nvim `:WorkflowBibImport` (`nvim-plugin/lua/workflow/bib_import.lua`, wired in `commands.lua`) are fully implemented end-to-end. This is a **third stale-claim case** beyond the 2 the user already knew about |
| 2026-06-01-xdg-path-consolidation.md | ⚠️ open | **STALE** — `Status: Proposed` (legacy format, no frontmatter) but `tasks/plans/2026-06-05-wave-e-xdg-path-consolidation-plan.md` executed this and CLAUDE.md documents `src/workflow/paths.py` (platformdirs) as shipped |
| 2026-06-02-calculated-bibkey-enforcement.md | ⚠️ open | **STALE** — `Status: Proposed` (legacy format) but `workflow prisma bib recompute-keys` CLI command exists (`src/workflow/prisma/cli.py:484`), matching `tasks/plans/2026-06-02-calculated-bibkey-plan.md` |
| 2026-06-03-prisma-to-literature-note.md | ⚠️ open | genuinely still partially open (Wave D shipped per plan, but request itself carries no closure annotation — blocked_by note says "B1 stdin + A5 renderer have both landed") — orphaned-looking but is referenced live by 2026-07-03 roadmap backlog ("PRISMA Wave C needs C0 request rewrite") |
| 2026-07-03-convention-engine-batch-transform.md | ⚠️ open | correctly open, explicitly deferred post-candidatura, referenced by pre-candidatura roadmap backlog — not orphaned |
| 2026-07-03-exercise-composability-flags.md | ⚠️ open | **STALE — shipped.** `status: open`, empty `closed_on`/`closed_by`, but commit `39e4d6f` ("feat(exercise): Bundle B — sync --json/--dry-run/--status + list --concept") exists and all 4 flags verified present in `src/workflow/exercise/cli.py` |
| 2026-07-03-exercise-failloud-validators.md | ⚠️ open | **STALE — shipped.** `status: open`, empty `closed_on`/`closed_by`, but commit `7257024` ("feat(exercise): Bundle A — fail-loud validators") exists and `--strict-concepts` flag verified in `src/workflow/exercise/cli.py:377` |
| 2026-07-03-exercise-moodle-validate-scaffold.md | ✅ resolved | closed 2026-07-03, `f0aa62d`+`14a0f21` both verified in git log, all listed files exist |
| 2026-07-03-graphify-ideas.md | ⚠️ open | genuinely open/untracked (git status shows `??`), correctly unclosed, not referenced by any roadmap yet — orphaned by design (very new, same-day) |
| 2026-07-04-build-exam-balanceo.md | ✅ resolved | closed 2026-07-04, commit `47a50ec` verified, `src/workflow/exercise/balance.py` exists, 21 tests file present |

### Findings

1. **Bundle A request** (`2026-07-03-exercise-failloud-validators.md`) is fully shipped (commit `7257024`) but frontmatter still reads `status: open` with blank `closed_on`/`closed_by` — needs a closure update. **OPEN.**
2. **Bundle B request** (`2026-07-03-exercise-composability-flags.md`) is fully shipped (commit `39e4d6f`) but frontmatter still reads `status: open` — same fix needed. **OPEN.**
3. **literature-note-bib-block-import** (`2026-06-01-literature-note-bib-block-import.md`) is fully shipped end-to-end (CLI `--stdin` + nvim `:WorkflowBibImport`, commit `037e572`) but marked `status: open` — a third, previously-undetected stale-claim case (beyond the 2 the user already knew: #14 add-practice, note-frontmatter-main-topic). **OPEN.**
4. Two **legacy no-frontmatter requests** (`2026-05-28-content-bib-link-cli.md`, `2026-05-28-topic-content-cli-surface.md`) describe features that are fully shipped in code but carry no closure annotation of any kind — format/hygiene gap, not a functional risk. **OPEN.**
5. Two **legacy "Status: Proposed" requests** (`2026-06-01-xdg-path-consolidation.md`, `2026-06-02-calculated-bibkey-enforcement.md`) are both actually shipped (Wave E plan executed; `recompute-keys` CLI exists) — stale status labels. **OPEN.**

---

## Section C: Plans (`tasks/plans/`, 23 files)

| File | Verdict | Issue |
|---|---|---|
| 2026-05-30-discipline-areas-list.md | ✅ resolved | minimal-diff plan, feature present (`workflow db discipline-areas list`) |
| 2026-06-01-bibliography-dialect-plan.md | ✅ resolved | ADR-0019 Accepted, dialect module (`bibliography/dialect.py`) exists |
| 2026-06-01-literature-note-bib-import-plan.md | ✅ resolved | maps to shipped commit `037e572` |
| 2026-06-02-calculated-bibkey-plan.md | ✅ resolved | `recompute-keys` CLI shipped |
| 2026-06-02-v1.14-reviewer-followups-plan.md | ✅ resolved | 10 items, all commits cited verified in git log |
| 2026-06-03-wave-a-biblatex-100-plan.md | ✅ resolved | `bibliography/inheritance.py`, EAV overflow (`dd09ee4`) present |
| 2026-06-04-wave-c-prisma-to-note-plan.md | ✅ resolved | Wave C shipped per roadmap ("landed") |
| 2026-06-05-wave-d-notes-create-literature-plan.md | ✅ resolved | `workflow notes create --type literature --bibkey` documented shipped in CLAUDE.md |
| 2026-06-05-wave-e-xdg-path-consolidation-plan.md | ✅ resolved | `src/workflow/paths.py` XDG resolver shipped |
| 2026-06-06-template-gap-plan.md | ✅ resolved | ITEP-0013 note relation graph — per 2026-06-06 roadmap, ~70%→100% shipped by 2026-07-03 (W3 `3035684`) |
| 2026-07-03-freeze-window-features-plan.md | ⚪ WIP-accepted | active/current plan for the in-flight pre-candidatura window; Phase 0a (ADR INDEX hygiene) still explicitly flagged as pending in the plan's own verified-anchors section |
| adr-0001-notes-sync-plan.md | ✅ resolved | `status: completed` frontmatter; **naming-convention violation** (no `YYYY-MM-DD-` prefix) |
| biblatex-fields-catalog.md | ⚪ WIP-accepted | not a plan — a reference catalog (45 entry types/293 fields extracted from biblatex.tex); misplaced under `tasks/plans/` but harmless; **naming-convention violation** (no date prefix) |
| itep-0011-vault-unification-plan.md | ✅ resolved | `status: completed`; ITEP-0011 Implemented in ADR INDEX; **naming-convention violation** |
| ITEP-0012-plan.md | ✅ resolved | `status: completed`; ITEP-0012 Implemented; **naming-convention violation** |
| LZK-0004-plan.md | ✅ resolved | `status: completed`; Peewee shim removed — `src/latexzettel/infra/orm.py` no longer exists (renamed to `db.py`); **note: CLAUDE.md line "compatibility shim in infra/orm.py" is now stale** (out of this audit's 3-dir scope, flagged as a bonus finding); **naming-convention violation** |
| phase4c-test-review.md | ⚪ WIP-accepted | stale working note, superseded by main phase plans — `status: completed` but content is a coverage-gap review, not an implementation plan; **naming-convention violation** |
| phase5-test-review.md | ⚪ WIP-accepted | same as above; **naming-convention violation** |
| phase6-test-review.md | ⚪ WIP-accepted | same as above; **naming-convention violation** |
| phase7-test-review.md | ⚪ WIP-accepted | same as above; **naming-convention violation** |
| phaseA-notes-crud-plan.md | ✅ resolved | `status: completed`; notes CRUD shipped per `2026-05-03-notes-crud-subcommands.md` closure; **naming-convention violation** |
| phaseB-main-topic-fk-plan.md | ✅ resolved | `status: completed`; matches `2026-04-29-main-topic-discipline-area-fk.md` closure; **naming-convention violation** |
| PLAN-consolidated-architecture.md | ⚪ WIP-accepted | foundational Phase-1 architecture decision doc (zettelkasten-note frontmatter format, not plan template) — decisions all executed (SQLAlchemy migration, hybrid DB, exercise macro extension) but doc predates the plan template entirely; **naming-convention violation** (uses `PLAN-` prefix, no date, wrong frontmatter shape) |

### Findings

1. **12 of 23 plan files violate the `YYYY-MM-DD-<slug>.md` naming convention**: `adr-0001-notes-sync-plan.md`, `biblatex-fields-catalog.md`, `itep-0011-vault-unification-plan.md`, `ITEP-0012-plan.md`, `LZK-0004-plan.md`, `phase4c/5/6/7-test-review.md` (4 files), `phaseA-notes-crud-plan.md`, `phaseB-main-topic-fk-plan.md`, `PLAN-consolidated-architecture.md` — all are legacy (pre-dating the dated-template convention) and all show `status: completed`, so no functional risk, but they should be flagged for a rename/migration pass if the convention is to be enforced retroactively.
2. `phase4c/5/6/7-test-review.md` are confirmed **stale working notes** (coverage-gap reviews, not plans) exactly as the audit brief anticipated — correctly `⚪`.
3. `biblatex-fields-catalog.md` and `PLAN-consolidated-architecture.md` are **not plans at all** (a data catalog and a historical zettelkasten-format decision doc respectively) — both misplaced under `tasks/plans/`, both harmless, both `⚪`.
4. All active dated plans (2026-05-30 through 2026-07-03) map to real shipped code with verifiable commits; no plan-vs-reality gaps found in the dated cohort.
5. `2026-07-03-freeze-window-features-plan.md` is the one genuinely in-flight plan (`⚪ WIP-accepted`) — its own verified-anchors section already flags Phase 0a (ADR INDEX hygiene) as pending, consistent with the roadmap. (Note: as of 2026-07-05 the plan's phases 0–5 are complete per primer/`fafdfc2`; the remaining pending item is exactly the ADR INDEX hygiene captured in Section D/Summary below.)

---

## Section D: ADRs — Core 0001–0020 (Zettelkasten / System)

| File | Verdict | Issue |
|------|---------|-------|
| 0001-Zettelkasten-system.md | ✅ resolved | Correctly marked Superseded by 0015; INDEX matches. |
| 0002-Unified-knowledge.md | ✅ resolved | Markdown-as-canonical-layer premise still holds (notes/ dirs, .md files). |
| 0003-hybrid-database.md | ✅ resolved | GlobalBase/LocalBase split exists (`src/workflow/db/base.py`, engine.py). |
| 0004-sqlalchemy-single-orm.md | ✅ resolved | `Mapped[]` annotations throughout `db/models/`. |
| 0005-exercise-dsl-extends-macros.md | ✅ resolved | `\question`, `\qpart`, `\pts` macros extended, not replaced (PartialCommands.sty). |
| 0006-tikz-asset-pipeline.md | ✅ resolved | `src/workflow/tikz/builder.py`, `cli.py` present. |
| 0007-shared-db-module.md | ✅ resolved | `src/workflow/db/repos/protocols.py` Protocol interfaces exist. |
| 0008-xdg-directory-layout.md | ✅ resolved | `src/workflow/paths.py` platformdirs-based; amendment 2026-06-05 text present. |
| 0009-exercise-module-boundary.md | ✅ resolved | `src/workflow/exercise/{parser,moodle,generator,selector,exam_builder,cli}.py` all exist. |
| 0010-exercise-persistence-model.md | ✅ resolved | `.tex` file-as-truth confirmed; DB stores metadata index only (Exercise model has no body field). |
| 0011-latex-exercise-parser-strategy.md | ✅ resolved | `parser.py:159` docstring "Never raises exceptions"; `ParseResult.errors` (line 162) holds invalid-status errors (`INVALID_STATUS_ERROR_PREFIX`, line 39); amendment text (parser-never-raises, explicit invalid status → errors) is present and matches code exactly. |
| 0012-moodle-xml-export-mapping.md | ✅ resolved | `src/workflow/exercise/moodle.py`, `src/workflow/latex/normalize.py` exist. |
| 0013-codebase-consolidation.md | ✅ resolved | CLI split across modules (exercise/lecture/graph/evaluation/prisma each own `cli.py`). |
| 0014-zettelkasten-implementation.md | ⚠️ open | **Status mismatch**: file frontmatter says `status: Accepted` but `INDEX.md:173` lists it as **Proposed**. INDEX is stale — needs correction to Accepted. |
| 0015-zettelkasten-dailly-work.md | ✅ resolved | Notes/demos/images/exercises workflow all present (notes/, tikz/, exercise/ modules). |
| 0016-evaluation-cli.md | ✅ resolved | `evaluations`, `item`, `course` Click groups confirmed in `src/workflow/evaluation/cli.py:45,55`. |
| 0017-graph-neighbors-json-contract.md | ⚠️ open | Contract itself matches code (`--json` flag on `neighbors_cmd`, `graph/cli.py:512-516`), **but ADR is entirely missing from INDEX.md** — no row exists for 0017 in any section. |
| 0018-bulk-import-contract.md | ⚠️ open | Contract verified byte-accurate: `importer/cli.py:30,44,48,52` → `ctx.exit(1)`, `ctx.exit(2)`, `ctx.exit(3 if result.has_errors else 0)` matches ADR's documented exit codes 0/1/2/3. **But ADR is entirely missing from INDEX.md**, same as 0017. |
| 0019-bibliography-dialect-biblatex-bibtex.md | ✅ resolved | `src/workflow/bibliography/dialect.py`, `render.py`, `inheritance.py` exist. |
| 0020-bibliography-module-boundary.md | ✅ resolved | `src/workflow/bibliography/service.py`, `bibkey.py` present; foundation-layer boundary intact. |

### Findings

1. **0014 INDEX row stale** — INDEX row status (Proposed) contradicts the ADR's own frontmatter (Accepted) — likely never updated after the ADR was accepted. **OPEN.**
2. **0017 and 0018 missing from INDEX** — both recently added, both describing shipped/pinned contracts, yet **zero rows in INDEX.md** — a structural indexing gap, not just a stale status. **OPEN.**
3. 0011's fail-loud amendment (parser-never-raises / explicit invalid status → `ParseResult.errors`) lines up exactly with commits `7257024`/`39e4d6f` — text and code are in sync.

---

## Section E: ADRs — ITEP family

| File | Verdict | Issue |
|------|---------|-------|
| ITEP-0000-project-structure.md | ✅ resolved | Scaffolding conventions live in `src/itep/`. |
| ITEP-0001-sqlalchemy-persistence.md | ✅ resolved | — |
| ITEP-0002-four-layer-schema.md | ✅ resolved | Topic re-rooted at DisciplineArea, `MainTopicSyllabus` join table exists (`db/models/knowledge.py`) — amendment text matches. |
| ITEP-0003-config-yaml-as-db-pointer.md | ✅ resolved | `config.yaml` pointer pattern in `src/itep/models.py`. |
| ITEP-0004-two-project-types.md | ✅ resolved | `GeneralProject`/`LectureProject` in `itep/models.py`. |
| ITEP-0005-symlink-based-config.md | ✅ resolved | `relink` CLI (`itep.links:cli`) confirmed in pyproject entry points. |
| ITEP-0006-taxonomy-enums.md | ✅ resolved | `_TAXONOMY_LEVELS` in `academic.py`, `workflow item taxonomy` command exists. |
| ITEP-0007-crud-manager-layer.md | ✅ resolved | — |
| ITEP-0008-general-project-nomenclature.md | ✅ resolved | Status "Implemented (amended 2026-05-27)" — matches INDEX. |
| ITEP-0009-knowledge-lifecycle-and-ai-agents.md | ✅ resolved | Status "Implemented" matches INDEX. |
| ITEP-0010-schema-versioning-and-migrations.md | ✅ resolved | `workflow db migrate-xdg` command exists per CLAUDE.md/live code. |
| ITEP-0011-vault-unification.md | ✅ resolved | `src/workflow/vault/{unify,cli,paths}.py` all present; `.vault_pointer` marker logic confirmed by CLAUDE.md description. |
| ITEP-0012-concept-orm.md | ✅ resolved | Amendment "2026-07-04 — Concept referencing contract: slug-only strict (gap #18)" text present at line 315; matches this week's work. |
| ITEP-0013-note-relation-graph.md | ⚠️ open | File/INDEX both say **Accepted**, but per primer/commit history the full surface has shipped: `NoteEdge` model (`db/models/notes.py:273`), `graph trace`/`graph resume` commands (`graph/cli.py:698,736`), `notes sync --rebuild-edges` (`notes/sync.py:282,372`), `notes link --relation` (`notes/cli.py:463,755,801`) — all present and wired, with 30 tests per commit `39e4d6f`'s predecessor. This is a **status-upgrade candidate**: Accepted → Implemented. |
| ITEP-0014-incremental-sync-via-content-hash.md | ➖ | Correctly Proposed — `fm_hash` does not exist anywhere in `src/` (grep confirmed zero hits). Nothing shipped ahead of the decision. |
| ITEP-0015-editor-first-authoring-tooling.md | ➖ | Correctly Proposed. Note: nvim-plugin already has 49 `.lua` files (pickers, validate.lua etc. from W5, commit `1c908b9`), but those predate/are outside this ADR's specific "editor-first authoring tooling for the note graph" scope — no overlap confirmed, not a violation. |

### Findings

1. **ITEP-0013 is the clearest status-lag case in the whole audit**: every named primitive (note_edge table, DAG trace/resume, `--rebuild-edges`, `--relation`) is live and tested, yet the ADR still reads "Accepted" rather than "Implemented" — inconsistent with how ITEP-0008/0009/0010/0011/0012 were bumped to Implemented once shipped. **OPEN.**
2. ITEP-0014/0015 are honestly Proposed; verified no premature implementation (`fm_hash` absent, no editor-first-specific module found).

---

## Section F: ADRs — LZK family

| File | Verdict | Issue |
|------|---------|-------|
| LZK-0000-zettelkasten-engine-architecture.md | ✅ resolved | 7-layer dirs confirmed: `src/latexzettel/{cli,server,api,domain,infra,config,util}`. |
| LZK-0001-jsonl-rpc-server.md | ✅ resolved | `server/protocols.py`, `server/routers.py`, `server/main.py` present. |
| LZK-0002-pandoc-conversion-pipeline.md | ✅ resolved | `shared/latex/pandoc/{filter.lua,template.tex,defaults.yaml,preprocess.py}` per CLAUDE.md module map. |
| LZK-0003-note-reference-system.md | ✅ resolved | ID/regex utilities in `src/latexzettel/infra/regexes.py`. |
| LZK-0004-dependency-injection-db-shim.md | ✅ resolved | Self-consistent and accurate: documents the Peewee→SQLAlchemy shim AND its own removal. Status "Implemented (2026-05-23)" — retrospective confirms `infra/orm.py` deleted in v1.6.0 (commits f5ca75f/887e337/67b9f06), API modules now import `Note, Citation, Label, Link, Tag, NoteTag` directly from `workflow.db.models.notes`. Live check: `infra/orm.py` indeed absent from `src/latexzettel/infra/`. |

### Findings

1. LZK-0004 is a model ADR: it was updated post-hoc with a Retrospective + Change Log documenting shim removal, so the "Implemented" status and code truth are perfectly aligned. (Aside, out of ADR-audit scope: CLAUDE.md's architecture section still describes notes.py access "via compatibility shim in infra/orm.py" — that line is now stale relative to LZK-0004's own retrospective; flagged for doc hygiene, carried into the Summary as an out-of-scope aside.)

---

## Section G: ADRs — PRISMA family

| File | Verdict | Issue |
|------|---------|-------|
| PRISMA-0000-systematic-review-architecture.md | ✅ resolved | Django app `src/PRISMAreview/` + `workflow.prisma` CLI both exist per CLAUDE.md. |
| PRISMA-0001-dual-database-router.md | ✅ resolved | Correctly marked Superseded by PRISMA-0005. |
| PRISMA-0002-bibliography-import-pipeline.md | ✅ resolved | `workflow prisma bib import` command family confirmed live. |
| PRISMA-0003-screening-review-workflow.md | ✅ resolved | `workflow prisma review list` etc. |
| PRISMA-0004-data-model-schema.md | ✅ resolved | — |
| PRISMA-0005-cli-sqlalchemy-migration.md | ✅ resolved | `src/workflow/prisma/service.py` imports `sqlalchemy`/`Session` directly (lines 10-11) — dual-DB router superseded as claimed. |

### Findings

1. No issues in this family; PRISMA-0001→0005 supersession chain is internally consistent and matches code.

---

## Section H: ADRs — STY family (12 files)

| File | Verdict | Issue |
|------|---------|-------|
| STY-0000-set-format.md | ✅ resolved | `SetFormat.sty` (+ `SetFormatP.sty` variant) present in `share/latex/sty/`. |
| STY-0001-set-loyaut.md | ✅ resolved | `SetLoyaut.sty`, `SetLoyaut-StandAlone.sty` present. |
| STY-0002-set-commands.md | ✅ resolved | `SetCommands.sty` present. |
| STY-0003-partial-commands.md | ✅ resolved | `PartialCommands.sty` present. |
| STY-0004-set-units.md | ✅ resolved | `SetUnits.sty` present. |
| STY-0005-set-symbols.md | ✅ resolved | `SetSymbols.sty` present. |
| STY-0006-colors.md | ✅ resolved | `ColorsLight.sty`, `colors-UCR.sty`, `colors-Ufide.sty`, `colors-UCIMED.sty` all present — matches "Colors*.sty" glob in INDEX. |
| STY-0007-vector-pgf.md | ✅ resolved | `VectorPGF.sty` present. |
| STY-0008-set-profiles.md | ✅ resolved | `SetProfiles.sty` present. |
| STY-0009-set-headers.md | ✅ resolved | `SetHeaders.sty` present. |
| STY-0010-centred-page.md | ✅ resolved | Maps to `SetCommands.sty` per INDEX (CentredPage is a l3keys feature within it, not a standalone file) — consistent. |
| STY-0011-set-constant.md | ✅ resolved | `SetConstant.sty` present. |

### Findings

1. All 12 STY ADRs check out; file-to-ADR mapping in INDEX's "LaTeX Style System" table is accurate against `share/latex/sty/`.

---

## Section I: ADRs — Meta-files (not full ADRs)

| File | Verdict | Issue |
|------|---------|-------|
| 0000-TEMPLATE.md | ✅ resolved | Correctly listed in INDEX under "Planning & Review Documents", not in a status table (as expected for a template). |
| git-action.md | ✅ resolved | Correctly listed in INDEX as a plain doc ("CI/CD pipeline notes"), no status field expected/present — appropriate treatment. |
| INDEX.md | ⚠️ open | Carries the 0014 status mismatch + 0017/0018 missing rows — INDEX's own integrity bugs (see Summary #9–#10). |

---

## Summary / open items

Counts recap (✅ / ⚠️ / ⚪-or-➖ per group):

| Group | ✅ resolved | ⚠️ open | ⚪ WIP-accepted / ➖ | Total |
|---|---|---|---|---|
| Roadmaps | 4 | 2 | 0 | 6 |
| Requests | 25 | 9 | 0 | 34* |
| Plans | 15 | 0 | 8 | 23 |
| ADRs | 54 | 5 | 2 | 61 |

\* Per fragment B's own accounting; total request files on disk = 37, with the legacy-format files folded into the ✅/⚠️ rows shown in Section B. (Assembly note: Section B's table as carried over verbatim contains 36 rows — 25 ✅ + 11 ⚠️, where `2026-07-03-convention-engine-batch-transform.md` and `2026-07-03-graphify-ideas.md` are ⚠️-marked but "correctly open by design"; the fragment's own summary counted 9 actionable ⚠️. Both tallies are preserved here rather than silently reconciled.)

Only ⚠️-open items, merged from Sections A–I:

| # | File | Issue | Action needed |
|---|------|-------|---------------|
| 1 | `tasks/roadmap/2026-07-03-pre-candidatura-window-roadmap.md` | Audit-slug #14 line claims "post-window, surface decision needed" — `course add-practice` shipped 2026-05-27 (`87e3420`), request already closed | Fix the roadmap #14 line: mark shipped 2026-05-27, commit `87e3420` |
| 2 | `tasks/roadmap/2026-06-03-bibliography-and-two-workflow-roadmap.md` | No status field at all; "Wave B open" claim stale — Wave B shipped via `037e572` | Add frontmatter/status + closure annotation noting Wave B shipped (`037e572`); hygiene, not urgent |
| 3 | `tasks/requests/2026-07-03-exercise-failloud-validators.md` | Bundle A shipped but `status: open`, blank closure fields | Close request: `status: completed`, `closed_on: 2026-07-03`, `closed_by: 7257024` |
| 4 | `tasks/requests/2026-07-03-exercise-composability-flags.md` | Bundle B shipped but `status: open`, blank closure fields | Close request: `status: completed`, `closed_on: 2026-07-03`, `closed_by: 39e4d6f` |
| 5 | `tasks/requests/2026-06-01-literature-note-bib-block-import.md` | Feature shipped end-to-end (CLI `--stdin` + nvim `:WorkflowBibImport`) but `status: open` | Close request with `closed_by: 037e572` (third stale-claim case) |
| 6 | `tasks/requests/2026-06-01-xdg-path-consolidation.md` + `tasks/requests/2026-06-02-calculated-bibkey-enforcement.md` | Both legacy `Status: Proposed` but both shipped (Wave E plan executed; `recompute-keys` at `src/workflow/prisma/cli.py:484`) | Flip both to implemented/closed with pointers to their executed plans |
| 7 | `tasks/requests/2026-05-28-content-bib-link-cli.md` + `tasks/requests/2026-05-28-topic-content-cli-surface.md` | No status/closure annotation of any kind; both features fully shipped (`content/cli.py`, `topic/cli.py`) | Add retroactive closure annotations (in-body "Status: RESOLVED" marker at minimum) |
| 8 | `tasks/requests/2026-06-03-prisma-to-literature-note.md` | Genuinely partially open; blocked_by note says prerequisites landed; roadmap backlog says "PRISMA Wave C needs C0 request rewrite" | Write the C0 request rewrite per the 2026-07-03 roadmap backlog note (post-freeze) |
| 9 | `tasks/requests/2026-06-01-bibliography-dialect-biblatex-bibtex-compat.md` | Genuinely still open (P2) — the one true remaining bibliography-dialect gap | No doc fix; keep open and tracked (referenced by 2026-06-03 roadmap + Wave A plan) |
| 10 | `tasks/requests/2026-07-03-convention-engine-batch-transform.md` + `tasks/requests/2026-07-03-graphify-ideas.md` | Correctly open (deferred post-candidatura / brand-new untracked) | No status fix; commit `2026-07-03-graphify-ideas.md` (currently `??` in git status) and keep both tracked |
| 11 | `docs/ADR/INDEX.md:173` | ADR-0014 row shows "Proposed"; file frontmatter says "Accepted" | Update INDEX row for 0014 → `Accepted` |
| 12 | `docs/ADR/INDEX.md` | ADR-0017 and ADR-0018 have zero rows anywhere in INDEX.md despite being Accepted, code-verified contracts | Add INDEX rows for 0017 and 0018 (one edit fixes both; e.g. Graph CLI / Import CLI placement) — this is the pending Phase 0a of `tasks/plans/2026-07-03-freeze-window-features-plan.md` |
| 13 | `docs/ADR/ITEP-0013-note-relation-graph.md` | Marked "Accepted" but full surface (NoteEdge, graph trace/resume, `--rebuild-edges`, `--relation`) shipped + tested | Flip ITEP-0013 → Implemented with a dated amendment note (and matching INDEX row update), consistent with ITEP-0008..0012 practice |
| 14 | `CLAUDE.md` (architecture section, `src/latexzettel/` bullet) — out-of-scope aside | Describes notes.py access "via compatibility shim in infra/orm.py"; LZK-0004's retrospective says that file was deleted in v1.6.0 | Update the CLAUDE.md wording (doc hygiene; not an ADR fix) |
