# Implementation plan — literature-note `bib` block → `prisma bib import`

Request: `tasks/requests/2026-06-01-literature-note-bib-block-import.md`
Methodology: TDD (RED→GREEN→REFACTOR), reuse existing importer, no new parser.

## Key facts (verified)

- Importer exists: `import_bib_file(session, path, database_name=…)` in
  `src/workflow/prisma/importer.py:347`. Reads file at `:369` (`p.open()` →
  `bibtexparser.load(f)`), size guard at `:364`. Public `__all__` at `:30`.
- CLI: `prisma bib import <PATH>` at `src/workflow/prisma/cli.py:146`
  (`click.Path(exists=True)`).
- nvim `server.run_cli(args, config, on_done)` (`server.lua:14`) shells out via
  `jobstart` and **does not write stdin** — must extend.
- Literature template generated in `src/workflow/notes/init.py`.

## Workstream A — Python (sonnet TDD)  [files: prisma/*, notes/init.py, CLAUDE.md]

A1. Refactor `import_bib_file`: extract `import_bib_text(session, text, *,
    database_name=None) -> ImportResult` holding the parse+persist body
    (`bibtexparser.loads(text)` path). `import_bib_file` becomes: read file
    (keep size guard + `FileNotFoundError`) → call `import_bib_text`. Add
    `import_bib_text` to `__all__`. Apply `MAX_BIB_SIZE_BYTES` to the text
    (`len(text.encode())`).
A2. CLI: add `--stdin` flag to `bib_import` (`cli.py:146`). When set, make PATH
    optional and read `sys.stdin.read()` → `import_bib_text`. When not set,
    unchanged file path. `--stdin` + a PATH → error. Keep `--json`/`--verbose`/
    `--database-name`.
A3. Tests `tests/workflow/prisma/`: stdin creates BibEntry; file==stdin row
    parity; empty stdin → `ImportResult.errors` (no crash); existing file-path
    regression stays green. Use `global_session` fixture.
A4. Literature template: add a stub ```` ```bib ```` fenced block to the
    literature note body in `notes/init.py`; update/extend its template test.
A5. Docs: CLAUDE.md prisma row — note `--stdin`.

## Workstream B — nvim (sonnet)  [files: nvim-plugin/*]

B1. Extend `server.run_cli` to accept optional stdin: add 4th arg or
    `opts.stdin` string; after `jobstart`, if present `vim.fn.chansend(job,
    stdin)` then `vim.fn.chanclose(job, "stdin")`. Backward-compatible (nil →
    no write).
B2. New `nvim-plugin/lua/workflow/bib_import.lua`: find first ```` ```bib ````
    fenced block in current buffer; if none → INFO notify, no CLI call; else
    `run_cli({"prisma","bib","import","--stdin","--json"}, config, cb)` with the
    block text as stdin; notify created/skipped/error counts; on non-zero exit
    show stderr (mirror `content_bib.lua:38`).
B3. Register `:WorkflowBibImport` in `commands.lua` (pattern of existing
    `nvim_create_user_command` block).
B4. Plenary spec `tests/plenary/bib_import_spec.lua`: block extraction, empty
    buffer guard, run_cli invoked with `--stdin` + payload (mock run_cli).
    Mirror `content_bib_spec.lua`.
B5. Docs: `nvim-plugin/doc/workflow.txt` — document `:WorkflowBibImport`.

A and B share no files → run in parallel.

## Verification (main, after agents return)

- `pytest -q tests/workflow/prisma --ignore=tests/test_database.py`
- `flake8 src/ tests/ --max-line-length=127 --max-complexity=10`
- Real CLI: `printf '@book{k,title={X},year={2020}}' | workflow prisma bib import --stdin --json`
- Plenary: CI runs it; note if local nvim/plenary unavailable.

## Out of scope (per request)

Neutral `workflow bib import` alias (followups item 8); auto content-link;
biblatex export.
