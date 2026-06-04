# PRISMA-to-Literature-Note Request Audit — 2026-06-03

Scope: verify feature request `tasks/requests/2026-06-03-prisma-to-literature-note.md`
(auto-generate literature notes from PRISMA-accepted articles) against current code and
ADR truth-sources. Verdict: request is directionally sound but **NOT implementation-ready**
— 4 schema contradictions must be corrected before any plan/TDD phase begins.

## Truth-sources

- **PRISMA screening model** → `src/workflow/db/models/bibliography.py` `ReviewRecord`, `ReviewRationale`, `RationaleOption`, `BibKeyword`. `ReviewRecord` fields: `id`, `keyword_id` (FK→BibKeyword), `bib_entry_id` (FK→BibEntry), `included` (SmallInteger, tri-state None/0/1), `include_rationale` (Text, nullable). UniqueConstraint: `(keyword_id, bib_entry_id)`. `ReviewRationale` is a join table: `review_record_id` + `rationale_option_id`; no `.text` attribute.
- **PRISMA ADR** → `docs/ADR/PRISMA-0003-screening-review-workflow.md` — keyword-centric screening; no standalone `Review` entity.
- **Notes CLI** → `src/workflow/notes/cli.py:77` command `new`, `--type` Choice includes `"literature"`, calls `create_note` + `validate_note_frontmatter`.
- **Notes model** → `src/workflow/db/models/notes.py:53` — `source` attribute is a relationship back-populated from `Link.source`; `source_format` column (md/tex).
- **Bibliography service** → `src/workflow/bibliography/service.py:33` `get_bib_entry_by_bibkey` — contract: 0→None, 1→entry, 2+→raises `BibKeyAmbiguous`.
- **Biblatex exporter** → `src/workflow/prisma/exporter.py` `_entry_to_biblatex`, `_biblatex_field_pairs` — private renderer already exists (ADR-0019 P3).
- **Graph CLI** → `src/workflow/graph/cli.py` orphans command — `--type` Choice: `note/exercise/bib_entry/content/topic/course`.
- **Vault paths** → `src/workflow/vault/paths.py` `resolve_vault_root()`.
- **Notes link** → `src/workflow/notes/cli.py:498` link command — mutex targets `--main-topic` / `--concept`.
- **Note-relation-graph ADR** → `docs/ADR/ITEP-0013-note-relation-graph.md` — status: Accepted (2026-05-22).
- **ADR-0020** → `docs/ADR/0020-bibliography-module-boundary.md` — bibliography as foundation layer, 0/1/2+ lookup contract.

---

## Section A: Request Data-Model Claims

| Claim | Verdict | Issue |
|-------|---------|-------|
| `prisma_review_id: <Review.id>` frontmatter field | ⚠️ open | No `Review` entity exists; screening is `ReviewRecord(keyword_id, bib_entry_id)` |
| CLI flag `--review-id <id>` | ⚠️ open | Must be `--keyword-id` or `--review-record-id` |
| `rationale_N.text` rendering | ⚠️ open | `ReviewRationale` has no `.text`; free-text is `ReviewRecord.include_rationale` |
| `included == True` filter | ⚠️ open | `included` is tri-state SmallInteger (None/0/1); must filter `included == 1` |

### Findings

1. **No `Review` entity / `review_id` (Critical)** — Request's frontmatter `prisma_review_id: <Review.id>`, CLI `--review-id`, and fetch logic ("Reviewed record + Review_rationale for bib_entry_id, review_id") are wrong. Real screening decision is `class ReviewRecord` (table `review_record`) keyed by `(keyword_id, bib_entry_id)` UniqueConstraint (`src/workflow/db/models/bibliography.py`). ADR PRISMA-0003 confirms keyword-centric screening with no standalone `Review` model. **FIX:** replace `prisma_review_id` frontmatter key with `prisma_keyword_id` (or `prisma_review_record_id`); replace CLI `--review-id` with `--keyword-id` / `--review-record-id`. **OPEN.**

2. **Rationale shape wrong (Critical)** — Request renders `rationale_N.text` from what it calls a rationale list. `class ReviewRationale` (`review_rationale` table) is a pure join: `review_record_id` + `rationale_option_id`; it carries no `.text` attribute. Free-text rationale lives on `ReviewRecord.include_rationale: Mapped[str|None]` (Text). Controlled-vocab rationales come from `RationaleOption.label`. **FIX:** render `ReviewRecord.include_rationale` for the free-text block; join through `ReviewRationale` → `RationaleOption` for controlled labels. **OPEN.**

3. **`included` is tri-state SmallInteger, not bool (Critical)** — `ReviewRecord.included: Mapped[int|None] = mapped_column(SmallInteger, default=None)`. Values: None=unscreened, 0=excluded, 1=included. Request says "filter included=True". **FIX:** use `included == 1`. **OPEN.**

4. **ITEP-0013 status stale (High)** — Request body describes note-relation-graph dependency on an ADR in "Proposed" status (written twice). `docs/ADR/ITEP-0013-note-relation-graph.md` status is `Accepted` (accepted 2026-05-22). **FIX:** update request wording; the ADR is already Accepted. **OPEN.**

---

## Section B: Request CLI / Rendering Claims

| Claim | Verdict | Issue |
|-------|---------|-------|
| `workflow notes create --type literature` as new command | ⚠️ open | `notes new --type literature` already exists; request duplicates it |
| "No schema changes needed" for frontmatter | ⚠️ open | New keys (bibkey, prisma_review_id, source, created) fail existing validator |
| Frontmatter key `source: prisma\|manual` | ⚠️ open | Collides with `Note.source` relationship + `source_format` column |
| `<BIBKEY>` as sole CLI selector | ⚠️ open | bibkey is NON-unique by design; `BibKeyAmbiguous` case unhandled |

### Findings

5. **`notes new --type literature` already exists (Medium)** — `src/workflow/notes/cli.py:77`, command name=`new`, `--type` Choice includes `"literature"`, builds frontmatter dict and calls `create_note`. Request invents a duplicate renderer and treats this path as hypothetical-future. **FIX:** reuse `notes new` / `create_note` instead of duplicating note rendering. **OPEN.**

6. **Proposed frontmatter fails validation (Medium)** — `notes new` calls `validate_note_frontmatter`. The new keys (`bibkey`, `prisma_review_id`, `source`, `created`) are unknown to the existing validator schema → validation rejects. Request's claim "No schema changes are needed" is false. **FIX:** extend the validator schema for the new keys (or document them as optional passthrough via an allow-extras flag). **OPEN.**

7. **`source` key name collides (Medium)** — `src/workflow/db/models/notes.py:53` has a `source` relationship attribute (back-populated from `Link.source`); `source_format` is a separate column. Request's frontmatter `source: prisma|manual` introduces a third meaning for "source". **FIX:** rename to `origin:` or `note_source:` in the frontmatter spec. **OPEN.**

8. **bibkey ambiguity unhandled (Medium)** — `get_bib_entry_by_bibkey` (`src/workflow/bibliography/service.py:33`) raises `BibKeyAmbiguous` when 2+ entries share a bibkey (non-unique by design, ADR-0019). Request uses `<BIBKEY>` as the sole CLI selector and never handles the ambiguous case. **FIX:** add `--bib-entry-id` as a fallback selector; catch `BibKeyAmbiguous` and emit a helpful error with the conflicting IDs. **OPEN.**

---

## Section C: Improvement Opportunities

| Claim | Verdict | Issue |
|-------|---------|-------|
| "write minimal render_biblatex in workflow.bibliography" | ⚠️ open | Private renderer already exists; should be promoted + relocated per ADR-0020 |
| `adr_refs` list in frontmatter | ⚠️ open | Missing ADR-0020, ITEP-0012, ITEP-0013 |

### Findings

9. **Biblatex renderer already exists — promote instead of rewrite (Low)** — `src/workflow/prisma/exporter.py` has `_entry_to_biblatex(entry)` and `_biblatex_field_pairs` (landed ADR-0019 P3). Request says "write a minimal render_biblatex in workflow.bibliography". **FIX:** promote `_entry_to_biblatex` to public; per ADR-0020 (bibliography = foundation layer), relocate it into `workflow.bibliography` so both `prisma` and this feature share one renderer. **OPEN.**

10. **`adr_refs` frontmatter gaps (Low)** — Request body references ITEP-0012 (concept/note linking), ADR-0020 (bibliography boundary), and ITEP-0013 (note-relation-graph, now Accepted). None appear in the `adr_refs:` frontmatter list. **FIX:** add `"0020"`, `"ITEP-0012"`, `"ITEP-0013"` to `adr_refs`. **OPEN.**

---

## Section D: Verified Correct Claims

| Claim | Verdict | Notes |
|-------|---------|-------|
| `graph orphans --type note` valid Choice | ✅ resolved | `src/workflow/graph/cli.py` orphans `--type` choices include `note` |
| `resolve_vault_root()` exists | ✅ resolved | `src/workflow/vault/paths.py` |
| `notes link --main-topic` / `--concept` exist | ✅ resolved | `src/workflow/notes/cli.py:498` link command, mutex targets |
| `get_bib_entry_by_bibkey` is the right reuse target | ✅ resolved | `src/workflow/bibliography/service.py:33` |
| `notes/literature/` vault path consistent with ITEP-0011 | ✅ resolved | Vault note type directories per ITEP-0011 |

---

## Summary / open items

| # | Severity | Claim / File | Issue | Action needed |
|---|----------|-------------|-------|---------------|
| 1 | Critical | `prisma_review_id` frontmatter + `--review-id` CLI | No `Review` entity; screening is `ReviewRecord(keyword_id, bib_entry_id)` | Replace with `prisma_keyword_id` / `--keyword-id` or `--review-record-id` |
| 2 | Critical | `rationale_N.text` rendering | `ReviewRationale` has no `.text`; free-text is `ReviewRecord.include_rationale` | Render `include_rationale` + joined `RationaleOption.label` |
| 3 | Critical | `included == True` filter | Tri-state SmallInteger (None/0/1) | Use `included == 1` |
| 4 | High | ITEP-0013 described as "Proposed" | ADR is `Accepted` (2026-05-22) | Update request body wording |
| 5 | Medium | `workflow notes create --type literature` as new | `notes new --type literature` already exists | Reuse existing `notes new` / `create_note` path |
| 6 | Medium | "No schema changes needed" | New frontmatter keys fail validator | Extend validator schema for new keys |
| 7 | Medium | Frontmatter key `source:` | Collides with `Note.source` relationship + `source_format` column | Rename to `origin:` or `note_source:` |
| 8 | Medium | `<BIBKEY>` as sole selector | `BibKeyAmbiguous` unhandled (non-unique by design) | Add `--bib-entry-id` fallback; catch ambiguity |
| 9 | Low | "write minimal render_biblatex" | Private renderer exists in `exporter.py` | Promote + relocate per ADR-0020 |
| 10 | Low | `adr_refs` frontmatter | Missing ADR-0020, ITEP-0012, ITEP-0013 | Add three entries |
