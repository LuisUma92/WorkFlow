---
id: ITEP-0009
title: "Knowledge lifecycle, discipline taxonomy, and AI agent collaboration conventions"
aliases:
  - ADR-ITEP-0009
status: Implemented
date: 2026-04-21
implemented_at: 2026-04-29
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - ITeP
  - knowledge-management
  - zettelkasten
  - ai-agents
  - nomenclature
  - discipline-taxonomy
decision_scope: system
supersedes: null
superseded_by: null
related_adrs:
  - "ITEP-0000"
  - "ITEP-0008"
  - "0001"
  - "0002"
  - "0015"
  - "LZK-0000"
---

## Context

The WorkFlow system has grown beyond its original scope of physics and teaching
materials to cover a multi-disciplinary personal knowledge ecosystem spanning
ten academic disciplines, personal interests, and professional research
projects. Several architectural decisions have been made informally during the
design of this expanded system:

1. **Discipline taxonomy** (`DD` codes `00`–`09`) covering Física, Filosofía,
   Informática, Docencia, Lingüística, Ciencias de la Salud, Ingeniería
   Práctica, Música, Artes Visuales, and Agronomía y Sostenibilidad — each
   with a corresponding `DD-*Codes.csv` in `data/`.

2. **Two-layer knowledge entry**: the Zettelkasten is the primary, zero-friction
   entry point for all incoming knowledge; ITeP `GeneralProject` structures are
   created only when knowledge matures into a formal product.

3. **Project maturation criteria**: what distinguishes a Zettelkasten note from
   a project worthy of a `GeneralProject` entry and a Git repository.

4. **AI agent and SKILL collaboration**: a growing set of specialized agents
   (`exam-author`, `note-curator`, `prisma-screener`, `gap-reporter`,
   `workflow-runner`) and skills (`exam-build`, `prisma-screen-session`,
   `workflow-cli`) operate within the `~/Documents/01-U` workspace. No ADR
   exists to govern how these agents should read the system state, scope their
   work, and avoid destructive interference.

This ADR formalizes all four areas as binding conventions for the system and
for any AI agent or SKILL operating within it.

---

## Decision Drivers

- **Attention economy**: the owner has attention deficit disorder with emphasis
  on inattention. The system must minimize decision overhead at the point of
  knowledge capture while maintaining rigor at the point of formalization.
- **Scalability**: the taxonomy must accommodate a multi-decade professional
  career without requiring restructuring.
- **AI-agent correctness**: agents must be able to determine project scope,
  maturity status, and safe write boundaries from the filesystem and DB alone,
  without requiring human clarification on structural questions.
- **Zettelkasten integrity**: notes are the single source of truth for personal
  knowledge. ITeP structures are derived from notes, not the reverse.
- **Separation of hobbies and professional work**: personal interests use the
  same infrastructure but have lower formalization requirements.

---

## Decision

### Part I — Discipline taxonomy

Ten disciplines are registered, each with a two-digit `DD` code and a
corresponding CSV file at `data/DD-*Codes.csv`.

| DD  | Discipline                 | CSV file                           |
| --- | -------------------------- | ---------------------------------- |
| 00  | Física                     | `00-PhysicsCodes.csv`              |
| 01  | Filosofía                  | `01-PhilosophyCodes.csv`           |
| 02  | Informática                | `02-InformaticsCodes.csv`          |
| 03  | Docencia                   | `03-TeachingCodes.csv`             |
| 04  | Lingüística                | `04-LinguisticsCodes.csv`          |
| 05  | Ciencias de la Salud       | `05-HealthSciencesCodes.csv`       |
| 06  | Ingeniería Práctica        | `06-PracticalEngineeringCodes.csv` |
| 07  | Música                     | `07-MusicCodes.csv`                |
| 08  | Artes Visuales             | `08-VisualArtsCodes.csv`           |
| 09  | Agronomía y Sostenibilidad | `09-AgronomyCodes.csv`             |

Codes `10`–`99` are reserved for future disciplines. Each CSV follows the
schema: `Rama,código,Dewey` where `código` = `TTAA` (topic index + area
initials) and `Dewey` is the Dewey Decimal classification reference.

The full project code format is defined in **ITEP-0008**: `DDTTAA-YYPP-title`.
This ADR does not redefine that format; it establishes the discipline registry
that feeds it.

---

### Part II — Knowledge lifecycle: Zettelkasten → ITeP

Knowledge entry follows a two-stage model. The stages are not a pipeline that
automatically promotes notes; promotion requires a conscious decision by the
owner.

#### Stage 1 — Zettelkasten (default for all new knowledge)

All incoming knowledge — readings, observations, ideas, course notes, hobby
learning — enters through the Zettelkasten. No project creation, no Git
initialization, no bibliographic overhead is required at this stage.

A Zettelkasten note is appropriate when:

- The topic is exploratory or the owner's commitment is uncertain.
- No formal product (document, report, publication, course material) is
  planned.
- The knowledge is personal (hobby, informal learning).
- The topic is in early contact phase (reading a first book, attending a
  first lecture).

#### Stage 2 — ITeP GeneralProject (on maturation)

A `GeneralProject` is created when **at least one** of the following criteria
is met:

| Criterion                      | Signal                                                                                                        |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| **Bibliographic accumulation** | The topic has ≥ 3 source documents that warrant indexed bibliography (`.bib` file, BibTeX keys in notes).     |
| **Formal product**             | A deliverable exists or is planned: paper, thesis chapter, course material, technical report, formal summary. |
| **Collaborative scope**        | The work involves external collaborators who need repository access.                                          |
| **Systematic review**          | A PRISMA or equivalent review is being conducted under this topic.                                            |
| **Institutional affiliation**  | The work is conducted under a formal institutional mandate (UCR, UFide, UCIMED).                              |
| **Multi-semester continuity**  | The topic has been actively developed across more than one academic semester.                                 |

When none of these criteria is met, the knowledge **stays in the
Zettelkasten**. Creating a `GeneralProject` prematurely for a hobby or
exploratory topic is an anti-pattern — it generates maintenance overhead
without corresponding value.

#### Hobby-specific rule

Disciplines `04`–`09` (personal interests and non-primary academic fields)
follow the same maturation criteria but with a higher threshold: the
**Formal product** criterion alone is sufficient to justify a project; the
**Bibliographic accumulation** criterion requires ≥ 5 sources, not 3.

#### Promotion procedure

When a topic matures from Stage 1 to Stage 2:

1. Run `inittex` to scaffold the `GeneralProject` directory using the
   `DDTTAA-YYPP-title` code from ITEP-0008.
2. Migrate relevant Zettelkasten notes into the new project's `tex/` tree.
3. Initialize a Git repository in the project directory.
4. Register the `MainTopic` (child) and link it to the area `MainTopic`
   (parent) via `parent_id` per ITEP-0008.

---

### Part III — AI agent and SKILL conventions

The following rules apply to every agent and SKILL operating within the
`~/Documents/01-U` workspace or reading the WorkFlow codebase at
`~/Projects/WorkFlow`.

#### A. Scope resolution

Before taking any action, an agent MUST determine its scope by reading in
order:

1. The explicit user instruction (course slug, project code, topic name).
2. `config.yaml` in the current working directory (project pointer to DB).
3. The `DDTTAA-YYPP` code in the directory name (discipline + topic + year).
4. The `data/DD-*Codes.csv` for the relevant discipline (area and topic
   context).

An agent MUST NOT assume scope from memory or prior sessions. Each session
starts from filesystem and DB state.

#### B. Read before write

Every agent MUST perform a read pass before any write operation:

- For CLI operations: run `workflow <group> --help` once per group per
  session and cache the output.
- For file operations: `Read` the target file before `Edit` or `Write`.
- For DB operations: dispatch `workflow-runner` with a `list` or `show`
  command to verify current state before any `add`, `create`, or `import`.

#### C. Confirmation protocol

The confirmation taxonomy is:

| Class                 | Examples                                             | Rule                                           |
| --------------------- | ---------------------------------------------------- | ---------------------------------------------- |
| **Read**              | `list`, `show`, `stats`, `validate`, `graph orphans` | Run immediately, no confirmation.              |
| **Idempotent write**  | `sync`, `relink`                                     | Confirm once with path + expected side-effect. |
| **Destructive write** | `cleta`, `gc`, `split`, file deletion                | Confirm with explicit diff or file list.       |
| **Novel creation**    | `create`, `import`, `inittex`, `build-exam`          | Confirm with full path + row count estimate.   |

No agent MAY batch-confirm multiple write operations. Each operation in the
destructive or novel-creation class requires its own confirmation.

#### D. Gap logging

Every agent that uses `workflow-runner` MUST log gaps. A gap is any of:

- A workflow required ≥ 3 CLI calls that should have been 1.
- A CLI flag was absent, forcing bash/python glue of > 5 lines.
- JSON output shape was inconsistent with a sibling command.
- An error message did not name the failing input.
- A `--dry-run` or `--json` flag was missing on a write command.

Gap logs go to `~/Documents/01-U/.claude/gaps/raw/<agent-name>.md` using
the template at `~/Documents/01-U/.claude/gaps/TEMPLATE.md`. Gap logging
does NOT require user confirmation — it is mandatory and automatic.

#### E. Agent specialization boundaries

Each agent owns a domain and MUST NOT perform operations outside it without
delegating to the appropriate specialist:

| Agent             | Domain                                       | Delegates to                 |
| ----------------- | -------------------------------------------- | ---------------------------- |
| `exam-author`     | Exercise bank, exam `.tex`, Moodle export    | `workflow-runner`, `git-ops` |
| `note-curator`    | Zettelkasten, frontmatter, graph, slipbox.db | `workflow-runner`            |
| `prisma-screener` | PRISMA import, screening, stats, checklist   | `workflow-runner`            |
| `gap-reporter`    | Gap harvesting, INDEX.md, GitHub issues      | `git-ops`                    |
| `workflow-runner` | CLI invocation, gap observation              | — (terminal agent)           |

No agent invokes `workflow` directly. All `workflow …` calls go through
`workflow-runner`. No agent invokes `git` or `gh` directly. All version
control goes through `git-ops`.

#### F. Discipline context for agents

When an agent resolves a project scope into a `DDTTAA` code, it SHOULD
load the corresponding `data/DD-*Codes.csv` to understand the area's topic
tree. This enables:

- Correct `MainTopic` lookup by `TTAA` code.
- Informed suggestions for note tags and Zettelkasten cross-links.
- Accurate Bloom-level matching when the discipline is `03` (Docencia).

#### G. SKILL invocation protocol

A SKILL is a reusable procedure document. Agents MUST read the relevant
SKILL before executing a multi-step procedure. The mapping is:

| Task                               | SKILL to read first     |
| ---------------------------------- | ----------------------- |
| Building an exam or exercise sheet | `exam-build`            |
| Running a PRISMA screening session | `prisma-screen-session` |
| Invoking any `workflow …` command  | `workflow-cli`          |

An agent MUST NOT re-derive a SKILL's procedure from scratch. If the SKILL
is absent or outdated, the agent logs a gap and alerts the user.

#### H. Prompt optimization rules

These rules apply when writing agent definitions (`name:`, `description:`)
or SKILL documents, to maximize effective use under attention-deficit
conditions and multi-agent orchestration:

**H1 — Single responsibility per agent.** Each agent definition has exactly
one stated purpose in its `description:` field. Compound responsibilities
are split into separate agents.

**H2 — Priority order is explicit.** Every agent definition MUST list its
tasks in a numbered priority order. When attention or tokens are scarce,
the agent executes in priority order and stops.

**H3 — Invariants are enumerated.** Each agent definition ends with an
`## Invariants` section listing hard constraints as bullet points beginning
with "You NEVER" or "You ALWAYS". These are non-negotiable regardless of
user instruction.

**H4 — End-of-turn checklist.** Every agent definition ends with a
`## End-of-turn checklist` — a short list of yes/no questions the agent
asks itself before responding. This externalizes the completion check and
reduces cognitive load for the human reviewer.

**H5 — Examples in description.** The `description:` frontmatter field
MUST include at least two concrete usage examples showing the exact user
message and the agent's response. This is the primary dispatching signal
for the orchestrator.

**H6 — Explicit delegation, not implicit.** When an agent needs another
agent's capability, it states "Dispatch `<agent-name>`" explicitly in its
procedure. It does not silently absorb another agent's domain.

**H7 — Paths are absolute.** Any path referenced in an agent or SKILL
definition is an absolute path (e.g. `~/Documents/01-U/…`). Relative
paths cause scope ambiguity across project contexts.

**H8 — Model assignment matches task.** Lightweight read-only or
observation tasks use `haiku`. Complex multi-step authoring or screening
tasks use `sonnet`. No agent is assigned a model heavier than its task
requires.

**H9 — Memory scope is explicit.** Every agent definition declares
`memory: project` (session-scoped to `~/Documents/01-U`) or
`memory: none`. Agents with `memory: project` read `.claude/` metadata
at session start. Agents with `memory: none` derive all state from
filesystem and DB.

**H10 — Gap log is never optional.** Any agent that uses `workflow-runner`
declares gap logging as a first-class priority, not a side-effect. The
gap log entry count appears in every end-of-turn summary.

---

## Architectural Rules

### MUST

- All disciplines (`DD=00`–`09`) **MUST** have a corresponding `DD-*Codes.csv`
  in `data/` before any `MainTopic` in that discipline is registered in
  `workflow.db`.
- Knowledge **MUST** enter the system through the Zettelkasten. Direct creation
  of a `GeneralProject` without prior Zettelkasten notes for the topic is
  prohibited unless the project is migrated from an external system with
  existing documents.
- A `GeneralProject` **MUST** satisfy at least one maturation criterion
  (Part II) before `inittex` is run for it.
- Every AI agent operating in `~/Documents/01-U` **MUST** route all
  `workflow …` calls through `workflow-runner`.
- Every AI agent **MUST** confirm destructive or novel-creation operations
  individually before executing.
- Agent `description:` fields **MUST** include at least two dispatching
  examples.
- Agent definitions **MUST** include an `## Invariants` section and an
  `## End-of-turn checklist`.

### SHOULD

- Zettelkasten notes for disciplines `04`–`09` **SHOULD** be tagged with the
  `DDTTAA` code of their area to enable future project promotion without
  manual reclassification.
- Agents **SHOULD** load `data/DD-*Codes.csv` when resolving project scope
  to enrich their understanding of the topic tree.
- SKILL documents **SHOULD** include a `## Gap focus` section listing the
  specific CLI surfaces most likely to produce loggable gaps during that
  procedure.
- New agents **SHOULD** be modeled on the existing `exam-author` /
  `prisma-screener` pattern: priority order → typical flow → gap focus →
  delegation → invariants → end-of-turn checklist.

### MAY

- A Zettelkasten note **MAY** carry a `candidate_project: DDTTAA-YYPP`
  frontmatter field as a forward reference to a future project code, before
  that project is formalized.
- Agents **MAY** propose maturation (suggest running `inittex`) when they
  observe that a topic's Zettelkasten note count exceeds 10 and a `.bib`
  file exists, even if the user has not explicitly requested it.

---

## Implementation Notes

### CSV registration checklist

Before creating any `MainTopic` in a new discipline, verify:

```bash
ls ~/Projects/WorkFlow/data/DD-*Codes.csv
# must include the DD for the new discipline
```

### Maturation signal detection (for note-curator)

`note-curator` is the natural agent for detecting maturation signals. It
SHOULD run the following heuristic after each `workflow graph stats` call:

```
for each MainTopic T with parent_id IS NULL:
    note_count = count of notes tagged with T.code
    bib_count  = count of BibEntry linked to T
    if note_count >= 10 AND bib_count >= 3:
        propose maturation to user
```

This is a suggestion protocol, not an automated action. The user confirms.

### Agent and SKILL file locations

```
~/Documents/01-U/.claude/
├── agents/
│   ├── exam-author.md
│   ├── gap-reporter.md
│   ├── note-curator.md
│   ├── prisma-screener.md
│   └── workflow-runner.md
├── skills/
│   ├── exam-build/SKILL.md
│   ├── prisma-screen-session/SKILL.md
│   └── workflow-cli/SKILL.md
├── gaps/
│   ├── TEMPLATE.md
│   ├── INDEX.md
│   ├── raw/
│   └── requests/
└── prompts/
```

### Adding a new agent — checklist

A new agent definition is complete when it has:

- [ ] `name:` — single noun or hyphenated noun phrase
- [ ] `description:` — one sentence + ≥ 2 dispatching examples
- [ ] `tools:` — explicit list, no wildcards
- [ ] `model:` — `haiku` or `sonnet` per H8
- [ ] `memory:` — `project` or `none` per H9
- [ ] `## Priority order` — numbered list
- [ ] `## Typical flow` — numbered steps with tool calls named
- [ ] `## Gap-log focus` — 3–6 specific CLI surfaces to watch
- [ ] `## Tools and delegation` — explicit delegation statements
- [ ] `## Invariants` — "You NEVER / You ALWAYS" bullets
- [ ] `## End-of-turn checklist` — 4–6 yes/no questions

---

## Impact on AI Coding Agents

- Agents reading this ADR **MUST** treat Part III (sections A–J) as binding
  operational rules, not recommendations.
- When an agent is asked to create a new `GeneralProject`, it **MUST** first
  check that the maturation criteria in Part II are satisfied and surface
  them to the user if they are not.
- When an agent proposes a new discipline CSV, it **MUST** follow the
  `Rama,código,Dewey` schema exactly; it **MUST NOT** introduce additional
  columns or reorder existing ones.
- Agents **MUST NOT** write to `data/DD-*Codes.csv` files without user
  confirmation, as these files are the source of truth for the entire
  taxonomy.
- When generating new agent or SKILL definitions, agents **MUST** apply
  rules H1–H10 and verify the new-agent checklist before presenting the
  output.

---

## Consequences

### Benefits

- A single ADR captures the complete knowledge lifecycle from first note
  to archived project — no implicit conventions that exist only in the
  owner's memory.
- AI agents can determine project maturity, discipline context, and safe
  write boundaries from the filesystem and DB alone, without human
  clarification on structural questions.
- The Zettelkasten-first model reduces friction at the point of knowledge
  capture — the most cognitively expensive moment for someone with
  attentional constraints.
- Prompt engineering rules (H1–H10) are codified as an ADR, making them
  enforceable by review rather than relying on agent author memory.
- The hobby discipline taxonomy (`04`–`09`) formalizes the boundary between
  personal and professional knowledge without creating a separate system.

### Costs

- Agents that predate this ADR (`exam-author`, `note-curator`,
  `prisma-screener`, `gap-reporter`, `workflow-runner`) should be audited
  against rules H1–H10 and updated where gaps exist.
- The maturation criteria introduce a judgment call that cannot be fully
  automated — the owner must periodically review Zettelkasten note clusters
  and decide whether to promote them.
- Ten discipline CSVs must be maintained as the taxonomy evolves; outdated
  CSV entries can cause incorrect scope resolution by agents.

---

## Alternatives Considered

### Alternative A — Single flat taxonomy (no DD hierarchy)

All topics in a flat list, no discipline grouping.

#### Advantages

- Simpler lookup.

#### Disadvantages

- No lexicographic grouping; `ls` output is unstructured. No basis for
  agent scope resolution. Rejected.

### Alternative B — Separate system for hobbies

A parallel non-ITeP system for disciplines `04`–`09`.

#### Advantages

- Zero overhead for hobby knowledge capture.

#### Disadvantages

- Two systems to maintain; knowledge that crosses professional and personal
  domains (e.g. Filosofía de la Física) has no natural home. Rejected in
  favor of the maturation-threshold approach.

### Alternative C — Agent rules in a separate document outside the ADR system

A standalone `AGENTS.md` rather than an ADR.

#### Advantages

- Simpler to edit without ADR overhead.

#### Disadvantages

- Not visible to agents that scan `docs/ADR/` for architectural context.
  ADR format ensures the rules appear in the INDEX and in the cross-system
  dependency graph. Rejected.

---

## Compatibility / Migration

This ADR is forward-looking. No existing data requires migration.

Existing agents (`exam-author`, `note-curator`, `prisma-screener`,
`gap-reporter`, `workflow-runner`) were written before this ADR and are
partially compliant. They SHOULD be audited against H1–H10 in a future
session; non-compliance is not a blocker for current operation.

The ten discipline CSVs are already committed to `data/` as of 2026-04-21.
No filesystem changes are required before this ADR takes effect.

---

## References

- ITEP-0000: ITeP project structure conventions
- ITEP-0008: General project nomenclature
- ADR 0002: Markdown as canonical knowledge layer
- ADR 0015: Zettelkasten daily work
- LZK-0000: LaTeXZettel 7-layer engine architecture
- Ahrens, S. — _How to Take Smart Notes_ (Zettelkasten methodology),
  ISBN 978-3-9824181-0-1
- Matuschak, A. — _Evergreen notes_ (maturation model),
  <https://notes.andymatuschak.org/Evergreen_notes>

---

## Change Log

| Date       | Change                                                                                         |
| ---------- | ---------------------------------------------------------------------------------------------- |
| 2026-04-21 | Initial ADR — discipline taxonomy, knowledge lifecycle, agent conventions, prompt rules H1–H10 |
| 2026-04-29 | WorkFlow-side parts implemented (Phases A+B+C). Part III deferred to ~/Documents/01-U.         |
| 2026-05-27 | Status flipped to `Implemented`. WorkFlow-repo scope (Parts I–II + MAY rule) is complete: all three phases (A/B/C) shipped, 38 tests green. Part III agent conventions remain deferred to `~/01-U/.claude/` workspace per the original plan; they are out of scope for this repo. |

## Implementation Notes (WorkFlow-side, 2026-04-29)

Status flipped to `Implemented (partial)` because Parts I–II and the
`candidate_project` MAY rule shipped in this repo, while Part III A–H
(agent conventions + prompt rules H1–H10) is **deferred** to the
`~/Documents/01-U/.claude/` workspace and tracked separately.

Plan: `~/.claude/plans/itep-0009-workflow-side.md`.

Shipped on `master`:

- **Phase A** — `feat(db): discipline taxonomy registry + CLI` (commit
  on master, post-ITEP-0008): `src/workflow/db/taxonomy.py` exposes
  `DISCIPLINES` (DD → Spanish name), `HOBBY_DD_THRESHOLD = 4`,
  `DisciplineInfo` and `discover_disciplines()`. New CLI
  `workflow db disciplines list [--json] [--data-dir PATH]` joins the
  registry with bundled CSVs so agents can consume the catalog without
  re-parsing filenames. (Original surface was `workflow db taxonomy
list`; renamed to `disciplines` to disambiguate from the Bloom
  taxonomy of ADR ITEP-0006. A hidden `taxonomy` alias still
  forwards with a deprecation notice.)
- **Phase B** — `feat(db): maturation signals + propose-maturation CLI`:
  `src/workflow/db/maturation.py` exposes `MaturationSignal`,
  `evaluate_area` (queryable subset of Part II criteria —
  `bibliographic_accumulation` with hobby-aware threshold,
  `institutional_affiliation`, `multi_semester_continuity`;
  `formal_product` / `systematic_review` / `collaborative_scope`
  return `met=None` "needs slipbox scan"). New CLI
  `workflow project propose-maturation [--json] [--area DDTTAA]`
  reports per-area status. `inittex` now warns when no queryable
  criterion is met and offers `--force-no-maturation` for scripted
  paths.
- **Phase C** — `feat(validation): candidate_project frontmatter field`:
  `NoteFrontmatter.candidate_project` is now an optional, regex-
  validated forward reference. New
  `check_candidate_project_against_db()` returns warnings when the
  `DDTTAA` portion is not yet registered.

Deferred to a follow-up plan in
`~/.claude/plans/itep-0009-01u-workspace.md`:

- Audit of existing agents (`exam-author`, `note-curator`,
  `prisma-screener`, `gap-reporter`, `workflow-runner`) against
  rules H1–H10.
- Agent-definition restructure (`## Invariants`,
  `## End-of-turn checklist`, `## Gap-log focus` sections,
  explicit `tools:`, `model:`, `memory:` fields).
- SKILL document updates (`exam-build`, `prisma-screen-session`,
  `workflow-cli`).
- Gap-log infrastructure under `~/Documents/01-U/.claude/gaps/`.
- Note-curator maturation-suggestion loop consuming
  `workflow.db.maturation.evaluate_area`.
