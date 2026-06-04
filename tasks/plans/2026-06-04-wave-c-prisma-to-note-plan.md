# Implementation plan — Wave C: PRISMA-accepted → literature note (the handoff)

Request: `tasks/requests/2026-06-03-prisma-to-literature-note.md` (rewritten in C0 per audit)
Audit (spec for C0): `tasks/audit/2026-06-03-prisma-to-literature-note-audit.md`
Roadmap: `tasks/roadmap/2026-06-03-bibliography-and-two-workflow-roadmap.md` §Wave C
Methodology: TDD (RED→GREEN→REFACTOR), reviewer-esquema each phase, forward-only
migrations (ITEP-0010). Phases ship independently; commit at each GREEN.

---

## Verified anchors (confirmed in code)

- `workflow.db.models.bibliography.ReviewRecord` — fields `id`, `keyword_id` (FK→BibKeyword),
  `bib_entry_id` (FK→BibEntry), `included` (SmallInteger, **tri-state None/0/1**),
  `include_rationale` (Text, nullable). UniqueConstraint `(keyword_id, bib_entry_id)`.
- `ReviewRationale` — join table `(review_record_id, rationale_option_id)`; **no `.text`**.
  Controlled labels live on `RationaleOption.label`.
- `workflow.bibliography.service.get_bib_entry_by_bibkey` — contract 0→None / 1→entry /
  2+→raises `AmbiguousLookupError` (was `BibKeyAmbiguous`, renamed per ADR-0020 followups).
- `workflow.bibliography.render.entry_to_biblatex(entry)` — **A5 shared renderer** (foundation
  layer, ADR-0020). This is the bib-block source; do NOT write a second renderer.
- `workflow.db.models.notes.Note` — `source` is a **relationship** (back-pop from `Link.source`),
  `source_format` a column. Frontmatter must NOT use `source:` → use `origin:`.
- Note creation/template: `workflow notes new --type literature` / `create_note` +
  `validate_note_frontmatter` (validator schema must learn the new keys).
- `workflow.vault.paths.resolve_vault_root()` — vault path (env `WORKFLOW_VAULT_ROOT`).
- `import_bib_text(session, text, …)` + `prisma bib import --stdin` — **B1 done**; the generated
  ```` ```bib ```` block round-trips through it. `:WorkflowBibImport` — **B2 done**.
- Migration harness: `src/workflow/db/migrations/global/`; latest = `0015_bib_relation.py`
  → next = `0016_` **only if** a schema change is needed (none expected — all columns exist).
- CLI pattern: `prisma bib export` in `src/workflow/prisma/cli.py` (Click group + `with_schema_guard`).

---

## Target / design

A `workflow prisma bib accept-to-note` command turns a screened `BibEntry` into a literature
`.md` note under `<vault_root>/notes/literature/<YYYYMMDD>-lit-<bibkey>.md`, idempotent by file
presence, reusing the existing note template + A5 biblatex renderer. The PRISMA-rationale
section is emitted only when a screening record is resolvable. A bulk `--all-accepted` form
generates one note per `included == 1` record for a keyword. A nvim command wraps it.

### Commands / API surface

```bash
workflow prisma bib accept-to-note <BIBKEY> [--bib-entry-id N] [--keyword-id N] \
    [--review-record-id N] [--vault-root PATH] [--dry-run] [--json]
workflow prisma bib accept-to-note --all-accepted --keyword-id N \
    [--vault-root PATH] [--dry-run] [--json]
```

`--json` (single): `{"note_path": "...", "bibkey": "...", "created": true|false}`
`--json` (bulk): `{"created": N, "skipped": N, "notes": [{...}, …]}`

Frontmatter emitted (validator must accept these keys):

```yaml
id: <YYYYMMDD>-lit-<bibkey>
title: "<BibEntry.title>"
type: literature
bibkey: <bibkey>
prisma_review_record_id: <ReviewRecord.id | null>   # D3 provenance key
prisma_keyword_id: <keyword_id | null>
main_topic_id: null
concepts: []
tags: []
created: <ISO date>
origin: prisma | manual            # renamed from `source:` (collision)
```

---

## Resolved design rules

- **Provenance key = `prisma_review_record_id`** (D3, locked). Ties the note to one screening
  decision (`ReviewRecord.id`), resolved from `(keyword_id, bib_entry_id)` UniqueConstraint
  or passed directly via `--review-record-id`.
- **Entry selector:** positional `<BIBKEY>` first; `--bib-entry-id` is the unambiguous fallback.
  bibkeys are non-unique (ADR-0019) → catch `AmbiguousLookupError` and emit a helpful error
  listing the conflicting `bib_entry_id`s, instructing the user to pass `--bib-entry-id`.
- **Inclusion filter:** `included == 1` (tri-state SmallInteger; never `== True`).
- **Rationale rendering:** free text from `ReviewRecord.include_rationale`; controlled labels by
  joining `ReviewRationale → RationaleOption.label`. Section emitted only when a ReviewRecord
  resolves (keyword-id or review-record-id given AND a record exists).
- **Reuse, don't duplicate:** bib block via `render.entry_to_biblatex`; note skeleton via the
  existing `create_note` / literature template; vault path via `resolve_vault_root()`.
- **Idempotent by file presence:** existing target file → `created: false`, no overwrite
  (exit non-zero in single mode; counted as skipped in bulk).
- **`origin:` not `source:`** — avoids the `Note.source` relationship collision.
- **Fallbacks:** missing DOI/journal → omit that metadata line; no ReviewRecord → omit PRISMA
  section (this is the free-read / Wave D path).

---

## Decisions — LOCKED (user, 2026-06-03 roadmap)

1. **D3** — provenance key is `prisma_review_record_id` (per-record), not `prisma_review_id`.
2. Renderer is the A5 shared `workflow.bibliography.render` — no second biblatex renderer.
3. C0 (request rewrite per audit) is mandatory before any TDD; the audit is the spec.

---

## Phases

### Phase C0 — Rewrite the request per the audit (doc, no code) — MANDATORY GATE

**Goal:** the request file is implementation-ready; all 8 audit findings resolved in-text.

**Edits** (`tasks/requests/2026-06-03-prisma-to-literature-note.md`):
1. `prisma_review_id`/`Review.id` → `prisma_review_record_id`/`ReviewRecord` everywhere;
   CLI `--review-id` → `--keyword-id` / `--review-record-id`.
2. Rationale: `include_rationale` (free text) + `ReviewRationale→RationaleOption.label`.
3. `included == True` → `included == 1` (tri-state).
4. Frontmatter `source:` → `origin:`.
5. Reuse `create_note` + `render.entry_to_biblatex`; drop "write a minimal renderer".
6. Add validator-schema extension to scope (new keys are NOT free — claim was false).
7. Add `--bib-entry-id` fallback selector; catch `AmbiguousLookupError`.
8. `adr_refs`: add `0019`, `0020`, `ITEP-0012`, `ITEP-0013`; fix ITEP-0013 "Proposed"→"Accepted".

**Commit point:** request rewritten → commit (docs). No suite run needed (doc-only).

---

### Phase C1 — `accept-to-note` single-entry CLI + service (TDD)

**Goal:** one screened BibEntry → one literature `.md` note via the shared renderer.

**RED tests** (`tests/workflow/prisma/test_accept_to_note.py`):
- bibkey → note file created at `notes/literature/<YYYYMMDD>-lit-<bibkey>.md` with expected
  frontmatter (`origin: prisma`, `prisma_review_record_id`, `main_topic_id: null`).
- `--keyword-id` resolves the ReviewRecord → `## PRISMA rationale` section has free text +
  controlled labels; without it, section omitted.
- bib block round-trips through `import_bib_text` without error.
- second run → `created: false`, file unchanged (idempotent), exit non-zero.
- `--dry-run` prints to stdout, writes nothing.
- ambiguous bibkey (2 entries) → `AmbiguousLookupError` caught → helpful error naming ids;
  `--bib-entry-id` disambiguates.
- `--json` shape.

**GREEN impl** — files touched:
- `src/workflow/prisma/accept_to_note.py` (new) — service: resolve entry, resolve ReviewRecord,
  render frontmatter+body+bib block, write file. Pure-ish, returns a result DTO.
- `src/workflow/prisma/cli.py` (edit) — `bib accept-to-note` command.
- `src/workflow/validation/…` (edit) — extend frontmatter schema for the new keys.

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema C1.

---

### Phase C2 — bulk `--all-accepted --keyword-id` (TDD)

**Goal:** one note per `included == 1` record for a keyword; existing notes skipped.

**RED tests:**
- 3 included + 1 excluded + 1 pending → 3 notes; excluded/pending ignored.
- re-run → all skipped (idempotent); report counts created/skipped.
- `--json` list shape.
- `--dry-run` writes nothing.

**GREEN impl:**
- `src/workflow/prisma/accept_to_note.py` (edit) — bulk loop reusing the single-entry path.
- `src/workflow/prisma/cli.py` (edit) — `--all-accepted` branch + mutex guards.

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema C2.

---

### Phase C3 — nvim `:WorkflowPrismaAcceptToNote` (Lua)

**Goal:** trigger generation from nvim; open the note; report counts; errors verbatim.

**RED tests** (`nvim-plugin/tests/plenary/prisma_note_spec.lua`):
- prompt → CLI call shape; `created:false` path opens existing; empty-result guard; error notify.

**GREEN impl:**
- `nvim-plugin/lua/workflow/prisma_note.lua` (new) — `vim.ui.input` bibkey/keyword,
  `server.run_cli … --json` (pattern of `content_bib.lua`), open split.
- register in `commands.lua` / `plugin/workflow.lua`.
- `nvim-plugin/doc/workflow.txt` + `CLAUDE.md` — document command.

**Commit point:** spec green → commit + reviewer C3.

---

## Risks / out of scope

- **In scope:** C0 rewrite; C1 single CLI; C2 bulk; C3 nvim; validator schema extension.
- **Out of scope:** Wave D `notes create --type literature` (falls out of C1; file/track
  separately); P2 screening-transition hook (deferred); graph→research-question (ITEP-0013);
  auto-linking to `Content`.
- **Risk — validator rejects new keys:** the "no schema change" claim was false (audit #6);
  extending `validate_note_frontmatter` is in scope and must land in C1.
- **Risk — writes files into the live vault:** gate every phase behind `--dry-run` tests and
  isolated `WORKFLOW_VAULT_ROOT`/`tests/outputs/`; never write the real vault in tests.
- **No schema migration expected** — all columns already exist (ReviewRecord/Note unchanged).

---

## Verification (each phase)

```bash
WORKFLOW_DATA_DIR=$(mktemp -d) WORKFLOW_VAULT_ROOT=$(mktemp -d) \
  uv run pytest -q --ignore=tests/test_database.py
uv run flake8 src/ tests/ --max-line-length=127 --max-complexity=10
```
