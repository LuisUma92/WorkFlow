# Implementation plan — Note template gap (frontmatter ↔ schema ↔ ITEP-0013)

ADR: `docs/ADR/ITEP-0013-note-relation-graph.md` (**Accepted**)
Methodology: TDD (RED→GREEN→REFACTOR), reviewer-esquema each phase. Phases ship independently.

---

## Verified anchors (confirmed in code)

- `workflow.notes.init._create_note_templates` — `src/workflow/notes/init.py` writes 3 templates.
  Each block is `if not <file>.exists()`-guarded → `workflow init` NEVER overwrites existing
  templates; live-vault files require a SEPARATE edit.
- `NoteFrontmatter` — `src/workflow/validation/schemas.py`, `@dataclass(frozen=True)`.
  Already has `main_topic`, `discipline_area`, `bibkey`, `origin`.
  **MISSING: `relations`, `entry_point`.**
- `validate_note_frontmatter` body; helpers `_string_list`, `_validate_literature_provenance`
  (pattern to mirror for `_validate_relations`).
- Existing template tests — `tests/workflow/notes/test_init.py`: asserts bib-fence present
  in literature, absent in permanent/fleeting. Any template change needs test updates there.
- ITEP-0013 canonical schema: edge key is **`derived_from`** (NOT `delivered_from`).
  `relations.derived_from` (type ∈ continuation|refines|branches|synthesis|rebuttal) +
  `relations.links` (type ∈ supports|contradicts|expands|see_also); `entry_point` optional bool.
  Edge item shape: `{id, type, weight?, note?}`.
- ITEP-0013 Impl Notes scope: `note_edge` table/sync/cycle-validator are ITEP-0013 P0/P2/P3
  — OUT OF SCOPE here. This plan only adds the frontmatter DTO parse.
- Live vault `~/01-U/0000AA-Vault/templates/*.md` and
  `~/.config/nvim/lua/plugins/obsidian.lua` are OUTSIDE the repo.
- **Discrepancy**: obsidian.lua writes `relations.delivered_from` but ITEP-0013 mandates
  `derived_from`. ADR is authoritative → obsidian.lua has a bug.

---

## Target / design

`NoteFrontmatter` gains optional `relations` (parsed into typed edge DTOs) and `entry_point`
fields. The three templates in `init.py` and the live vault are updated to scaffold all
validator-supported fields. `obsidian.lua` is corrected (`delivered_from`→`derived_from`).
No DB migration. No `note_edge` persistence. Relations parsed leniently — unknown types warn
but don't crash.

### Template frontmatter targets

**permanent.md** (gains):

```yaml
main_topic:
discipline_area:
relations:
  derived_from: []
  links: []
entry_point: false
```

**literature.md** (gains):

```yaml
main_topic:
discipline_area:
origin:
relations:
  derived_from: []
  links: []
entry_point: false
```

(keeps `bibkey:` and bib fence already present)

**fleeting.md** — stays minimal (transient notes; no relations scaffold).

---

## Decisions — LOCKED (2026-06-06)

1. **`derived_from` is canonical** — ITEP-0013 ADR wins. Do NOT amend the ADR.
   obsidian.lua's `delivered_from` is a bug to fix in Phase 3.
2. **`relations` + `entry_point` parsed leniently** into `NoteFrontmatter` DTO.
   No DB write, no migration, no cycle check — those are deferred ITEP-0013 P0/P2/P3.
3. **`fleeting.md` stays minimal** — transient; no `main_topic`/`relations`.
4. **Live-vault templates overwritten** in Phase 3, gated on `.bak-2026-06-06` backup.
   Never rely on `workflow init` for the live vault (it's `exists()`-guarded).

---

## Phases

### Phase 1 — schema: parse `relations` + `entry_point` in NoteFrontmatter

**Goal:** Validator accepts (and round-trips) the ITEP-0013 edge frontmatter without DB touch.

**RED tests** (`tests/workflow/validation/test_validation_relations.py` — new file):

- absent `relations` block → valid, `fm.relations is None`, `fm.entry_point is False`
- valid `derived_from` list → parsed into typed DTOs; `type` in allowed set
- valid `links` list → parsed; `type` in allowed associative set
- item missing `id` → validation error
- item `type` outside allowed set → validation error
- `entry_point: true` → `fm.entry_point is True`
- `entry_point: "yes"` (non-bool) → validation error
- regression: existing permanent/literature fixtures still pass

**GREEN impl** — files touched:

- `src/workflow/validation/schemas.py` — add `RelationEdge` dataclass
  (`id: str, type: str, weight: float|None, note: str|None`);
  `_STRUCTURAL_REL_TYPES`, `_ASSOCIATIVE_REL_TYPES` frozensets;
  `NoteRelations` dataclass (`derived_from`, `links`);
  `entry_point: bool = False` + `relations: NoteRelations | None = None` to `NoteFrontmatter`;
  `_validate_relations(data, errors)` helper wired into `validate_note_frontmatter`.

**Commit point:** suite green + flake8 0 → commit.

---

### Phase 2 — init.py templates + test updates

**Goal:** `workflow init` creates templates that scaffold all validator-supported fields.

**RED tests** (edit `tests/workflow/notes/test_init.py`):

- permanent template contains `main_topic`, `discipline_area`, `relations`, `entry_point`
- permanent template does NOT contain `delivered_from` (lock against obsidian.lua bug)
- literature template contains `bibkey`, `origin`, `main_topic`, `discipline_area`, `relations`
- literature template still has bib fence (regression)
- fleeting template does NOT contain `main_topic` or `relations`
- each rendered template passes `validate_note_frontmatter` without errors

**GREEN impl** — files touched:

- `src/workflow/notes/init.py` — rewrite the three `write_text` blocks in
  `_create_note_templates`; keep `if not <file>.exists()` guards.

**Opus review**:

- launch a python, architect and security opus sub-agents reviwers
- Fix any finding

**Commit point:** suite green + flake8 0 → commit.

---

### Phase 3 — discrepancy fix + live vault sync + docs (outside-repo, gated)

**Goal:** Live vault templates and obsidian.lua match the canonical schema.

**Steps (manual, not in test suite):**

1. Backup live vault templates:

   ```bash
   cp ~/01-U/0000AA-Vault/templates/permanent.md \
      ~/01-U/0000AA-Vault/templates/permanent.md.bak-2026-06-06
   cp ~/01-U/0000AA-Vault/templates/literature.md \
      ~/01-U/0000AA-Vault/templates/literature.md.bak-2026-06-06
   ```

2. Overwrite with the new content (matching init.py output for permanent/literature).
3. Fix `~/.config/nvim/lua/plugins/obsidian.lua`:
   - Change `delivered_from` → `derived_from` in the frontmatter func
   - Run `luac -p ~/.config/nvim/lua/plugins/obsidian.lua` to verify parse
4. Update `CLAUDE.md` — note `relations.derived_from` / `entry_point` in NoteFrontmatter
   fields list (already partially documented under validation).
5. Add ITEP-0013 Change Log entry: "2026-06-06 — Template gap fix: templates updated;
   obsidian.lua `delivered_from` bug corrected."

**Commit point (repo side only):** CLAUDE.md + any ADR changelog → commit.

---

## Risks / out of scope

- **In scope:** `NoteFrontmatter` DTO parse, `init.py` templates, test alignment,
  obsidian.lua bug fix, live vault manual update.
- **Out of scope:** `note_edge` ORM/migration, sync edge pass, cycle validation,
  `notes link --relation`, `graph trace`/`resume` — all deferred ITEP-0013 P0–P4.
  Wave C/D generated notes are already correct — do NOT touch.
- **Risk:** live vault overwrite → gated on backup + explicit manual step, never automated.
- **Risk:** obsidian.lua is outside the repo → cannot be tested in CI; luac -p is the check.
- Parsing is lenient: unknown `relation_type` values warn, don't break existing notes.

---

## Verification (each phase)

```bash
# Isolated suite — never touches live DB
WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py

# Lint
uv run flake8 src/ tests/ --max-line-length=127 --max-complexity=10
```
