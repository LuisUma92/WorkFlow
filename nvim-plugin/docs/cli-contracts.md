# CLI JSON Contracts

Human-readable reference for the four `workflow` CLI `--json` shapes decoded
by the Neovim plugin.  The authoritative EmmyLua types live in
`lua/workflow/contracts.lua`.

---

## 1. `notes list --json` → `WorkflowNoteJSON[]`

Array of note summary objects.

```json
[
  {
    "id": "Ab3CdEfGhIjK",
    "title": "Riemann Hypothesis",
    "type": "permanent",
    "tags": ["math", "open-problem"],
    "concepts": ["ZETAC-001"],
    "path": "/home/user/vault/notes/permanent/Ab3CdEfGhIjK-riemann-hypothesis.md"
  }
]
```

| Field      | Type       | Notes                              |
|------------|------------|------------------------------------|
| `id`       | string     | NanoID, 8–21 chars `[A-Za-z0-9_-]`|
| `title`    | string?    | From frontmatter `title:` key      |
| `type`     | string?    | `fleeting`, `permanent`, etc.      |
| `tags`     | string[]   | Empty array if no tags             |
| `concepts` | string[]   | Concept code slugs                 |
| `path`     | string     | Absolute path, always present      |

---

## 2. `notes show <id> --json` → `WorkflowNoteJSON` (single object)

Same fields as above, but returned as a single JSON object (not array).

---

## 3. `notes edges list --json` → `WorkflowEdgeJSON[]`

Array of edge objects.

```json
[
  {
    "id": 42,
    "source_id": 17,
    "source_zettel_id": "Ab3CdEfGhIjK",
    "target_zettel_id": "XyZ9AbCdEfGh",
    "edge_class": "structural",
    "relation_type": "elaborates",
    "weight": 1.0,
    "rationale": "Provides formal proof sketch"
  }
]
```

| Field              | Type     | Notes                              |
|--------------------|----------|------------------------------------|
| `id`               | integer  | DB primary key                     |
| `source_id`        | integer  | DB FK to Note                      |
| `source_zettel_id` | string?  | Resolved zettel_id of source note  |
| `target_zettel_id` | string?  | zettel_id of target note           |
| `edge_class`       | string   | `structural` or `semantic`         |
| `relation_type`    | string   | e.g. `supports`, `refutes`         |
| `weight`           | number   | Float, default 1.0                 |
| `rationale`        | string?  | Free text, may be null/empty       |

---

## 4. `notes sync --json` → `WorkflowSyncReportJSON`

Single object emitted after a vault sync.

```json
{
  "notes_scanned": 312,
  "labels_registered": 47,
  "links_created": 89,
  "citations_registered": 12,
  "edges_created": 5,
  "orphans_dropped": 2,
  "concept_links_created": 34,
  "concept_issues": [],
  "dry_run": false
}
```

| Field                  | Type    | Notes                             |
|------------------------|---------|-----------------------------------|
| `notes_scanned`        | integer |                                   |
| `labels_registered`    | integer |                                   |
| `links_created`        | integer |                                   |
| `citations_registered` | integer |                                   |
| `edges_created`        | integer |                                   |
| `orphans_dropped`      | integer |                                   |
| `concept_links_created`| integer |                                   |
| `concept_issues`       | array   | `{note_id, code, reason}` objects |
| `dry_run`              | boolean |                                   |

---

## 5. `notes edges check --json` → `WorkflowEdgesCycleJSON`

Emitted only when cycles are detected (exit code 1).

```json
{
  "cycles": [
    ["Ab3CdEfGhIjK", "XyZ9AbCdEfGh", "MnOpQrStUvWx"]
  ]
}
```

| Field    | Type       | Notes                                   |
|----------|------------|-----------------------------------------|
| `cycles` | string[][] | Each inner array is one cycle path      |

---

*Generated from `src/workflow/notes/formatters.py`, `notes/sync.py`,
`notes/cli.py` — update this file whenever CLI output shapes change.*
