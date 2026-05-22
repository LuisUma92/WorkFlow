# Implementation Plan: Phase A — `workflow notes` CRUD

## Overview
Extend the `workflow notes` Click group (currently only `init`) with five filesystem-resident CRUD subcommands: `new`, `list`, `show`, `tag`, `link`. All operations read/write `.md` files with YAML frontmatter and re-validate via the existing `NoteFrontmatter` dataclass before any disk write. No DB access required.

## Requirements
- Subcommands: `new`, `list`, `show`, `tag`, `link` (preserve existing `init`).
- Reuse `NoteFrontmatter` + `validate_note_frontmatter` from `src/workflow/validation/schemas.py`.
- All mutating ops re-validate before write; non-zero exit on failure.
- `--json` shape mirrors `course list --json` (flat `[{...}, ...]` for list; `{...}` for show).
- Empty filtered list returns `[]` exit 0.
- Tests at `tests/workflow/test_notes.py` using `tmp_path` and Click's `CliRunner`.

## Architecture Changes

### File-by-file change list

| Path | Action | LOC | Purpose |
|------|--------|-----|---------|
| `src/workflow/notes/cli.py` | EDIT | +180 | Wire 5 new `@notes.command()` decorators; delegate to service. |
| `src/workflow/notes/service.py` | NEW | ~220 | Pure functions: `create_note`, `list_notes`, `read_note`, `update_tags`, `add_link`. Filesystem I/O + validation. |
| `src/workflow/notes/formatters.py` | NEW | ~70 | `format_note_json`, `format_note_table`, `format_notes_list_json`, `format_notes_list_table`. Mirrors `evaluation/formatters.py`. |
| `src/workflow/notes/discovery.py` | NEW | ~60 | `iter_note_files(root: Path) -> Iterator[Path]`; `parse_frontmatter(path) -> tuple[dict, str]` (YAML head + body). |
| `src/workflow/notes/__init__.py` | EDIT | +2 | Re-export `notes` group (no behavior change). |
| `tests/workflow/test_notes.py` | NEW | ~280 | TDD test suite (see below). |
| `tests/workflow/conftest.py` | EDIT (if exists) or skip | — | Optional shared `tmp_workspace` fixture. |

Note: `service.py` is intentionally pure (no Click, no DB). `cli.py` only translates flags → service calls → formatter output.

## Click Signatures

```python
@notes.command(name="new")
@click.option("--id", "note_id", required=True, help="Slug/ID for the note.")
@click.option("--title", required=True)
@click.option("--type", "note_type",
              type=click.Choice(["permanent", "literature", "fleeting"]),
              default="permanent")
@click.option("--tags", default="", help="Comma-separated tags.")
@click.option("--concepts", default="", help="Comma-separated concepts.")
@click.option("--candidate-project", "candidate_project", default=None,
              help="Forward reference DDTTAA-YYPP.")
@click.option("--dir", "target_dir", type=click.Path(file_okay=False), default=".")
@click.option("--force", is_flag=True, help="Overwrite if exists.")
@click.option("--json", "as_json", is_flag=True)

@notes.command(name="list")
@click.argument("note_id", required=False, default=None)
@click.option("--tag", default=None)
@click.option("--concept", default=None)
@click.option("--candidate-project", "candidate_project", default=None)
@click.option("--type", "note_type",
              type=click.Choice(["permanent", "literature", "fleeting"]), default=None)
@click.option("--depth", type=int, default=None,
              help="Max traversal depth (only with <note_id>). Default: unlimited.")
@click.option("--edge-types", "edge_types", default="concepts,references,exercises,wikilinks",
              help="Comma-separated edge types to follow when <note_id> given.")
@click.option("--dir", "root_dir", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--json", "as_json", is_flag=True)
# Behaviour:
#   no note_id → flat top-level listing of `root_dir` (no recursion).
#   note_id    → BFS from that note, follow outgoing edges per --edge-types,
#                cycle-safe, capped by --depth.

@notes.command(name="show")
@click.argument("note_id")
@click.option("--dir", "root_dir", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--json", "as_json", is_flag=True)

@notes.command(name="tag")
@click.argument("note_id")
@click.option("--add", "add_tags", multiple=True)
@click.option("--remove", "remove_tags", multiple=True)
@click.option("--dir", "root_dir", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--json", "as_json", is_flag=True)

@notes.command(name="link")
@click.argument("note_id")
@click.option("--concept", "concept", default=None)
@click.option("--reference", "reference", default=None)
@click.option("--exercise", "exercise", default=None)
@click.option("--dir", "root_dir", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--json", "as_json", is_flag=True)
# Mutex: exactly one of --concept/--reference/--exercise required → click.UsageError otherwise.
```

JSON shape for `list` (mirrors `course list --json`):
```json
[{"id": "...", "title": "...", "tags": [...], "concepts": [...],
  "candidate_project": null, "type": "permanent", "path": "/abs/path.md"}]
```
JSON shape for `show`: same dict + `"references"`, `"exercises"`, `"images"`, `"created"`.

## Implementation Steps

### Phase A.1 — Service layer (TDD)
1. **Write service tests first** (`tests/workflow/test_notes.py`) — RED.
2. **Implement `discovery.py`** — YAML frontmatter parse (use stdlib + `yaml.safe_load`; bail on missing `---` fences).
3. **Implement `service.py`**:
   - `create_note(target_dir, fm: NoteFrontmatter, force: bool) -> Path` — serializes frontmatter, refuses overwrite unless `force`, re-validates via `validate_note_frontmatter` before write.
   - `list_notes(root, *, tag, concept, candidate_project, note_type) -> list[tuple[Path, NoteFrontmatter]]` — top-level only (no recursion); silently skips files whose frontmatter fails to parse (warning to stderr).
   - `walk_connections(root, start_id, *, depth, edge_types) -> list[tuple[Path, NoteFrontmatter]]` — BFS from `start_id`, follow outgoing edges in `edge_types ⊆ {concepts, references, exercises, wikilinks}`. Visited set; honours `depth` cap; resolves `[[wikilinks]]` in body via stdlib regex.
   - `resolve_workspace_root(start: Path) -> Path` — walks up looking for `config.yaml` then `.git`; falls back to CWD with stderr warning.
   - `read_note(root, note_id) -> tuple[Path, NoteFrontmatter, str]` — raises `NoteNotFound` if no match.
   - `update_tags(root, note_id, add, remove) -> NoteFrontmatter` — load, mutate immutable dataclass via `dataclasses.replace`, re-validate, rewrite file (preserve body).
   - `add_link(root, note_id, *, concept=None, reference=None, exercise=None) -> NoteFrontmatter` — append (idempotent) to one of `concepts`/`references`/`exercises`, re-validate, rewrite.
4. **Implement formatters** mirroring `evaluation/formatters.py`.
5. **Wire `cli.py`**.

### Phase A.2 — CLI wiring + integration tests
6. CLI commands delegate to service; `--json` switches formatter; raise `click.ClickException` on validation errors (non-zero exit).

## TDD Test List (`tests/workflow/test_notes.py`)

Fixtures:
- `runner` → `CliRunner()`.
- `workspace(tmp_path)` → `tmp_path` with empty `notes/` subdir.
- `seed_note(workspace)` → factory writing a valid `.md` and returning its path/id.

| Test name | Asserts |
|-----------|---------|
| `test_new_creates_md_with_valid_frontmatter` | File exists; YAML round-trips through `validate_note_frontmatter` clean. |
| `test_new_json_emits_path_and_id` | `--json` output is dict with keys `{path, id}`. |
| `test_new_refuses_overwrite_without_force` | Second call exits non-zero; `--force` succeeds. |
| `test_new_rejects_invalid_candidate_project` | `--candidate-project foo` exits non-zero, stderr names the field. |
| `test_new_rejects_invalid_type` | Click choice rejects `--type bogus`. |
| `test_list_empty_returns_empty_json_array` | Exit 0, stdout `[]`. |
| `test_list_no_id_top_level_only` | Notes nested in subdir not returned without `<id>`. |
| `test_list_with_id_walks_connections` | `notes list <id>` returns id + connected notes via `concepts`/`references`/`exercises`. |
| `test_list_with_id_depth_limit` | `--depth 1` returns id + direct neighbours only. |
| `test_list_with_id_edge_type_filter` | `--edge-types concepts` ignores reference/exercise edges. |
| `test_list_with_id_cycle_safe` | A↔B mutual link → each appears once. |
| `test_list_unknown_id_exits_nonzero` | `notes list missing-id` errors clearly. |
| `test_list_filters_by_tag` | Two notes seeded; only one tagged returned. |
| `test_list_filters_by_concept` | Filter works via `concepts` field. |
| `test_list_filters_by_type` | Filter works via `type` field. |
| `test_list_filters_by_candidate_project` | Filter works on DDTTAA-YYPP. |
| `test_list_json_shape_matches_sibling` | Each item has `{id, title, tags, concepts, candidate_project, type, path}`. |
| `test_show_known_id_returns_full_dict` | All `NoteFrontmatter` fields present. |
| `test_show_unknown_id_exits_nonzero` | Exit code != 0, error mentions id. |
| `test_tag_add_and_remove` | Frontmatter file updated; round-trips validation. |
| `test_tag_idempotent_add` | Adding existing tag doesn't duplicate. |
| `test_tag_remove_missing_is_noop` | Removing absent tag does not error. |
| `test_link_concept_appends` | `concepts` list grows by 1. |
| `test_link_reference_appends` | `references` list grows by 1. |
| `test_link_exercise_appends` | `exercises` list grows by 1. |
| `test_link_idempotent` | Adding same link twice → still one entry. |
| `test_link_requires_exactly_one_target` | Zero or two of `--concept/--reference/--exercise` → exit 2. |
| `test_create_then_list_then_show_round_trip` | End-to-end happy path. |
| `test_mutating_ops_revalidate_before_write` | Monkeypatch frontmatter to corrupt state pre-write → write aborted, file unchanged on disk. |
| `test_validate_notes_clean_on_freshly_created` | After `notes new`, running `validate notes` (existing CLI) reports zero warnings (sanity). |

## Edge Cases / Failure Modes
- File without YAML fences → `list` skips with stderr warning (not fatal).
- Duplicate IDs across files → `show`/`tag`/`link` raise `click.ClickException("ambiguous id")`.
- Frontmatter present but body missing → still writeable; preserve trailing newline.
- Unicode in title → ensure `yaml.safe_dump(allow_unicode=True)`.
- `--tags ""` → empty list, not `[""]`.
- Concurrent write race → out of scope for Phase A (single-user CLI).
- Symlinked note files → `Path.resolve()` once; do not follow symlinks during list discovery to avoid loops.
- `note_id` with `/` or path traversal → reject (`click.UsageError`).
- Unknown CLI flags rejected by Click automatically.

## Verification Commands

```bash
# Run new test file only
pytest tests/workflow/test_notes.py -v

# Coverage on new package
pytest tests/workflow/test_notes.py \
  --cov=src/workflow/notes --cov-report=term-missing

# Lint (CI-equivalent)
flake8 src/workflow/notes tests/workflow/test_notes.py \
  --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 src/workflow/notes tests/workflow/test_notes.py \
  --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

# Smoke
workflow notes --help
workflow notes new --id test-001 --title "Hello" --json
workflow notes list --json
workflow validate notes  # existing command should pass
```

## Risks & Mitigations
- **Risk**: YAML serialization round-trip alters key order / formatting → diff churn.
  - Mitigation: Use `sort_keys=False`, fixed key order matching `NoteFrontmatter` field order.
- **Risk**: Body preservation across mutations subtly breaks (trailing whitespace).
  - Mitigation: Split on first occurrence of closing `---\n`, preserve byte-exact tail.
- **Risk**: `list` discovery walks `node_modules` / `.git` / large `images/`.
  - Mitigation: Default-skip directories starting with `.` and an explicit blocklist (`images/`, `.git/`, `__pycache__/`).
- **Risk**: JSON shape drift from `course list --json`.
  - Mitigation: Lock shape in `test_list_json_shape_matches_sibling` with explicit key set.
- **Risk**: Future Phase B adds `main_topic`/`discipline_area` → list/show JSON shape grows.
  - Mitigation: Additive JSON evolution; keep Phase A keys stable.

## Resolved Decisions (2026-05-04)
- **Q1 — `notes new` default dir:** auto-resolve to `<workspace>/notes/<type>/`.
  Workspace root = nearest ancestor containing `config.yaml` (ITeP project marker)
  or `.git`. If none found → fall back to CWD with stderr warning.
- **Q2 — `tag --add/--remove`:** `multiple=True` flag-repeat style
  (`--add foo --add bar`). Comma-style stays only on `notes new --tags a,b` for
  one-shot scaffold terseness.
- **Q3 — `list` scope:** depends on positional `[note_id]`:
  - `notes list` (no id) → top-level files in `--dir` only, no recursion.
  - `notes list <id>` → start at `<id>`, BFS-walk outgoing connections
    (`concepts`, `references`, `exercises`, `[[wikilinks]]` in body).
    Add `--depth N` (default unlimited) and `--edge-types concepts,references,...`
    (default all). Cycle-safe via visited set.
- **Q4 — `notes new` non-JSON stdout:** absolute path.

## Success Criteria
- [ ] `workflow notes --help` lists `init, new, list, show, tag, link`.
- [ ] `notes new` round-trips through `workflow validate notes` clean.
- [ ] `notes list --json` returns `[]` on empty workspace, exit 0.
- [ ] All test cases in `tests/workflow/test_notes.py` pass.
- [ ] flake8 clean on new files at max-line-length 127, complexity 10.
- [ ] No DB engine touched (Phase A is filesystem-only).
- [ ] Phase B can extend `NoteFrontmatter` additively without breaking Phase A tests.

## Pattern references
- `src/workflow/evaluation/cli.py` — Click group split + service delegation.
- `src/workflow/evaluation/formatters.py` — JSON/table formatter pair.

## Status
`done` — A.1 + A.2 shipped; 4-reviewer audit + fix pass shipped (`3057e87`).
Suite: 978 pass.

## Deferred follow-ups (Linux-only priority — defer until first non-Linux user lands)

### CRLF frontmatter fence round-trip
**Scope:** `discovery.parse_frontmatter` + `service._write_note_file`.
**Current behaviour:** body bytes after closing fence preserved byte-exact;
fence area (opening `---`, YAML block, closing `---`, post-fence newline) is
re-emitted with `\n` line endings regardless of input EOL. `yaml.safe_dump`
never emits `\r\n`.
**Symptom on CRLF input:** mixed line endings post-mutation (frontmatter LF,
body CRLF). `git diff` whitespace churn on every `tag`/`link`. Functionally OK.
**Fix when needed:** detect input EOL at parse (`_detect_eol(text) -> "\n" | "\r\n"`),
re-emit fences and post-fence separator using detected EOL. ~10 LOC + 1 test
(`test_crlf_frontmatter_round_trip`).
**Trigger:** first vault note authored on Windows (CRLF throughout). Today
the vault is 100% Linux-authored (LF) — UCIMED-CI0006 migration confirmed.
