---
id: ITEP-0014
title: "Incremental sync via per-note content hashing (`fm_hash`)"
aliases:
  - ADR-ITEP-0014
status: Proposed
date: 2026-05-22
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - notes
  - performance
  - sync
  - incremental
decision_scope: cross-module
supersedes: null
superseded_by: null
related_adrs:
  - 0001-zettelkasten-note-semantic-layer
  - 0010-exercise-persistence-model
  - ITEP-0011-vault-unification
  - ITEP-0013-note-relation-graph
---

## Context

Phase 1 (`workflow notes sync`, v1.4.0) re-reads every `.md` file on every
invocation. For small vaults (<1000 notes) this is fast — observed ~10–50 ms
in tests. For larger vaults, or CI hooks that run sync on every commit, the
cost grows linearly with corpus size regardless of how many notes changed.

ITEP-0013 (note relation graph, Proposed) introduces a fourth pass — per-file
edge re-import — that compounds this cost. As the vault scales (target: 10k–
100k notes per ITEP-0013 scalability notes), full re-reads become wasteful.

## Problem Statement

Current `sync_vault()`:

- Reads every `.md` file under scope
- Parses YAML frontmatter for every file
- Upserts Note / Label / Link / Citation rows for every file
- Issues SELECT queries to determine "exists already?" for every label/link/citation

A note whose content hasn't changed since the last sync still triggers all
parsing, regex matching, and DB round-trips. The DB writes are idempotent
(no-op for unchanged rows) but the work to determine that is not free.

## Proposed Direction

Add a content hash per Note row:

```sql
ALTER TABLE note ADD COLUMN fm_hash TEXT;
```

`fm_hash` = `sha256(frontmatter_yaml_raw || "\n---\n" || body)`, stored after
a successful sync of that note. Hash is content-only — identical file bytes
yield identical hash regardless of mtime or inode.

Sync algorithm becomes:

1. For each `.md` file in scope:
   - Compute current hash of file content
   - If `Note.fm_hash == current_hash`: **skip** — note is in DB and unchanged
   - Else: full parse + upsert path, write new hash on success
2. Orphan cleanup — unchanged
3. Edge rebuild (ITEP-0013): same gate — skip files whose hash matches

`sync --force` and `sync --rebuild-edges` MUST bypass the hash check
unconditionally.

## Decision Drivers (TBD — Defer Detailed Analysis)

- **Speedup magnitude** — needs benchmark on realistic vault size before committing
- **Hash function** — sha256 vs blake3 vs xxhash (collision resistance vs speed)
- **Hash invalidation conditions** — schema changes, ADR-0010 migrations,
  frontmatter validator updates must trigger a full rebuild
- **Force-rebuild story** — `sync --force` and `sync --rebuild-edges` bypass
- **Migration** — existing notes have `fm_hash = NULL`; first sync after
  upgrade computes hashes with no special logic needed
- **Memory cost** — sha256 hex is 64 bytes per note; 100k notes ≈ 6.4 MB

## Open Questions

1. **Scope of the hash** — Content-only (robust) vs content + mtime (faster
   pre-pass but fragile across git checkout/clone). Content-only is preferred;
   confirm no hidden coupling before committing.
2. **Split hashes** — Should there be separate hashes for frontmatter and body
   to selectively re-run only the affected pass (label/link vs edge rebuild)?
   Adds complexity; worth it only if ITEP-0013 edge re-import proves the
   dominant cost.
3. **Dry-run contract** — Should `sync --dry-run` update hashes? Probably no
   (dry-run is read-only), but this must be explicit in the implementation.
4. **Concurrent invocations** — Hash write race conditions when two sync
   processes run simultaneously against the same DB.

## Alternatives Considered

| Alternative | Reason Rejected (briefly) |
|---|---|
| mtime-based detection | Fragile across git checkout/clone, filesystem touch ops |
| External cache file (`.workflow/sync-cache.json`) | Adds state outside DB, breaks atomicity guarantees |
| No incremental sync | Current behavior; acceptable until vault scales to target size |

## Status

**Proposed (placeholder).** This ADR registers the idea for future deep
analysis. No code is written by this ADR. Implementation MUST NOT begin before:

1. Vault size justifies the optimization (benchmark current sync on realistic corpus)
2. Open questions above are resolved
3. ITEP-0013 ships — its edge re-import pass is the larger driver of
   incremental sync value, and the skip-gate logic composes cleanly only after
   ITEP-0013 defines the edge-rebuild interface

## Change Log

| Date       | Change                                                           |
| ---------- | ---------------------------------------------------------------- |
| 2026-05-22 | Initial placeholder — register `fm_hash` idea for future design. |
