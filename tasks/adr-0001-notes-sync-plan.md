# ADR-0001 Phase 1 Plan — `workflow notes sync`

**Status:** in-progress
**Tag target:** v1.4.0
**Route map:** tasks/route-map-post-itep-0011.md

## Goal

Make the GlobalBase `Link` / `Label` / `Citation` tables a queryable index of what
Markdown files actually contain. File-as-truth, DB-as-index. Idempotent bulk sync.

---

## Design decisions (pre-coding)

### R2 resolution — schema for plain `[[wikilink]]` targets

`Link.target_id` is FK → `label.id`, not `note.id`. For plain `[[note-ref]]` wikilinks
(no anchor), `sync_vault` creates a synthetic Label row:
```
Label(note_id=<target_note>.id, label="__note__")
```
This synthetic label is the `target_id` of the Link. On re-sync it is upserted
(already-exists check in `_upsert_label`). Orphan cleanup deletes Links whose
source or target Note no longer exists; synthetic labels are deleted via CASCADE.

`[[note-ref#anchor]]` wikilinks target real frontmatter-anchor Labels (label = anchor text).

### Wikilink regex source

Lift from `src/latexzettel/infra/regexes.py` — four compiled patterns:
- `WIKILINK_NOTE_RE` → `\[\[([^{#\]|]+)\]\]`
- `WIKILINK_NOTE_LABEL_RE` → `\[\[([^{#\]|]+)#\^?([^]]+)\]\]`
- `WIKILINK_NOTE_TEXT_RE` → `\[\[([^{#\]|]+)\|([^]]+)\]\]`
- `WIKILINK_NOTE_LABEL_TEXT_RE` → combined

Import them directly — **do not duplicate**.

### Upsert helpers source

Reuse `_upsert_label`, `_upsert_cite`, `_upsert_link` from
`src/workflow/lecture/linker.py:157,175,190`.

If these three grow beyond a copy-paste risk, extract to `src/workflow/notes/linker_ops.py`.
For now: import directly from `workflow.lecture.linker`.

### Frontmatter anchor field

Scan YAML frontmatter `anchors:` list (list of strings). Each entry → `Label(note_id, label=entry)`.

---

## Sub-tasks

- [ ] **T1** RED tests: `tests/workflow/notes/test_sync.py` (9 unit tests)
- [ ] **T2** RED tests: `tests/workflow/notes/test_cli_sync.py` (1 CLI smoke test)
- [ ] **T3** GREEN: `src/workflow/notes/sync.py` — `sync_vault()` + `SyncReport`
- [ ] **T4** GREEN: `src/workflow/notes/cli.py` — add `sync` subcommand
- [ ] **T5** Verification pass (pytest + regression + smoke)
- [ ] **T6** 4-reviewer pass (python + security + tdd + architect)
- [ ] **T7** Tag v1.4.0 + update primer

---

## New surface: `src/workflow/notes/sync.py`

```python
@dataclass
class SyncReport:
    notes_scanned: int = 0
    labels_registered: int = 0
    links_created: int = 0
    orphans_dropped: int = 0

def sync_vault(
    vault_root: Path,
    session: Session,
    *,
    dry_run: bool = False,
    project_filter: str | None = None,
) -> SyncReport:
    ...
```

Mirrors `link_lecture_files` in `src/workflow/lecture/linker.py:282-332`.

---

## CLI surface: `workflow notes sync`

```
workflow notes sync [--dry-run] [--project DDTTAA-YYPP]
```

Reports: notes scanned, labels registered, links created, orphans dropped.

---

## Tests (all RED before implementation)

### `tests/workflow/notes/test_sync.py`

| Test | Verifies |
|------|---------|
| `test_sync_empty_vault_noop` | Empty dir → SyncReport all zeros |
| `test_sync_creates_note_rows_from_md` | .md files → Note rows upserted |
| `test_sync_creates_label_rows_from_frontmatter_anchors` | `anchors:` → Label rows |
| `test_sync_creates_link_rows_from_wikilinks` | `[[ref]]` body → Link rows |
| `test_sync_idempotent_second_run_no_changes` | 2nd run delta = 0 |
| `test_sync_dry_run_writes_nothing` | dry_run=True → 0 DB writes |
| `test_sync_orphan_link_dropped_and_reported` | deleted file → Link dropped |
| `test_sync_project_filter_scopes_to_subtree` | --project limits scan |
| `test_sync_path_traversal_in_frontmatter_blocked` | malicious anchor rejected |

### `tests/workflow/notes/test_cli_sync.py`

| Test | Verifies |
|------|---------|
| `test_cli_sync_dry_run_exits_zero` | CLI smoke via CliRunner, WORKFLOW_DATA_DIR + WORKFLOW_VAULT_ROOT overridden |

---

## Verification gates

1. `pytest tests/workflow/notes/ -q` — all new tests green; coverage ≥ 80%.
2. `pytest -q --ignore=tests/test_database.py` — regression delta = 0 vs pre-phase baseline (49 failed / 984 passed).
3. Smoke: `WORKFLOW_VAULT_ROOT=/tmp/vault WORKFLOW_DATA_DIR=/tmp/wfdata workflow notes sync --dry-run`
4. Idempotency: second run delta = 0.
5. 4-reviewer pass; fix CRITICAL/HIGH.
6. Tag v1.4.0.
7. Update primer.md.

---

## Risks

- **R1 (MED):** wikilink regex divergence → mitigation: import from `latexzettel/infra/regexes.py`.
- **R2 (LOW):** schema mismatch for plain wikilinks → resolved above (synthetic `__note__` label).
- **R3 (LOW):** path traversal via frontmatter anchors → validate anchor strings with allowlist regex `^[a-zA-Z0-9._:-]+$`.
