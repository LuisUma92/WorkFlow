---
id: 
title: 
aliases: []
type: permanent
created: 
tags: []
concepts: []
references: []
exercises: []
images: []
---

# Security Review: Phase 7 — Notes Init, LaTeXZettel API, Pandoc Preprocessor

**Reviewer**: security-reviewer agent
**Date**: 2026-03-26
**Scope**: `src/workflow/notes/init.py`, `src/latexzettel/api/{notes,sync,markdown}.py`, `shared/latex/pandoc/preprocess.py`

---

## Findings

### 1. [MEDIUM] Hardcoded output path in `preprocess.py` (line 22)

**File**: `shared/latex/pandoc/preprocess.py:22`

```python
with open('preprocessed.md', 'w') as f:
    f.write(text)
```

Always writes to `preprocessed.md` in CWD regardless of input path. This is not a traversal risk per se, but it silently overwrites any existing file at that location. The script also takes `sys.argv[1]` without any validation (line 26).

**Severity**: MEDIUM
**Fix**: Accept output path as argument or derive from input. Validate input path exists before reading.

---

### 2. [LOW] `default_filename()` sanitization is solid

**File**: `src/latexzettel/util/text.py:13-29`

The `default_filename()` function strips accents via NFKD normalization, lowercases, and restricts to `[a-z0-9_]` only. This effectively prevents path traversal via note names (e.g., `../../etc/passwd` becomes `etc_passwd`). This is well done.

**Severity**: Not a finding — positive observation.

---

### 3. [LOW] `NotesPaths.abs()` uses `.resolve()` — safe path canonicalization

**File**: `src/latexzettel/config/settings.py:51-55`

```python
def abs(self, path: Path) -> Path:
    return (self.root / path).resolve()
```

Using `.resolve()` collapses `..` components and symlinks, which is correct. Combined with `default_filename()` sanitization, path traversal via user-controlled filenames is not feasible in the latexzettel API layer.

**Severity**: Not a finding — positive observation.

---

### 4. [LOW] `init_workspace` iterates only direct children — no traversal risk

**File**: `src/workflow/notes/init.py:75`

```python
for entry in sorted(workspace_dir.iterdir()):
```

Only iterates direct children (not recursive), validates pattern `[0-9]*-*`, and creates subdirectories within those entries. The `workspace_dir` itself comes from `Path(workspace).resolve()` in the CLI (cli.py:23). No traversal risk here.

**Severity**: Not a finding — positive observation.

---

### 5. [LOW] DB queries use SQLAlchemy ORM — no injection risk

**Files**: `src/latexzettel/api/notes.py`, `sync.py`, `markdown.py`

All database access uses SQLAlchemy's `select()` with `.where()` on mapped attributes. No raw SQL, no string concatenation in queries. Parameterization is handled by SQLAlchemy automatically.

**Severity**: Not a finding — positive observation.

---

### 6. [MEDIUM] `rename_reference` writes to arbitrary backref files without path validation

**File**: `src/latexzettel/api/notes.py:249-256`

```python
for fname in backref_files:
    fpath = slipbox / f"{fname}.tex"
    ...
    fpath.write_text(updated, encoding="utf-8")
```

The `fname` values come from `note.labels -> referenced_by -> source.filename`, which are DB-stored values. If a malicious or corrupted DB entry contains `../../something`, `Path(slipbox / "../../something.tex")` could write outside slipbox. However, `default_filename()` sanitization at creation time strips `../`, making this exploitable only via direct DB manipulation.

**Severity**: MEDIUM (defense-in-depth concern)
**Fix**: Add a guard: `assert fpath.resolve().is_relative_to(slipbox.resolve())` before writing.

---

### 7. [MEDIUM] `sync_md` passes user-controlled text to pandoc via stdin

**File**: `src/latexzettel/api/markdown.py:293-306`

```python
md_text = md_file.read_text(encoding="utf-8")
latex_ready_text = _convert_wikilinks_to_latex(db, session, md_text)
proc = run_pandoc(options=options, input_text=latex_ready_text, check=False)
```

Markdown content is passed to pandoc via stdin (not as a filename argument), which is the correct pattern. The `run_pandoc` function uses `subprocess.run` with a list of args (no shell=True). The `-o` output path is derived from `_slipbox_tex_path` which uses `NotesPaths.abs()` with `.resolve()`.

**Severity**: MEDIUM (pandoc itself could have vulns, but the invocation pattern is safe)
**Mitigation**: Already correct — stdin piping avoids filename injection.

---

### 8. [LOW] `open_with_system` takes a Path, not user string

**File**: `src/latexzettel/infra/processes.py:189-201`

Uses `subprocess.run` with list args (no `shell=True`). The `open_command` is hardcoded per platform. The `target` is a `Path` object. No injection risk.

---

## Summary

| # | Severity | File | Issue |
|---|----------|------|-------|
| 1 | MEDIUM | `shared/latex/pandoc/preprocess.py` | Hardcoded output path, no input validation |
| 6 | MEDIUM | `latexzettel/api/notes.py:249` | DB-sourced filenames written without path containment check |
| 7 | MEDIUM | `latexzettel/api/markdown.py:306` | Pandoc invocation — pattern is safe, but note the trust boundary |
| 2-5,8 | LOW/NONE | Various | Positive observations — sanitization, ORM, resolve() all correct |

## Verdict

**No CRITICAL or HIGH findings.** The codebase shows good security hygiene:
- `default_filename()` is an effective sanitizer against path traversal
- `NotesPaths.abs()` uses `.resolve()` consistently
- All DB access uses parameterized SQLAlchemy ORM queries
- Subprocess calls use list args (no shell injection)

The three MEDIUM items are defense-in-depth recommendations, not exploitable vulnerabilities under normal operation.
