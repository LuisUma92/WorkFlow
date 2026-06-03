# Template / Snippet YAML-Metadata Audit — 2026-06-03

Scope: verify the YAML metadata in template + snippet files matches the **current**
workflow truth-sources.

## Truth-sources

- **Note frontmatter** → `src/workflow/validation/schemas.py` `NoteFrontmatter` +
  `validate_note_frontmatter`. Recognized keys ONLY:
  `id, title, aliases, tags, created, concepts, references, exercises, images, type,
  candidate_project, main_topic, discipline_area`.
  Valid `type`: `permanent | literature | fleeting`.
  `aliases: tuple[str,...] = ()` — added 2026-06-03; Obsidian-compatible.
  `src/workflow/notes/service.py` round-trips notes **through** `NoteFrontmatter`
  (lines 77–116); `aliases` is now emitted right after `title`.
- **Bulk-import YAML** → `src/workflow/topic/bulk_import.py` `validate_schema`. Requires:
  - top: `discipline_area_code` (str), `topics` (list)
  - topic: `name` (str), `serial` (int), `contents` (**list**)
  - content: `name` (str), `concepts` (**list**)
  - concept: `code`, `label`, `domain` (all str); `parent_code` optional str;
    `description` optional. `domain` ∈ {Información, Procedimiento Mental,
    Procedimiento Psicomotor, Metacognitivo}.

---

## A. Vault Markdown note templates (`~/01-U/0000AA-Vault/templates/`)

| File | Verdict | Issue |
|------|---------|-------|
| `permanent.md` | ⚠️ open | `aliases` ✅ (now in schema); **still missing** `main_topic` + `discipline_area` (both supported+validated, and the `pn.` nvim snippet includes them → template/snippet drift) |
| `literature.md` | ✅ resolved | `aliases` ✅ (now in schema); `bibkey` DROPPED — literature↔bib linkage goes through `content link-bib` |
| `fleeting.md` | ✅ resolved | `aliases` now recognized in schema; no other issues |

### Findings
1. ~~**`aliases` is dead metadata**~~ **RESOLVED 2026-06-03**: `aliases: tuple[str,...] = ()`
   added to `NoteFrontmatter` with `_string_list` parser; `notes/service.py` emits it
   after `title`. Round-trip safe. Obsidian-compatible. 4 regression tests added.
2. ~~**`bibkey` on literature notes is a gap.**~~ **RESOLVED 2026-06-03**: `bibkey`
   dropped from `literature.md` template and `ln.` snippet. Literature↔bib linkage
   is documented as going through `content link-bib`, not note frontmatter.
3. **`permanent.md` should add `main_topic:` + `discipline_area:`** to match the `pn.`
   snippet and the validator's `--strict-main-topic` path. **STILL OPEN.**

---

## B. Vault bulk-import stubs (`~/01-U/0000AA-Vault/templates/*.yml`)

| File | Verdict | Issue |
|------|---------|-------|
| `0010MC-contents-skyfolding.yml` | ⚪ WIP — accepted | topics 2–4 (`Dinánica`/Energía/Sistemas) have `contents:` = null; topic 1 content `name:` null + `concepts:` null; typo `Dinánica`→`Dinámica`. Work-in-progress user data, not a shipped template. **Won’t fix / WIP — accepted.** |
| `0001MM-contents-skyfolding.yml` | ⚪ WIP — accepted | Algebra content `name:` null + `concepts:` null. Same WIP status. **Won’t fix / WIP — accepted.** |

Both are half-filled skeletons the user is actively filling in; they are not shipped
templates. The canonical schema reference is `workflow/templates/topic-content-concept.yaml`.

---

## C. workflow/templates (`~/01-U/workflow/templates/topic-content-concept.yaml`)

✅ **CORRECT & canonical.** Matches `validate_schema` exactly; good doc header;
valid `domain` values; correct `parent_code` usage. This is the reference template the
vault `*-skyfolding.yml` stubs should follow.

---

## D. nvim snippets (`nvim-plugin/lua/workflow/snippets/`)

| File | Verdict | Notes |
|------|---------|-------|
| `yml.lua` (`wf.`,`tl.`,`ci.`,`nc.`) | ✅ correct | Keys align 1:1 with `validate_schema` (discipline_area_code/topics/name/serial/contents/concepts; concept code/label/domain/description/parent_code). |
| `md.lua` `fn.` (fleeting) | ✅ resolved | `aliases` now recognized in schema |
| `md.lua` `pn.` (permanent) | ✅ resolved | includes `main_topic`+`discipline_area` ✅; `aliases` now recognized in schema |
| `md.lua` `ln.` (literature) | ✅ resolved | `bibkey` DROPPED 2026-06-03; `aliases` now recognized in schema |
| `md.lua` `bib.*` blocks | ✅ correct | biblatex `@book/@article/@techreport/@online`; field names map to BibEntry; importer ignores unknown fields by design (`:WorkflowBibImport`). Not note-frontmatter. |

---

## Consolidated action list

1. ~~**Resolve `aliases`** (systemic)~~ ✅ **DONE 2026-06-03** — added `aliases:
   tuple[str,...] = ()` to `NoteFrontmatter`, `_string_list` parser, emitted after
   `title` in `notes/service.py`. 4 regression tests passing.
2. ~~**Resolve `bibkey` on literature notes**~~ ✅ **DONE 2026-06-03** — `bibkey` dropped
   from `literature.md` vault template and `ln.` nvim snippet. `content link-bib` is
   the documented linkage path.
3. **`permanent.md`**: add `main_topic:` + `discipline_area:` (match `pn.` snippet). **OPEN.**
4. ~~**Fix vault `*-skyfolding.yml`**~~ ⚪ **WON'T FIX** — user WIP data, not shipped templates.
   Accepted as-is.
5. No change needed: `topic-content-concept.yaml`, `yml.lua`, `md.lua` `bib.*`.

## Verdict matrix

| Artifact | Status |
|----------|--------|
| workflow/templates/topic-content-concept.yaml | ✅ |
| vault permanent.md | ⚠️ missing `main_topic` + `discipline_area` (open) |
| vault literature.md | ✅ resolved (bibkey dropped) |
| vault fleeting.md | ✅ resolved (aliases now in schema) |
| vault *-skyfolding.yml ×2 | ⚪ WIP — accepted |
| nvim yml.lua | ✅ |
| nvim md.lua (frontmatter fn./pn./ln.) | ✅ resolved |
| nvim md.lua (bib.*) | ✅ |

---

## Resolution (2026-06-03)

Three audit items resolved, one accepted as-is, one remains open:

**RESOLVED — `aliases` field (items 1 + frontmatter snippets)**
- `src/workflow/validation/schemas.py`: `aliases: tuple[str,...] = ()` added to
  `NoteFrontmatter`, parsed via `_string_list`.
- `src/workflow/notes/service.py`: `aliases` emitted in round-trip dicts after `title`
  (Obsidian-compatible order). No longer silently dropped.
- `tests/workflow/test_validation.py`: 4 regression tests added (parse / default-empty /
  type-error / yaml round-trip). All passing.

**RESOLVED — `bibkey` dropped (item 2)**
- `~/01-U/0000AA-Vault/templates/literature.md`: `bibkey:` field removed.
- `nvim-plugin/lua/workflow/snippets/md.lua` (`ln.` snippet): `bibkey` line removed.
- Rationale: literature↔bib linkage goes through `workflow content link-bib`, not
  note frontmatter.

**ACCEPTED — vault `*-skyfolding.yml` stubs (item 4)**
- `0010MC-contents-skyfolding.yml`, `0001MM-contents-skyfolding.yml`: WIP user data,
  not shipped templates. Left as-is.

**STILL OPEN — `permanent.md` missing `main_topic` + `discipline_area`**
- Vault template `~/01-U/0000AA-Vault/templates/permanent.md` does not yet include
  `main_topic:` or `discipline_area:` fields, while the `pn.` nvim snippet does.
  Fix: add both fields (empty string default) to the template.
