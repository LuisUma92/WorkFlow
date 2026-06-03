---
status: completed
---

# LZK-0004 — Remove latexzettel Peewee/SQLA shim

> Deferred plan. Target release: v1.6.0 (after vault CLI + migration 0008 hotfix v1.5.1).

## Context

`src/latexzettel/infra/orm.py` (55 LOC) is a leftover compatibility shim from the Peewee→SQLAlchemy migration. It now does nothing but re-export `Note, Citation, Label, Link, Tag, NoteTag` from `workflow.db.models.notes` and lazy-init the global engine. Peewee migration is complete (zero `peewee` imports in `src/`).

The shim survives because `latexzettel/api/` modules thread a `db` module-object through every function signature (`db.Note`, `db.Citation`) and `server/main.py` loads it dynamically via `_import_db_module("latexzettel.infra.orm")`. ADR `LZK-0004-dependency-injection-db-shim.md` marks shim removal as the end-state.

**Outcome:** Drop the `db` parameter from every API function, import SQLA models directly, delete the shim file. Net negative LOC, simpler call graph, no behavior change.

## Scope

**Delete:** `src/latexzettel/infra/orm.py` (55 LOC)

**Inline-import models (replace `db.Note` → `Note`):**
- `src/latexzettel/api/notes.py` (306 LOC)
- `src/latexzettel/api/render.py` (540 LOC)
- `src/latexzettel/api/analysis.py` (195 LOC)
- `src/latexzettel/api/markdown.py` (377 LOC)
- `src/latexzettel/api/sync.py` (447 LOC)
- `src/latexzettel/api/export.py` (251 LOC)
- `src/latexzettel/api/workflows.py` (129 LOC)

**Drop `db` param threading:**
- `src/latexzettel/server/main.py:235–322` — remove `_import_db_module`, `db_module_path`, `ServerContext.db`
- `src/latexzettel/server/routers.py` — drop `ctx.db` from 14 callsites (179, 198, 241, 256, 275, 299, 318, 340, 353, 377, 400, 473, 481, 494)
- `src/latexzettel/server/protocols.py` — drop `db` field from `ServerContext`

**Engine init:**
- `src/latexzettel/infra/db.py:162` — replace `from latexzettel.infra import orm as db_mod` with direct `from workflow.db.engine import get_global_engine, init_global_db`.

## Phased execution

### P1 — API inline imports (per file, GREEN-keeping)
For each `api/*.py`:
1. Add `from workflow.db.models.notes import Note, Citation, Label, Link, Tag, NoteTag` (only names used).
2. Find/replace `db.Note` → `Note`, `db.Citation` → `Citation`, etc.
3. Remove `db` parameter from every function signature.
4. Run `pytest -k latexzettel or notes`.
5. Commit per file (7 commits).

### P2 — Server context cleanup
1. Drop `ServerContext.db` field.
2. Remove `_import_db_module` + `db_module_path` from `server/main.py`.
3. Drop `ctx.db` from 14 router callsites.
4. RPC smoke (if test added).
5. Single commit.

### P3 — Engine init + shim deletion
1. Rewrite `infra/db.py:162` to use `workflow.db.engine` directly.
2. Delete `infra/orm.py`.
3. Grep-purge `latexzettel.infra.orm` strings.
4. Full pytest GREEN.
5. Single commit.

### P4 — Tests + ADR
1. Add `tests/latexzettel/test_rpc_smoke.py` — start `RPCServer`, send `notes.list`, assert response.
2. Add `tests/latexzettel/test_api_imports.py` — assert each `api/*.py` imports without error.
3. Mark ADR LZK-0004 **Implemented (date)** + retrospective.
4. Update CLAUDE.md ADR table + `primer.md`.
5. Single commit. Tag `v1.6.0`.

## Reuse — no new code needed

- `workflow.db.engine.get_global_engine()` exists.
- `workflow.db.engine.init_global_db()` exists.
- `workflow.db.models.notes` exports all six model classes.

## Risks + mitigations

| Risk | Mitigation |
|------|------------|
| 14-route refactor breaks RPC silently (no tests today) | Add smoke test BEFORE P2/P3 |
| `get_engine.cache_clear()` used in tests | Grep + redirect to `get_global_engine.cache_clear`, or wrap cache in engine.py |
| Import cycle workflow.db.models.notes ↔ latexzettel | Engine init lazy; should not cycle — verify on first P1 commit |
| Dynamic `_import_db_module` used by tests | Grep usages outside server/main.py first |

## Verification

```bash
pytest --ignore=tests/test_database.py -x
grep -r "latexzettel.infra.orm" src/ tests/      # zero hits
grep -r "ctx.db\|db.Note\|db.Citation" src/latexzettel/  # zero hits
python -c "from latexzettel.api import notes, render, analysis, markdown, sync, export, workflows; print('ok')"
pytest tests/latexzettel/ -v
```

## Out of scope (defer)

- ADR-0014 broader goal: replace `latexzettel/api/` with `workflow.notes` calls. Separate, larger refactor.
- Tag `Concept` rename consistency (separate ITEP).
