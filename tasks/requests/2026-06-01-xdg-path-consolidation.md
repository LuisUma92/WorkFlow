# Request: XDG path consolidation — align code with ADR-0008

- **Date:** 2026-06-01
- **Status:** RESOLVED — Implemented (executed via `tasks/plans/2026-06-05-wave-e-xdg-path-consolidation-plan.md`;
  `src/workflow/paths.py` platformdirs-based resolver shipped, ADR-0008 amended 2026-06-05; closure
  annotation applied retroactively 2026-07-05 per `tasks/audit/2026-07-05-tasks-adr-completeness-audit.md`
  Summary #6)
- **Related:** ADR-0008 (Accepted, 2026-03-25), ADR-0003, ITEP-0011
- **Type:** Refactor / infrastructure (no new feature surface)

## Problem

ADR-0008 ("XDG Directory Layout", **Accepted** 2026-03-25) defines a coherent
filesystem strategy. The code never fully adopted it and has since diverged into
a **split-brain layout**: the same logical app stores its database in one root
and its assets in another. Path defaults are also duplicated across three
distinct appdirs namespaces.

### Divergence audit (code vs ADR-0008)

| Concern | ADR-0008 mandates | Code reality | Location |
|---|---|---|---|
| Global DB | `~/.local/share/workflow/workflow.db` | `~/01-U/workflow/workflow.db` | `db/engine.py:53` (`_default_global_path`) |
| `base.py` docstring | data dir | stale — claims `~/.config/workflow/workflow.db` | `db/base.py:4` |
| sty / templates | `~/.local/share/workflow/` | `user_data_dir("workflow")/sty` ✓ | `itep/defaults.py:14` |
| `itep.db` | single `workflow` namespace | separate `user_data_dir("itep")` namespace | `itep/defaults.py:10` |
| `cleta` config | (config under workflow) | third namespace `user_config_dir("cleta","LuisUmana")` | `lectkit/cleta.py:7` |
| Single config file | `~/.config/workflow/config.yaml` (`vault_path`, `default_institution`, `default_timezone`) | **never implemented** — no reader exists | — |
| Physics default | (not in ADR) | hardcoded `~/Documents/01-U/00-Fisica` | `itep/defaults.py:5` |
| Migration dump | (not in ADR) | hardcoded `~/01-U/workflow/...` | `migrations/global/0009_normalize_models.py:228` |
| Vault root | stays **outside** XDG (hand-edited docs) | `~/01-U/0000AA-Vault` ✓ (but ADR text says `~/Documents/01-U` — ADR itself stale) | `vault/paths.py:15` |

### Concrete symptom

Live global DB resolves to `~/01-U/workflow/workflow.db` while shared `.sty`
files resolve to `~/.local/share/workflow/sty/`. One app, two roots. A user
copying/backing up `~/.local/share/workflow/` silently omits the database.

## Benefits of migrating

1. **Correctness** — closes the gap against an already-Accepted ADR instead of
   leaving it aspirational.
2. **Single data root** — DB, sty, templates, img under one
   `~/.local/share/workflow/`; one backup/sync target.
3. **One namespace** — collapse `itep` + `cleta` appdirs namespaces into
   `workflow`; removes "where did my file go" surprises.
4. **Config single-source** — implement the `config.yaml` reader so
   `vault_path` / institution / timezone stop being hardcoded constants.
5. **Env override preserved** — `WORKFLOW_DATA_DIR` / `WORKFLOW_VAULT_ROOT`
   still win, so power users and tests are unaffected.

## Risks / non-goals

- **Live DB relocation.** The active DB is at `~/01-U/workflow/workflow.db`.
  Changing the default silently points the engine at an empty
  `~/.local/share/workflow/workflow.db`. **Mitigation:** back-compat resolver —
  if `WORKFLOW_DATA_DIR` unset AND XDG path missing AND legacy
  `~/01-U/workflow/workflow.db` exists, use legacy + emit a one-time migration
  notice (or `workflow db migrate-xdg` mover command). No data moves without
  explicit user action.
- **Vault stays non-XDG.** Vault is hand-edited documents, not regenerable
  data — keep `~/01-U/0000AA-Vault` (env-overridable). Fix the *ADR text* to
  match the real vault path rather than moving the vault.
- **Not** a schema change. ORM/migrations untouched except the hardcoded dump
  path in migration 0009.

## Proposed scope (phased, TDD)

- **P0 — Audit lock + ADR amendment.** Amend ADR-0008 to: (a) correct vault
  path to `~/01-U/0000AA-Vault`, (b) record `WORKFLOW_DATA_DIR` env override as
  canonical, (c) note legacy back-compat resolver. Fix stale `base.py:4`
  docstring.
- **P1 — Path module + `platformdirs` swap.** Replace `appdirs` dep with
  `platformdirs` in `pyproject.toml`. Introduce `workflow.paths` (single
  source): `data_dir()`, `config_dir()`, `cache_dir()`, `global_db_path()`
  using `platformdirs` with `WORKFLOW_DATA_DIR` override + legacy fallback.
  Route `engine._default_global_path`, `itep/defaults.py`, `cleta.py` through
  it. RED→GREEN tests for override precedence + legacy fallback.
- **P2 — Config reader.** Implement `~/.config/workflow/config.yaml` loader
  (`vault_path`, `default_institution`, `default_timezone`) with documented
  precedence: env > config.yaml > built-in default. Wire `vault/paths.py` and
  `itep` institution defaults to read it.
- **P3 — Namespace collapse + migrator.** Move `itep.db` under the `workflow`
  namespace; add `workflow db migrate-xdg` (idempotent, dry-run default,
  **explicit only — never auto-runs**) to relocate a legacy `~/01-U/workflow/`
  DB into the XDG data dir with backup. Fix migration-0009 hardcoded dump path.
- **P4 — Docs.** Update `CLAUDE.md`, primer, `nvim-plugin/doc/workflow.txt`,
  ADR INDEX.

## Open questions

1. ~~`platformdirs` vs current `appdirs`?~~ **DECIDED (2026-06-01): swap to
   `platformdirs`** (maintained successor of unmaintained `appdirs`). Bundled
   into P1: replace the `appdirs` dep in `pyproject.toml`, port the 3 call sites
   (`itep/defaults.py`, `lectkit/cleta.py`, new `workflow.paths`).
2. ~~Auto-move on first run, or require explicit `workflow db migrate-xdg`?~~
   **DECIDED (2026-06-01): explicit `workflow db migrate-xdg` only.** No
   auto-relocate. First run with a legacy DB present uses the legacy path via
   fallback resolver and emits a one-time notice pointing at the command.
3. ~~Keep `WORKFLOW_DATA_DIR` at `~/01-U/workflow`, or actually relocate?~~
   **DECIDED (2026-06-01): relocate this machine's DB** to
   `~/.local/share/workflow/workflow.db` via `workflow db migrate-xdg`. Do NOT
   pin `WORKFLOW_DATA_DIR` to the legacy path afterward — let the XDG default
   take over. Post-migration, `~/01-U/workflow/` holds only the backup.

## Recommendation

**Proceed.** Benefits are real (consistency, single backup root, config
single-source) and the dominant risk — live DB relocation — is fully mitigated
by a legacy fallback resolver plus an explicit, dry-run-default migrator. No
data moves implicitly.
