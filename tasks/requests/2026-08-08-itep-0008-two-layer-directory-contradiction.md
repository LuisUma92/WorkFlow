---
id: 20260808-itep-0008-two-layer-directory-contradiction
title: ITEP-0008 "two-layer directory structure" contradicts ITEP-0000's flat layout and the implemented root_dir property
type: bug
source_agent: user
opened_on: 2026-08-08

status: open
resolution: open
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
implementation: []
closed_on: null
closed_by: null

acceptance_criteria:
  - "ITEP-0008 no longer contains a diagram or prose implying `DDTTAA-YYPP-title/` is nested inside a physical `DDTTAA-title/` directory. The 'Two-layer directory structure' section is rewritten to state the layout is flat on disk: `DDTTAA-YYPP-title` project directories are siblings of an (optional, DB-absent) `DDTTAA-title` area directory under the workspace root, and the area/project hierarchy exists only as `MainTopic.parent_id` in the DB."
  - "The term 'discipline root' is either defined explicitly (as the workspace root directory, e.g. `~/01-U`) in a glossary/definitions subsection of ITEP-0008, or removed and replaced with 'workspace root' throughout (lines currently at 95, 228, 272)."
  - "ITEP-0008's MUST/SHOULD/MAY rules are amended so the SHOULD 'area directory... exist as a physical directory' and MAY 'area directory... omitted' language are reconciled with the flat-layout correction — either both removed as vestigial, or rewritten to describe an optional non-nesting marker directory."
  - "ITEP-0000 §'Main topic directory structure' and ITEP-0008 no longer disagree on `ABS_PARENT_DIR`: ITEP-0008 states explicitly that `itep.defaults.DEF_ABS_PARENT_DIR` should resolve to the actual workspace root used by the project (not a hardcoded `~/Documents/01-U/00-Fisica`), and cross-references the fix required in `itep.defaults` (see below)."
  - "`src/itep/defaults.py:7-10` `_DEFAULT_PHYSICS_DIR` no longer points at a nonexistent path. Either it defaults to an env-var-required value that fails loudly with a clear error when `WORKFLOW_PHYSICS_DIR` is unset, or it defaults to the real workspace convention documented in ITEP-0000/ITEP-0008 amendment."
  - "`src/itep/structure.py:53-57` `GeneralDirectory` StrEnum values (`00AA-Lectures`, `00II-ImagesFigures`, `00BB-Library`, `00EE-ExamplesExercises`) are corrected to match the real workspace naming (`0000AL-Lectures`, `0000II-ImagesFigures`, `0000BB-Library`, `0000EE-ExamplesExercises`) or ITEP-0008 documents the discrepancy as a deliberate, tracked migration with a target date."
  - "A regression test in `tests/itep/` asserts `GeneralDirectory` values match the CLAUDE.md-documented workspace directory names, so a future rename doesn't silently re-break `relink`."

verification:
  - "`grep -rn 'DDTTAA-title/' docs/ADR/ITEP-0008-general-project-nomenclature.md` returns no nested-tree diagram — only sibling/flat examples remain."
  - "`grep -n 'discipline root' docs/ADR/ITEP-0008-general-project-nomenclature.md` either returns 0 matches, or every match resolves against an explicit definition earlier in the same document."
  - "`python -c \"from itep import defaults; print(defaults.DEF_ABS_PARENT_DIR)\"` does not print a path containing `Documents/01-U` unless `WORKFLOW_PHYSICS_DIR` is explicitly set to that value."
  - "`python -c \"from itep.structure import GeneralDirectory; print(list(GeneralDirectory))\"` output matches the four real directory names in `~/01-U` (`0000AL-Lectures`, `0000II-ImagesFigures`, `0000BB-Library`, `0000EE-ExamplesExercises`)."
  - "`pytest tests/itep/ -k general_directory -v` passes with the new regression test."
  - "`ls ~/01-U | grep -E '^DDTTAA-YYPP'` pattern check: confirm zero directories anywhere in the real workspace currently use the two-layer nested form described in the current (unfixed) ITEP-0008."
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

(See frontmatter `acceptance_criteria`.)

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

## Progress log

- 2026-08-08 — opened by user after independent verification of ITEP-0000 vs
  ITEP-0008 vs `src/itep/create.py`, `src/workflow/db/models/project.py`,
  `src/itep/defaults.py`, and `src/itep/structure.py` surfaced the nested-vs-flat
  contradiction and two related stale-default bugs.
