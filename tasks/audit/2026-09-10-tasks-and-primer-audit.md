# tasks/ + .claude/primer.md Audit — 2026-09-10

Scope: verify `tasks/**` statuses and the local `.claude/primer.md` (mtime 2026-08-08) match code, DB, git and CLAUDE.md.

## Truth-sources

- **Suite** → `WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py` → **2627 passed, 3 skipped** (run 2026-09-10).
- **Lint** → `flake8 src/ tests/ --max-line-length=127 --max-complexity=10 --exclude=src/PRISMAreview` → **123** (src 47: 18 F401, 14 C901, 5 F841…; tests 76). CI hard-select `E9,F63,F7,F82` → **0**.
- **Git** → `git ls-remote public` = `d146b4c` (2026-08-08); HEAD `c3f6808`; `origin/master` = `45b60f9` (2026-08-13, ref local); `home/master` ref = `5f6c12c` (2026-03-13, never refreshed).
- **DB** → `workflow project list --json`: 17 projects, incl. the 7 `0060NP2xxx` rows (ids 2–8).
- **Code** → greps cited per row.

---

## A. `.claude/primer.md`

| Claim | Verdict | Issue |
|-------|---------|-------|
| Baseline 2627 passed, 3 skipped | ✅ resolved | exact match |
| `tests/test_database.py` collection error | ✅ resolved | still `ModuleNotFoundError: itep.database` |
| Lint noise only in `src/PRISMAreview/` | ⚠️ open | 123 findings outside it (47 src, 76 tests); CI hard-select clean |
| Next step: register 7 NP repos, "sin fila aún" | ⚠️ open | **already done** — 7 `GeneralProject` + `MainTopic` rows exist |
| `public` (GitHub) synced | ⚠️ open | public at `d146b4c`; **16 commits unpushed** (2026-08-10 → 09-08: ucimed, nvim tex_macros, sty) |
| Gitea down, 11 unpushed to origin | ⚠️ open | origin ref advanced to `45b60f9` (08-13) → was pushed later; HEAD still 11 ahead. `home` status unknown (stale ref) |
| 0060NP config drift, 5 findings exit 1 | ✅ resolved | still 5 findings, exit 1 |
| `exercises.py:62` stale `00EE-` comment | ✅ resolved (still true) | debt remains |
| "Estado: ITEP-0008 CERRADO" as active state | ⚠️ open | 16 commits since not reflected (UCIMED bundle, labguide, `tex_gf` nvim, `\labq`, standalone TikZ preamble) |

## B. `tasks/requests/`

| File | Verdict | Issue |
|------|---------|-------|
| `2026-06-01-bibliography-dialect-biblatex-bibtex-compat.md` | ⚠️ open | says `open`, **DONE**: `bibliography/dialect.py`, `--dialect`/`--resolve-xref` (`prisma/cli.py:247-293`); UNIQUE(bibkey) rejected in favor of calculated bibkey (`9df3465`) |
| `2026-06-03-prisma-to-literature-note.md` | ⚠️ open | says `open`, **DONE**: `prisma/accept_to_note.py`, nvim `prisma_note.lua`, `c737c41` |
| `2026-07-03-convention-engine-batch-transform.md` | ✅ resolved | open, correctly — no code, ADR-0023 not written |
| `2026-07-03-graphify-ideas.md` | ✅ resolved | open, correctly — Wave 4 not started |
| `2026-07-09-sync-numeric-zettel-id-skip.md` | ✅ resolved | open, correctly — `notes/sync.py:118` no coercion; `41315a0` fixed relation *targets* (`edges.py`), not own `id:`; no sync.py commit since W1 |
| `2026-08-12-tikz-build-pipeline.md` | ⚠️ open | open & correct, but **untracked** in git |
| 8 requests w/o frontmatter status (`graph-neighbors-json`, `nvim-plugin-taxonomy-coverage`, `bibliography-service-extraction`, `content-service-split`, `nvim-plugin-plenary-harness`, `v1.14.0-reviewer-esquema-followups`, `topic-content-concept-bulk-import`, `xdg-path-consolidation`) | ⚠️ open | all **DONE** per code; lack template frontmatter → invisible to status scans |
| 3 requests with body-only `RESOLVED` (`content-bib-link-cli`, `topic-content-cli-surface`, `calculated-bibkey-enforcement`) | ⚪ WIP-accepted | resolved, pre-template format |

## C. `tasks/plans/` + `tasks/roadmap/`

| File | Verdict | Issue |
|------|---------|-------|
| `2026-07-05-wave0` / `wave1` / `wave3` plans | ⚠️ open | shipped, no status marker |
| `2026-07-05-wave2` (fm_hash + ResearchQuestion) | ✅ resolved | not started (no `fm_hash`/`ResearchQuestion` in src) — consistent |
| `2026-07-05-wave4` | ✅ resolved | not started — consistent |
| `2026-08-19-tex-gf-macro-expansion.md` | ⚠️ open | shipped (`a7ac37a`, `tex_macros.lua`), no status |
| `roadmap/2026-07-05-post-freeze-implementation-roadmap.md` | ⚠️ open | no status; reality = waves 0,1,3 done, 2,4 pending |
| 15 older plans without frontmatter (2026-05-30 … 2026-06-06) | ⚪ WIP-accepted | pre-template; historical |

## D. Root files + security

| File | Verdict | Issue |
|------|---------|-------|
| `tasks/todo.md` | ⚠️ open | only PRISMA P2 plan (last touched 2026-05-27); header says "In progress", all 30 items `[x]`. Not a live todo |
| `tasks/lessons.md` | ⚪ WIP-accepted | 34 entries, last 2026-07-09; nothing since (no corrections logged 08-08→09-08) |
| `tasks/WIKI-UPDATE-BRIEF.md` | ⚠️ open | ground-truth for a 2026-05-23 wave; stale, belongs in archive |
| `security/2026-06-03-roadmap-new-surfaces.md` | ⚠️ open | HIGH path traversal marked `open` (line 120) but mitigated: `_SAFE_BIBKEY_RE` allowlist `accept_to_note.py:48,287`, tested in `test_accept_to_note.py` |

## E. Docs contradictions found en route

1. `CLAUDE.md:104` — "soon to move to a dedicated `workflow.bibliography.service`": module **exists** (`src/workflow/bibliography/service.py`). **OPEN.**
2. `docs/ADR/0021-vault-full-text-search.md:8` — `Status: Proposed`, but FTS5 `notes search` is live and documented in CLAUDE.md. **OPEN.**
3. CLAUDE.md has no mention of `share/latex/ucimed/` bundle nor nvim `tex_gf` macro expansion (16 unpushed commits). **OPEN.**

---

## Summary / open items

| # | File | Issue | Action needed |
|---|------|-------|---------------|
| 1 | `.claude/primer.md` | next step already done; push state wrong; 16 commits missing | rewrite state section |
| 2 | git | 16 commits not on `public`, 11 not on `origin` | push (network check first) |
| 3 | 2 requests `open` | actually DONE | close with `closed_by` |
| 4 | 8 requests no frontmatter | DONE, unscannable | add `status: closed` frontmatter |
| 5 | wave0/1/3 + tex-gf plans, post-freeze roadmap | no status | mark shipped / partial |
| 6 | `security/2026-06-03-…` | HIGH listed open, mitigated | mark fixed w/ evidence |
| 7 | `todo.md`, `WIKI-UPDATE-BRIEF.md` | stale | archive / reset |
| 8 | `CLAUDE.md:104`, ADR-0021 | stale claims | fix text / flip to Accepted |
| 9 | `tikz-build-pipeline.md` | untracked | `git add` |
| 10 | flake8 | 123 non-CI findings outside PRISMAreview | decide: accept as baseline or clean |
