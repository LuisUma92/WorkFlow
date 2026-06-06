# Implementation plan — Wave E: XDG path consolidation

Request: `tasks/requests/2026-06-01-xdg-path-consolidation.md` (all 3 open questions DECIDED 2026-06-01)
Roadmap: `tasks/roadmap/2026-06-03-bibliography-and-two-workflow-roadmap.md` §Wave E
ADR: `docs/ADR/0008-*.md` (Accepted 2026-03-25) — **amended by P0**.
Methodology: TDD (RED→GREEN→REFACTOR). Phases ship independently; commit at each GREEN.
**NOT a schema change** — ORM/migrations untouched except the hardcoded dump path in migration 0009.

---

## Verified anchors (confirmed in code)

- `src/workflow/db/engine.py:53` — `_default_global_path()` →
  `Path(os.environ.get("WORKFLOW_DATA_DIR", "~/01-U/workflow")).expanduser() / "workflow.db"`.
  **Non-XDG default.** This is the live-DB risk surface.
- `src/workflow/db/base.py:4` — STALE docstring: "GlobalBase: tables in
  `~/.config/workflow/workflow.db`" (wrong root; data not config).
- `src/itep/defaults.py:3,9,10,14` — uses `appdirs.user_data_dir`:
  - `DEF_ABS_SRC_DIR = user_data_dir("workflow", "LuisUmana")`
  - `DB_PATH = user_data_dir("itep") / "itep.db"`  ← **separate namespace**
  - `_XDG_STY = user_data_dir("workflow") / "sty"`  ← no-author variant
- `src/lectkit/cleta.py:3,7` — `user_config_dir("cleta", "LuisUmana")` ← **third namespace**.
- `src/workflow/vault/paths.py:16` — `ENV_VAULT_ROOT = "WORKFLOW_VAULT_ROOT"`,
  `resolve_vault_root()` default `~/01-U/0000AA-Vault` (stays NON-XDG — vault is hand-edited docs).
- `src/workflow/db/migrations/global/0009_normalize_models.py:228` — hardcoded `~/01-U/workflow/…`
  dump path.
- `pyproject.toml:18` — `dependencies = ["appdirs", "bibtexparser", "click", "pyyaml", "sqlalchemy"]`.
  **`appdirs` → `platformdirs` swap.**
- Engine session pattern: Click cmds use `get_engine_from_ctx(ctx)` (`obj["engine"]` injectable in tests).
- conftest autouse `_isolate_workflow_data_dir` sets `WORKFLOW_DATA_DIR` per-test;
  `global_session`/`global_engine` are **in-memory** (`sqlite:///:memory:`). Path-resolution tests
  must monkeypatch env + use tmp_path, NOT global_session.

---

## Target / design

One data root (`platformdirs.user_data_dir("workflow")`), one config file
(`~/.config/workflow/config.yaml`), one namespace. `WORKFLOW_DATA_DIR` / `WORKFLOW_VAULT_ROOT`
env overrides still win. Legacy `~/01-U/workflow/workflow.db` keeps working via a back-compat
resolver; relocation happens ONLY via explicit `workflow db migrate-xdg` (dry-run default).

### `workflow.paths` resolution contract (P1)

`global_db_path()` precedence:
1. `$WORKFLOW_DATA_DIR/workflow.db` if env set (highest — tests/power users).
2. else XDG `data_dir()/workflow.db` if it **exists**.
3. else legacy `~/01-U/workflow/workflow.db` if it **exists** → return legacy **+ emit one-time
   notice** pointing at `workflow db migrate-xdg`.
4. else XDG `data_dir()/workflow.db` (new-install default; may not exist yet).

`data_dir()` / `config_dir()` / `cache_dir()` = `platformdirs.{user_data,user_config,user_cache}_dir("workflow")`.

### Commands / API surface (P3)

```bash
workflow db migrate-xdg [--dry-run/--no-dry-run] [--yes]   # dry-run DEFAULT; explicit only; never auto
```
- Moves legacy `~/01-U/workflow/workflow.db` → `data_dir()/workflow.db`, backs up legacy first.
- Idempotent: no legacy DB or XDG target already present → reports "nothing to do", exit 0.
- `--dry-run` (default) prints the plan, moves nothing.

---

## Decisions — LOCKED (request 2026-06-01)

1. **platformdirs swap** — replace `appdirs` dep; port all 3 call sites + new `workflow.paths`.
2. **Explicit `workflow db migrate-xdg` only** — no auto-relocate; first run with legacy DB uses
   fallback resolver + one-time notice.
3. **Relocate this machine's DB** to `data_dir()/workflow.db` via the migrator. Do NOT pin
   `WORKFLOW_DATA_DIR` to legacy afterward. Post-migration, `~/01-U/workflow/` holds only the backup.
4. **Vault stays non-XDG** (`~/01-U/0000AA-Vault`, env-overridable). Fix ADR *text* only.
5. Env override (`WORKFLOW_DATA_DIR`/`WORKFLOW_VAULT_ROOT`) always wins (tests unaffected).

---

## Phases

### P0 — ADR amendment + stale docstring (docs only) — INDEPENDENT
- Amend `docs/ADR/0008-*.md`: (a) vault path → `~/01-U/0000AA-Vault`, (b) record
  `WORKFLOW_DATA_DIR` env override as canonical, (c) note legacy back-compat resolver + explicit
  `migrate-xdg`. Add an amendment block (do not rewrite history; append "## Amendment 2026-06-05").
- Fix `src/workflow/db/base.py:4` docstring: `~/.config/workflow/workflow.db` →
  `~/.local/share/workflow/workflow.db` (data dir, env-overridable).
- **No tests** (doc/comment only). **Commit:** `docs(wave-e): amend ADR-0008 + fix base.py docstring`.

### P1 — `workflow.paths` + platformdirs swap (TDD) — FOUNDATION
- `pyproject.toml`: `appdirs` → `platformdirs`. (`pip install platformdirs` in the venv.)
- NEW `src/workflow/paths.py`: `data_dir()`, `config_dir()`, `cache_dir()`, `global_db_path()`,
  `legacy_db_path()`, plus a `_notice_once` guard for the legacy notice.
- Route through it: `engine._default_global_path` → `paths.global_db_path()`; `itep/defaults.py`
  (`DEF_ABS_SRC_DIR`, `_XDG_STY`) → `paths.data_dir()`; `lectkit/cleta.py` → `paths.config_dir()`.
- **RED tests** (`tests/workflow/test_paths.py`): env override wins; XDG-exists path; legacy
  fallback when XDG missing + legacy exists (monkeypatch `platformdirs` + tmp dirs); new-install
  default; `data_dir/config_dir/cache_dir` shape. Use monkeypatch.setenv/delenv + tmp_path;
  monkeypatch `platformdirs.user_data_dir` to a tmp root. DO NOT touch the real `~/.local/share`.
- **Commit:** suite green + flake8 0 → `feat(paths): workflow.paths + platformdirs swap (Wave E P1)`.

### P2 — config.yaml reader (TDD) — depends on P1
- NEW `src/workflow/config.py`: `load_config()` reads `config_dir()/config.yaml`
  (`vault_path`, `default_institution`, `default_timezone`); missing file → empty/defaults.
- Precedence: **env > config.yaml > built-in default.** Wire `vault/paths.py` (`vault_path`) and
  `itep` institution default to consult it.
- **RED tests** (`tests/workflow/test_config.py`): missing file → defaults; file values read;
  env beats config; malformed YAML → clear error. tmp config dir via monkeypatch.
- **Commit:** `feat(config): config.yaml reader (Wave E P2)`.

### P3 — namespace collapse + `migrate-xdg` (TDD) — depends on P1
- `itep/defaults.py`: `DB_PATH` `itep` namespace → `paths.data_dir()/itep.db` (collapse).
- NEW `workflow db migrate-xdg` Click command (dry-run default, `--yes`, never auto-runs):
  back up legacy DB, move to `global_db_path()` XDG target, idempotent.
- Fix `migrations/global/0009:228` hardcoded dump path → `paths.data_dir()` (or removed if dead).
- **RED tests** (`tests/workflow/test_migrate_xdg.py`): dry-run moves nothing + prints plan;
  real move relocates + backs up + idempotent re-run "nothing to do"; missing legacy → no-op.
  Use tmp dirs + monkeypatched paths; NEVER the live DB.
- **Commit:** `feat(db): migrate-xdg + itep namespace collapse (Wave E P3)`.

### P4 — docs — depends on all
- `CLAUDE.md` (XDG layout note + `workflow db migrate-xdg`), primer, `nvim-plugin/doc/workflow.txt`
  (if any nvim surface — none here), `docs/ADR/INDEX.md`.
- **Commit:** `docs(wave-e): document XDG consolidation + migrate-xdg (Wave E P4)`.

---

## Parallelization (honest)

- **Round 1 (parallel, disjoint files):** P0 (docs: ADR-0008 + base.py docstring) ∥ P1 (foundation).
- **Round 2 (sequential):** P2 and P3 BOTH edit `itep/defaults.py` (P1 already touched it) →
  collision risk → run them sequentially (or as one agent), NOT in parallel.
- **Round 3:** P4 docs after P2+P3 land.

## Risks / out of scope

- **Live-DB relocation** — mitigated by the 4-step fallback resolver + explicit dry-run-default
  migrator. No data moves implicitly. NEVER run `migrate-xdg --no-dry-run` against the live machine
  inside tests or agents.
- **Out of scope:** moving the vault; schema/ORM changes; the `permanent.md` template gap
  (`main_topic`+`discipline_area`) — roadmap bundles it under Wave E but it is a separate template
  edit; **track as P5/follow-up, not blocking the path work.**
- **Invariant:** with `WORKFLOW_DATA_DIR` set (as in every test via conftest autouse), behaviour is
  byte-identical to today — the full existing suite is the regression gate.

## Verification (each phase)

```bash
pip install platformdirs    # P1 once
pytest tests/workflow/test_paths.py tests/workflow/test_config.py tests/workflow/test_migrate_xdg.py -q
pytest tests/workflow -q    # full regression (env override keeps everything green)
flake8 src/workflow/paths.py src/workflow/config.py <edited files> --max-line-length=127 --max-complexity=10
```
