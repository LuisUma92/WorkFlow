# Implementation plan — Wave D: `notes create --type literature --bibkey`

Request: `tasks/requests/2026-06-03-prisma-to-literature-note.md` (§Wave D, lines 263-264)
Roadmap: `tasks/roadmap/2026-06-03-bibliography-and-two-workflow-roadmap.md` §Wave D (line 109)
ADR: none new — reuses ADR-0020 renderer boundary + C1 service.
Methodology: TDD (RED→GREEN→REFACTOR). Single phase; commit at GREEN. NO migration (no schema change).

---

## Verified anchors (confirmed in code)

- `workflow.prisma.accept_to_note.accept_to_note(session, *, bibkey, bib_entry_id, keyword_id,
  review_record_id, vault_root, dry_run)` — **already produces a manual literature note when
  keyword_id/review_record_id are BOTH None**: `_resolve_record` returns None, `build_note(...,
  record=None)` omits the `## PRISMA rationale` section, `_build_frontmatter` sets
  `origin: manual`, `prisma_review_record_id: null`, `prisma_keyword_id: null`. Wave D's core is
  THIS path — no new renderer.
- `accept_to_note.py:88` — `origin = "prisma" if record is not None or keyword_id is not None
  else "manual"`. Currently auto-derived; Wave D adds an explicit override.
- `accept_to_note.accept_to_note_json(result)` → `{"note_path","bibkey","created"}` — reuse
  verbatim for `--json` (same shape C1/C3 nvim already consume).
- `accept_to_note._SAFE_BIBKEY_RE` — path-traversal guard already applied per entry.
- `workflow.bibliography.service.get_bib_entry_by_bibkey` raises `BibKeyAmbiguous` on non-unique
  bibkey (caught + surfaced as ClickException).
- `src/workflow/notes/cli.py` — `@notes.command(name="new")` makes **blank** notes via
  `create_note(target, fm_obj, force)`. Wave D adds a SIBLING `create` command (bibkey-driven);
  does NOT touch `new`. Imports already present: `click`, `json`, `with_schema_guard`,
  `get_engine_from_ctx` pattern (confirm in file).
- Notes tests live in `tests/workflow/notes/`; isolated `WORKFLOW_DATA_DIR` via conftest autouse;
  `global_session` fixture available.

---

## Target / design

A new bottom-up entry point that creates a literature note directly from a bibkey, with no PRISMA
context. Symmetric to the PRISMA-driven `prisma bib accept-to-note` (Wave C) but lives under the
`notes` group and reuses the same renderer.

### Commands / API surface

```bash
workflow notes create --type literature --bibkey <key> \
  [--bib-entry-id <id>] [--origin <label>] [--vault-root <path>] [--dry-run] [--json]
```

- `--type` — `click.Choice(["literature"])`, default `literature` (only literature for now;
  blank notes of other types remain `notes new`).
- `--bibkey` — required; resolves the BibEntry (raises `BibKeyAmbiguous` if non-unique →
  ClickException advising `--bib-entry-id`).
- `--bib-entry-id` — optional disambiguator.
- `--origin` — default `manual`; written verbatim into frontmatter `origin:`.

`--json` shape (reuse `accept_to_note_json`):

```json
{ "note_path": "/…/notes/literature/20260605-lit-<key>.md", "bibkey": "<key>", "created": true }
```

Text mode echoes the note path (created) or "exists: <path>" (created==false).

---

## Resolved design rules

- **Reuse, do not duplicate.** `notes create` calls `accept_to_note(session, bibkey=…,
  bib_entry_id=…, origin=…, vault_root=…, dry_run=…)` — the SAME service as Wave C. No second
  renderer. (Accepts a new `notes → prisma.accept_to_note` import edge; the renderer is
  literature-note-generic, not PRISMA-specific. Relocating it to a neutral module is **out of
  scope** — tracked as optional follow-up.)
- **`--origin` threading.** Add `origin: str | None = None` to `accept_to_note` →
  `build_note` → `_build_frontmatter`. When `None`: preserve current auto-derive (`prisma` if
  record/keyword else `manual`) — keeps ALL C1/C2/C3 tests green. When provided: override verbatim.
  `notes create` passes `origin` (default `"manual"`).
- **Idempotency / dry-run / safety** — inherited unchanged from `accept_to_note` (file exists →
  `created: false`, no overwrite; `--dry-run` writes nothing; `_SAFE_BIBKEY_RE` guard).
- **Type restriction.** `--type` Choice is `["literature"]` only; attempting other types is a
  usage error (extend later if a bibkey-driven non-literature note is ever needed).

---

## Decisions — LOCKED (roadmap 2026-06-03 + plan)

1. Command name = `notes create` (roadmap §Wave D, line 111) — sibling to `notes new`, NOT a flag on it.
2. Default `--origin manual`; no PRISMA section; `prisma_*` frontmatter keys = `null`.
3. Reuse `accept_to_note` + `accept_to_note_json`; no schema change, no migration.
4. `--origin=None` sentinel preserves Wave C auto-derivation (backwards-compat invariant).

---

## Phase D1 — `notes create` command + `origin` threading (TDD)

**RED tests** (`tests/workflow/notes/test_create_literature.py`):
- create from bibkey → file at `<vault>/notes/literature/<YYYYMMDD>-lit-<key>.md`; frontmatter
  `type: literature`, `prisma_review_record_id: null`, `prisma_keyword_id: null`, `origin: manual`;
  body has **no** `## PRISMA rationale` section; has `## Bib block`.
- `--origin reading-list` → frontmatter `origin: reading-list`.
- idempotent re-run → `created: false`, file unchanged.
- `--dry-run` → no file written, reports intended path.
- `--json` → `{"note_path","bibkey","created"}`.
- ambiguous bibkey (2 entries) → ClickException mentioning `--bib-entry-id`; `--bib-entry-id`
  resolves it.
- unsafe bibkey → ClickException (no file).
- `--type` rejects a non-literature value (Click usage error, exit 2).

**Service regression** (`tests/workflow/prisma/test_accept_to_note.py` — add, do not break):
- `accept_to_note(origin="manual")` → frontmatter `origin: manual` even with no record.
- `accept_to_note(origin=None)` (default) preserves auto-derive: with a record → `origin: prisma`.

**GREEN impl:**
- `src/workflow/prisma/accept_to_note.py` (edit) — add `origin: str | None = None` param to
  `accept_to_note`, `build_note`, `_build_frontmatter`; thread through; default None = current
  behaviour.
- `src/workflow/notes/cli.py` (edit) — new `@notes.command(name="create")` calling the service;
  ClickException mapping for `BibKeyAmbiguous`/`ValueError`; `--json` via `accept_to_note_json`.
- Docs: `CLAUDE.md` notes/PRISMA bullet + `nvim-plugin/doc` only if an nvim command is added
  (it is NOT in this wave — CLI only).

**Commit point:** suite green (notes + prisma + bib) + flake8 0 → commit `feat(notes): notes
create --type literature --bibkey (Wave D)`.

---

## Risks / out of scope

- **In scope:** `notes create` CLI; `origin` threading; tests; CLAUDE.md doc.
- **Out of scope:** relocating `build_note`/`accept_to_note` to a neutral module (optional
  follow-up); nvim command for `notes create`; bulk free-read; `--type` beyond literature.
- **Risk — writes into the live vault:** every test sets `--vault-root` to a tmp dir; `--dry-run`
  asserted to write nothing.
- **Invariant:** `origin=None` default MUST keep Wave C frontmatter byte-identical (run the full
  C1/C2/C3 suite as the regression gate).

## Verification (phase)

```bash
pytest tests/workflow/notes tests/workflow/prisma tests/workflow/bibliography -q
flake8 src/workflow/notes/cli.py src/workflow/prisma/accept_to_note.py \
  tests/workflow/notes/test_create_literature.py --max-line-length=127 --max-complexity=10
```
