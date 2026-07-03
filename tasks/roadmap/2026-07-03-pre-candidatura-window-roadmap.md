# Pre-candidatura window roadmap — 2026-07-03 → 2026-07-06

_Snapshot 2026-07-03. Merges the 2026-07-03 gap audit
(`~/01-U/.claude/gaps/2026-07-03-workflow-gap-audit.md` + transversal analysis)
with the open remainders of prior roadmaps. Feature-freeze resumes after this
window until post-candidatura (exam nov 2026)._

**Scoring rule (binding, from audit council):**
`score = volumen_futuro_pre-candidatura × implementabilidad`, NOT historical
recurrence. Prevention (validators) > transformation (batch engine) in this
window — the costliest logged incident was silent drift (`status: solved`
accepted → 11,301 files hand-normalized), not a missing batch command.

**User scope decision (2026-07-03):** bundles A + B + D in-window; bundle C
(reposición) deferred; Moodle surface under existing groups (no new top-level
group); one request file per bundle.

---

## Status of prior roadmaps (drift correction)

| Roadmap | Status |
|---|---|
| 2026-05-27, 2026-05-29, route-map-post-itep-0011 | ✅ completed |
| 2026-06-03 bibliography (Waves A–E) | A/C/D/E shipped; **Wave B open** (bib-block stdin import + `:WorkflowBibImport` — request `2026-06-01-literature-note-bib-block-import.md`) |
| 2026-06-06 note-graph & editor tooling (W1–W5) | ✅ ALL shipped: W1 `7d8c385`, W2 `e0a1a49`, W4 `4bba8ab`+`c19afaa`, W3 `3035684`, W5 `1c908b9` (W3/W5 committed 2026-07-03) |

## Window plan (jul 3–6), in council implementation order

Each bundle: TDD RED→GREEN→REFACTOR; reviewer-esquema pass before commit
(locked methodology). Stop line: whatever is unfinished Monday night goes back
under freeze — bundles ordered so early ones are self-contained.

### 1. Bundle A — fail-loud validators (P0, blocker)
Request: [`2026-07-03-exercise-failloud-validators.md`](../requests/2026-07-03-exercise-failloud-validators.md)
- `exercise sync --strict-concepts` (CLI exposure of existing service param)
- invalid explicit `status:` → hard error (no silent `_infer_status` fallback)
- unknown frontmatter key warning + difflib suggestion

### 2. Bundle B — composability flags (P0, recurring-friction)
Request: [`2026-07-03-exercise-composability-flags.md`](../requests/2026-07-03-exercise-composability-flags.md)
- `exercise sync --json --status --dry-run` (json incl. `dropped_concepts`)
- `exercise list --concept <code>` (ExerciseConcept M2M; near-miss content-error evidence)

### 3. Bundle D-validator — Moodle XML lint (P1)
Request: [`2026-07-03-exercise-moodle-validate-scaffold.md`](../requests/2026-07-03-exercise-moodle-validate-scaffold.md)
- structural lint: 1×fraction=100, ≥2×fraction=0, CDATA, defaultgrade/penalty/single
- **Surface decision pending at implementation**: `exam validate` (recommended —
  `workflow exam scaffold-xml` already exists, discovered post-audit) vs
  `exercise validate-moodle` (user's pre-discovery pick)

### 4. Bundle D-scaffold — weekly quiz scaffolder (P1, **droppable**)
Same request as #3.
- weekly DC.md-driven pair (`--week --dc --kind comprension|practica`)
- `--category-style flat|hierarchical`, default **flat** (9/11 empirical norm)
- `Practica-N → PC-N → Tema #(N+1)` offset encoded
- Extend `exam/scaffold.py`, don't duplicate. If time runs out: ship validator only.

### Carry-over (in-window only if A–D land early)
- graph filter helpers (`_expand_by_depth`, `_filter_by_cluster`, `_filter_by_tags`,
  `_parse_cluster_name`) out of `graph/cli.py` → `graph/filters.py` (architect HIGH, deferred from W4 review)
- ADR INDEX hygiene: ITEP-0013 Proposed→Accepted; add ITEP-0014/0015 rows

## Audit slug disposition (completeness check, slugs #1–#18)

| Slug | Disposition |
|---|---|
| #1 strict-concepts, #2 unknown-key warn, #3 status enum | Bundle A request |
| #4 quiz validate | Bundle D-validator |
| #5 `\exa` lint | **NOT scoped** — thin; fold into Bundle A only if trivial after #2, else post-window |
| #6 sync --json/--status/--dry-run, #7 list --concept | Bundle B request |
| #8 evaluations crash | ✅ closed — schema guard verified (evaluation/cli.py:64); note appended to 2026-04-29 request |
| #9 clone --variant, #10 build-exam --reposicion | Bundle C — **deferred by user**, next window |
| #11 scaffold-quiz, #16 category-style flat | Bundle D-scaffold |
| #12 register UCIMED verify | ✅ closed — verified live; note appended to 2026-04-29 request |
| #13 topic import deprecation | ✅ closed — healthy alias → `workflow import` (ADR-0018) |
| #14 course add-practice | post-window P2 (surface decision needed; `course --help` unverified) |
| #15 NoteFrontmatter.main_topic real propagation | post-candidatura (see below) |
| #17 build-exam --balanceo | post-window, first post-freeze sprint candidate |
| #18 concept slug vs Spanish labels | **DECISION-NEEDED** (user-deferred A/B/C) — architecture, do not implement |

## Post-candidatura backlog (do NOT touch before nov 2026)

- **Convention engine / batch transform (marco)** — [`2026-07-03-convention-engine-batch-transform.md`](../requests/2026-07-03-convention-engine-batch-transform.md); ADR first; 54-gap corpus = acceptance checklist
- Bundle C reposición flow (#9/#10)
- Real Tag/MainTopic propagation to GraphNode/collectors (replaces W4 id-hash workaround; request `2026-05-03-note-frontmatter-main-topic.md` stays open P2/P3)
- ITEP-0014 fm_hash incremental-sync benchmark spike (parked by own ADR gate)
- Bibliography Wave B (bib-block import), PRISMA Wave C (needs C0 request rewrite)
- PDF pipelines: `exercise extract --pdf`, `figure extract --bbox` (spec ready at `requests/2026-06-26-figure-extract-pdf-bbox/`)
- `\exa` lint-units (SetUnits.sty parser), `--chapter` filter on exercise list

## Housekeeping done 2026-07-03

- W3 + W5 committed (`3035684`, `1c908b9`, `f3cfc6e`); pushes deferred (net `Docentes 1`, not in reachability table)
- `graphify-out/` gitignored; knowledge graph built (2969 nodes / 287 communities)
- Requests closed/annotated: graph-export-tikz-filters (closed, W4), exercise-list-json-filters, exercise-register-existing-tex, evaluations-schema-migration (re-verify notes)
