# 0021 — Vault full-text search via SQLite FTS5

- **Status:** Proposed
- **Date:** 2026-07-05
- **Domain:** Zettelkasten / Notes
- **Depends on:** ITEP-0011 (vault unification, GlobalBase), 0010 (file-as-truth), ITEP-0014 (incremental sync via content hash, Proposed)

## Context

The vault holds 313 notes (verified count, 2026-07-05) and has **zero search
surface**. Verified across the codebase: no FTS table, index, or query path
exists in `workflow.db`, `latexzettel`, or `nvim-plugin`. Discovery today is
entirely metadata-driven — tags (`workflow.db.models.notes.Tag`/`NoteTag`),
concepts (`NoteConcept`), and graph traversal (`workflow graph neighbors`,
`workflow.graph.collectors`). None of these let a user find a note by
*content* — a phrase in the body, a title fragment, an alias — without
already knowing its tag or concept code.

This gap was surfaced during the 2026-07-05 council evaluation of
post-freeze work as a concrete, low-risk win: the vault is Markdown-first
(ADR-0002) and file-as-truth (ADR-0010), so an index built from `.md`
content is inherently derived and rebuildable — no new authority is created.

## Decision (Proposed)

Add a SQLite FTS5 virtual table indexing three fields per `Note`: `title`,
`aliases`, and `body` (raw Markdown body, post-frontmatter). The table is
populated/refreshed as part of `notes sync`'s existing per-note passes — no
new top-level command touches the vault; sync remains the single writer.

- New table: `note_fts` (FTS5, `content='note'`-style external-content or a
  synced shadow table — exact contentless/external-content tradeoff is an
  implementation-time decision, not pinned here).
- New CLI: `workflow notes search <query> [--json]` — ranks via FTS5 `bm25()`,
  returns `note_id`, `title`, `path`, snippet (via `snippet()`), plugging into
  the same result shape conventions as `graph neighbors --json` (ADR-0017)
  where practical (id/title/path fields).
- New Neovim Telescope picker (`:WorkflowNoteSearch`), following the existing
  picker pattern (`nvim-plugin/lua/workflow/picker/`).
- Index is **derived, not authoritative**: `.md` files remain truth (ADR-0010).
  A corrupted or stale `note_fts` table is always fully recoverable by a
  rebuild pass over the vault.

## Alternatives Considered

| Alternative | Reason Rejected (briefly) |
|---|---|
| Ad hoc `ripgrep` over the vault directory | No ranking, no field weighting (title vs body), no snippet/highlight support, no `--json` contract for the picker |
| External search engine (e.g. Meilisearch, Elasticsearch) | New service dependency, operational weight (daemon, port, index lifecycle) disproportionate to a single-user, 313-note vault |
| Full re-index on every `notes search` call (no persisted index) | Defeats the purpose at scale; couples query latency to corpus size |

## Consequences

- **Rebuild story**: `note_fts` must be fully reconstructible from `.md`
  files alone (ADR-0010 invariant). A `--rebuild-index` flag or equivalent
  on `notes sync` is required before this ships.
- **Cost of staying fresh**: every `notes sync` invocation that re-parses a
  note (i.e., does not skip it) must also re-index that note's FTS row. If
  ITEP-0014 (`fm_hash`, Proposed) ships first, the FTS re-index gates on the
  same hash-skip decision — an unchanged note is neither re-parsed nor
  re-indexed. If ITEP-0014 has not shipped, FTS indexing pays the same
  full-rescan cost sync already pays today; this ADR does not require
  ITEP-0014 as a precondition, only notes the coupling.
- **Query surface growth**: this is additive to, not a replacement for,
  tag/concept/graph discovery — a user may still resolve notes by concept
  code where that's the faster path.
- **Schema footprint**: one new virtual table in GlobalBase; no change to
  `Note` itself.

## Resolved design questions (2026-07-05, W1 gate ★b/★c)

- **FTS5 table shape → external-content.** `note_fts` is an external-content
  FTS5 table: `content='note', content_rowid='id'` (rowid aliases
  `Note.id`). No shadow/synced copy of the body is stored redundantly.
- **Rebuild semantics → delete + repopulate from `.md` files.** A rebuild
  pass drops and re-inserts all `note_fts` rows by re-reading the vault's
  `.md` files directly — never from the DB body cache. This keeps ADR-0010
  (file-as-truth) intact: `note_fts` is fully reconstructible from disk
  alone, with no dependency on any in-DB derived state.
- **No `fm_hash` (ITEP-0014) coupling required.** Confirmed: FTS indexing
  does not require ITEP-0014's `fm_hash` skip-check as a precondition to
  ship. The coupling noted in Consequences above remains an optimization,
  not a dependency.
- **Neovim surface → CLI-subprocess.** `:WorkflowNoteSearch` shells out to
  `workflow notes search --json`, consistent with every other live picker
  in `nvim-plugin/workflow` (evaluations, items, courses, PRISMA, enums).
  The LZK-0001 JSONL/NDJSON RPC server was considered and **rejected** for
  this surface — it is not wired into the current picker pattern today and
  introducing it here would be a one-off inconsistency.
- **`note_alias` migration → folded into this ADR's migration.** The
  `note_alias` table proposed under ITEP-0015 (note picker aliasing) is
  folded into the same schema migration that ships `note_fts` (migration
  `0017`), rather than shipped as a separate migration.

## Status

**Proposed.** Implementation deferred to post-freeze (target: November 2026).
Originates from the 2026-07-05 council evaluation. No code is written by this
ADR. Design questions above are resolved; implementation itself remains
in-progress under the W1 plan.

## Change Log

| Date       | Change                                                    |
| ---------- | ---------------------------------------------------------- |
| 2026-07-05 | Initial placeholder — register FTS5 vault search proposal. |
| 2026-07-05 | W1 gate ★b/★c design resolved: external-content FTS5 (`content='note'`, `rowid=Note.id`); rebuild = delete+repopulate from `.md` files (ADR-0010 intact, no `fm_hash` coupling required); nvim surface = CLI-subprocess (RPC rejected, not wired today); `note_alias` folded into the same `0017` migration. |
