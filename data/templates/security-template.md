---
title: "Security Review: <scope>"
reviewer: security-reviewer agent | <human>
date: YYYY-MM-DD
scope:                           # files / modules audited
  - <src/workflow/module/file.py>
status: open | resolved
findings_summary:                # tally before writing findings
  critical: 0
  high: 0
  medium: 0
  low: 0
---

# Security Review: <scope>

**Reviewer**: <agent or human name>
**Date**: YYYY-MM-DD
**Scope**: `<path/to/file.py>`, `<path/to/other.py>`
**Overall**: <one-line verdict, e.g. "No CRITICAL/HIGH findings. Two MEDIUM defense-in-depth items.">

---

## Findings

<!-- Repeat this block for each finding. Positive observations (no-finding) are allowed — omit the code block and set Severity to "Not a finding". -->

### 1. [SEVERITY] <short title>

**File**: `<path/to/file.py:line>`

```python
# offending snippet — keep it minimal
<paste relevant lines here>
```

**Severity**: CRITICAL | HIGH | MEDIUM | LOW | Not a finding — <positive observation>
**Fix**: <one or two sentences — concrete action, not a restatement of the problem>

---

### 2. [SEVERITY] <short title>

**File**: `<path/to/file.py:line>`

```python
# offending snippet
```

**Severity**: CRITICAL | HIGH | MEDIUM | LOW | Not a finding — <positive observation>
**Fix**: <recommended change>

---

<!-- Add more ### N. blocks as needed. Remove unused placeholder blocks before saving. -->

## Summary

| # | Severity | File | Issue | Status |
|---|----------|------|-------|--------|
| 1 | <CRITICAL\|HIGH\|MEDIUM\|LOW> | `<file.py:line>` | <short description> | open \| fixed \| wontfix |
| 2 | <CRITICAL\|HIGH\|MEDIUM\|LOW> | `<file.py:line>` | <short description> | open \| fixed \| wontfix |

## Verdict

**<CRITICAL count> CRITICAL / <HIGH count> HIGH / <MEDIUM count> MEDIUM / <LOW count> LOW.**

<!-- Summarise security hygiene: what's already correct, what must be fixed before ship. -->
- <positive pattern observed, e.g. "All DB access uses parameterized ORM queries">
- <another pattern, e.g. "subprocess calls use list args — no shell injection">

<!-- If any CRITICAL or HIGH exist, add: -->
<!-- **Blockers**: items N, M must be fixed before merging. -->
