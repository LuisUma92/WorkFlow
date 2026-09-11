# Implementation plan — flake8 strict-run cleanup (123 → C901 only)

Request: none — audit `tasks/audit/2026-09-10-tasks-and-primer-audit.md` item 10; Luis 2026-09-10:
"si su arreglo mejora el código, proceder con el arreglo".
Methodology: behaviour-preserving cleanup; suite must stay **2629 passed, 3 skipped**; no migration.

---

## Verified anchors (2026-09-10)

Strict run: `flake8 src/ tests/ --max-line-length=127 --max-complexity=10 --exclude=src/PRISMAreview` → 123:
F401 75 · F841 15 · C901 14 · E402 8 · E731 3 · E203 3 · E301 2 · E501 1 · E303 1 · E127 1.

- `latexzettel/api/sync.py:311` `force_synchronize` — `ts = timestamp or now()` never used; timestamps
  come from file mtimes. Parameter kept (public API), dead line removed.
- `latexzettel/cli/commands/notes.py:300` `cmd_to_md` — `out_path` computed via `click.Path.convert`
  (no validation options) then ignored in favour of `_Path(out_dir)` → dead block.
- `db/models/academic.py:31-37` — `BibEntry`, `Concept`, `GeneralProject` under `TYPE_CHECKING`,
  used in no annotation (relationship strings resolve via the mapper registry, not imports).
- `latexzettel/server/routers.py:26` `DEFAULT_SETTINGS` — not used, not re-exported (`server/main.py`
  imports only `ROUTES, CancelledError, CancelToken, ServerContext`).
- `tests/test_manager.py:17` E402 is legitimate (import after `pytest.importorskip`) → `noqa` with reason.
- E203 ×3 (`latex/braces.py`, `latex/comments.py`) = ruff-format slice style; the ruff format hook
  would re-introduce them.
- `flake8 .` (CI command form in CLAUDE.md) walks `.venv/` → 36 bogus hard-select hits.

## Decisions

1. F401 → `ruff check --select F401 --fix` on exactly the flagged files; suite catches side-effect imports.
2. F841 by hand: tests where the value *should* be checked get an assertion, otherwise drop the binding.
3. E731 → `operator.attrgetter`.
4. `.flake8`: `extend-ignore = E203` (formatter-compatible) + `extend-exclude = .venv`.
5. **C901 ×14 out of scope** → `tasks/requests/2026-09-10-c901-complexity-refactors.md` (refactors of
   complexity-50/38 functions need their own TDD plan).

## Results (2026-09-10)

- F401 75 → 0 via `uvx ruff check --select F401 --fix` (75 fixed, 0 remaining); suite green right
  after → none was a side-effect import.
- F841 15 → 0. Tests strengthened, not just silenced: `exercise gc` abort now asserts exit 1;
  `sync_vault` test asserts `report.concept_links_created == 2`. Dead code removed:
  `force_synchronize` `ts` (+ its now-unused `now` import), `cmd_to_md` `out_path`, 3× unused
  `CLIContext` bindings, dead `__import__` query in `test_service.py`.
- E731 → `attrgetter`; E402 moved to top (`unify.py`, `test_collectors.py`), `noqa` only in
  `test_manager.py`; E501 was a pasted `:contentReference[oaicite:7]{index=7}` artifact in a
  `fs.py` docstring; E301/E303/E127 fixed.
- Strict run: **123 → 14 (C901 only)**. `flake8 . --select=E9,F63,F7,F82` → 0 (was 36, all `.venv`).
- Suite **2629 passed, 3 skipped** (unchanged). `workflow --help` OK; touched modules import.
- Found, not fixed (pre-existing since `014d0a5`): `numpy` is imported by
  `latexzettel/api/analysis.py` (and transitively `latexzettel/server/routers.py`, the nvim RPC
  server) but is **not declared** in `pyproject.toml`/`uv.lock` → those modules fail to import in
  the project venv.

## Verification

```bash
WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py   # 2629 passed, 3 skipped
uv run flake8 src/ tests/ --max-line-length=127 --max-complexity=10 --exclude=src/PRISMAreview  # only C901
uv run flake8 . --count --select=E9,F63,F7,F82   # 0 (venv excluded)
```
