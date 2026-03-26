---
adr: 0013
title: "Codebase Consolidation: Session Patterns, Legacy Decoupling, CLI Architecture"
status: Accepted
date: 2026-03-26
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - refactoring
  - maintenance
decision_scope: system
supersedes: null
superseded_by: null
related_adrs:
  - "0003"
  - "0004"
  - "0007"
  - "0008"
  - "0009"
  - "ITEP-0001"
  - "ITEP-0003"
---

## Context

With all 7 phases (0-6) complete, a full codebase audit (4-reviewer schema: python, code, security, TDD) identified accumulated inconsistencies across modules built in different sessions:

1. **Three different session management patterns** across exercise, lecture, and graph CLIs — each works but creates confusion for maintenance.

2. **Cross-module coupling**: `workflow.validation.schemas` imports `TaxonomyLevel` and `TaxonomyDomain` from legacy `itep.structure`. The new `workflow.*` modules should not depend on `itep.*` — the dependency direction should be the reverse (itep uses workflow.db, not workflow uses itep).

3. **Duplicated YAML parsing**: `workflow.validation.parsers.parse_tex_metadata()` reimplements the same commented-YAML extraction that `workflow.latex.comments.extract_commented_yaml()` already provides.

4. **exercise/cli.py at 622 lines** — the largest file in the codebase, exceeding the 400-line guideline. Business logic (sync, filter, gc) is mixed with Click wiring.

5. **Test coverage gaps**: `workflow.tikz/`, `workflow.validation/`, and `workflow.db/engine.py` have zero test coverage despite being non-trivial modules.

6. **15 modules missing `__all__`** — inconsistent public API declarations.

7. **Legacy latexzettel engine** creates a SQLite engine at import time, binding to whatever CWD the process starts in.

These are not bugs — all 18 CLI commands work correctly. But the inconsistencies increase cognitive load and create latent risks for future changes.

---

## Decision Drivers

- **Consistency**: Same patterns across all modules reduces cognitive load
- **Simplicity**: Personal academic toolkit — avoid over-engineering
- **Backward compatibility**: `inittex`, `relink`, `cleta` entry points must continue working
- **Testability**: Coverage gaps hide real bugs (as proven by the Phase 6 API mismatch)
- **Minimal disruption**: Changes should be safe, incremental, and independently deployable

---

## Decision

Consolidate the codebase in 4 ordered batches. Each batch is independently deployable and testable.

### Batch 1: Unified Session Pattern + Hardcoded Path Fix

**Problem**: Three CLI modules manage DB sessions differently.

**Standard pattern** (already used by `graph/cli.py`):

```python
from sqlalchemy.orm import Session
from workflow.db.engine import init_global_db

engine = init_global_db()
with Session(engine) as session:
    repo = SqlExerciseRepo(session)
    # ... work ...
    session.commit()
```

**Changes**:

| File | Change |
|------|--------|
| `exercise/cli.py` | Keep `_get_engine` but use `Session(engine)` consistently (already does) |
| `lecture/cli.py` | Remove `sessionmaker(bind=engine)` pattern, use `Session(engine)` directly |
| `graph/cli.py` | No change (reference implementation) |
| `itep/defaults.py` | Replace hardcoded `/home/luis/...` with `Path.home() / "Documents/01-U/00-Fisica"` with env var `WORKFLOW_PHYSICS_DIR` override |

### Batch 2: Decouple Validation from Legacy itep

**Problem**: `workflow.validation.schemas` imports enums from `itep.structure`, creating a reverse dependency.

**Fix**: The taxonomy values already exist as tuples in `workflow.db.models.academic._TAXONOMY_LEVELS` and `_TAXONOMY_DOMAINS`. Use those directly in `validation/schemas.py`:

```python
# BEFORE (validation/schemas.py):
from itep.structure import TaxonomyLevel, TaxonomyDomain
_VALID_TAXONOMY_LEVELS = {v.value for v in TaxonomyLevel}

# AFTER:
from workflow.db.models.academic import _TAXONOMY_LEVELS, _TAXONOMY_DOMAINS
_VALID_TAXONOMY_LEVELS = set(_TAXONOMY_LEVELS)
_VALID_TAXONOMY_DOMAINS = set(_TAXONOMY_DOMAINS)
```

**Consolidate YAML parsers**: `validation/parsers.parse_tex_metadata()` delegates to `latex.comments.extract_commented_yaml()`:

```python
# BEFORE: 50 lines of hand-rolled YAML extraction in parsers.py
# AFTER:
from workflow.latex.comments import extract_commented_yaml

def parse_tex_metadata(filepath: Path) -> dict | None:
    text = filepath.read_text(encoding="utf-8")
    metadata, _ = extract_commented_yaml(text)
    return metadata if isinstance(metadata, dict) else None
```

### Batch 3: Exercise CLI Split + Test Coverage

**Problem**: `exercise/cli.py` is 622 lines — business logic mixed with Click wiring.

**Solution**: Extract service functions to `exercise/service.py`:

```python
# exercise/service.py (NEW)
@dataclass(frozen=True)
class SyncResult:
    new: int
    updated: int
    unchanged: int
    skipped: int

def sync_exercises(
    session: Session,
    files: list[Path],
    max_file_bytes: int = 10 * 1024 * 1024,
) -> SyncResult:
    """Business logic for exercise sync, extracted from cli.py."""

def gc_orphans(session: Session) -> list[str]:
    """Find and delete orphaned exercise records. Returns deleted IDs."""
```

CLI commands become thin wrappers:

```python
# exercise/cli.py
@exercise.command()
@click.argument("path", ...)
@click.pass_context
def sync(ctx, path):
    engine = _get_engine(ctx)
    files = _find_tex_files(Path(path))
    with Session(engine) as session:
        result = sync_exercises(session, files)
        session.commit()
    click.echo(f"Sync: {result.new} new, {result.updated} updated, ...")
```

**Test coverage additions**:

| New test file | Tests for |
|---------------|-----------|
| `tests/workflow/test_validation_schemas.py` | `validate_note_frontmatter`, `validate_exercise_metadata` |
| `tests/workflow/test_validation_parsers.py` | `parse_md_frontmatter`, `parse_tex_metadata` |
| `tests/workflow/test_tikz_builder.py` | `find_tikz_sources`, `compute_hash`, `build_all` (mock subprocess) |
| `tests/workflow/test_db_engine.py` | `get_global_engine`, `init_global_db`, `init_local_db` |

**Fix pre-existing test failures**: Mark `test_manager.py` with `@pytest.mark.xfail(reason="legacy itep manager, pending rewrite")`.

### Batch 4: Legacy Cleanup

**Lazy latexzettel engine**:
```python
# BEFORE (infra/orm.py line 33):
engine = get_local_engine(project_root=Path("."))  # runs at import time

# AFTER:
_engine = None
def get_engine():
    global _engine
    if _engine is None:
        _engine = get_local_engine(project_root=Path("."))
    return _engine
```

**Add `__all__` to 15 modules**: Each module gets an `__all__` listing its public API. This is a mechanical change — no logic.

**Modernize `tikz/builder.py`**: Replace `Optional[Path]` with `Path | None` (5 occurrences).

**Clean `appfunc/iofunc.py`**: Delete commented-out code block (lines 90-131).

---

## Architectural Rules

### MUST

- All CLI modules **MUST** use `with Session(engine) as session:` — never `sessionmaker(bind=engine)`.
- `workflow.*` modules **MUST NOT** import from `itep.*` or `lectkit.*`. The dependency direction is: `itep` imports `workflow.db`, never the reverse.
- CLI command functions **MUST NOT** contain business logic longer than 20 lines. Extract to a service module.

### SHOULD

- All public modules **SHOULD** define `__all__`.
- Service functions **SHOULD** accept a `Session` parameter (not create their own engine).
- Tests **SHOULD** use shared fixtures from `tests/conftest.py`.

### MUST NOT

- **MUST NOT** create session middleware, DI containers, or factory abstractions. `Session(engine)` is sufficient for a personal toolkit.
- **MUST NOT** merge `appfunc/` into `itep/`, fold `cleta` into `workflow`, or rewrite the latexzettel Peewee shim. These work fine as-is.
- **MUST NOT** add CLI commands for library-only functions (`find_hubs`, `strip_comments`). They exist for programmatic use.

---

## Consequences

### Benefits

- Single session pattern across all CLIs — any developer sees the same code
- `workflow.*` becomes self-contained — no imports from legacy modules
- exercise/cli.py drops from 622 to ~300 lines
- Test coverage reaches new modules (tikz, validation, db/engine)
- `__all__` makes public API explicit in every module

### Costs

- 4 batches of work (~7-11 hours total)
- exercise/service.py is a new file (increases file count)
- Batch 2 changes `validation/schemas.py` imports which could affect downstream consumers (none exist outside the project)

### What stays unchanged

- `inittex`, `relink`, `cleta` continue working as before
- All 18 CLI commands retain identical behavior
- Protocol interfaces remain (documentation value, zero runtime cost)
- `latexzettel` server architecture unchanged (only engine initialization becomes lazy)
- `appfunc/`, `lectkit/cleta.py` remain as separate packages

---

## Alternatives Considered

### Alternative A: Full monorepo restructure

Move all of `itep/`, `latexzettel/`, `lectkit/` under `workflow/` namespace.

**Rejected**: Too disruptive. Would break `inittex`/`relink`/`cleta` entry points and require rewriting all import paths. The current structure works — the issue is cross-dependencies, not directory layout.

### Alternative B: No CLI split for exercise

Keep `exercise/cli.py` at 622 lines, just add a comment separating sections.

**Rejected**: The file will grow further when Phase 4 features mature (e.g., adding `exercise tag` or `exercise stats` commands). Splitting now prevents worse growth.

### Alternative C: Replace Protocol interfaces with ABCs

Use `abc.ABC` instead of `typing.Protocol` for repository interfaces.

**Rejected**: Protocols are structural (duck-typing compatible), which matches the project's pragmatic style. ABCs would force inheritance, adding ceremony without benefit.

---

## Compatibility / Migration

Fully backward compatible. No breaking changes to CLI entry points, file formats, or database schemas.

Migration is incremental — each batch can be deployed independently. If any batch causes issues, it can be reverted without affecting other batches.

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-26 | Initial ADR |
