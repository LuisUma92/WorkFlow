# Phase 4c Security Review

**Date:** 2026-03-25
**Reviewer:** security-reviewer agent
**Scope:** normalize.py, moodle.py, cli.py, braces.py
**Overall:** No CRITICAL issues. Code is well-structured with good defensive patterns already in place.

---

## Findings

### 1. ReDoS in Math Delimiter Regex — LOW

**File:** `/home/luis/Projects/WorkFlow/src/workflow/latex/normalize.py` lines 132-145

The `$$.+?$$` and `$.+?$` patterns use non-greedy quantifiers with `re.DOTALL`. These are safe against catastrophic backtracking because the delimiter characters (`$`) are unambiguous and the `.+?` quantifier has a single, clear termination point. The `\$` protection via placeholder substitution eliminates ambiguity.

**Verdict:** No action needed.

### 2. Resource Exhaustion in Multi-Pass Expansion — LOW

**File:** `/home/luis/Projects/WorkFlow/src/workflow/latex/normalize.py` line 161

`max_passes=10` is hardcoded with a reasonable default. However, `rule.template.format(*args)` could theoretically produce output larger than input if a macro expands to something containing other macros that themselves expand further.

**Risk:** A pathological macro map could cause text to grow exponentially across 10 passes. The default `DEFAULT_MACRO_MAP` is safe (no recursive expansion).

**Recommendation:** Consider adding a `max_output_length` guard inside the loop. LOW priority because the macro map is developer-controlled, not user-supplied.

### 3. Path Traversal in Image Resolution — MEDIUM

**File:** `/home/luis/Projects/WorkFlow/src/workflow/exercise/moodle.py` lines 56-65

```python
ref_path = source_dir / ref_path  # ref comes from parsed LaTeX \includegraphics
```

Image references are extracted from `.tex` files. A malicious `.tex` file containing `\includegraphics{../../../etc/passwd}` would cause the tool to read and base64-encode that file into the XML output. The path is resolved relative to `source_dir` with no validation that the resolved path stays within the project directory.

**Recommendation:** Add path containment check:
```python
resolved = (source_dir / ref_path).resolve()
if not str(resolved).startswith(str(source_dir.resolve())):
    continue  # skip paths outside source directory
```

### 4. XML Injection via LaTeX Content — LOW

**File:** `/home/luis/Projects/WorkFlow/src/workflow/exercise/moodle.py`

Uses `xml.etree.ElementTree` which automatically escapes text content assigned to `.text` attributes. Characters like `<`, `>`, `&` are properly escaped. No raw string concatenation into XML. The `tostring()` call on line 234 handles serialization safely.

**Verdict:** No action needed. ElementTree provides adequate protection.

### 5. XXE (XML External Entity) — NOT APPLICABLE

The code only generates XML (via ElementTree builders), it does not parse external XML input. XXE is not a risk here.

### 6. Base64 Encoding Safety — LOW

**File:** `/home/luis/Projects/WorkFlow/src/workflow/exercise/moodle.py` line 52

`image_path.read_bytes()` reads entire file into memory. Combined with finding #3, a symlink or path traversal could cause reading large files. However, the CLI already enforces `_MAX_FILE_BYTES` on `.tex` files (not on images).

**Recommendation:** Add a size check on image files before reading:
```python
if image_path.stat().st_size > MAX_IMAGE_BYTES:
    continue
```

### 7. File Size Limits — GOOD (already implemented)

**File:** `/home/luis/Projects/WorkFlow/src/workflow/exercise/cli.py` lines 22-23

`_MAX_FILES = 10_000` and `_MAX_FILE_BYTES = 10 * 1024 * 1024` are enforced consistently across parse, sync, and export-moodle commands. Good defensive practice.

### 8. SQL Injection — NOT APPLICABLE

Database access uses SQLAlchemy ORM via `SqlExerciseRepo`. No raw SQL or string concatenation.

---

## Summary

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | ReDoS in math delimiters | LOW | Safe as-is |
| 2 | Multi-pass expansion growth | LOW | Safe with default map |
| 3 | Path traversal in image resolution | MEDIUM | Needs fix |
| 4 | XML injection | LOW | Safe (ElementTree escapes) |
| 5 | XXE | N/A | Code only generates XML |
| 6 | No size limit on image reads | LOW | Recommend adding |
| 7 | File size limits | GOOD | Already implemented |
| 8 | SQL injection | N/A | ORM used correctly |

**Action items (ordered by priority):**
1. MEDIUM: Add path containment validation in `_attach_images` (moodle.py)
2. LOW: Add image file size limit in `_embed_image` (moodle.py)
