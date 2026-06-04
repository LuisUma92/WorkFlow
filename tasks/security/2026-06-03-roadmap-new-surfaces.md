---
title: "Security Review: roadmap new surfaces (bib stdin import, vault note writes, EAV overflow)"
reviewer: security-reviewer agent
date: 2026-06-03
scope:
  - src/workflow/prisma/importer.py          # B1 --stdin / import_bib_text
  - src/workflow/prisma/cli.py               # C1 accept-to-note CLI
  - src/workflow/bibliography/render.py      # A5 promoted renderer (planned)
  - src/workflow/db/models/bibliography.py   # A1 BibExtraField, A4 BibRelation
  - src/workflow/vault/paths.py              # vault note write path
status: open
findings_summary:
  critical: 0
  high: 1
  medium: 3
  low: 1
---

# Security Review: roadmap new surfaces

**Reviewer**: security-reviewer agent
**Date**: 2026-06-03
**Scope**: planned surfaces from the 2026-06-03 roadmap (Waves A/B/C). This is a *pre-implementation*
review — findings are design constraints the TDD phases MUST satisfy, not bugs in shipped code.
**Overall**: No CRITICAL. One HIGH (path traversal via bibkey-derived note filename). Three MEDIUM
defense-in-depth items on the new stdin + EAV ingestion paths. Reuse existing importer guards.

---

## Findings

### 1. [HIGH] Path traversal via bibkey-derived note filename

**File**: `src/workflow/prisma/cli.py` (C1 `accept-to-note`, planned)

```python
# planned: note path built from a DB-sourced bibkey
note_path = vault_root / "notes" / "literature" / f"{date}-lit-{bibkey}.md"
```

**Severity**: HIGH
**Fix**: bibkey is user/`.bib`-influenced and non-unique. Calculated bibkeys are `[a-z0-9]` but
imported source IDs are kept verbatim and may contain `/`, `..`, NUL, or absolute prefixes. Slugify
the filename component (`re.sub(r"[^a-z0-9._-]", "", bibkey.lower())`), reject empty/`.`/`..`
results, and assert `note_path.resolve().is_relative_to(vault_root.resolve())` before any write.
Same guard for `--vault-root` overrides.

---

### 2. [MEDIUM] stdin import bypasses the size guard if not routed through it

**File**: `src/workflow/prisma/importer.py` (B1 `import_bib_text`, planned)

```python
# the file path enforces MAX_BIB_SIZE_BYTES on read; stdin must too
text = sys.stdin.read()   # unbounded
```

**Severity**: MEDIUM
**Fix**: `import_bib_text` must enforce `MAX_BIB_SIZE_BYTES` on the in-memory text (length-check
before parse), identical to the file path. Read stdin with a cap (`sys.stdin.read(MAX+1)` then
reject if over). The `--stdin` path must reuse `_ALLOWED_URL_SCHEMES` URL validation unchanged.

---

### 3. [MEDIUM] EAV overflow table is an unvalidated field sink

**File**: `src/workflow/db/models/bibliography.py` (A1 `BibExtraField`, planned)

```python
# any "unknown but biblatex-ish" field flows in verbatim
BibExtraField(bib_entry_id=..., field=raw_key, value=raw_value)
```

**Severity**: MEDIUM
**Fix**: Whitelist `field` against the known biblatex field/alias catalog (the 293-field set) —
do NOT accept arbitrary keys, or the table becomes a vector for unbounded junk / oversized values
from a hostile `.bib`. Cap `value` length, cap rows-per-entry, and keep it parameterized ORM
(already the case). Unknown-to-catalog fields keep their current *drop* behavior.

---

### 4. [MEDIUM] Idempotency check is TOCTOU between existence test and write

**File**: `src/workflow/prisma/cli.py` (C1/C2, planned)

```python
if note_path.exists():      # check
    abort()
note_path.write_text(...)   # use — racy under bulk --all-accepted
```

**Severity**: MEDIUM
**Fix**: Use atomic create (`open(path, "x")` / `O_EXCL`) instead of exists-then-write so the
bulk path can't clobber a note created concurrently or earlier in the same batch. Treat
`FileExistsError` as the "skipped" outcome in the `--json` report.

---

### 5. [LOW] biblatex `bib` block in generated note can carry LaTeX / shell-looking payloads

**File**: `src/workflow/bibliography/render.py` (A5, planned)

```python
# rendered ```bib block is later piped back through --stdin
```

**Severity**: LOW
**Fix**: The renderer emits DB-stored field values into a fenced block that round-trips through
the importer (which already validates). No shell is involved (`run_cli` uses list args, not a
shell). Keep it that way — never build the import invocation via a shell string. Brace-balance
the emitted values so a stray `}` can't break out of the block.

---

## Summary

| # | Severity | File | Issue | Status |
|---|----------|------|-------|--------|
| 1 | HIGH | `prisma/cli.py` (C1) | bibkey-derived filename → path traversal | open |
| 2 | MEDIUM | `prisma/importer.py` (B1) | stdin bypasses size guard | open |
| 3 | MEDIUM | `db/models/bibliography.py` (A1) | EAV field sink unvalidated | open |
| 4 | MEDIUM | `prisma/cli.py` (C1/C2) | TOCTOU on idempotent write | open |
| 5 | LOW | `bibliography/render.py` (A5) | bib block payload round-trip | open |

## Verdict

**0 CRITICAL / 1 HIGH / 3 MEDIUM / 1 LOW.**

- Existing importer already does the hard parts right: parameterized ORM, `MAX_BIB_SIZE_BYTES`,
  `_ALLOWED_URL_SCHEMES`, list-arg `run_cli` (no shell injection). Reuse them — do not fork.
- The new risk is concentrated where DB/`.bib` data becomes a **filesystem path** (finding 1) or
  an **unbounded sink** (findings 2, 3). Both are closed by validate-at-boundary + caps.

**Blockers**: finding 1 must be fixed in the C1 TDD phase before any note is written to the vault.
