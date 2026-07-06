# Implementation plan — Wave 4: graph evolution metrics + convention engine (R4) marco

Request: `tasks/requests/2026-07-03-graphify-ideas.md`; `tasks/requests/2026-07-03-convention-engine-batch-transform.md`
ADR: `docs/ADR/0023-<slug-tbd>.md` (**Proposed** — drafted in F0b, number reserved as next-free per `docs/ADR/INDEX.md`; slug decided when written) <!-- R4 ADR only; graph metrics F1 needs no new ADR, extends existing workflow.graph module boundary -->
Methodology: TDD (RED→GREEN→REFACTOR), reviewer-esquema each phase, forward-only
migrations (ITEP-0010). Phases ship independently; commit at each GREEN.

---

## Verified anchors (confirmed in code)

- `src/workflow/graph/domain.py` — `GraphNode(node_id, node_type, label, tags: frozenset[str], main_topic: str | None)`, `GraphEdge(source_id, target_id, edge_type, label)`, `KnowledgeGraph(nodes: tuple, edges: tuple)` — all frozen dataclasses, immutable, hashable. No `weight`/`community_id` field on either yet.
- `src/workflow/graph/analysis.py` — `GraphStats` dataclass (`total_nodes, total_edges, nodes_by_type, edges_by_type, orphan_count, component_count`); `compute_stats(graph)` is the existing pure-function entry point F1 extends (no DB access, side-effect-free, per module docstring). `find_orphans`, `connected_components` already implemented alongside it.
- `src/workflow/graph/clustering.py` — `detect_communities(graph) -> tuple[tuple[GraphNode, ...], ...] | None`. Returns `None` gracefully via `try: import networkx / except ImportError: return None` (lines 18-21). **Confirmed live 2026-07-05**: networkx NOT installed in uv env nor system python (re-verified per request's own Findings §3 and roadmap item 8) — `detect_communities` currently always returns `None` in this repo.
- `src/workflow/graph/cli.py` — Click group, existing commands `orphans|stats|export-dot|export-tikz|clusters|neighbors`, all accept `--main-topic/--discipline-area/--topic` filters (Phase 4E). `clusters` command is the one that calls `detect_communities` and degrades when it returns `None` — confirm exact degrade message before F1 (read the command body, not re-derived here).
- `src/workflow/graph/collectors.py` — `build_knowledge_graph`, `filter_graph_by_taxonomy`, `resolve_taxonomy_filter`, `TaxonomyFilter` — the only path that queries global+local DBs into a `KnowledgeGraph`. F1's `workflow graph metrics` MUST reuse this collector, never re-query the DB directly.
- Manifest split (graphify skill, `~/.claude/skills/graphify/SKILL.md` lines 948-1009, "Scope merge" section, already improved 2026-07-04): `graphify-out/manifest.json` is vendor-owned per-file index (`{path: {mtime, ast_hash, semantic_hash}}`, `detect.py:926-936`) — **not ours to extend**. `graphify-out/graph-meta.json` is the skill's own sidecar, per scan-root entry, **already created** (primer.md 2026-07-05: "graph-meta.json sidecar creado"). F2 must extend `graph-meta.json` only, never touch vendor `manifest.json`.
- Scope-merge (graphify-ideas request, acceptance criterion 5) — **already shipped** per primer.md 2026-07-05: "Graphify scope-merge DONE: 7047 nodos/10625 links/551 comunidades; tests+share+data indexados." `tasks/(73)/scripts/(4)/.github(3)` are flagged hash-tracked but NOT extracted — next `--update` sees them `unchanged`; a dedicated pass is needed if they are to enter the graph. This plan does NOT re-do scope-merge; F2 only covers the manifest-tag gap.
- `tasks/requests/2026-07-03-graphify-ideas.md` Findings §4 ("Gap real destilado"): the only work still open on the graphify side is (b) `last_graph_update` + manifest entry tags for CI, and (c) deterministic metrics — this plan's F1/F2 map 1:1 onto (c)/(b).
- ADR index next-free number: `docs/ADR/INDEX.md` + `ls docs/ADR/` confirm highest top-level ADR is `0022-research-question-entity.md` (Status Proposed) → next number is **0023**.
- Migration harness: `src/workflow/db/migrations/global/`; latest = `0016_exercise_type_normalize_legacy_codes.py` → next = `0017_` (only if F3's convention-store design lands as a DB table rather than YAML — see Resolved design rules, ★ open until F0a/F0b decisions land).
- `tasks/requests/2026-07-03-convention-engine-batch-transform.md` — R4 marco, `blocked_by: ["ADR pending (post-candidatura)", "candidatura exam (nov 2026)"]` in its own frontmatter; acceptance criteria require the ADR to be written FIRST and accepted before any transform-runner code exists. The 54-gap corpus lives at `~/01-U/.claude/gaps/2026-07-03-transversal-gap-analysis.md` (external to this repo — cite path, do not copy the table into this plan).
- `tasks/roadmap/2026-07-05-post-freeze-implementation-roadmap.md` Wave 4 (items 8-9) — locks this wave's scheduling: parallel track, independent of Waves 0-3, scheduled last; R4 explicitly gated on "no calendar pressure before the exam."

---

## Target / design

End state: (1) `workflow graph metrics [--json]` and `workflow graph coupling-matrix [--json]` commands compute fan-in/fan-out, community-coupling ratios, and (if a centrality library is available) betweenness/pagerank/closeness/eigenvector — entirely offline, over the vault's `workflow.graph` `KnowledgeGraph`, with graceful `None`/omitted-section degrade when the chosen library isn't installed (mirroring `detect_communities`'s existing pattern). (2) `graphify-out/graph-meta.json` gains a `last_graph_update` timestamp field and per-entry activation tags, closing the manifest-tag gap from the request's Findings §4(b) — this is a skill-level change (`~/.claude/skills/graphify/SKILL.md`), not a `src/workflow` change; it has no test suite and no CLI surface, so it is documented here but not phased as TDD. (3) ADR `docs/ADR/0023-<slug>.md` for R4 (convention engine), decided against the 54-gap corpus as acceptance checklist, covering conventions-as-data storage + transform runner surface + which historical transforms become built-in — **Proposed only in this plan's scope**; R4's own implementation (Phase 1 first increment) is gated on user acceptance of that ADR and does not start until Decision-locked.

### Commands / API surface

```bash
workflow graph metrics [--main-topic CODE] [--discipline-area CODE] [--topic NAME] [--json]
workflow graph coupling-matrix [--main-topic CODE] [--discipline-area CODE] [--json]
# R4 (indicative only — ADR 0023 decides the real surface, F3 implements first increment only)
workflow transform <name> --glob '<pattern>' [--dry-run] [--json]
```

Expected output / JSON shape (`graph metrics --json`):

```json
{
  "fan_in": {"community:src.workflow.graph": 12},
  "fan_out": {"community:src.workflow.graph": 4},
  "coupling": {"community:src.workflow.graph": {"internal": 29, "external": 7, "ratio": 0.241}},
  "centrality": null
}
```

`"centrality": null` when no centrality library is installed (F0a "stdlib-only" branch); populated object when the F0a "install networkx" branch is chosen.

---

## Resolved design rules

- **F1 scope boundary**: `workflow graph metrics` operates on the vault's live `KnowledgeGraph` (via `workflow.graph.collectors.build_knowledge_graph`), the same source `graph stats`/`graph orphans` already use — it does NOT read `graphify-out/` at all. `graphify-out` is a separate LLM-enriched artifact (skill-owned, not `src/workflow`-owned); a metrics sidecar for it is optional and, if wanted, lives in the skill's own tooling, not this CLI. ★ Confirm with user: is a `graphify-out`-side metrics sidecar in scope for this wave, or strictly out of scope? (default assumption below: out of scope, F1 is vault-only.)
- **F0a networkx decision governs F1's centrality section**: if user picks "install as optional dep" → `uv add networkx` (mirrors the existing `clustering.py` optional-import pattern, no new hard dependency), centrality functions implemented for real; if user picks "stdlib-only" → fan-in/fan-out/coupling-ratio (pure counting, no graph-theory library needed) ship in F1, centrality section returns `None`/omitted with a documented reason, exactly like `detect_communities` degrades today. ★ AskUser at wave kickoff, before F1 starts.
- **Fallbacks**: node/community with zero external edges → `ratio: 0.0` (not `null`, not division error) in coupling-matrix; `graph metrics` on an empty graph → all-empty dict sections (mirrors `compute_stats`'s existing empty-graph handling, not re-derived here — verify by reading `compute_stats` call sites before F1).
- **Collision / disambiguation**: "community" here means whatever `detect_communities`/networkx returns (arbitrary node groupings), NOT `MainTopic`/`DisciplineArea` — do not conflate; document the distinction explicitly in the `graph metrics` docstring so future readers don't assume taxonomy-driven communities.
- **Manifest sidecar** (F2): `graph-meta.json` schema addition is additive-only — existing consumers (skill's own fast-path check, per SKILL.md ~line 1009) must keep working unchanged; new fields are optional keys, never a breaking rename.
- **R4 ADR-first discipline** (F0b/F3): per the request's own frontmatter (`blocked_by: ["ADR pending..."]`) and the roadmap's explicit warning ("do not start design work before the freeze lifts"), F3 code MUST NOT be written until ADR 0023 is `Accepted` by the user. This is a hard phase-order gate, not a suggestion.

---

## Decisions — LOCKED (user, TBD)

<!-- Empty until F0a/F0b AskUser gates run — do not backfill assumptions here. -->

1. [PENDING F0a] networkx as optional formal dependency vs stdlib-only for `graph metrics` centrality section.
2. [PENDING F0b] ADR 0023 accepted — conventions-as-data storage location (YAML in `data/conventions/` vs DB table) and transform-runner command surface shape.
3. [PENDING F0a] Whether a `graphify-out`-side metrics sidecar is in scope this wave (default: out of scope per Resolved design rules above; confirm).

---

## Phases

### Phase 0a — ★ GATE: networkx dependency decision (AskUser, blocks F1)

**Goal:** Get an explicit user decision on optional dependency strategy before any centrality code is written.

**Not a TDD phase** — no RED tests, no GREEN impl. Present both branches:

- Branch A ("install networkx as optional extra"): `pyproject.toml` gains an optional-dependency group (e.g. `[project.optional-dependencies] graph-metrics = ["networkx"]`), `clustering.py`'s existing `try/except ImportError` pattern is reused verbatim for the new centrality functions — no behavior change to the existing graceful-degrade contract, just a second consumer of the same optional import.
- Branch B ("stdlib-only"): fan-in/fan-out/coupling-ratio ship (pure counting, `collections.Counter` over `KnowledgeGraph.edges`, no library needed); centrality section of `graph metrics --json` is permanently `null` with a one-line `"centrality_note"` string explaining why; `detect_communities`'s existing optional-networkx path in `clusters` is untouched either way (this decision is scoped to the NEW metrics command only, not a retroactive change to `clusters`).

**Commit point:** none (decision-only; record the answer in "Decisions — LOCKED" above, then proceed).

---

### Phase 0b — ★ GATE: R4 ADR drafted + accepted (opus, blocks F3)

**Goal:** Produce `docs/ADR/0023-<slug>.md` deciding conventions-as-data storage + transform-runner surface, using the 54-gap corpus as the acceptance-test checklist, per the request's own acceptance criteria.

**Not a TDD phase** — architecture document, not code. Deliverable checklist (from the request):

- One-page ADR, `Status: Proposed` initially.
- Decides: (1) conventions-as-data location (YAML in `data/conventions/` vs DB table) covering at minimum exercise fragment layout + `\ifthenelse` guard, `\exa[área]{id}` format, status enum, Moodle category-style, weekly naming offsets, note→tex fragment mapping; (2) transform runner surface — single `workflow transform <name> --glob <pattern> [--dry-run]` vs per-domain verbs sharing one engine; (3) which ≥3 historical transforms become built-in first (candidates: reformat-bank subfiles→guard+question, notes import-tex/export-tex round-trip, lab expand — per the request's acceptance criteria).
- Cross-reference every row of the 54-gap corpus (`~/01-U/.claude/gaps/2026-07-03-transversal-gap-analysis.md`, Cara 1) as either "covered by this ADR's decision" or "explicit wontfix" — per the request's closure checklist, this cross-link is a hard acceptance requirement, not optional.
- ★ **AskUser**: present the drafted ADR to the user for Accept/Reject/Revise. F3 does not start until `Status: Accepted` is recorded and the request's `blocked_by` field is updated to reflect the exam-date gate being cleared (post-candidatura, per its own frontmatter — this gate cannot be cleared before nov 2026 regardless of ADR status; note this explicitly to the user when presenting).

**Commit point:** ADR file committed once Accepted (docs-only commit, reviewer-esquema not required for a pure ADR text — confirm with user if a lightweight peer read is still wanted).

---

### Phase 1 — graph metrics (pure function, no DB, depends on F0a)

**Goal:** `compute_metrics(graph: KnowledgeGraph, communities: ... | None) -> GraphMetrics` proves fan-in/fan-out/coupling-ratio are computable deterministically from the existing immutable `KnowledgeGraph`, with centrality wired per the F0a branch chosen.

**RED tests** (`tests/workflow/graph/test_metrics.py`):

- Empty graph → all-empty `GraphMetrics` (no division-by-zero, no exception).
- Single community, zero external edges → `ratio: 0.0`.
- Two communities with known internal/external edge counts → exact expected ratio (hand-computed fixture, mirrors the request's own worked example: `12/3` style ratio).
- Fan-in/fan-out counts match a hand-built fixture graph (3-4 nodes, asymmetric edges).
- Branch A only: centrality functions return non-`None` populated dict on a fixture graph with a known betweenness value (small graph, hand-verifiable). Branch B only: centrality section is `None`/omitted with the documented note, and this is asserted explicitly (not just "not error").
- CLI: `graph metrics --json` on the isolated test-DB vault fixture emits the documented JSON shape; `--main-topic`/`--discipline-area`/`--topic` filters compose (reuse existing `TaxonomyFilter` fixture pattern from `test_graph_cli.py` if present — check first).

**GREEN impl** — files touched:

- `src/workflow/graph/analysis.py` (edit) — new `GraphMetrics` frozen dataclass + `compute_metrics(graph, communities)` pure function, alongside existing `GraphStats`/`compute_stats`.
- `src/workflow/graph/clustering.py` (edit, Branch A only) — new centrality functions (`betweenness_centrality`, `pagerank`, etc.) behind the same `try/except ImportError` pattern as `detect_communities`.
- `src/workflow/graph/cli.py` (edit) — new `metrics` and `coupling-matrix` Click commands, reusing `build_knowledge_graph`/`filter_graph_by_taxonomy`/`resolve_taxonomy_filter` exactly as `stats`/`orphans` do today.
- `pyproject.toml` (edit, Branch A only) — optional-dependency group for `networkx`.

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P1.

---

### Phase 2 — manifest meta tags (skill-level, depends on nothing, parallel to F1)

**Goal:** Close the request's Findings §4(b) gap — add `last_graph_update` + per-entry activation tags to the skill's own `graphify-out/graph-meta.json` sidecar, verifying what's already present before adding anything.

**Not a `src/workflow` TDD phase** — this is a skill-file change with no pytest suite. Verification-first steps:

- Read `graphify-out/graph-meta.json` (live file) to confirm current schema (per-scan-root entries, "indexed" + date per primer.md 2026-07-05) and identify exactly which of `last_graph_update` / per-entry tags is genuinely missing vs already covered by the existing "indexed"-with-date field — do not assume the gap is as wide as the original request text; the SKILL.md "Findings" section may already be stale relative to the 2026-07-04 skill improvement.
- If a real gap remains: extend `~/.claude/skills/graphify/SKILL.md`'s "Scope merge" section (lines ~948-1009) documenting the new field(s), additive-only per Resolved design rules.
- If CI wiring is wanted (light-weight, per the original request's "Desired CI Strategy" — git diff → structural analysis → metrics → validations, no LLM): this is explicitly F1's `graph metrics` CLI being callable from a CI step, not new skill code — cross-reference, don't duplicate.

**Commit point:** skill-file edit only (no reviewer-esquema — not `src/workflow` code); confirm with user whether skill-directory changes need any sign-off convention this repo doesn't have documented.

---

### Phase 3 — R4 first increment ONLY (sequential, last, depends on F0b Accepted)

**Goal:** Implement exactly the first increment the accepted ADR 0023 defines — this plan does not pre-specify RED tests or GREEN files here because the ADR (not this plan) owns that design. This phase is a placeholder committing to sequencing only.

**RED tests:** deferred to the ADR's own implementation section — write them only after Phase 0b's ADR is Accepted, following whatever conventions-as-data format and transform-runner shape it locks in.

**GREEN impl** — files touched: deferred to ADR; expected candidates per the request's acceptance criteria — `data/conventions/<name>.yaml` (or DB table + migration `0017_conventions.py`, if ADR picks DB), `src/workflow/transform/` new module (engine + CLI), replaying ≥1 of the 3 named historical transforms as the acceptance gate for this first increment (not all 3 — "first increment" per the wave brief, remaining transforms are future waves).

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P3. **Hard gate: do not start this phase's RED tests before Phase 0b's ADR shows `Status: Accepted` in the file.**

---

## Risks / out of scope

- **In scope:** F1 graph metrics CLI (vault-side only), F2 manifest-tag verification/extension, F0b ADR drafting, F3 first-increment R4 code (post-ADR-acceptance only).
- **Out of scope:** full R4 transform-runner implementation beyond the first increment (ADR 0023 will define subsequent phases as its own follow-on plan); `graphify-out`-side metrics sidecar (pending ★ user confirmation, default out); re-doing scope-merge (already shipped `fafdfc2`/primer.md); extracting `tasks/`, `scripts/`, `.github/` into the graph (flagged as needing a dedicated pass, not this wave).
- **Risk:** F0a "install networkx" branch adds a new runtime dependency — gate on user confirming it's acceptable as an optional extra (not a hard install-time requirement for the base package).
- **Risk:** F3 starting before ADR 0023 is Accepted violates the request's own `blocked_by` frontmatter and the roadmap's explicit "do not start design work before the freeze lifts" instruction — this is the single most important gate in this plan; do not let calendar pressure from other waves cause a shortcut here.
- **Risk:** the request's own Findings §4 may already be partially stale (like the scope-merge item was) by the time F1/F2 actually start — re-verify `graph-meta.json`'s live schema and `graphify-out/` state immediately before F2, not from this plan's text alone.
- No schema migration expected for F1/F2 (all data structures are in-memory dataclasses / a skill-owned JSON sidecar). F3 may require one (`0017_`) only if the ADR picks a DB-table conventions store — deferred, not committed here.

---

## Verification (each phase)

```bash
# Isolated suite — never touches live DB
WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py

# Lint
uv run flake8 src/ tests/ --max-line-length=127 --max-complexity=10

# F1 live dry-run (on a COPY of the live DB, never the original)
# cp ~/.local/share/workflow/workflow.db /tmp/workflow-test.db
# WORKFLOW_DATA_DIR=/tmp workflow graph metrics --json

# F2 verification (no DB involved — file inspection only)
# cat graphify-out/graph-meta.json | jq .
```

---

## Orquestación

| Fase | Rol primario | Rol secundario | Notas |
|------|---------------|----------------|-------|
| F0a  | parent (director, AskUser) | — | decisión, no código |
| F0b  | opus (arquitecto pleno esta wave — redacta ADR 0023) | parent (AskUser Accept/Reject) | ADR-first, corpus de 54 gaps como checklist |
| F1   | sonnet (impl/tests) | opus (review si Branch A añade dependencia nueva) | depende de F0a |
| F2   | sonnet o haiku (skill-file, texto) | — | sin suite pytest; verificar antes de escribir |
| F3   | sonnet (impl) | opus (review arquitectónico, dado que es el mayor esfuerzo del roadmap) | secuencial al final, post-ADR Accepted |
| Todas | haiku | — | git-ops (commits, no push sin verificar red) |
| Suite integrada | parent (director) | — | corre tras cada fase GREEN |

**Paralelización:**

- F0a ‖ F0b — decisión de networkx y redacción del ADR R4 son independientes entre sí (distintos dominios: dependencia técnica de graph vs arquitectura de conventions-as-data).
- F1 ‖ F2 — una vez F0a resuelto, F1 (graph/ CLI, `src/workflow`) y F2 (skill/sidecar, `graphify-out/graph-meta.json`) tienen fronteras de archivo disjuntas (`src/workflow/graph/*` vs `~/.claude/skills/graphify/SKILL.md` + `graphify-out/*`) — no hay conflicto de merge, corren en paralelo.
- F3 SIEMPRE secuencial al final: es transversal (puede tocar `src/workflow/transform/`, `data/conventions/`, posible migración `0017_`), y depende de un gate de usuario (ADR Accepted) que ninguna otra fase de esta wave comparte.

**Wait-gates:**

1. F1 espera la decisión networkx (F0a) — no se escribe código de centralidad sin ella.
2. F3 espera ADR R4 `Status: Accepted` por el usuario — **nunca implementar R4 sin ADR**, regla explícita del propio request (`blocked_by` frontmatter).
3. Esta wave es la última en prioridad del roadmap post-freeze (`tasks/roadmap/2026-07-05-post-freeze-implementation-roadmap.md`, Wave 4) — cede recursos si Waves 0-3 se reabren o requieren atención antes de completarse.
4. Migraciones: regla global forward-only (ITEP-0010) — si F3 requiere `0017_`, no se reescribe historial de migraciones existente.
5. reviewer-esquema corre pre-commit en F1 y F3 (F0a/F0b/F2 son docs/decisión, no código de producción con suite).
6. El director (parent) corre la suite integrada tras cada fase GREEN, antes de autorizar el siguiente commit.
