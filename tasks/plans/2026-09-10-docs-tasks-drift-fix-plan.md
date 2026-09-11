# Implementation plan — Docs + tasks/ drift fix (audit 2026-09-10 items 2–10)

Request: none — sourced from `tasks/audit/2026-09-10-tasks-and-primer-audit.md` (Summary / open items)
ADR: none new — flips ADR-0021 Proposed→Accepted (already implemented by W1 F2, `68d348e`)
Methodology: docs/tasks only — **no code, no migration, no tests touched**. Verification is
grep/`git status` against the anchors below, not the pytest suite.

---

## Verified anchors (confirmed in code/git, 2026-09-10)

- Bib dialect shipped: `bibliography/dialect.py`; `prisma bib export --dialect` `3087063`; `--resolve-xref` `3c824c7`.
- `bibkey` UNIQUE deliberately **rejected** — ADR-0019 §5 note 2026-06-02 (`9df3465`); `db/models/bibliography.py:130`
  still nullable/non-unique by design. Wave-3 Phase 1 (migration `0017_bibkey_unique_identity`) never ran —
  `0017` is `note_fts_and_alias`.
- PRISMA → literature note shipped: `c737c41` (C1), `e3b83d2` (C2 bulk), `03651eb` (C3 nvim); P2 hook deferred by the request itself.
- Security 2026-06-03: #1 HIGH mitigated `accept_to_note.py:48,287` + `test_accept_to_note.py:166`;
  #2 `import_bib_text` size cap `importer.py:899`; #3 EAV whitelist + caps `importer.py:54-62`;
  #4 TOCTOU — **no** `open(..., "x")`/`O_EXCL` in `accept_to_note.py` → still open; #5 LOW → still open.
- `workflow.bibliography.service` exists (CLAUDE.md:104 says "soon to move").
- On-disk LaTeX tree is `share/latex/` (CLAUDE.md says `shared/latex/`, renamed in `5502828`).
- `share/latex/ucimed/` bundle + nvim `tex_macros.lua`/`tex_paths.lua` (`088dfe8`, `84c5895`, `a7ac37a`) undocumented in CLAUDE.md.
- `nvim-plugin/lua/workflow/lectures.lua:50` — `build_eval` intentionally not implemented (closes the taxonomy-coverage Tier-3 remainder).
- `tasks/requests/2026-08-12-tikz-build-pipeline.md` is **already tracked** (added in `9598731`) → audit item 9 resolved.

---

## Target / design

Every `tasks/` status is scannable and true; CLAUDE.md + ADR INDEX match code. After this plan,
the only non-resolved audit rows are: #2 (git push — outside docs scope, needs network check) and
#10 (flake8 baseline — Luis's decision).

---

## Phases

### Phase A — Request closures
- `2026-06-01-bibliography-dialect-…` + `2026-06-03-prisma-to-literature-note` → `status: closed`,
  `resolution: implemented`, `closed_on`, `closed_by`, progress-log line.
- 8 frontmatter-less requests (`graph-neighbors-json`, `nvim-plugin-taxonomy-coverage`,
  `bibliography-service-extraction`, `content-service-split`, `nvim-plugin-plenary-harness`,
  `v1.14.0-reviewer-esquema-followups`, `topic-content-concept-bulk-import`, `xdg-path-consolidation`)
  → prepend minimal template frontmatter (`status: closed`, evidence = the release/commits already
  cited in each body). `source_agent: unknown` where the body doesn't say — never invented.

### Phase B — Plans + roadmap status
- wave0 / wave1 / tex-gf → `Status: SHIPPED` + commits. wave3 → `Status: CLOSED` (Phase 1 superseded,
  Phases 2–3 = Phase A of this plan). Roadmap → status line: waves 0,1 shipped; 3 closed; 2,4 not started.

### Phase C — Security
- `security/2026-06-03-roadmap-new-surfaces.md`: #1–#3 `fixed` w/ evidence; #4, #5 stay `open`;
  frontmatter `status: partially-fixed`.

### Phase D — Root files
- `git mv tasks/todo.md tasks/archive/2026-05-27-prisma-p2-todo.md`,
  `git mv tasks/WIKI-UPDATE-BRIEF.md tasks/archive/2026-05-23-wiki-update-brief.md`.
- New `tasks/todo.md` = this plan's checklist (root log restarts).

### Phase E — Docs
- CLAUDE.md: line 104 fix; `shared/latex` → `share/latex`; add `src/workflow/bibliography/` module
  bullet (closes bib-dialect docs box); add `share/latex/ucimed/` bullet; nvim `gf` macro-expansion note.
- ADR-0021 + `docs/ADR/INDEX.md` → Accepted (implemented W1 F2, `68d348e`).

### Phase F — Bookkeeping
- Audit summary table: resolution per row. Primer rewrite.

---

## Risks / out of scope

- **Out of scope:** git push (item 2), flake8 cleanup (item 10 — ★ Luis decides: accept 123 as baseline vs. clean),
  security #4 TOCTOU fix (real code → own request), `notes/sync.py:118` numeric-id request, `exercises.py:62` comment.
- **Risk:** closing a request whose acceptance box is not literally met — mitigated by stating the
  supersession (bibkey UNIQUE) explicitly in `resolution` notes instead of ticking the box.

---

## Verification

```bash
grep -L '^status:' tasks/requests/*.md          # only pre-template body-RESOLVED files may remain
grep -n 'soon to move\|shared/latex' CLAUDE.md  # → empty
grep -n 'Status' docs/ADR/0021-vault-full-text-search.md
git status --short                               # only intended paths
```
