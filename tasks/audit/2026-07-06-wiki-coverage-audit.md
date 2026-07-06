# WorkFlow docs/wiki/ Coverage Evaluation (2026-07-06)

Method note: context-mode MCP was broken in this environment (native module
NODE_MODULE_VERSION mismatch, better_sqlite3.node) — fell back to direct
Bash/Read against `uv run workflow ... --help` for all 18 top-level groups +
~90 subcommands, `nvim-plugin/doc/workflow.txt` + `lua/workflow/keymaps.lua`,
and all 12 `docs/wiki/*.md` pages (full read, not excerpts).

## 1. CLI coverage matrix (18 groups)

Legend: ✅ documented-with-examples · 🟡 mentioned-no-examples/partial · ❌ absent

| Group | Commands (leaf) | Wiki page(s) | Verdict |
|---|---|---|---|
| exercise | parse,list,sync,gc,export-moodle,create,create-range,build-exam,register,register-batch | Exercise-Workflow.md | 🟡 core commands ✅ with examples; **list --chapter, build-exam --balanceo/--balanceo-csv/--json/--fail-under, sync --strict-concepts, register/register-batch ❌ absent** |
| exam | scaffold-xml (legacy+weekly), validate | **none** | ❌ **no wiki page for `workflow exam` group at all** — weekly mode, --dc/--kind/--category-style, exam validate --strict/--json all undocumented |
| lectures | scan,link,split,build-eval | Lectures-Workflow.md, Getting-Started.md | 🟡 scan/link/build-eval ✅; **split --sync/--no-sync (new default-sync behavior) ❌ absent**; --project-root shown as required though CLI marks it "currently ignored" per ITEP-0011 — wiki doesn't correct this |
| graph | orphans,stats,export-dot,export-tikz,clusters,neighbors,resume,trace | Knowledge-Graph.md | 🟡 orphans/stats/export-dot/export-tikz/clusters/neighbors ✅ (older layer only); **--main-topic/--discipline-area/--topic filters (Phase 4E), --include-tags/--exclude-tags/--color-by/--layout/--depth/--cluster (F5), `graph resume`, `graph trace` — all ❌ absent** |
| evaluations | list,show,add,edit | Evaluation-CLI.md | ✅ |
| item | list,add,taxonomy | Evaluation-CLI.md | 🟡 list/add ✅; `item taxonomy --levels/--domains` ❌ absent |
| course | list,add,add-practice,practices | Evaluation-CLI.md | 🟡 list/add ✅; **add-practice/practices ❌ absent entirely** |
| prisma (bib/keyword/rationale/review/tag/checklist) | list,show,import,export,recompute-keys,accept-to-note,search,+subgroups | PRISMA-Review.md | 🟡 bib list/show/search/import/export, keyword/tag/rationale, review, checklist ✅; **bib accept-to-note (single+bulk), bib recompute-keys, export --dialect/--resolve-xref, import --recompute-bibkeys — all ❌ absent** |
| vault | info,validate,unify | Home.md (mention only), Zettelkasten-Notes.md (mention) | 🟡 mentioned, no worked example of `vault unify` flags (--rename-strategy, --backup-dir, --dry-run/--no-dry-run) |
| concept | list,show,add,tree,rm,rename,harvest | Concept-Skyfolding.md, Fleeting-Monolith-Flow.md | ✅ add/list/tree/rm/rename via ADR+skyfolding context; harvest ✅ (both flow pages cover it with examples) |
| notes | capture,create,edges,enums,init,link,list,new,new-id,promote,search,show,sync,tag | Zettelkasten-Notes.md | 🟡 init/sync/edges ✅ with examples; **capture, create (bibkey literature note), promote, search, new-id, enums — all ❌ absent from wiki text** (capture/promote/search only appear in nvim workflow.txt, not in any wiki page); worse, Zettelkasten-Notes.md §"Creacion de notas" (lines 342-380) **actively asserts "Ni el CLI workflow notes... exponen un comando para crear notas nuevas... intencional, no un bug"** — this is now false (notes new/capture/create all exist) |
| import | (bulk YAML import) | Concept-Skyfolding.md, Fleeting-Monolith-Flow.md | ✅ well covered via skyfolding docs; not in Home.md quick-reference table though |
| topic | add,list,show,import(deprecated) | not directly; Concept-Skyfolding.md covers the YAML shape | 🟡 topic CLI itself (add/list/show) ❌ absent; only the YAML-import path documented |
| content | add,list,show,link-bib,bib-links,unlink-bib | not covered | ❌ absent from any wiki page |
| validate | notes [--strict-main-topic/--strict-concepts/--graph], exercises [--recursive] | scattered mentions in Home.md quick-ref only | 🟡 command exists in Home.md ref block; **validate exercises unit-lint (\si/\SI vs SetUnits.sty, F2a) and validate notes --graph (ITEP-0013 cycle/orphan check) ❌ absent** from any prose page |
| db | migrate,migrate-xdg,discipline-areas,disciplines,import-codes | Home.md (mention only) | 🟡 listed in quick-ref table, no worked examples/no dedicated page |
| project | propose-maturation | Home.md (mention only) | 🟡 same as db |

### Counts (CLI side, by group, 18 groups)
- ✅ documented-with-examples: 3 (evaluations, concept, import-via-skyfolding)
- 🟡 mentioned/partial: 12 (exercise, lectures, graph, item, course, prisma, vault, notes, topic, validate, db, project)
- ❌ absent: 3 (exam, content, — and notes-new-command-family is worse than absent: actively wrong)

At the **flag/subcommand** level the gap is much larger — nearly every command shipped 2026-06-26 through 2026-07-05 (the "freeze window" F1-F5 bundle) is undocumented in wiki prose: build-exam balance report, list --chapter, validate exercises unit-lint, concept harvest, exam group entirely, notes capture/create/promote/search, notes sync --rebuild-index/--rebuild-edges, graph tag/main_topic filters.

## 2. Neovim commands + keymaps coverage

Side A ground truth: `nvim-plugin/doc/workflow.txt` (413 lines, itself the primary
nvim reference) + `lua/workflow/keymaps.lua` (24 keymaps total under `<leader>z`
default prefix).

Full keymap list (from keymaps.lua): sn, se, v, p, te, ti, tc, np, ns, nn, nt,
nl, ne, nc, en, er, ec, eg, ei, eI, eb, ek, nC, nf.

- workflow.txt §3 KEYMAPS only prose-documents **nC, nf** (Wave 1) and defers
  **en, er, ec, eg, ei, eI, eb, ek** (Wave 5) to a bullet list — the pre-Wave-5
  keymaps (sn, se, v, p, te, ti, tc, np, ns, nn, nt, nl, ne, nc) are NOT listed
  in §3 at all, only reachable by reading keymaps.lua directly (doc says "See
  lua/workflow/keymaps.lua for the full mapping table" — i.e. nvim's own doc
  admits incompleteness).
- **docs/wiki/ side**: zero wiki page mentions any `<leader>z*` keymap except
  Zettelkasten-Notes.md's STALE table (prefix shown as `<leader>w`, listing
  only s/v/p/te-ti-tc/tb-tk-tr — none of which match the real prefix or the
  real Wave-5 keymap set). Evaluation-CLI.md has one correct small table
  (`<leader>zte/zti/ztc`) — the only wiki keymap table that matches reality.
- Verdict: **ei, eI, eb, ek, ns, nC (as named in the task) are absent from
  wiki entirely** — confirmed. They exist only in workflow.txt/keymaps.lua.
  nC IS documented in workflow.txt (§2.13) but not in any wiki page.

### Nvim commands (:Workflow*) coverage on wiki side
~30 `:Workflow*` commands exist (utility, note, edge, eval, PRISMA, taxonomy
pickers, graph, lecture, biblink, bib-import, Wave5 enum/graph-validate,
search/capture). **Not one is mentioned in any docs/wiki/*.md page.** Wiki
Evaluation-CLI.md and Zettelkasten-Notes.md give keymap tables but never
`:Workflow*` command names, and no wiki page mentions
:WorkflowConceptPicker, :WorkflowGraphStats/Orphans, :WorkflowPrismaAcceptToNote,
:WorkflowNoteCapture/:WorkflowNoteSearch, :WorkflowValidateGraph, etc.

## 3. End-to-end flow coverage

| Flow | Wiki page | Verdict |
|---|---|---|
| (a) fleeting-monolith → split --sync → harvest → import | Fleeting-Monolith-Flow.md | ✅ **current and complete** — explicitly covers `lectures split` default --sync, the two concept lifecycles (skyfolding-first / harvest-later), `concept harvest` + `import` closing the loop, and cross-links Concept-Skyfolding.md. Dated 2026-07-05, matches shipped reality. |
| (b) captura rápida en nvim (nC) → promote → search | none | ❌ **no wiki page walks this.** `:WorkflowNoteCapture`/`nC` only in nvim workflow.txt §2.13; `notes promote` CLI has zero wiki mention (only appears as the OLD/wrong `<prefix>p` "move inbox→root" description in Zettelkasten-Notes.md, which describes pre-ITEP-0011 mechanics, not the current flip-only `notes promote REFERENCE` semantics — "flip-only, never moves the file" per CLI help, directly contradicting the wiki's "mueve de inbox/ a raiz del vault"); `notes search`/`nf` has zero wiki mention anywhere. |
| (c) exam weekly production (scaffold-xml --week --dc --kind, validate) | none | ❌ **no wiki page at all** — no Exam-CLI.md exists; Exercise-Workflow.md doesn't mention exam group; Home.md quick-ref doesn't list `workflow exam` in its command block. |
| (d) PRISMA accept-to-note (single + bulk) | none | ❌ **absent from PRISMA-Review.md** (page predates this feature and ADR-0019/0020 dialect work); also absent from nvim-side wiki coverage even though :WorkflowPrismaAcceptToNote is a real, documented (in workflow.txt) command. |

Only 1 of 4 target flows (a) is documented end-to-end and current. Flows b/c/d
have zero wiki coverage.

## 4. Staleness findings (contradicts shipped reality)

1. **Getting-Started.md** — "Deberias ver los 6 grupos de comandos: exercise,
   graph, lectures, notes, tikz, validate" — actual count is **18 groups**
   (missing: exam, evaluations, item, course, prisma, vault, concept, import,
   topic, content, db, project). Entire page describes pre-ITEP-0011 per-project
   `slipbox.db` note model as canonical ("Registrar notas en la base de datos
   local") and shows `--project-root` as load-bearing, when CLI help states it
   is "currently ignored." No mention of vault/capture/promote/search at all.
2. **Zettelkasten-Notes.md** — internally self-contradictory: top section
   (lines 20-34) correctly describes GlobalBase vault unification (ITEP-0011),
   but the later "Creacion de notas" section (lines 342-380) asserts notes
   creation is deliberately NOT exposed by the CLI ("Ni el CLI `workflow notes`
   ni el plugin... exponen un comando para crear notas nuevas... intencional,
   no un bug") — false: `notes new`, `notes capture`, `notes create` (bibkey
   literature) all exist and ship today. The keymap table in that section also
   uses the wrong prefix (`<leader>w` vs actual default `<leader>z`) and a
   stale keymap set that doesn't match keymaps.lua.
3. **Knowledge-Graph.md** — data-sources table states notes/citations live in
   "Local (slipbox.db)" — contradicts ITEP-0011 (notes are GlobalBase since
   P1). No mention of the F5 real Tag/MainTopic propagation, --include-tags/
   --exclude-tags/--color-by/--layout, or the Phase 4E --main-topic/
   --discipline-area/--topic filters — the whole filter/coloring/graph
   resume+trace surface added since is invisible.
4. **Lectures-Workflow.md** — shows `scan`/`link` with `--project-root` as if
   required/meaningful (CLI says "reserved... currently ignored"); `split`
   examples omit the new `--sync/--no-sync` default-sync behavior entirely
   (this is the mechanism Fleeting-Monolith-Flow.md now depends on).
5. **Home.md** — Guias index table is missing **both** Fleeting-Monolith-Flow.md
   and Concept-Skyfolding.md (both exist, both dated 2026-07-05, neither
   linked from the wiki's own index page). Quick-reference command block
   omits `exam`, `concept`, `notes capture|create|promote|search`, `content`,
   `topic` entirely.
6. **PRISMA-Review.md** — "Phases" table stops at P2 and doesn't reflect
   accept-to-note (Wave C) or bibliography dialect work (ADR-0019/0020:
   --dialect, --resolve-xref, recompute-keys).

Staleness count: **6 distinct pages** carry factually incorrect or
significantly outdated content relative to shipped code (Getting-Started,
Zettelkasten-Notes, Knowledge-Graph, Lectures-Workflow, Home, PRISMA-Review).
Fleeting-Monolith-Flow.md, Concept-Skyfolding.md, Architecture.md, Exercise-
Workflow.md, Evaluation-CLI.md, LaTeX-Macros.md are reasonably current for
their scope (Exercise-Workflow.md missing only the newest F1/F2 flags).

## 5. Prioritized fix list (top 10, ordered by daily-use impact)

1. **Fix Zettelkasten-Notes.md "Creacion de notas" section** — delete the
   false "no create command" claim; document `notes new`/`notes capture`/
   `notes create` (bibkey) with real flags and current keymap prefix `<leader>z`
   with correct Wave-5 keymap table. (Target: Zettelkasten-Notes.md)
2. **Write flow (b) end-to-end**: capture (nC/`notes capture`) → promote
   (`notes promote`, flip-only semantics) → search (nf/`notes search`).
   (Target: new page or Zettelkasten-Notes.md section)
3. **Create `Exam-CLI.md`** (or fold into Exercise-Workflow.md) covering
   `exam scaffold-xml` legacy vs weekly mode, `--dc/--kind/--category-style`,
   `Practica-N → PC-N → Tema #(N+1)` offset, and `exam validate --strict/--json`.
   (Target: new page)
4. **Add PRISMA accept-to-note flow (single+bulk) + dialect export** to
   PRISMA-Review.md — this is flow (d), fully shipped, zero wiki mention.
   (Target: PRISMA-Review.md)
5. **Fix Getting-Started.md group count and DB model** — 18 groups not 6;
   replace slipbox.db-as-canonical narrative with vault/GlobalBase pointer to
   Zettelkasten-Notes.md; correct `--project-root` framing.
   (Target: Getting-Started.md)
6. **Fix Home.md index** — add Fleeting-Monolith-Flow.md + Concept-Skyfolding.md
   links; expand quick-reference command block with exam/concept/notes
   capture-create-promote-search/content/topic. (Target: Home.md)
7. **Update Knowledge-Graph.md** — fix stale slipbox.db data-source claim; add
   --main-topic/--discipline-area/--topic filters, --include-tags/
   --exclude-tags/--color-by/--layout/--depth/--cluster, and `graph resume`/
   `graph trace` commands. (Target: Knowledge-Graph.md)
8. **Add build-exam balance report + list --chapter + sync --strict-concepts**
   to Exercise-Workflow.md (F1/F2 freeze-window features, exercise-bank daily
   use). (Target: Exercise-Workflow.md)
9. **Document nvim `:Workflow*` command surface in wiki** — currently zero
   wiki page names a single `:Workflow*` command; at minimum cross-link
   workflow.txt from each relevant wiki page (notes commands ↔
   :WorkflowNoteCapture/:WorkflowNoteSearch/:WorkflowPromote; graph commands ↔
   :WorkflowGraphStats/:WorkflowGraphOrphans; concept ↔
   :WorkflowConceptPicker). (Target: all relevant pages)
10. **Add `content` CLI + `course add-practice/practices`** — both fully
    absent from any wiki page despite being shipped, non-trivial surfaces.
    (Target: new Content-CLI section or Evaluation-CLI.md addendum)

## Report-back summary

- CLI side (18 groups): ~3 ✅ / ~12 🟡 / ~3 ❌ at group level; at flag level the
  freeze-window (2026-06-26 → 2026-07-05) features are almost entirely
  undocumented in prose across every page.
- Nvim side: workflow.txt itself is the only complete reference; **zero**
  `:Workflow*` commands and **zero** correct keymap tables appear in
  docs/wiki/ (Evaluation-CLI.md's small picker table is the one exception and
  is correct).
- Top 5 gaps: (1) Zettelkasten-Notes.md false "no create command" claim,
  (2) no exam CLI page, (3) no PRISMA accept-to-note flow, (4) Getting-
  Started.md wrong group count/stale DB model, (5) Knowledge-Graph.md stale
  slipbox.db claim + missing F5/Phase-4E filter surface.
- Staleness: 6 pages carry outdated/incorrect content (Getting-Started,
  Zettelkasten-Notes, Knowledge-Graph, Lectures-Workflow, Home, PRISMA-Review).
