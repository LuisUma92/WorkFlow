# Add `plenary.busted` test harness to `nvim-plugin/`

## Summary

The Neovim plugin (`nvim-plugin/`) has grown from 4 commands at
the start of 2026 to **28 user commands** as of v1.13.0/v1.13.1,
across 17 Lua modules (~2100 LOC). It has **zero automated unit
tests.** The only validation is `scripts/smoke_taxonomy.sh`
which exercises the underlying Python CLI (not the Lua surface)
plus a headless `nvim --noplugin -u plugin/workflow.lua -c "qa"`
check that catches syntax errors but no logic.

Architect review (2026-05-29 reviewer-esquema) flagged this as
load-bearing debt: **the plugin is now a non-trivial codebase
without test infrastructure.** TDD reviewer concurred.

Each subsequent plugin expansion (v1.11.0 / v1.12.0 / v1.13.0
plugin side) explicitly deferred test infra. Time to land it.

## Motivation

- Reporting agent(s): architect-reviewer + tdd-guide (2026-05-29)
- Total occurrences: 3 deferrals (v1.11.0, v1.12.0, v1.13.0
  plugin)
- Severity: **MEDIUM-HIGH** (no functional bugs known, but
  refactoring confidence is zero — any future picker change is
  blind)
- Blocks / slows down:
  - Refactoring confidence: any change to picker, frontmatter
    parser, or kv-arg parser must be manually exercised in
    nvim
  - JSON contract regressions: `contracts.lua` says "no runtime
    behaviour — for type checking only"; nothing actually
    validates that picker code matches the CLI's JSON shape
  - Cross-version Neovim compatibility (0.9 vs 0.10 API
    differences are caught only at runtime by users)

## Proposed setup

### 1. Add plenary.nvim as a dev dependency

Document in `nvim-plugin/README.md` (and the plugin doc) that
plenary.nvim must be installed for `make test` to work. No
runtime dependency for end users.

### 2. Directory layout

```
nvim-plugin/
    tests/
        plenary/
            minimal_init.lua             # loads plenary + plugin
            picker/
                topics_spec.lua
                contents_spec.lua
                concepts_spec.lua
                content_bib_spec.lua
                edges_spec.lua
                notes_spec.lua
                evaluations_spec.lua
            frontmatter_spec.lua
            commands_spec.lua            # tests kv-arg parser
            server_spec.lua              # tests basename allowlist
```

### 3. Per-picker test pattern

For each picker, validate:
- **JSON contract**: feed a stub `server.run_cli` that returns a
  known JSON shape, assert the picker decodes correctly and
  builds the expected `items` table
- **Cursor insert**: assert `<CR>` confirm callback calls
  `nvim_buf_set_text` with the expected string
- **Empty result**: assert the empty-set notify path
- **Snacks guard**: assert the `_G.Snacks = nil` path returns
  without crashing

### 4. Stub strategy

Use plenary's `stub()` to replace `server.run_cli` per test —
NO real CLI invocation. The Python smoke script already covers
CLI contracts.

### 5. CI hook

Add `make test-plugin` target in repo root Makefile (or as a
new GH Action step) running:
```bash
nvim --headless -u nvim-plugin/tests/plenary/minimal_init.lua \
     -c "PlenaryBustedDirectory nvim-plugin/tests/plenary/" \
     -c "qa"
```

Exit non-zero if any spec fails.

## Acceptance test

- `cd nvim-plugin && make test` (or repo-root `make test-plugin`)
  runs the harness and reports PASS/FAIL counts.
- Each picker module has ≥ 3 specs (contract, insert, empty).
- `frontmatter_spec.lua` covers the YAML edge cases (empty,
  comments, missing delimiter, multi-line — current parser is
  hand-rolled and untested).
- `commands_spec.lua` covers the kv-arg regex including
  hyphenated keys (`discipline-area=FI0001`) and the
  unconstrained-value risk flagged in v1.13.1 security review.
- `server_spec.lua` asserts the basename allowlist (v1.13.1):
  `workflow_cmd = "/tmp/evil"` → notify + return early.
- CI green on at least one `nvim --version` from the 0.9.x and
  0.10.x branches.
- Existing `scripts/smoke_taxonomy.sh` stays as a Python-CLI
  contract check (orthogonal scope).

## Out of scope

- Full integration tests that spin up a real Snacks picker
  (Snacks is hard to drive headless; stub the API instead)
- Test coverage targets (set after first pass; aim for ≥ 60%
  Lua coverage)
- Replacing the Python smoke script
- Visual/UI tests of picker formatting

## Phase plan

1. **P1**: harness setup + minimal_init + 1 picker spec proof
   (`topics_spec.lua`)
2. **P2**: pickers (6 more spec files)
3. **P3**: `frontmatter_spec.lua` + `commands_spec.lua` +
   `server_spec.lua`
4. **P4**: CI integration + coverage reporting

Each phase commits separately; tag as `plugin-v1.14.0` (or
similar) when P4 lands.

## Cross-references

- `2026-05-29` reviewer-esquema synthesis (architect debt +
  tdd debt)
- `2026-05-23-nvim-plugin-review-hardening.md` — closed; first
  formal Lua review of the plugin, established `contracts.lua`
  infrastructure this builds on
- `nvim-plugin/lua/workflow/contracts.lua` — EmmyLua type
  surface that specs should validate against
- `nvim-plugin/lua/workflow/server.lua` — basename allowlist
  added in v1.13.1; needs test coverage
- `nvim-plugin/lua/workflow/frontmatter.lua` — hand-rolled YAML
  parser; long-untested
