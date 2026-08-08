---
id: 20260808-itep-0008-two-layer-directory-contradiction
title: ITEP-0008 "two-layer directory structure" contradicts ITEP-0000's flat layout and the implemented root_dir property
type: bug
source_agent: user
opened_on: 2026-08-08

status: closed
resolution: fixed
priority: P0
severity: blocker

labels:
  - adr
  - itep
  - documentation
  - config

components:
  - workflow.db.models.project
  - itep.create
  - itep.defaults
  - itep.structure
  - workflow.project.cli
  - workflow.paths
  - workflow.config
  - workflow.vault.paths

adr_refs:
  - ITEP-0000
  - ITEP-0008
  - ITEP-0009
related_requests: []
related_gaps: []
duplicates: []
blocked_by: []

assignee: unassigned
target_release: unassigned
implementation:
  - "8606444 feat(paths): add WORKFLOW_WORKSPACE_ROOT and derive subsystem defaults"
  - "596ea25 fix(itep): correct GeneralDirectory names and topic placeholder handling"
  - "ce7a395 test(paths): pin workspace-root derivation contract and fix order-dependent test"
  - "e068285 feat(itep): expose general-project fields as inittex flags"
  - "6751bd7 feat(project): add `workflow project adopt` and `workflow project list`"
  - "c9cc174 refactor(vault): make .vault_pointer a timestamp-only marker"
  - "2045f7d feat(validate): add `workflow validate config` drift detector"
  - "Phase 5 (this change, uncommitted at time of writing): docs — ITEP-0008 ADR amended, docs/ADR/INDEX.md and CLAUDE.md updated, this request closed"
closed_on: 2026-08-08
closed_by: Luis Fernando Umaña Castro

acceptance_criteria:
  - "ITEP-0008 no longer contains a diagram or prose implying `DDTTAA-YYPP-title/` is nested inside a physical `DDTTAA-title/` directory. The 'Two-layer directory structure' section is rewritten to state the layout is flat on disk: `DDTTAA-YYPP-title` project directories are siblings of an (optional, DB-absent) `DDTTAA-title` area directory under the workspace root, and the area/project hierarchy exists only as `MainTopic.parent_id` in the DB."
  - "The term 'discipline root' is either defined explicitly (as the workspace root directory, e.g. `~/01-U`) in a glossary/definitions subsection of ITEP-0008, or removed and replaced with 'workspace root' throughout (lines currently at 95, 228, 272)."
  - "ITEP-0008's MUST/SHOULD/MAY rules are amended so the SHOULD 'area directory... exist as a physical directory' and MAY 'area directory... omitted' language are reconciled with the flat-layout correction — either both removed as vestigial, or rewritten to describe an optional non-nesting marker directory."
  - "ITEP-0000 §'Main topic directory structure' and ITEP-0008 no longer disagree on `ABS_PARENT_DIR`: ITEP-0008 states explicitly that `itep.defaults.DEF_ABS_PARENT_DIR` should resolve to the actual workspace root used by the project (not a hardcoded `~/Documents/01-U/00-Fisica`), and cross-references the fix required in `itep.defaults` (see below)."
  - "`src/itep/defaults.py:7-10` `_DEFAULT_PHYSICS_DIR` no longer points at a nonexistent path. Either it defaults to an env-var-required value that fails loudly with a clear error when `WORKFLOW_PHYSICS_DIR` is unset, or it defaults to the real workspace convention documented in ITEP-0000/ITEP-0008 amendment."
  - "`src/itep/structure.py:53-57` `GeneralDirectory` StrEnum values (`00AA-Lectures`, `00II-ImagesFigures`, `00BB-Library`, `00EE-ExamplesExercises`) are corrected to match the real workspace naming (`0000AL-Lectures`, `0000II-ImagesFigures`, `0000BB-Library`, `0000EE-ExamplesExercises`) or ITEP-0008 documents the discrepancy as a deliberate, tracked migration with a target date."
  - "A regression test in `tests/itep/` asserts `GeneralDirectory` values match the CLAUDE.md-documented workspace directory names, so a future rename doesn't silently re-break `relink`."
  - "`itep create-general`'s CLI (`src/itep/create.py` `cli()`) exposes `--area-code`, `--title`, `--year-init`, and `--project-initials` options that thread through to `create_general(...)`'s existing kwargs, so historical repos can be adopted without a one-off Python script."
  - "`_create_dirs_from_tree` (`src/itep/create.py:76-88`) skips (or errors on) any tree entry still containing an unexpanded `{t_idx`/`{t_name}` placeholder when `topics` is empty, instead of `mkdir`-ing the literal placeholder string as a directory name."
  - "A `workflow project` (or `itep`) `adopt` command exists that registers a pre-existing on-disk git repo as a `GeneralProject` row (via `MainTopic`/`GeneralProject` DB inserts) without recreating the tree or overwriting existing files, so repos migrated by hand can be backfilled into `workflow.db`."
  - "`workflow project list` exists and prints/`--json`-emits every registered `GeneralProject`/`LectureProject`, so registration status is checkable without querying the DB directly."
  - "A `workflow validate config` (or equivalent) command exists that compares each area's `config.yaml` `data.abs_parent_dir`/`abs_project_dir` against both `workflow.db` and the real filesystem, and flags drift (e.g. the confirmed-stale `0060NP-NuclearPhysics/config.yaml` pointing at `/home/luis/Documents/01-U/00-Fisica/60NP-NuclearPhysics/`, and its `code: 60NP` two-digit scheme)."
  - "`.vault_pointer` files are either regenerated from `WORKFLOW_VAULT_ROOT`/`workflow.config` on every relevant command (so they can't drift), or the mechanism is removed entirely in favor of the single existing `WORKFLOW_VAULT_ROOT`/`vault_path` resolution path."
  - "A single `WORKFLOW_WORKSPACE_ROOT` env var is introduced in `src/workflow/paths.py`/`src/workflow/config.py`/`src/itep/defaults.py`, with `WORKFLOW_DATA_DIR`, `WORKFLOW_VAULT_ROOT`, and `WORKFLOW_PHYSICS_DIR` deriving from it when they are themselves unset (each remains individually overridable)."

verification:
  - "`grep -rn 'DDTTAA-title/' docs/ADR/ITEP-0008-general-project-nomenclature.md` returns no nested-tree diagram — only sibling/flat examples remain."
  - "`grep -n 'discipline root' docs/ADR/ITEP-0008-general-project-nomenclature.md` either returns 0 matches, or every match resolves against an explicit definition earlier in the same document."
  - "`python -c \"from itep import defaults; print(defaults.DEF_ABS_PARENT_DIR)\"` does not print a path containing `Documents/01-U` unless `WORKFLOW_PHYSICS_DIR` is explicitly set to that value."
  - "`python -c \"from itep.structure import GeneralDirectory; print(list(GeneralDirectory))\"` output matches the four real directory names in `~/01-U` (`0000AL-Lectures`, `0000II-ImagesFigures`, `0000BB-Library`, `0000EE-ExamplesExercises`)."
  - "`pytest tests/itep/ -k general_directory -v` passes with the new regression test."
  - "`ls ~/01-U | grep -E '^DDTTAA-YYPP'` pattern check: confirm zero directories anywhere in the real workspace currently use the two-layer nested form described in the current (unfixed) ITEP-0008."
  - "`inittex --help` (`itep create-general` entry point) lists `--area-code`/`--title`/`--year-init`/`--project-initials`; running it against a pre-existing directory year (e.g. `year_init=23`) creates a `GeneralProject` row with `year_init=23` without a Python one-off."
  - "`grep -n 't_idx' src/itep/create.py` shows the empty-`topics` branch either `continue`s past unexpanded-placeholder entries or raises, and a fresh `inittex` general-project run with zero topics produces no directory whose name contains a literal `{` character (`find <new_project_dir> -name '*{*'` returns nothing)."
  - "`workflow project adopt --help` (or equivalent) exists and, run against one of the 7 already-migrated `0060NP-NuclearPhysics/pro/*` repos, inserts a `GeneralProject`/`MainTopic` row without touching the repo's files (`git status --short` in the repo stays empty after running it)."
  - "`workflow project list` (or `--json`) run after the fix shows `0831PI-26SK-Sketchbook` (id=1) and, once adopted, the 7 `0060NP` repos."
  - "`workflow validate config` (or equivalent) run against `0060NP-NuclearPhysics/config.yaml` reports the `abs_parent_dir`/`abs_project_dir` drift and the `code: 60NP` legacy scheme as findings."
  - "`cat ~/01-U/0060NP-NuclearPhysics/.vault_pointer` either no longer exists (mechanism removed) or resolves to `/home/luis/01-U/0000AV-Vault` after the fix, matching `WORKFLOW_VAULT_ROOT`."
  - "`python -c \"from workflow import paths; import os; os.environ['WORKFLOW_WORKSPACE_ROOT']='/tmp/x'; print(paths.data_dir())\"` (or equivalent for vault/physics dirs) shows the new root propagating to at least one of the three subsystem defaults when its own env var is unset."
---

# Request: ITEP-0008 "two-layer directory structure" contradicts ITEP-0000's flat layout and the implemented `root_dir` property

## Context

ITEP-0000 (`docs/ADR/ITEP-0000-project-structure.md`) is the foundational ADR for
where project directories physically live. It defines:

- `ABS_PARENT_DIR=/home/luis/Documents/01-U/00-Fisica` (line 37) — the parent
  directory projects are created under.
- `${ABS_PARENT_DIR}/${ROOT}` (line 325) — a `GeneralProject` hangs directly off
  `ABS_PARENT_DIR`, with no intermediate area-code subdirectory.

The implemented code agrees with this flat model:

- `src/itep/create.py:329` — `root_dir = parent_dir / project.root_dir`: one join,
  no nested area directory.
- `src/workflow/db/models/project.py:111-120` — `GeneralProject.root_dir` returns
  `f"{self.area.code}-{self.year_init:02d}{self.project_initials}-{slug}"`: the
  `DDTTAA` area code is baked into the leaf directory's **name**, never used as a
  parent directory segment.
- There is no concatenation anywhere in `src/itep/` that builds `area.code` as a
  standalone path component (`grep -n "area.code" src/itep/*.py` only turns up
  string interpolation into a single directory name and DB lookups).

ITEP-0008 (`docs/ADR/ITEP-0008-general-project-nomenclature.md`), marked
`status: Implemented`, contradicts this. Its "Two-layer directory structure"
section (line 80) presents:

```
DDTTAA-title/                        ← Area directory  (no GeneralProject in DB)
└── DDTTAA-YYPP-title/               ← Project directory (GeneralProject in DB)
```

and a worked example (lines 111-114):

```
0060NP/                                 ← Nuclear Physics area directory
├── 0060NP-25SF-ScintillatingFibers/    ← Master's thesis (created 2025)
├── 0060NP-26BE-BerylliumErosion/       ← 7Be meta-analysis (created 2026)
└── 0060NP-26SC-ScintillatorCharact/    ← Scintillator characterization (created 2026)
```

showing `0060NP-*` projects nested one level inside a physical `0060NP/`
directory. The SHOULD/MAY rules (lines 94-96, 270-272) reinforce this: "the area
directory `DDTTAA` SHOULD exist as a physical directory" and "MAY be omitted and
the project directory placed directly in the discipline root."

The undefined term **"discipline root"** appears three times (lines 95, 228,
272) and is never defined anywhere in the document — it is load-bearing for the
MAY-omission rule but has no referent.

`status: Implemented` is misleading: what actually shipped was the **naming**
convention (`DDTTAA-YYPP` codes, `src/itep/naming.py`,
`MainTopic.parent_id` for the area↔project DB relationship — confirmed by the
already-closed request `2026-05-27-topic-reroot-discipline-area.md`, which
explicitly notes "the 'two-layer directory' naming rule is unchanged; only the
DB-level FK root of `Topic` changes"). The physical nesting-on-disk half of the
ADR was never implemented, and the real workspace (`~/01-U`) has **zero**
directories in the `DDTTAA-title/DDTTAA-YYPP-title/` nested form — every project
directory that exists is flat.

## Locked decision

**ITEP-0000 governs by precedence.** It is the foundational structure ADR and
matches what the code (`create.py`, `project.py`) actually does. ITEP-0008 is
amended, not ITEP-0000. Going forward:

- The on-disk layout is **flat**: `DDTTAA-YYPP-title` project directories are
  siblings of each other (and of an optional, DB-absent `DDTTAA-title` marker
  directory) directly under the workspace root — never nested one inside the
  other.
- The area→project hierarchy exists **only in the database**, via
  `MainTopic.parent_id` (area-level row, `parent_id=NULL`) → (project-level row,
  `parent_id=<area row id>`).
- The `DDTTAA-` prefix baked into the project directory's own name (per
  `GeneralProject.root_dir`) already satisfies the ADR's stated goal of
  lexicographic ordering discipline → topic → area → chronology — no physical
  nesting is required to achieve it.
- "discipline root" must be either defined (as the workspace root, e.g.
  `~/01-U`) or struck from the document.

## Proposal

### ITEP-0008 amendment — sections to rewrite

1. **"Two-layer directory structure" (line 80 heading through the worked
   example at line ~118)** — replace the nested-tree diagram and worked example
   with a flat one:

   ```
   ${ABS_PARENT_DIR}/
   ├── 0060NP-25SF-ScintillatingFibers/    ← Master's thesis (created 2025)
   ├── 0060NP-26BE-BerylliumErosion/       ← 7Be meta-analysis (created 2026)
   └── 0060NP-26SC-ScintillatorCharact/    ← Scintillator characterization (created 2026)
   ```

   New prose: "Area and project are both encoded lexicographically in the
   project directory's own name (`DDTTAA-YYPP-title`); no physical parent
   directory is created for the area. The area/project relationship is
   represented exclusively in `workflow.db` via `MainTopic.parent_id`."
   Retitle the section from "Two-layer directory structure" to something that
   doesn't imply physical nesting, e.g. "Area/project naming and DB hierarchy."

2. **The `| Layer | Has GeneralProject in DB | ... |` table (lines 86-90)** —
   drop or relabel; there is no physical "Area" layer on disk to describe.

3. **MUST rules** — no change needed to the `DDTTAA-YYPP` naming MUSTs; they
   already describe the flat form correctly (e.g. "Every `GeneralProject`
   directory MUST follow the format `DDTTAA-YYPP-title` exactly").

4. **SHOULD rule (line 94-96)** — delete "The area directory `DDTTAA` SHOULD
   exist as a physical directory even when only one sub-project is present, to
   make the two-layer structure explicit from the start." This SHOULD only
   makes sense under the (incorrect) nested model.

5. **MAY rule (lines 270-272)** — delete "When only one project exists under an
   area... the area directory MAY be omitted and the project directory placed
   directly in the discipline root." Vestigial once nesting is removed
   entirely — omission of something that never physically exists is not a rule.

6. **"discipline root" (lines 95, 228, 272)** — all three instances are struck
   as part of rules 4-5 above, except line 228 (archival section: "move the
   directory to an `_archive/` subfolder within the discipline root"), which
   must be rewritten to "within the workspace root" or "within
   `ABS_PARENT_DIR`" to stay consistent with the flat model.

7. **`status:` frontmatter (line 8)** — change from `Implemented` to
   `Amended` (or add a changelog entry) noting the physical-nesting half was
   never correct and is corrected by this request; the naming/DB half remains
   implemented.

### Operational bug fixes (separate from the ADR text, same request)

- `src/itep/defaults.py:7-10` — `_DEFAULT_PHYSICS_DIR = Path.home() / "Documents" / "01-U" / "00-Fisica"`
  does not exist on this machine (verified: `ls ~/Documents/01-U` → No such file
  or directory) and `WORKFLOW_PHYSICS_DIR` is not set by default. Any `inittex`
  invocation without an explicit `--parent_dir` silently resolves to a dead
  path. Fix: either raise a clear `ClickException` when the default doesn't
  exist and the env var isn't set ("set WORKFLOW_PHYSICS_DIR or pass
  --parent_dir"), or change the default to match the real workspace root
  documented in CLAUDE.md.
- `src/itep/structure.py:53-57` — `GeneralDirectory` StrEnum uses 2-digit-prefix
  names (`00AA-Lectures`, `00II-ImagesFigures`, `00BB-Library`,
  `00EE-ExamplesExercises`) that do not match the real workspace, which uses
  4-digit prefixes and has renamed Lectures from `AA` to `AL`
  (`0000AL-Lectures`, `0000II-ImagesFigures`, `0000BB-Library`,
  `0000EE-ExamplesExercises`, verified via `ls ~/01-U`). Any `relink` run
  against the real workspace would generate symlinks pointing at nonexistent
  paths. Fix the enum values and add a regression test.

## Acceptance criteria

(See frontmatter `acceptance_criteria`.) Honest per-criterion status as of
closure (2026-08-08), verified directly against code and the amended ADR
text, not assumed from the plan:

1. **ADR no longer implies physical nesting; flat-layout prose added.** MET.
   "Two-layer directory structure" retitled "Area/project naming and DB
   hierarchy"; nested diagram replaced with a flat sibling diagram; new prose
   states the hierarchy lives only in `MainTopic.parent_id`.
2. **"discipline root" defined or removed everywhere (lines 95, 228, 272).**
   MET, via removal. `grep -n "discipline root"
   docs/ADR/ITEP-0008-general-project-nomenclature.md` returns zero matches.
   The two occurrences inside the deleted SHOULD/MAY rules went with them;
   the archival-section occurrence was reworded to "workspace root
   (`${ABS_PARENT_DIR}`)".
3. **SHOULD/MAY area-directory rules reconciled with the flat-layout
   correction.** MET, via the "removed as vestigial" branch (not the
   rewrite-to-marker-directory branch) — both rules only made sense under
   the incorrect nested model and were deleted outright rather than
   reinterpreted.
4. **ITEP-0000 and ITEP-0008 agree on `ABS_PARENT_DIR`; ITEP-0008
   cross-references the `itep.defaults` fix.** MET. The new 2026-08-08
   amendment section states `DEF_ABS_PARENT_DIR` derives from
   `WORKFLOW_WORKSPACE_ROOT` and cross-references `src/workflow/paths.py`
   and `src/itep/defaults.py`.
5. **`_DEFAULT_PHYSICS_DIR` no longer points at a nonexistent path.** MET
   (Phase 1, commit `8606444`): `WORKFLOW_WORKSPACE_ROOT` (default `~/01-U`)
   is now the source `WORKFLOW_PHYSICS_DIR` derives from when unset —
   verified directly in `src/workflow/paths.py`
   (`ENV_WORKSPACE_ROOT = "WORKFLOW_WORKSPACE_ROOT"`).
6. **`GeneralDirectory` enum values corrected.** MET (commit `596ea25`) —
   verified directly: `src/itep/structure.py` `GeneralDirectory` now reads
   `LEC = "0000AL-Lectures"`, `IMG = "0000II-ImagesFigures"`, `BIB =
   "0000BB-Library"`, `EXE = "0000EE-ExamplesExercises"`, matching the real
   `~/01-U` names.
7. **Regression test for `GeneralDirectory` values.** MET — `tests/itep/
   test_general_directory.py` exists (commit `ce7a395`).
8. **`inittex`/`create-general` CLI exposes `--area-code --title --year-init
   --project-initials`.** MET (commit `e068285`) — documented in CLAUDE.md
   Key Patterns.
9. **`_create_dirs_from_tree` skips/errors on unexpanded `{t_idx}`
   placeholders when `topics` is empty, instead of `mkdir`-ing the literal
   string.** MET (commit `596ea25`) — verified directly:
   `src/itep/create.py`'s guard is now `if "{t_idx" in directory: if not
   topics: continue`, i.e. it skips rather than falls through to the
   literal-mkdir `else` branch.
10. **`workflow project adopt` command exists, registers without recreating
    the tree.** MET (commit `6751bd7`) — `src/workflow/project/cli.py`
    defines `adopt` with `--dry-run`/`--json`.
11. **`workflow project list` exists.** MET (commit `6751bd7`) — same file,
    `list` command.
12. **`workflow validate config` drift detector exists.** MET (commit
    `2045f7d`) — `src/workflow/validation/cli.py` defines `config` with the
    finding kinds documented in CLAUDE.md.
13. **`.vault_pointer` regenerated or removed as a drift-prone mechanism.**
    MET, via the "mechanism narrowed" reading rather than full removal
    (commit `c9cc174`): `.vault_pointer` is now timestamp-only
    (`unified_at:`), carrying no path — verified directly:
    `src/workflow/vault/unify.py` writes `f"unified_at: {timestamp}\n"` with
    no `vault_root:` field, so there is no path left in the file to drift.
14. **Single `WORKFLOW_WORKSPACE_ROOT` env var, with `WORKFLOW_DATA_DIR`,
    `WORKFLOW_VAULT_ROOT`, `WORKFLOW_PHYSICS_DIR` deriving from it when
    unset.** PARTIALLY MET, by deliberate design deviation, documented
    both in code and here: `WORKFLOW_WORKSPACE_ROOT` was added
    (`src/workflow/paths.py`) and `WORKFLOW_VAULT_ROOT`/`WORKFLOW_PHYSICS_DIR`
    both derive from it when unset (verified in `src/workflow/paths.py` and
    `src/workflow/vault/paths.py`). **`WORKFLOW_DATA_DIR` intentionally does
    NOT derive from it** — `src/workflow/paths.py::data_dir()` carries an
    explicit docstring: "Deliberately NOT derived from `workspace_root()` —
    ADR-0008 pins the global DB to the XDG data dir, and deriving it would
    relocate a live database whenever the workspace moves." This is a
    conscious scope narrowing of the criterion as originally written, not an
    oversight: ADR-0008 (XDG directory layout) already governs
    `WORKFLOW_DATA_DIR` and takes precedence for that one variable, per its
    own "amended 2026-06-05" status. Two of three subsystem defaults derive
    from the new root; the third stays independently XDG-anchored on
    purpose.

**Summary: 13 of 14 acceptance criteria fully met; 1 (criterion 14, the
`WORKFLOW_DATA_DIR` derivation) met for 2 of its 3 named variables by
deliberate, documented design choice rather than oversight.**

## Verification

(See frontmatter `verification`.)

## Out of scope

- Renaming or restructuring `DisciplineArea`/`MainTopic` DB tables — this
  request is about the ADR text and two config constants, not schema.
- A `workflow project archive` command implementation — ITEP-0008 already
  marks this as a future MAY; only the "discipline root" wording it uses is
  fixed here.
- Auditing every other ADR for similar physical-layout claims — scoped to
  ITEP-0008 vs ITEP-0000 only.
- Migrating any existing directories on disk — the real workspace is already
  flat, so no directory moves are needed; this request only corrects the
  documentation and the two stale config defaults.

## Findings from the 2026-08-08 real migration

The following surfaced while actually migrating 7 repos out of
`0060NP-NuclearPhysics/pro/*` (1.7 GB) to flat siblings under `~/01-U/`, and
creating the workspace's first registered `GeneralProject`
(`0831PI-26SK-Sketchbook`, id=1). All were checked directly against the
current tree at commit `217e277` (`refactor(imports): Phase 2 — rewire
moved-symbol imports`), not copied from memory — see per-item verification
below.

1. **`inittex`/`itep create-general` has no CLI path to adopt a repo with a
   historical year.** `create_general()` (`src/itep/create.py:280-297`)
   accepts `title`, `year_init`, `project_initials`, `area_code` kwargs and,
   when `year_init` is `None`, silently falls back to
   `date.today().year % 100` (line ~296). The `cli()` entry point
   (`src/itep/create.py:411-429`) only defines `--parent_dir`, `--src_dir`,
   `--clone_id`, `--force-no-maturation` — none of the four kwargs above are
   exposed as flags, and `create_general(...)` is called with none of them
   (line 429). Of the 7 migrated repos, 5 predate this year (`23`, `24`,
   `25`×3) — registering them with the correct `year_init` required calling
   `create_general()`/DB inserts from a one-off Python script instead of the
   CLI.

2. **`_create_dirs_from_tree` mkdir's the literal placeholder string when
   `topics` is empty.** `GeneralProject.tree`
   (`src/itep/models.py:20-29`) includes `"tex/{t_idx:03}-{t_name}"`, meant
   to be expanded once per topic. `create_general()` always calls
   `_create_dirs_from_tree(root_dir, GPModel.tree, [])` (line 330) — an empty
   topics list. In `_create_dirs_from_tree`
   (`src/itep/create.py:76-88`), the guard is
   `if "{t_idx" in directory and topics:` — with `topics=[]` (falsy) this is
   `False` regardless of the string check, so execution falls to the `else`
   branch and calls `ensure_dir(base_dir / directory, forced=True)` with
   `directory` still literally `"tex/{t_idx:03}-{t_name}"`. This is a
   confirmed code defect by static read, exactly as filed.

   It also **did** reproduce on disk when `0831PI-26SK-Sketchbook` was
   created on 2026-08-08: `create_general()` produced a directory named
   literally `tex/{t_idx:03}-{t_name}`, which was removed with `rmdir`
   immediately afterwards as cleanup. That manual removal — not a failure
   of the defect to trigger — is why a later `find ~/01-U/0831PI-26SK-Sketchbook
   -name '*{*'` returns nothing and `tex/` now holds only
   `000-0-Glossaries`, `000-1-Summaries`, `000-2-Notes`.

   To re-observe: create any `GeneralProject` with zero topics and inspect
   `tex/` before cleaning up.

3. **No adoption command exists.** `grep -rn "adopt" src/ --include=*.py`
   returns zero matches anywhere in the codebase. `inittex` only creates from
   scratch. All 7 `0060NP` repos moved today
   (`0060NP-NuclearPhysics/pro/` is now empty, confirmed via `ls -la`) remain
   unregistered in `workflow.db` — there is no `GeneralProject`/`MainTopic`
   row for any of them yet.

4. **`workflow project` group is nearly empty.** `src/workflow/project/cli.py`
   defines exactly one subcommand, `propose-maturation` (ADR ITEP-0009 Part
   II reporting). There is no `list`, `move`, or `archive` (ITEP-0008's own
   §Project archival marks `archive` as a future MAY). With no `list`, there
   is currently no CLI-level way to see which `GeneralProject` rows exist —
   only a direct DB query.

5. **No config↔DB↔filesystem drift validator exists**, and the area this
   migration touched already shows real drift. Confirmed by reading
   `~/01-U/0060NP-NuclearPhysics/config.yaml` directly: `code: "60NP"` (the
   legacy two-digit scheme, not `DDTTAA`), `data.abs_parent_dir:
   "/home/luis/Documents/01-U/00-Fisica"` and `data.abs_project_dir:
   ".../00-Fisica/60NP-NuclearPhysics/"` — both under the same dead
   `Documents/01-U` prefix as `itep.defaults._DEFAULT_PHYSICS_DIR` (§bug
   above), not the real path `/home/luis/01-U/0060NP-NuclearPhysics/`. No
   `workflow validate config` or similar exists anywhere in `src/` to have
   caught this.

6. **`.vault_pointer` is a third, unsynchronized path-resolution mechanism.**
   `~/01-U/0060NP-NuclearPhysics/.vault_pointer` reads `vault_root:
   /home/luis/Documents/01-U/0000AA-Vault` — both the dead `Documents/01-U`
   prefix and the pre-rename `0000AA-Vault` name (the real vault is
   `/home/luis/01-U/0000AV-Vault`, per the `AA`→`AV` rename noted elsewhere
   in this primer/session log). Confirmed `WORKFLOW_VAULT_ROOT`
   (`src/workflow/vault/paths.py:16,31`) and `workflow.config`'s
   `get_vault_root` (`src/workflow/config.py:69-73`) both read a single env
   var / config key correctly — `.vault_pointer` is a redundant per-directory
   file with no code path shown here that re-derives or validates it against
   those two, so it silently goes stale on any rename.

7. **No single workspace-root env var.** Confirmed by reading
   `src/workflow/paths.py` (`WORKFLOW_DATA_DIR`, line 88),
   `src/workflow/config.py` (`WORKFLOW_VAULT_ROOT`, line 73),
   `src/workflow/vault/paths.py` (`WORKFLOW_VAULT_ROOT` again, line 31), and
   `src/itep/defaults.py` (`WORKFLOW_PHYSICS_DIR`, line 9): three
   independent env vars, each subsystem computing its own hardcoded default
   when unset. Moving the workspace root (as literally happened today,
   `Documents/01-U` → `01-U`) requires updating all three by hand — items 5
   and 6 above are direct symptoms of this having been missed for at least
   one of the three.

### Evidence

- `~/01-U/0060NP-NuclearPhysics/pro/` — 7 repos migrated out today, directory
  now empty (`ls -la` shows `pro` present, 0 entries, mtime `Aug 8 12:31`).
- `~/01-U/0831PI-26SK-Sketchbook/` — first `GeneralProject` created,
  `general_project.id = 1`.
- `~/01-U/0060NP-NuclearPhysics/config.yaml` and
  `~/01-U/0060NP-NuclearPhysics/.vault_pointer` — read directly, both quoted
  verbatim above.

## Progress log

- 2026-08-08 — opened by user after independent verification of ITEP-0000 vs
  ITEP-0008 vs `src/itep/create.py`, `src/workflow/db/models/project.py`,
  `src/itep/defaults.py`, and `src/itep/structure.py` surfaced the nested-vs-flat
  contradiction and two related stale-default bugs.
- 2026-08-08 (later same day) — expanded with 7 operational findings surfaced
  by actually migrating 7 `0060NP-NuclearPhysics/pro/*` repos (1.7 GB) to
  flat siblings under `~/01-U/` and creating the workspace's first
  `GeneralProject` (`0831PI-26SK-Sketchbook`, id=1): (1) `create-general` CLI
  doesn't expose `title`/`year_init`/`project_initials`/`area_code`, forcing
  a Python one-off to register 5 repos with historical years; (2)
  `_create_dirs_from_tree` mkdir's an unexpanded `{t_idx}/{t_name}`
  placeholder literally when `topics=[]` — confirmed both by reading
  `src/itep/create.py:76-88` and on disk when `0831PI-26SK-Sketchbook` was
  created (the brace-named directory was `rmdir`'d as cleanup right after,
  which is why it is no longer present); (3) no `adopt` command exists anywhere in `src/`, so the 7
  migrated repos remain unregistered in `workflow.db`; (4) `workflow project`
  CLI has only `propose-maturation`, no `list`/`move`/`archive`; (5) no
  config↔DB↔filesystem drift validator, and `0060NP-NuclearPhysics/config.yaml`
  is confirmed stale (`code: 60NP`, dead `Documents/01-U/00-Fisica` paths);
  (6) `.vault_pointer` is a third, unsynced path-resolution mechanism,
  confirmed stale on the same repo (`Documents/01-U/0000AA-Vault`, pre-rename
  name); (7) three independent env vars
  (`WORKFLOW_DATA_DIR`/`WORKFLOW_VAULT_ROOT`/`WORKFLOW_PHYSICS_DIR`) each
  with their own default, no unifying `WORKFLOW_WORKSPACE_ROOT`. Added
  matching `acceptance_criteria`/`verification` entries and two new
  `components`. New section: "Findings from the 2026-08-08 real migration".
- 2026-08-08 (Phases 1-4, implementation) — `8606444` added
  `WORKFLOW_WORKSPACE_ROOT` (default `~/01-U`) to `src/workflow/paths.py`
  and rewired `WORKFLOW_VAULT_ROOT`/`WORKFLOW_PHYSICS_DIR` to derive from it
  when unset, deliberately excluding `WORKFLOW_DATA_DIR` (stays XDG-anchored
  per ADR-0008). `596ea25` fixed `GeneralDirectory` StrEnum values to the
  real 4-digit-prefix names and fixed `_create_dirs_from_tree` to skip
  unexpanded `{t_idx}` placeholder tree entries when `topics=[]` instead of
  `mkdir`-ing them literally. `ce7a395` added a regression test pinning the
  workspace-root derivation contract and fixed an order-dependent test.
  `e068285` exposed `--area-code --title --year-init --project-initials` on
  `inittex`. `6751bd7` added `workflow project adopt`/`workflow project
  list`. `c9cc174` made `.vault_pointer` a timestamp-only marker (no path,
  so it cannot drift out of sync with `WORKFLOW_VAULT_ROOT`). `2045f7d`
  added `workflow validate config`, a read-only config↔DB↔filesystem drift
  detector.
- 2026-08-08 (Phase 5, documentation, this closure) — ITEP-0008 amended:
  "Two-layer directory structure" retitled and rewritten as flat
  area/project naming with the hierarchy expressed only via
  `MainTopic.parent_id`; nested diagram and worked example replaced with a
  flat one using the real `0060NP-23BP-BerylliumProcess`,
  `0060NP-25SC-SciFiCharacterization`, `0060NP-26LY-LightYield` project
  names; the SHOULD/MAY area-directory rules deleted as vestigial; the
  undefined area-root term removed throughout (verified: zero
  `discipline root` matches, zero `DDTTAA-title/` matches); `status:`
  changed `Implemented` → `Amended`; a new "Amendment 2026-08-08" section
  and Change Log row added, following the same convention as the existing
  2026-05-27 amendment. `docs/ADR/INDEX.md` and `CLAUDE.md`'s ADR Index
  table updated to `Amended (2026-08-08)`. `CLAUDE.md` Key Patterns
  documented the new `workflow project list`/`adopt`, `workflow validate
  config`, `inittex` flags, `WORKFLOW_WORKSPACE_ROOT`, and the
  timestamp-only `.vault_pointer`. This request closed; 13/14 acceptance
  criteria fully met, 1 partially met by deliberate design deviation (see
  "Acceptance criteria" section below for the honest per-criterion review).
  Verification commands (greps + full pytest suite) run and confirmed
  passing before closure.
