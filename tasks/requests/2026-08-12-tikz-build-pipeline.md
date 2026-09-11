---
id: 20260812-tikz-build-pipeline
title: "`workflow tikz build` exists but doesn't match how TikZ assets actually live: no vault-central support, no palette flag, no Inkscape-pdf_tex guard, no naming convention"
type: gap
source_agent: user
opened_on: 2026-08-12

status: open
resolution: unresolved
priority: P2
severity: recurring-friction

labels:
  - cli
  - tikz
  - adr
  - vault

components:
  - workflow.tikz.builder
  - workflow.tikz.cli

adr_refs:
  - "0006"
  - "0015"
related_requests: []
related_gaps: []
duplicates: []
blocked_by: []

assignee: unassigned
target_release: unassigned
implementation: []
closed_on: null
closed_by: null

acceptance_criteria: []
verification: []
---

# Request: close the gap between `workflow tikz build` and real vault usage

## Context

ADR-0006 (`docs/ADR/0006-tikz-asset-pipeline.md`, *Accepted*, 2026-03-25)
decided that TikZ diagrams are standalone assets compiled independently to
PDF+SVG, incremental by source hash, with a CLI (`tikz build`, `tikz list`).

**Correction to the original premise of this request: the CLI already
exists.** Verified 2026-08-12 by grepping `src/` for `tikz` and reading the
matches directly:

- `src/workflow/tikz/builder.py` — pure builder core: `find_tikz_sources`,
  `compute_hash` (SHA-256), `compile_tikz` (`latexmk -pdf` by default, engine
  selectable among `latexmk|pdflatex|xelatex|lualatex`), `convert_to_svg`
  (`pdf2svg` preferred, `dvisvgm` fallback), `build_all` (incremental, keyed
  by full source path + hash).
- `src/workflow/tikz/cli.py` — `tikz build [--assets-dir --output-dir
  --force --no-svg]`, `tikz list [--assets-dir]`, `tikz clean [--output-dir]`.
- Wired: `src/main.py:8,31` (`from workflow.tikz.cli import tikz` /
  `cli.add_command(tikz)`).
- Tested: `tests/workflow/test_tikz_builder.py`.
- Git history: `a521914 feat: complete Phases 1c, 1d, 2, and 3` then
  `b2135e8 refactor: ADR-0013 Batches 3+4 — CLI split, test coverage, lazy
  engine, __all__ exports`. So this shipped as part of a broader ADR-0013
  refactor pass, not a dedicated tikz milestone — plausibly why it never
  reached the `0000AL-Lectures`/vault workflow.

**What the ADR specified but the shipped code does NOT do** — this is the
actual gap, verified against the same two files:

1. **State store is a JSON file, not a DB table.** ADR-0006 §Implementation
   Notes: "Build state stored in local `slipbox.db` (new `TikzAsset` table:
   filename, source_hash, last_build)." Confirmed no `TikzAsset` model exists
   anywhere (`grep -rln TikzAsset src/` → no matches). The shipped code uses
   `output_dir/.tikz-state.json` (`builder.py` `_STATE_FILE`, `_load_state`/
   `_save_state`) instead. Functionally incremental-by-hash either way, but
   `tikz list` has no `--json` state view and nothing queryable from
   `workflow validate` or the DB layer the way other subsystems are.
2. **No `--palette` flag.** `share/latex/sty/SetFormatStandalone.sty` and
   `share/latex/sty/ColorsSemantic.sty` already exist in this repo (both
   confirmed present) — built by hand in the 2026-08-12 vault session
   specifically to give a standalone TikZ source a canonical preamble with a
   `palette=UCR|UCIMED|Ufide|Nord` option. `compile_tikz` has no notion of
   palette; a caller would have to bake the palette choice into the `.tex`
   source itself (which is what actually happened — 22 figures, by hand).
   `tikz build` should accept `--palette NAME` and either pass it through as
   a LaTeX class/package option or validate that the source already declares
   one matching it.
3. **No vault-central support — only per-project `assets/tikz/`.** ADR-0006
   hardcodes `assets/tikz` → `assets/figures` (see the CLI defaults above).
   But ADR-0015 (`docs/ADR/0015-zettelkasten-dailly-work.md:51`) says figures
   live in the **vault-central** `0000II-ImagesFigures/`, and "markdown only
   references the svg output, LaTeX projects includes PDF." These two ADRs
   were never reconciled: 0006 assumes one `assets/tikz` per project, 0015
   assumes one flat directory for the whole workspace. The 2026-08-12 session
   worked entirely against `0000II-ImagesFigures/` — nothing under any
   project's `assets/tikz/`. `--assets-dir`/`--output-dir` defaults already
   make pointing the CLI at the vault directory *possible* today
   (`workflow tikz build --assets-dir ~/01-U/0000II-ImagesFigures --output-dir
   ~/01-U/0000II-ImagesFigures`), so this may be a documentation/ADR-conflict
   fix more than a code fix — flag it for whoever picks this up to decide
   whether source and output should be the *same* flat directory (current
   vault layout: `.tex`, `.pdf`, `.svg` siblings in one directory) or ADR-0006's
   separate-directories model, and amend whichever ADR loses.
4. **No naming convention enforced or documented.** Neither ADR defines one.
   The vault in practice uses `<Concept>-<Institution><YYYY><CourseCode>-
   I<NNN>.tex` (see `~/01-U/0000II-ImagesFigures/`, e.g.
   `SimetriasBiotSavartAmpere-UCIMED2026CBI07-I001.tex`). `tikz list` has no
   `--validate-naming` or similar; nothing stops a source from being added
   without following it.
5. **No guard against Inkscape `.pdf_tex` siblings.** Verified count: 5 such
   pairs exist under the vault (4 in `530_S439fi14-Sears/`, 1 in `10MC/own/`).
   For these, the `.svg` is the Inkscape *source* (not a build artifact) and
   the `.pdf` is multi-page (PDF+LaTeX export, meant to be `\input`-ed
   alongside a `.pdf_tex` overlay, not converted by `pdf2svg`). Running
   `tikz build` with `--assets-dir`/`--output-dir` pointed at a directory
   containing these would treat the `.svg` as disposable and either skip or
   clobber it depending on hash-cache state — `find_tikz_sources` only
   globs `*.tex`, so today's actual risk is `convert_to_svg` overwriting the
   Inkscape-authored `.svg` if `build_all` is ever pointed at a source `.tex`
   that happens to share a stem with one of these 5. Low probability under
   current per-file directory layout, but real once source+output directories
   are unified per gap 3 above.

## Evidence of cost

Session 2026-08-12 in `~/01-U` (see `~/01-U/.claude/primer.md`, "Session
2026-08-12: piloto visión" section, and the CI0007 figure-migration entries
in the same file across prior sessions): 22 fragment `.tex` figures in the
vault were converted to standalone by hand across 3 subagents, compiled one
at a time with `latexmk -lualatex`, converted with `pdf2svg` one at a time,
because `tikz build` — despite existing — was never pointed at the vault and
has no palette/naming support to make that pointing turn-key. Final coverage
reached (263 PDF / 272 SVG, 0 PDF without SVG) only because a human tracked
it file by file.

```bash
# What happened instead of one command:
for f in *.tex; do
  latexmk -lualatex "$f"
  pdf2svg "${f%.tex}.pdf" "${f%.tex}.svg"
done
# repeated by 3 separate subagents, coordinated by hand
```

## Proposal

1. `--palette UCR|UCIMED|Ufide|Nord` on `tikz build`: inject or validate
   against `SetFormatStandalone.sty`'s existing `palette=` class option
   (reuse the contract already implemented in `share/latex/sty/
   SetFormatStandalone.sty` + `ColorsSemantic.sty` — do not invent a second
   palette mechanism).
2. Reconcile ADR-0006 vs ADR-0015 on asset location: decide whether
   `assets-dir`/`output-dir` collapsing to the same flat vault directory is
   the sanctioned mode, document it in whichever ADR needs amending, and add
   a `--vault` convenience flag if that's the resolution (equivalent to
   `--assets-dir --output-dir` both pointed at the configured vault figures
   path, reusing whatever workspace-root/vault-path resolution
   `workflow.paths`/`workflow.vault.paths` already expose per the
   2026-08-08 XDG consolidation).
3. Document (and optionally lint via `tikz list --check-naming`) the
   `<Concept>-<Institution><YYYY><CourseCode>-I<NNN>` convention observed in
   the vault, or whatever convention gets formally adopted.
4. Add a skip guard in `build_all`/`find_tikz_sources`: any `.tex` whose
   stem has a sibling `.pdf_tex` file is not a `tikz build` source (it's an
   Inkscape PDF+LaTeX export) — skip it outright, don't just rely on
   directory separation.

## Out of scope

- Migrating `TikzAsset` state from JSON file to a DB table — the JSON state
  file works for incremental builds today; only revisit if/when a consumer
  needs to query build state from the DB layer (e.g. `workflow validate`).
- `tikz watch` (ADR-0006 lists it as MAY, not MUST/SHOULD).
- Retroactively renaming the 263 already-compiled vault figures to a new
  naming convention if one is adopted — separate migration, not this request.

## Progress log

- 2026-08-12 — opened. Verified `tikz build`/`list`/`clean` already exist
  (grep + read of `src/workflow/tikz/{builder,cli}.py`, `src/main.py:8,31`,
  `tests/workflow/test_tikz_builder.py`); original premise ("nothing
  implemented") corrected in place before writing the gap list above.
