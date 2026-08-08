---
id: ITEP-0008
nav_order: 31
parent: ADRs
title: "General project nomenclature: discipline, area, year and project initials"
aliases:
  - ADR-ITEP-0008
status: Amended (2026-08-08, physical-nesting correction; naming/DB layer remains Implemented)
date: 2026-04-21
implemented_at: 2026-04-28
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - ITeP e
  - nomenclature
  - filesystem
  - general-project
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "ITEP-0000"
  - "ITEP-0004"
  - "ITEP-0003"
---

## Context

ITEP-0000 established the base naming convention for `GeneralProject` directories
as `{DDTTAA}-{title}`, where `DD` encodes the discipline, `TT` the topic within
the discipline, and `AA` the two-letter area initials. This scheme covers the
top-level classification of academic work.

As research activity grows across multiple institutions and professional roles, a
single area code (e.g. `0060NP` for Nuclear Physics) may host several simultaneous
and independent projects — a master's thesis, a meta-analysis, and an external
collaboration — each with its own lifecycle, collaborators, Git history, and
bibliographic scope.

The original `DDTTAA` scheme has no mechanism to distinguish these sub-projects.
Placing them inside a single `GeneralProject` directory:

- Violates the 1:1 constraint between `GeneralProject` and `MainTopic` already
  enforced by `create.py`.
- Conflates Git histories from projects with different confidentiality requirements
  and collaborator sets.
- Prevents independent use of `workflow prisma` per research question.
- Produces a `slipbox.db` knowledge graph that cannot distinguish project boundaries.

A systematic naming convention is required that:

1. Preserves the existing `DDTTAA` structure for area-level directories.
2. Uniquely identifies each sub-project within an area.
3. Encodes the creation year without consulting the database.
4. Scales to a full professional and academic career without exhausting the
   identifier space.
5. Is registrable and uniqueness-enforceable in the global `workflow.db`.

---

## Decision Drivers

- **Career scalability**: the scheme must not impose artificial limits on the
  number of projects per area over a multi-decade horizon.
- **Lexicographic ordering**: directory listings must sort by discipline → topic →
  area → time, without additional tooling.
- **Legibility**: the directory name must communicate the project's subject and
  approximate origin date without opening any file.
- **Git isolation**: each sub-project must be an independent Git repository,
  enabling selective access for external collaborators.
- **DB consistency**: the naming must map cleanly to `MainTopic` and
  `GeneralProject` records in the global database.
- **Zero ambiguity**: every segment must have exactly one interpretation rule.

---

## Decision

### Area/project naming and DB hierarchy

The on-disk layout is **flat**. Every `DDTTAA-YYPP-title` project directory is a
direct child of the workspace root (`${ABS_PARENT_DIR}`, per ITEP-0000) and a
sibling of every other project directory, including other projects in the same
area. No physical directory is ever created to represent the area on its own —
there is no `DDTTAA`-named parent directory to nest project directories inside.

Area and project are both encoded lexicographically in the project directory's
own name (`DDTTAA-YYPP-title`): `DDTTAA` alone already sorts all projects in an
area together, and `YYPP` sub-sorts them by creation year and initials. This
achieves the ADR's original ordering goal (discipline → topic → area →
chronology) in a plain directory listing without any physical nesting.

The area/project **hierarchy** — as opposed to the naming — exists exclusively
in `workflow.db`, via `MainTopic.parent_id`: an area-level `MainTopic` row
(`parent_id = NULL`) is the parent of each project-level `MainTopic` row
(`parent_id` = the area row's id). See "`MainTopic` hierarchy in the database"
below.

### Full code format

```
DDTTAA-YYPP-title
│    │  │└─ PP : project initials (2 uppercase letters, unique within DDTTAA+YY)
│    │  └── YY : two-digit creation year (year the directory is first created)
│    └───── AA : area initials (2 uppercase letters, fixed per topic, from discipline CSV)
└────────── DDTT : discipline (DD) + topic index (TT), as defined in ITEP-0000
```

**Examples:**

```
${ABS_PARENT_DIR}/                          ← workspace root, e.g. ~/01-U
├── 0060NP-23BP-BerylliumProcess/           ← Nuclear Physics project (created 2023)
├── 0060NP-25SC-SciFiCharacterization/      ← Nuclear Physics project (created 2025)
├── 0060NP-26LY-LightYield/                 ← Nuclear Physics project (created 2026)
└── 0010MC-26HM-HamiltonMechanics/          ← Classical Mechanics project, unrelated area
```

All four directories above are siblings on disk, regardless of area. The three
`0060NP-*` projects share nothing on the filesystem beyond their common
`DDTTAA` name prefix; their shared-area relationship is recorded only in
`workflow.db` (three project-level `MainTopic` rows all pointing at the same
`0060NP` area-level `MainTopic` row via `parent_id`).

### `YY` — creation year rule

`YY` is the **two-digit calendar year in which the project directory is first
created**, without exception. It does not represent the year the research topic
was conceived, the year of first publication, or the academic cycle year. Once
assigned, `YY` is immutable for the lifetime of the project.

### `PP` — project initials and collision resolution

`PP` encodes the project name as two uppercase letters derived from the project
title using the following ordered rules. The first rule that produces a code not
already registered under `(DDTTAA, YY)` in the database is applied:

| Priority                 | Rule                                                      | Example title          | Result |
| ------------------------ | --------------------------------------------------------- | ---------------------- | ------ |
| 1                        | First letter of word 1 + first letter of word 2           | `Scintillating Fibers` | `SF`   |
| 2 (collision)            | First two letters of word 1                               | `Scintillating Fibers` | `SC`   |
| 3 (collision)            | First two letters of word 2                               | `Scintillating Fibers` | `FI`   |
| 4 (persistent collision) | Manual assignment, recorded in DB with justification note | —                      | —      |

The uniqueness scope is `(DDTTAA, YY, PP)`. Two projects in the same area created
in different years MAY share the same `PP` without conflict.

### `MainTopic` hierarchy in the database

The area directory `DDTTAA` corresponds to a **parent `MainTopic`** record with
`parent_id = NULL`. Each sub-project `DDTTAA-YYPP` corresponds to a **child
`MainTopic`** with `parent_id` pointing to the area record.

This requires adding an auto-referential `parent_id` field to `MainTopic`:

```python
class MainTopic(GlobalBase):
    ...
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("main_topic.id"), nullable=True, default=None
    )
    parent:   Mapped["MainTopic | None"] = relationship(
        back_populates="children", remote_side="MainTopic.id"
    )
    children: Mapped[list["MainTopic"]] = relationship(back_populates="parent")
```

Existing `MainTopic` records are unaffected (`parent_id = NULL`). Area-level
`MainTopic` records also have `parent_id = NULL`; project-level records have
`parent_id` set to their area's record `id`.

### Catalog vs State: why two tables

`DisciplineArea` and `MainTopic` look similar at the area level but model
different concerns. Both are required and **MUST** stay separate.

|             | `DisciplineArea` (catalog)                             | `MainTopic` (state)                                                          |
| ----------- | ------------------------------------------------------ | ---------------------------------------------------------------------------- |
| Origin      | CSV files in `data/DD-*Codes.csv`                      | Created on demand by `inittex`                                               |
| Scope       | Every DDTTAA code that exists in the world (~233 rows) | Areas + projects the user has actually registered                            |
| Mutability  | Reseedable from CSV at any time                        | Project-coupled, varies per install                                          |
| Inbound FKs | none (pure reference data)                             | `Topic.main_topic_id`, `GeneralProject.main_topic_id`, `MainTopic.parent_id` |
| Hierarchy   | flat                                                   | 2-level (area → project)                                                     |
| Code length | always 6 (`DDTTAA`)                                    | 6 (area-level) or 10 (`DDTTAAYYPP`, project-level)                           |

The split keeps reference-data reseeds (adding or renaming a DDTTAA code in
CSV) from touching user state, and lets ITEP-0009 maturation logic
distinguish "available area" from "registered area".

### Catalog FK from state

To prevent `MainTopic` rows from drifting away from the catalog, every
`MainTopic` record carries a non-null FK to the `DisciplineArea` row that
defines its area:

```python
class MainTopic(GlobalBase):
    ...
    discipline_area_id: Mapped[int] = mapped_column(
        ForeignKey("discipline_area.id"), nullable=False
    )
    discipline_area: Mapped["DisciplineArea"] = relationship()
```

- Area-level `MainTopic`: `discipline_area_id` points to the row whose
  `code` equals `MainTopic.code`.
- Project-level `MainTopic`: `discipline_area_id` is **inherited from the
  parent area row** (i.e. equals `parent.discipline_area_id`); the first
  6 chars of `MainTopic.code` therefore equal the linked
  `DisciplineArea.code`.

This invariant **MUST** be enforced by `inittex.create_general` on every
insert. Schema migration owning this FK is `0002_main_topic_discipline_area_fk`
under ITEP-0010.

### Project archival

Archival state is managed exclusively through the `GeneralProject` model, not
through filesystem renaming or code mutation:

```python
class GeneralProject(GlobalBase):
    ...
    status:      Mapped[str]        = mapped_column(default="active")
    archived_at: Mapped[date | None] = mapped_column(nullable=True)
```

Allowed values for `status`: `active`, `archived`, `suspended`, `completed`.

The project directory name and its `DDTTAA-YYPP` code are **immutable** regardless
of status. A future `workflow project archive <code>` command will update `status`
and `archived_at` in the DB, move the directory to an `_archive/` subfolder within
the workspace root (`${ABS_PARENT_DIR}`), and re-run `relink` for the new path.

---

## Architectural Rules

### MUST

- Every `GeneralProject` directory **MUST** follow the format `DDTTAA-YYPP-title`
  exactly, with no omission of segments.
- `YY` **MUST** be the two-digit calendar year of first directory creation.
  It **MUST NOT** be changed after creation.
- `PP` **MUST** be unique within the scope `(DDTTAA, YY)` as recorded in
  `workflow.db`. Uniqueness **MUST** be enforced at creation time by `inittex`.
- `AA` **MUST** match the area initials registered in the discipline CSV file
  (`data/DD-Codes.csv`) for the given `DDTT` code.
- Each `DDTTAA-YYPP` project directory **MUST** be an independent Git repository.
- Archival **MUST NOT** alter the directory code. Status changes **MUST** be
  recorded in `GeneralProject.status` and `GeneralProject.archived_at`.
- The `MainTopic` for a project **MUST** have `parent_id` pointing to the
  area-level `MainTopic` for `DDTTAA`.
- Every `MainTopic` row (area- or project-level) **MUST** carry a non-null
  `discipline_area_id` FK to a real `DisciplineArea.id`. The first 6
  characters of `MainTopic.code` **MUST** equal the linked
  `DisciplineArea.code`. Project-level rows **MUST** inherit
  `discipline_area_id` from their parent area row.
- `inittex.create_general` **MUST** validate the catalog link before
  insert; an unknown `DDTTAA` **MUST** abort project creation with a
  pointer to `workflow db disciplines list`.

### SHOULD

- `PP` collision resolution **SHOULD** follow the priority table in order and
  **SHOULD NOT** skip directly to manual assignment without exhausting rules 1–3.
- Discipline CSV files (`data/DD-Codes.csv`) **SHOULD** be updated before
  creating any new area `MainTopic`, to register the `AA` code formally.

### MAY

- A `workflow project archive` CLI command **MAY** automate directory relocation
  and DB status update as a future enhancement.

---

## Implementation Notes

### Files requiring changes

| File                                 | Change                                                                                                                                                    |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/itep/models.py`                 | Update `GeneralProject.patterns["numbering"]` from `^[0-9]{2}` to `^[0-9]{4}`; add `"project"` pattern `^[0-9]{2}[A-Z]{2}$`                               |
| `src/itep/create.py`                 | Add `YY` + `PP` input steps; enforce uniqueness check `(DDTTAA, YY, PP)` before DB insert                                                                 |
| `src/workflow/db/models/academic.py` | Add `parent_id`, `parent`, `children` to `MainTopic`                                                                                                      |
| `src/workflow/db/models/project.py`  | Add `status` (str, default `"active"`) and `archived_at` (date, nullable) to `GeneralProject`                                                             |
| `data/`                              | Add `01-PhilosophyCodes.csv`, `02-InformaticsCodes.csv`, `03-TeachingCodes.csv`, `04-LanguagesCodes.csv` following the structure of `00-PhysicsCodes.csv` |

### Directory naming at creation time

`inittex` must construct the root directory name as:

```python
root_dir = f"{dd:02d}{tt:02d}{aa}-{yy:02d}{pp}-{title}"
```

where `yy` is derived from `datetime.today().year % 100` at creation time.

### Collision check query

```python
existing = session.query(GeneralProject).join(MainTopic).filter(
    MainTopic.code == f"{dd:02d}{tt:02d}{aa}",
    GeneralProject.year_init == yy,
    GeneralProject.project_initials == pp,
).first()
if existing:
    raise click.ClickException(f"Code {aa}-{yy:02d}{pp} already registered.")
```

---

## Impact on AI Coding Agents

- When generating or modifying `GeneralProject` records, agents **MUST** use
  the full `DDTTAA-YYPP-title` format and **MUST NOT** omit `YY` or `PP`.
- Agents adding `MainTopic` records for sub-projects **MUST** set `parent_id`
  to the corresponding area `MainTopic` id.
- Agents **MUST NOT** rename project directories or alter `YY`/`PP` segments
  under any circumstance, including archival operations.
- Before creating a new project, agents **MUST** query `workflow.db` to verify
  `(DDTTAA, YY, PP)` uniqueness.
- Agents **SHOULD** consult `data/DD-Codes.csv` to verify that `AA` is a
  registered area code before proceeding with project creation.

---

## Consequences

### Benefits

- Complete disambiguation between area-level and project-level entities in both
  the filesystem and the database.
- Lexicographic sort order reflects discipline → topic → area → chronology
  automatically in any directory listing or fuzzy finder.
- Year encoding enables at-a-glance project age without database queries.
- 676 unique `PP` codes per area per year provides practical career-scale capacity.
- Independent Git repositories per project enable selective collaborator access
  and clean per-project history.
- `status` + `archived_at` fields support full project lifecycle tracking without
  destructive filesystem changes.

### Costs

- Three existing `MainTopic` records (the active Nuclear Physics sub-projects)
  require new `parent_id` assignments once `parent_id` is added to the schema.
- `inittex` requires two additional input steps (`YY` is automatic; `PP` requires
  user input or derivation from title).
- Discipline CSV files for non-physics disciplines must be created before those
  areas can be used.
- Schema migration required for `MainTopic.parent_id`, `GeneralProject.status`,
  and `GeneralProject.archived_at`.

---

## Alternatives Considered

### Alternative A — Single digit project index `-P` (0–9)

Append a single digit to the area code: `0060NP-1-ScintillatingFibers`.

#### Advantages

- Minimal code change; one character.

#### Disadvantages

- Hard cap of 9 projects per area — inadequate for professional career scale.
- Carries no temporal information.
- Rejected.

### Alternative B — Two-digit sequential index `-PP` (01–99)

`0060NP-01-ScintillatingFibers`.

#### Advantages

- 99 projects per area; zero-padded lexicographic sort.

#### Disadvantages

- Still a finite cap. No temporal signal without consulting DB.
- Rejected.

### Alternative C — Single letter `-L` (A–Z)

`0060NP-S-ScintillatingFibers`.

#### Advantages

- 26 slots; mnemonic potential.

#### Disadvantages

- 26 is insufficient at career scale. Mnemonic assignment conflicts with
  chronological ordering. Rejected.

### Alternative D — Substitute discipline digits with `99` for archival

Replace `DD` with `99` in archived project codes: `9960NP-25SF`.

#### Advantages

- Archived projects sort to end of any listing.

#### Disadvantages

- Mixes project state (archival) with project identity (discipline code) in a
  single field — orthogonal concerns encoded in the same segment.
- Breaks `abs_parent_dir` in `config.yaml` and all symlinks on rename.
- `99` is consumed as a pseudo-discipline, unavailable for legitimate future use.
- Rejected in favor of `status` field in `GeneralProject`.

---

## Compatibility / Migration

This ADR applies to **new project directories only**. Existing `MainTopic`
directories (`0060NP`, `0010MC`, etc.) retain their current names unchanged.

When sub-projects are created under existing areas, the area directory is created
at that time if it does not already exist.

Schema migration steps (to be applied before first use of `inittex` under this ADR):

1. Add `parent_id` (nullable FK to `main_topic.id`) to `main_topic` table.
2. Add `status` (VARCHAR, default `'active'`) to `general_project` table.
3. Add `archived_at` (DATE, nullable) to `general_project` table.

No existing rows require data updates at migration time.

---

## References

- ITEP-0000: ITeP project structure conventions
- ITEP-0004: Two project types — Lecture & General
- ITEP-0003: `config.yaml` as minimal DB pointer
- `data/00-PhysicsCodes.csv`: registered physics area codes
- Martin Fowler — _Patterns of Enterprise Application Architecture_ (self-referential
  association pattern), ISBN 978-0-321-12521-7

---

## Amendment 2026-05-27 — DB-level clarification: Topic rooted at DisciplineArea

ITEP-0008's **"two-layer directory" rule is a filesystem statement** and remains
unchanged: each `DDTTAA` area directory contains `DDTTAA-YYPP` project directories.
The filesystem layout described in the Decision section above is unaffected by this
amendment.

At the **DB layer**, the Phase 4B migration (`0011_topic_root_discipline_area`,
see `tasks/requests/2026-05-27-topic-reroot-discipline-area.md`) changes where
`Topic` is rooted:

- **Before (migration 0010 and earlier):** `Topic.main_topic_id` (FK→`MainTopic`)
  meant every Topic belonged to a single project instance (`DDTTAA-YYPP`).
- **After (migration 0011+):** `Topic.discipline_area_id` (FK→`DisciplineArea`,
  RESTRICT) means Topic is a **canonical chapter/section in a field**, independent
  of any project iteration. `serial_number` is the canonical chapter index within
  the area, with a `UNIQUE(discipline_area_id, serial_number)` constraint.

**`MainTopic` keeps project-iteration state.** The area directory corresponds to
an area-level `MainTopic` (parent_id=NULL); each sub-project directory corresponds
to a child `MainTopic` (`DDTTAA-YYPP`, parent_id→area row). Per-iteration syllabus
ordering is now in `MainTopicSyllabus(main_topic_id, topic_id, week_no, order_no)`
rather than encoded by the direct `Topic.main_topic_id` FK.

This change makes the DB shape consistent with the mental model:
_"a chapter is canonical knowledge; a project picks which chapters it covers."_
Previously, two project iterations covering the same topic area required duplicate
`Content`/`Concept` rows; after Phase 4B they share the same `Topic` rows.

The "Catalog vs State: why two tables" section above (DisciplineArea vs MainTopic)
and all filesystem-naming rules (MUST/SHOULD/MAY under Architectural Rules) are
**unchanged**.

Reference: ITEP-0002 amendment 2026-05-27 and migration `0011`.

---

## Amendment 2026-08-08 — Physical-nesting correction: layout is flat, not two-layer

The original "Two-layer directory structure" section (and its worked example,
SHOULD rule, and MAY rule) described `DDTTAA-YYPP-title` project directories as
physically nested one level inside a `DDTTAA-title` area directory. **This was
never correct and was never implemented.** ITEP-0000 (the foundational
structure ADR, which this ADR does not and cannot supersede) always specified a
flat layout — `${ABS_PARENT_DIR}/${ROOT}`, one join, no area subdirectory — and
the shipped code agrees: `GeneralProject.root_dir`
(`src/workflow/db/models/project.py`) bakes `DDTTAA` into the leaf directory's
own name and is joined directly under the parent directory in
`src/itep/create.py`, with no intermediate area-directory segment anywhere.
Verified directly: `~/01-U` has zero directories in the nested
two-level form (area directory containing `DDTTAA-YYPP-title` project
directories); every project directory that exists is a flat sibling of every
other one.

Only the **naming and DB-hierarchy** half of the original decision was ever
implemented and remains implemented and correct: the `DDTTAA-YYPP-title` code
format, the `MUST` rules governing it, and the `MainTopic.parent_id` self-FK
representing the area/project relationship in `workflow.db`. What is corrected
by this amendment is exclusively the claim that this hierarchy is *also*
expressed as physical directory nesting on disk.

Changes made by this amendment:

- "Two-layer directory structure" retitled to "Area/project naming and DB
  hierarchy"; the nested-tree diagram and the `| Layer | ... |` table (there is
  no physical area layer to describe) are replaced with a flat sibling diagram
  and prose stating the hierarchy lives only in `MainTopic.parent_id`.
- The worked example under "Full code format" now shows the real
  `0060NP-23BP-BerylliumProcess`, `0060NP-25SC-SciFiCharacterization`,
  `0060NP-26LY-LightYield` projects as flat siblings under `${ABS_PARENT_DIR}`.
- The SHOULD rule ("area directory... SHOULD exist as a physical directory")
  and the MAY rule ("area directory... MAY be omitted") are deleted outright —
  both only made sense under the incorrect nested model; there is nothing to
  optionally omit when the area directory never physically exists in the
  first place.
- The previously undefined term for the physical parent of a project directory
  (used in the deleted SHOULD/MAY rules and in the Project archival section)
  is removed everywhere it referred to an area-level directory, and the
  remaining occurrence (Project archival section) is reworded to "workspace
  root (`${ABS_PARENT_DIR}`)", consistent with ITEP-0000's terminology.
- `status:` changes from `Implemented` to `Amended`, reflecting that this ADR
  is now correct in full only as of this amendment.
- `itep.defaults.DEF_ABS_PARENT_DIR` (or its successor) now derives from
  `WORKFLOW_WORKSPACE_ROOT` (default `~/01-U`) rather than a hardcoded,
  nonexistent `~/Documents/01-U/00-Fisica` path — see
  `src/workflow/paths.py` (`WORKFLOW_WORKSPACE_ROOT`, added this cycle) and
  `src/itep/defaults.py`. `WORKFLOW_PHYSICS_DIR` remains individually
  overridable and takes precedence when set.

This amendment does not change any `MUST` rule under Architectural Rules — the
`DDTTAA-YYPP-title` naming format, `YY`/`PP` semantics, and `MainTopic.parent_id`
requirements were already correct and are unchanged.

Reference: `tasks/requests/2026-08-08-itep-0008-two-layer-directory-contradiction.md`
(request that identified and specified this correction).

---

## Change Log

| Date       | Change                                                                     |
| ---------- | -------------------------------------------------------------------------- |
| 2026-04-21 | Initial ADR — design phase, pre-implementation                             |
| 2026-04-28 | Implemented across three phases (commits `6964d87`, `f5cf015`, `56bbacd`). |
| 2026-05-27 | DB-level clarification: `Topic` re-rooted at `DisciplineArea` (migration 0011, Phase 4B). Filesystem two-layer rule unchanged. |
| 2026-08-08 | **Amended**: the "two-layer" physical-nesting claim was never correct/implemented; layout is flat per ITEP-0000. Naming/DB hierarchy (`DDTTAA-YYPP`, `MainTopic.parent_id`) remains implemented. SHOULD/MAY area-directory rules deleted; the undefined area-root term removed. `status` → `Amended`. |

## Implementation Notes (2026-04-28)

Shipped in three phases on `master`:

- **Phase A** (`6964d87`) — schema scaffolding: `MainTopic.parent_id` self-FK,
  `DisciplineArea` reference table, `GeneralProject.{year_init, project_initials,
title, status, archived_at}`, `workflow db migrate itep-0008` idempotent
  one-shot migration with optional Nuclear Physics backfill.
- **Phase B** (`f5cf015`) — discipline-codes loader: `workflow.db.seed_codes`
  (`parse_csv`, `upsert_from_csv`, `upsert_all_csvs`, `UpsertReport`),
  `workflow db import-codes [--csv|--all|--data-dir]` CLI, hooked into
  `seed_reference_data`. CSV `código` column gives `TTAA`; the `DD` prefix is
  taken from the filename so `DisciplineArea.code` is the full 6-char `DDTTAA`.
- **Phase C** (`56bbacd`) — `inittex` flow: `itep.naming` (priority rules
  `word_initials → word1_prefix → word2_prefix → manual`, `is_taken`,
  `slugify_title`, `validate_pp`); rewritten `create_general` selects a
  `DisciplineArea`, gets-or-creates the area-level `MainTopic` (parent_id=NULL),
  derives `PP` with collision fallback, creates the child `MainTopic`
  (`DDTTAAYYPP`, 10 chars) and the `GeneralProject` row. `GeneralProject.root_dir`
  now CamelCase-slugs the title so spaces never reach the filesystem.

Test coverage at completion: 738 tests pass (47 new across the three phases),
flake8 clean. Smoke against bundled `data/`: 233 codes load idempotently.

## Post-migration data fix-up (Nuclear Physics backfill)

ITEP-0008 introduced `MainTopic.parent_id` and the `DisciplineArea` reference
table. Schema migration is generic; the Nuclear Physics children that pre-dated
ITEP-0008 needed area code `0060NP` created and three `GeneralProject` columns
(`year_init`, `project_initials`, `title`) backfilled before
`MainTopic.parent_id` could be reassigned.

Originally exposed as a Click flag `workflow db migrate itep-0008
--backfill-nuclear-physics`. Per ITEP-0010 this single-user data quirk is
**not** a generic migration step. It is recorded as a one-off SQL script under
`scripts/one-off/2026-04-itep-0008-nuclear-physics-backfill.sql` and run once
manually with user confirmation. The flag is dropped when the deprecated
`workflow db migrate itep-0008` alias is retired (one cycle after ITEP-0010
ships).

## Migration framework follow-up (ITEP-0010)

The bespoke `workflow db migrate itep-0008` Click subcommand becomes a
deprecated alias once ITEP-0010 lands. Its body is preserved verbatim as
`src/workflow/db/migrations/global/0002_itep_0008_general_project_nomenclature.py`
inside the generic forward-only runner. New schema changes ship as numbered
migrations under that runner, not as ad-hoc Click subcommands.
