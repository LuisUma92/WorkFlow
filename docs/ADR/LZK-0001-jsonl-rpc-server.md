---
adr: LZK-0001
title: "JSONL/NDJSON RPC Server for Editor Integration"
status: Accepted
date: 2026-03-26
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - latexzettel
  - rpc
  - neovim
  - server
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "LZK-0000"
  - "0001"
---

## Context

Neovim (and other editors) need programmatic access to the Zettelkasten engine for:

- Creating notes from within the editor
- Rendering notes to PDF/HTML
- Synchronizing databases
- Analyzing references and finding unreferenced notes
- Wiki-link navigation

A server protocol is needed that:
- Works over stdin/stdout (Neovim's jobstart model)
- Is stateless (no session management)
- Supports cancellation (long-running operations)
- Is language-agnostic (Lua client in Neovim)

---

## Decision

**JSONL (JSON Lines / NDJSON) request-response protocol** over stdin/stdout.

### Protocol Format

```json
{"id": 1, "method": "initialize", "params": {"root": "/path/to/project"}}
{"id": 1, "result": {"version": "0.2.0", "capabilities": [...]}}

{"id": 2, "method": "note.new", "params": {"reference": "20260326-gauss-law", "title": "Gauss's Law"}}
{"id": 2, "result": {"filename": "20260326-gauss-law.tex", "path": "/path/to/note.tex"}}

{"id": 3, "method": "cancel", "params": {"cancel_id": 2}}
```

Each line is a complete JSON object. The `id` field correlates requests with responses.

### Registered Routes (24)

| Category | Method | Handler | Description |
|----------|--------|---------|-------------|
| **Handshake** | `initialize` | `handle_initialize` | Set project root, return capabilities |
| | `cancel` | `handle_cancel` | Cancel a running operation |
| **Notes** | `note.new` | `handle_new_note` | Create new LaTeX note |
| | `note.new_md` | `handle_new_md_note` | Create new Markdown note |
| | `note.list_recent` | `handle_list_recent` | List recently modified notes |
| | `note.get_recent` | `handle_get_recent` | Get a specific recent note |
| | `note.rename_file` | `handle_rename_file` | Rename note file |
| | `note.rename_ref` | `handle_rename_ref` | Change note reference |
| | `note.remove` | `handle_remove` | Delete a note |
| **Render** | `render.note` | `handle_render_note` | Render single note to PDF/HTML |
| | `render.updates` | `handle_render_updates` | Render all changed notes |
| **Sync** | `sync.synchronize` | `handle_synchronize` | Sync file changes to DB |
| | `sync.force` | `handle_force_sync` | Force full resync |
| **Markdown** | `md.sync` | `handle_sync_md` | Sync Markdown notes to DB |
| | `md.tex_to_md` | `handle_tex_to_md` | Convert LaTeX note to Markdown |
| **Export** | `export.new_project` | `handle_new_project` | Create export project |
| | `export.project` | `handle_export_project` | Export notes to project |
| | `export.draft` | `handle_export_draft` | Export as draft document |
| **Analysis** | `analysis.unreferenced` | `handle_unreferenced` | Find notes with no references |
| | `analysis.dedup_citations` | `handle_dedup_citations` | Find duplicate citations |
| | `analysis.adjacency` | `handle_adjacency` | Build adjacency matrix |

### Server Architecture

```python
# server/main.py
class ZettelServer:
    def __init__(self, project_root: Path):
        self.context = ServerContext(project_root)
        self.router = Router()  # maps method → handler function
        self._register_routes()

    async def run(self):
        """Read JSONL from stdin, dispatch to handler, write response to stdout."""
        for line in sys.stdin:
            request = json.loads(line)
            handler = self.router.get(request["method"])
            result = handler(self.context, request.get("params", {}))
            response = {"id": request["id"], "result": result}
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
```

### Neovim Client

A Lua client (`latexzettel.nvim`) communicates with the server via `vim.fn.jobstart`:

```lua
local job = vim.fn.jobstart({"python", "-m", "latexzettel.server"}, {
    on_stdout = function(_, data) handle_response(data) end,
    stdin = "pipe",
})
vim.fn.chansend(job, vim.fn.json_encode(request) .. "\n")
```

---

## Architectural Rules

### MUST

- Each request **MUST** include an `id` field for correlation.
- Each response **MUST** include the matching `id`.
- Errors **MUST** be returned as `{"id": N, "error": {"code": X, "message": "..."}}`.
- The server **MUST** be stateless between requests (no session).

### SHOULD

- Long-running operations **SHOULD** support cancellation via `cancel` method.
- The server **SHOULD** log operations for debugging.
- Handlers **SHOULD** delegate to the API layer, not implement logic directly.

### MUST NOT

- Handlers **MUST NOT** import Click or other CLI dependencies.
- The server **MUST NOT** hold database connections between requests.
- The server **MUST NOT** write to stderr for non-error output (Neovim reads stderr).

---

## Consequences

### Benefits

- Editor-agnostic: any editor supporting JSONL over stdio can integrate
- Simple protocol: no HTTP overhead, no WebSocket complexity
- Cancellation support for expensive renders
- Stateless design enables easy restart/recovery

### Costs

- Single-threaded: long operations block subsequent requests
- No built-in authentication (trusted local process only)
- Neovim client must be maintained separately (Lua)

---

## Status

**Accepted** — documents existing server

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-26 | Initial ADR |
