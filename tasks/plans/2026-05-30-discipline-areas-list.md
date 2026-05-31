# Implementation Plan — `workflow db discipline-areas list`

Date: 2026-05-30
Scope: read-only list command. NO create/update/delete. Minimal diff.

> NOTE: The prompt's column names and access patterns were partly inaccurate.
> This plan uses the **verified** model + CLI patterns from the live source.

## Problem

`workflow topic import` resolves `discipline_area_code` against the `discipline_area`
table (`bulk_import.py:281`), but no CLI lists actual `DisciplineArea` rows. The existing
`workflow db disciplines list` reads **CSV taxonomy files** (`taxonomy.discover_disciplines`)
and returns top-level discipline *groups* — not DB rows. Users have no way to discover valid
codes (`0010MC`, `0210PG`, ...) before authoring the import YAML.

## Verified research facts (corrects the prompt)

- **`DisciplineArea` model** (`src/workflow/db/models/knowledge.py:44`) columns are:
  `id`, `code` (String(6), unique), `name` (String(120)), `dewey` (String(20)),
  `discipline_num` (Integer), `topic_num` (Integer), `area_initials` (String(2)).
  There are **NO** `dd`, `serial`, or `topic_prefix` columns (prompt was wrong).
  The "two-digit discipline prefix" maps to **`discipline_num`** (an int; `00` → 0, `02` → 2).
  The trailing 2-letter code segment is **`area_initials`** (e.g. `MC`, `PG`).
- **`with_schema_guard`** DOES exist (`src/workflow/db/errors.py:78`) and IS used by the
  existing `disciplines_list` and all DB-querying commands. **Use it** on the new command.
- **DB access pattern**: DB commands use `engine = get_engine_from_ctx(ctx)` then
  `with Session(engine) as session:`. `get_global_session()` is a plain factory (NOT a
  contextmanager) and is **not** the pattern used here — follow `get_engine_from_ctx` +
  `Session(engine)` (see `import_codes`, `migrate_status` in `cli.py`).
- `disciplines_list` (CSV-based) does NOT take `ctx`. The DB commands (`import_codes`,
  `migrate_status`) take `@click.pass_context`. The new command needs `@click.pass_context`.
- JSON emit pattern: `import json as _json` (already imported at `cli.py:10`);
  `click.echo(_json.dumps(payload, ensure_ascii=False, indent=2))`.
- `db` group already registered in `src/main.py:7,29` (`cli.add_command(db)`). A subcommand
  inside `db` needs **no `main.py` change**.
- Model import: `from workflow.db.models.knowledge import DisciplineArea`. `select` from
  `sqlalchemy` is not yet imported in `cli.py` — add `from sqlalchemy import select`.
- **Tests**: `tests/workflow/test_db_cli.py`. Existing pattern (verified, 73 lines):
  - Fixture `isolated_engine(tmp_path, monkeypatch)` builds a file-backed engine via
    `get_global_engine(db_path=...)` + `init_global_db(engine)`, then
    `monkeypatch.setattr("workflow.db.cli.get_engine_from_ctx", lambda _ctx: engine)` so the
    CLI hits the temp DB. **Reuse this fixture** (no `obj={...}` is passed).
  - Tests use `CliRunner().invoke(db, ["disciplines", "list", ...])` (no obj).
  - There is NO `_seed`/`_make_engine` helper — seed rows yourself by opening
    `with Session(isolated_engine) as s: s.add_all([...]); s.commit()` (import `Session`
    from `sqlalchemy.orm` and `DisciplineArea` from `workflow.db.models.knowledge`).

## 1. Command signature

```
workflow db discipline-areas list [--json] [--dd DD]
```

- New subgroup `discipline-areas` under `db`: `@db.group("discipline-areas")` →
  `discipline_areas_group`.
- Subcommand `list`: `@discipline_areas_group.command("list")`.
- `--json` / `as_json` (is_flag, default False) — JSON output.
- `--dd` (type=str, default=None) — two-digit discipline prefix (e.g. `00`, `02`).
  Accept as string to allow a leading zero; parse to int and match `DisciplineArea.discipline_num`.
- `@click.pass_context` + `@with_schema_guard`.

## 2. Output format

Table mode columns (mirror live data + `disciplines list` styling):

```
CODE    DD  NAME
------  --  ----------------------------------------
0010MC  00  Mecánica Clásica
0210PG  02  Programación
```

- CODE: `row.code` (<8). DD: `f"{row.discipline_num:02d}"` (<4). NAME: `row.name` (<40).
- Header + dashed separator line, same look as `disciplines_list`.
- Empty / no matches → `click.echo("No discipline areas found.")`, exit 0.
- Sort by `code` ascending (`order_by(DisciplineArea.code)`) for stable output.

JSON mode — list of objects:

```json
[
  {"code": "0010MC", "discipline_num": 0, "name": "Mecánica Clásica", "area_initials": "MC"}
]
```

- Keys: `code`, `discipline_num` (int), `name`, `area_initials`. Omit `id`/`dewey`/`topic_num`
  (internal/not needed by import authors). `_json.dumps(..., ensure_ascii=False, indent=2)`.
- Empty result → `[]` (machine-parseable, NOT the "No ... found" text).

## 3. Implementation location

- File: `src/workflow/db/cli.py`.
- Add the `discipline-areas` group + `list` command **after** the `disciplines` group
  (after `disciplines_list`, ~line 257) and **before** the deprecated `taxonomy` alias
  (line 261) — keeps the DB-vs-CSV discipline commands adjacent.
- Add imports near the top: `from sqlalchemy import select` and
  `from workflow.db.models.knowledge import DisciplineArea`.
- Small private helper `_render_discipline_areas_table(rows)` next to the command (<20 lines).
  Do NOT reuse the CSV-group renderer (different columns/source).
- No new module, no `main.py` change.

## 4. Session / DB access (pattern, verified)

```python
@discipline_areas_group.command("list")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Emit machine-readable JSON instead of a table.")
@click.option("--dd", "dd", type=str, default=None,
              help="Filter by two-digit discipline prefix (e.g. 00, 02).")
@click.pass_context
@with_schema_guard
def discipline_areas_list(ctx, as_json, dd):
    dd_num = _parse_dd(dd)  # None | int; raises click.BadParameter on malformed
    engine = get_engine_from_ctx(ctx)
    with Session(engine) as session:
        stmt = select(DisciplineArea).order_by(DisciplineArea.code)
        if dd_num is not None:
            stmt = stmt.where(DisciplineArea.discipline_num == dd_num)
        rows = session.scalars(stmt).all()
        # read attrs while session is open
        records = [
            {"code": r.code, "discipline_num": r.discipline_num,
             "name": r.name, "area_initials": r.area_initials}
            for r in rows
        ]
    # format from `records` (json vs table)
```

- `_parse_dd("02") -> 2`, `_parse_dd(None) -> None`, `_parse_dd("xx") -> raise click.BadParameter`.
  Validate: must be all-digit and ≤2 chars; otherwise `BadParameter` (exit code 2).
- Materialize `records` inside the `with` to avoid DetachedInstance errors.

## 5. Tests

File: extend `tests/workflow/test_db_cli.py`. Add a new `TestDisciplineAreasListCli` class
that reuses the existing `isolated_engine` fixture. Seed rows directly:

```python
from sqlalchemy.orm import Session
from workflow.db.models.knowledge import DisciplineArea

def _seed(engine, rows):
    with Session(engine) as s:
        s.add_all([DisciplineArea(**r) for r in rows]); s.commit()
```

Each row dict must set `code`, `name`, `discipline_num`, `topic_num`, `area_initials`
(all non-nullable; `dewey` defaults to ""). Invoke via
`CliRunner().invoke(db, ["discipline-areas", "list", ...])`.

Cases:
1. `test_discipline_areas_list_empty` — fresh engine, no rows → exit 0, output contains
   "No discipline areas found".
2. `test_discipline_areas_list_empty_json` — empty, `--json` → exit 0, `json.loads(out) == []`.
3. `test_discipline_areas_list_table` — seed 0010MC + 0210PG → table contains both codes &
   names, sorted by code (0010MC before 0210PG).
4. `test_discipline_areas_list_json_shape` — `--json` → `json.loads` yields list of dicts with
   keys `{code, discipline_num, name, area_initials}` and correct values/types
   (`discipline_num` is int).
5. `test_discipline_areas_list_dd_filter` — seed discipline_num=0 and =2; `--dd 00` returns
   only the dn=0 row; assert the dn=2 code is absent.
6. `test_discipline_areas_list_dd_unknown` — `--dd 99` (valid format, no rows) → exit 0,
   "No discipline areas found" (and `[]` with `--json`).
7. `test_discipline_areas_list_dd_malformed` — `--dd xx` → non-zero exit (BadParameter,
   exit code 2); error output mentions the bad value.

TDD: write tests RED first, then implement. Target ≥80% coverage of the new code.

## 6. Scope boundary

- Read-only `list` only. No `add`/`edit`/`rm`/`show`.
- No schema migration, no model change, no `main.py` change.
- Do not touch the existing CSV-based `disciplines` group or its renderer.
- Diff footprint: 2 import lines + 1 group + 1 command + 1 table helper + `_parse_dd` in
  `cli.py`; ~7 new tests appended to `tests/workflow/test_db_cli.py`.

## Verification (before marking complete)

1. `pytest tests/workflow/test_db_cli.py -q` green (all 7 new cases).
2. `flake8 src/workflow/db/cli.py --max-line-length=127` clean (no new warnings).
3. Manual smoke against live DB (`~/01-U/workflow/workflow.db`):
   `workflow db discipline-areas list` and `... list --json --dd 00` return real rows.
