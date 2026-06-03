# <Subject> Audit — <YYYY-MM-DD>

Scope: verify <what artifact set> matches <which truth-sources>.

## Truth-sources

<!-- List every authoritative file/symbol the audit checks against.
     Include path:line refs where possible. This is the discipline of an audit. -->
- **<Schema / model>** → `<src/path/to/file.py>` `<ClassName>` (line <N>). Recognized fields: `<field1>, <field2>, …`
- **<CLI contract>** → `<src/path/cli.py>` `<command_name>` — expected flags / output shape.
- **<Config / template>** → `<path/to/template.yaml>` — canonical example.

---

## <Section A: artifact group name>

<!-- One table per logical group of files being checked. -->

| File | Verdict | Issue |
|------|---------|-------|
| `<path/to/file>` | ✅ resolved | <brief note or "—"> |
| `<path/to/file>` | ⚠️ open | <what is wrong / missing> |
| `<path/to/file>` | ⚪ WIP-accepted | <why accepted as-is> |

<!-- Verdict legend:
     ✅ resolved — matches truth-source (or was fixed during this audit)
     ⚠️ open     — mismatch / gap that must be fixed
     ⚪ WIP-accepted — known deviation deliberately left; re-audit when stable -->

### Findings

1. **<Short title>** — <problem description; cite path:line>. **OPEN.**
2. ~~**<Short title>**~~ **RESOLVED <YYYY-MM-DD>**: <what was done to fix it>.

---

## <Section B: artifact group name>

| File | Verdict | Issue |
|------|---------|-------|
| `<path/to/file>` | ✅ resolved | — |

### Findings

1. <No findings — all correct.>

---

## Summary / open items

<!-- List ONLY items whose verdict is ⚠️ open. -->

| # | File | Issue | Action needed |
|---|------|-------|---------------|
| 1 | `<path>` | <one-line problem> | <concrete fix> |
