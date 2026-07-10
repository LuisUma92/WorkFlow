---
title: Neovim Plugin
parent: Wiki
---
# Neovim Plugin

Plugin de Neovim (`nvim-plugin/`) que envuelve el CLI `workflow` con comandos
`:Workflow*`, keymaps `<leader>z*`, pickers de Snacks y validación en
`BufWritePost`. No usa un servidor JSONL/RPC — todo pasa por invocaciones al
CLI, por eso requiere que `workflow` esté resoluble (venv activo o en PATH).

Referencia fuente de verdad: `nvim-plugin/doc/workflow.txt` (`:help workflow`
una vez corrido `:helptags ALL`) y `nvim-plugin/lua/workflow/{init,config,
commands,keymaps,autocmds}.lua`. Esta página es la puerta de entrada en
prosa — para el detalle exhaustivo de cada comando, `:help workflow`.

Ver también: [Zettelkasten Notes](Zettelkasten-Notes.md),
[Fleeting-Monolith Flow](Fleeting-Monolith-Flow.md),
[PRISMA Review](PRISMA-Review.md), [Getting Started](Getting-Started.md).

## 1. Instalación (lazy.nvim / packer)

```lua
{
  dir = "~/02-Projects/WorkFlow/nvim-plugin",
  name = "workflow",
  config = function()
    require("workflow").setup({
      workflow_cmd = nil,               -- nil = auto-detectado (venv o PATH)
      auto_sync_on_save = true,         -- sync DB en :w de .md dentro del workspace
      auto_validate_on_save = true,     -- valida frontmatter en :w
      auto_graph_validate_on_save = true, -- `validate notes --graph` en :w (diagnostics)
      workspace_dir = nil,              -- nil = auto-detectado (.workflow/config.yaml)
      vault_dir = "~/01-U/0000AV-Vault",
      keymaps = true,                  -- registra todos los <leader>z*
      keymap_prefix = "<leader>z",
      snippets = true,                 -- LuaSnip: yaml/markdown/tex
    })
  end,
}
```

Todas las claves de arriba son exactamente las de `M.defaults` en
`lua/workflow/config.lua` — no hay opciones adicionales sin documentar.

Requisitos opcionales:

- **snacks.nvim** (https://github.com/folke/snacks.nvim) para todos los
  pickers. Sin él, los pickers muestran una notificación de error; el resto
  de comandos (sync, validate, promote, capture, bib-import, etc.) funciona
  igual.
- **lyaml** (`luarocks install lyaml`) para parsear frontmatter. Sin él, la
  extracción de frontmatter devuelve el error `"lyaml not installed"`.
- **LuaSnip** para los snippets `rel.` / `link.` (opt-out con `snippets =
  false`).

La raíz del vault efectiva se resuelve en este orden de prioridad:

1. `$WORKFLOW_VAULT_ROOT` (env var)
2. `workspace_dir` (auto-detectado subiendo desde cwd buscando
   `.workflow/config.yaml`) + `vault_dir`
3. `nil` — los comandos vault-aware avisan y abortan

## 2. Tabla completa de comandos `:Workflow*`

### 2.1 Utilidad

| Comando | Qué hace | Cuándo usarlo |
|---|---|---|
| `:WorkflowSync` | Sincroniza metadata de nota/ejercicio del buffer actual a la DB | Después de editar frontmatter y no querer esperar el autocmd de guardado |
| `:WorkflowSyncExercise` | Igual, forzando el parser de ejercicio LaTeX | Cuando el buffer es un `.tex` de ejercicio |
| `:WorkflowValidate` | Valida el frontmatter YAML del buffer actual | Chequeo manual antes de guardar |
| `:WorkflowPromote` | Mueve la nota de `inbox/` a la raíz del vault y cambia `type: fleeting` → `permanent` | Cuando una nota fugaz maduró y merece vivir como permanente |

### 2.2 Notas

| Comando | Qué hace | Cuándo usarlo |
|---|---|---|
| `:WorkflowNoteSync[!]` | Bulk-sync del vault completo (.md → DB); `!` agrega `--strict-concepts` | Después de editar varias notas a mano fuera de Neovim |
| `:WorkflowNotePicker [tag=][concept=][note_type=][candidate_project=]` | Picker Snacks sobre todas las notas, con filtros opcionales | Explorar/filtrar el vault; `<CR>` abre, `<C-t>` tags, `<C-l>` linkea concepto/referencia/ejercicio |
| `:WorkflowNoteShow [id]` | Muestra una nota en scratch buffer (usa `id:` del frontmatter actual si se omite) | Inspección rápida sin abrir el archivo |
| `:WorkflowNoteTag {id} +tag1 -tag2` | Agrega/quita tags de la nota `id` | Retag masivo desde la línea de comandos |
| `:WorkflowNoteLink {id} {concept\|reference\|exercise} {value} [remove]` | Linkea (o desvincula con `remove`) la nota `id` | Cuando se necesita el `id` explícito en vez de la nota actual |
| `:WorkflowNoteNew {id} {título...}` | Crea una nota nueva | Alternativa de línea de comandos a `nn`/`nC` |
| `:WorkflowNoteSearch` | Prompt de query → picker Snacks sobre `workflow notes search --json` (FTS5, insensible a acentos) | Buscar por contenido, no por filtro de metadata |
| `:WorkflowNoteCapture [título...]` | `workflow notes capture --title ... --json` → abre la nota creada (o existente) | Captura de una idea en un solo gesto, sin salir de Neovim |

### 2.3 Edges (ITEP-0013)

| Comando | Qué hace | Cuándo usarlo |
|---|---|---|
| `:WorkflowEdgesPicker [source=][edge_class=][relation_type=]` | Picker sobre `NoteEdge`; `<CR>` abre la nota origen | Auditar relaciones estructurales entre notas |
| `:WorkflowEdgesCheck` | Detecta ciclos en el grafo de edges; los vuelca a quickfix y abre `:copen` | Antes de confiar en `derived_from`/`links` para navegación |
| `:WorkflowEdgesPickerFiltered` | Picker en dos pasos: primero elegí `edge_class` desde el vocabulario vivo del CLI, después navegá edges de esa clase | Evita hardcodear `edge_class` — siempre viene del CLI |

### 2.4 Evaluación / PRISMA / taxonomía

| Comando | Qué hace |
|---|---|
| `:WorkflowEvalPicker [institution]` | Lista plantillas de evaluación |
| `:WorkflowItemPicker [domain] [level]` | Lista ítems del banco (filtro Bloom domain/level) |
| `:WorkflowCoursePicker [institution]` | Lista cursos |
| `:WorkflowPrismaBibPicker [key=value...]` | Navega bibliografía PRISMA |
| `:WorkflowPrismaKeywordPicker` | Navega keywords de búsqueda PRISMA (sin args) |
| `:WorkflowPrismaReviewPicker {keyword-id} [status]` | Navega reviews de artículos para un keyword |
| `:WorkflowPrismaAcceptToNote` | Genera nota(s) de literatura desde una entrada PRISMA aceptada (ver §4.d) |
| `:WorkflowTopicPicker [discipline-area=CODE]` | Picker de topics; `<CR>` inserta el `id` en el cursor |
| `:WorkflowContentPicker [topic-id=N]` | Picker de contents; `<CR>` inserta el `id` |
| `:WorkflowConceptPicker [main-topic=CODE]` | Picker de concepts; `<CR>` inserta el slug `code` (listo para `concepts:` en frontmatter) |
| `:WorkflowContentBibPicker [content-id=N]` | Picker de bib-links de un content; `<CR>` inserta el bibkey; sin argumento usa `content_id:` del frontmatter del buffer |
| `:WorkflowContentLinkBib {content-id} {bibkey} {chapter} {section} {first-page} {last-page} [first-exercise] [last-exercise]` | Adjunta un bib entry a un content con locus |
| `:WorkflowContentUnlinkBib {content-id} {bibkey}` | Quita un bib-link |
| `:WorkflowBibImport` | Extrae el primer bloque ` ```bib ` del buffer e importa vía `workflow prisma bib import --stdin --json` (async, notifica conteos) |

### 2.5 Grafo / lectures

| Comando | Qué hace |
|---|---|
| `:WorkflowGraphStats [main-topic=][discipline-area=][topic=]` | `workflow graph stats --json` en split horizontal (filetype=json) |
| `:WorkflowGraphOrphans [type=][main-topic=][discipline-area=][topic=]` | `workflow graph orphans --json` en scratch buffer |
| `:WorkflowGraphNeighbors {node-id} [depth=N]` | Picker de vecinos del nodo en el grafo |
| `:WorkflowLectureScan` | `workflow lectures scan` en split horizontal — ver [Fleeting-Monolith Flow](Fleeting-Monolith-Flow.md) |
| `:WorkflowLectureLink` | `workflow lectures link` en split horizontal |

### 2.6 Wave 5 — enums, ids, graph-validate

| Comando | Qué hace |
|---|---|
| `:WorkflowReloadEnums` | Limpia el caché de vocabulario de sesión; el próximo picker de enum vuelve a pedirlo a `workflow notes enums --json` |
| `:WorkflowEnumRelationType [edge_class] [mode=insert\|yank]` | Elige un `relation_type` del vocabulario vivo |
| `:WorkflowEnumEdgeClass [mode=insert\|yank]` | Elige un `edge_class` |
| `:WorkflowEnumNoteType [mode=insert\|yank]` | Elige un `note_type` |
| `:WorkflowNoteNewId` | Genera un `zettel_id` fresco vía `workflow notes new-id` y lo inserta (también yankeado a `+`) |
| `:WorkflowValidateGraph` | `workflow validate notes <path> --graph --json` sobre el buffer actual → diagnostics de Neovim (namespace `workflow_graph_validate`). También corre solo en `BufWritePost` si `auto_graph_validate_on_save = true` |
| `:WorkflowRelationBlock [relation_type]` | Inserta un scaffold YAML `derived_from:`/`links:` en el cursor |

> Después de agregar comandos nuevos correr `:helptags ALL` una vez para que
> `:help :WorkflowXxx` resuelva.

## 3. Tabla completa de keymaps `<leader>z*`

Prefijo configurable vía `keymap_prefix` (default `<leader>z`); todo el
bloque se desactiva con `keymaps = false`. Los 24 keymaps existentes, tal
como están en `lua/workflow/keymaps.lua`:

| Keymap | Acción | Picker/comando invocado | Qué inserta/abre |
|---|---|---|---|
| `sn` | Sync DB de la nota actual | `workflow.sync_current()` | — (fire and forget) |
| `se` | Sync DB como ejercicio LaTeX | `workflow.sync_current_exercise()` | — |
| `v` | Validar frontmatter del buffer | `workflow.validate_frontmatter()` | notificación con errores/OK |
| `p` | Promover fleeting → permanent | `workflow.promote_note()` | mueve el archivo de `inbox/` a la raíz del vault, reabre |
| `te` | Pick evaluaciones | `picker.evaluations` | abre picker Snacks |
| `ti` | Pick items | `picker.items` | abre picker Snacks |
| `tc` | Pick cursos | `picker.courses` | abre picker Snacks |
| `np` | Pick notas | `picker.notes` | `<CR>` abre el archivo |
| `ns` | Sync notas (bulk vault) | `workflow.sync_notes()` | — |
| `nn` | Nueva nota (prompts id+título) | `workflow.new_note()` | crea archivo, `id` opcional (auto-genera) |
| `nt` | Tag de la nota actual (prompt `+add -remove`) | `workflow.tag_note()` | — |
| `nl` | Link de la nota actual (prompt kind+value) | `workflow.link_note()` | — |
| `ne` | Pick note edges | `picker.edges` | abre picker Snacks |
| `nc` | Check ciclos de edges | `workflow.edges_check()` | popula quickfix + `:copen` |
| `en` | Insertar `zettel_id` fresco en el cursor | `workflow.insert_new_id()` | id generado, también yankeado a `+` |
| `er` | Pick `relation_type` (enums vivos) | `picker.enums.pick_relation_type` | inserta en el cursor |
| `ec` | Pick `edge_class` (enums vivos) | `picker.enums.pick_edge_class` | inserta en el cursor |
| `eg` | Graph-validate la nota actual | `workflow.validate_graph()` | diagnostics de Neovim |
| `ei` | Pick una nota, insertar su `zettel_id` | `picker.notes({mode="insert_id"})` | el id en el cursor |
| `eI` | Pick una nota, insertar item YAML completo | `picker.notes({mode="insert_yaml"})` | bloque `- id: …\n  type: …` |
| `eb` | Pick un bibkey | `picker.prisma_bib` | yankea el bibkey a `+` |
| `ek` | Pick un concept code | `picker.concepts` | inserta el slug en el cursor |
| `nC` | Capturar nota (prompt título) | `workflow.capture_note()` | abre la nota creada |
| `nf` | Buscar notas (FTS5) | `picker.search` | `<CR>` abre el archivo encontrado |

LuaSnip (si `snippets = true`), disparadores en `markdown`:

| Trigger | Inserta |
|---|---|
| `rel.` | Scaffold `derived_from:` |
| `link.` | Scaffold `links:` |

## 4. Cuatro flujos punta a punta

### a. Captura rápida

```text
<leader>zn C          -- prompt "Capture note title:" → título
                       -- workflow notes capture --title "…" --json
                       -- abre la nota creada (o la existente, idempotente)
(editar el cuerpo)
:w                     -- BufWritePost: sync + validate frontmatter
                       -- + graph-validate (auto_graph_validate_on_save)
<leader>zek            -- pick concept code → insertar en `concepts:`
<leader>zp             -- cuando la nota maduró: promote fleeting → permanent
```

`<leader>znC` es literalmente el keymap `nC` (no hay tecla `n` intermedia con
timeout — es una sola secuencia bajo el prefijo). Nótese que `:WorkflowPromote`
es un **flip** de `type:` + `rename`, ejecutado sobre el archivo abierto — no
un comando de "mover cualquier nota"; solo actúa si el buffer vive dentro de
`<vault_root>/inbox`.

### b. Búsqueda y navegación

```text
<leader>zns            -- (ns = sync bulk) o <leader>znf para buscar directo
<leader>znf            -- prompt query → workflow notes search --json (FTS5,
                       -- insensible a acentos, ranking bm25) → picker Snacks
<CR>                   -- abre la nota (resuelve ruta relativa al vault_root
                       -- configurado si el CLI devuelve una ruta relativa)
```

Desde la nota abierta, para enlazarla a otra:

```text
<leader>zei            -- pick una nota → inserta su zettel_id en el cursor
<leader>zeI            -- pick una nota → inserta bloque YAML
                       -- "- id: …\n  type: …" (para relations.derived_from/links)
```

### c. Semana docente (monolito)

```text
1. Crear inbox/semanaNN-tema.md (zonas STAGING + bloques %>id.md … %>END)
2. :WorkflowLectureScan      -- o `workflow lectures scan` en terminal
3. :WorkflowLectureLink      -- o `workflow lectures split inbox/semanaNN-tema.md`
                             -- (split es solo CLI, no tiene comando :Workflow*
                             -- dedicado hoy — usar terminal o `:!workflow lectures split …`)
4. :w sobre cada nota emitida -- dispara validate + graph-validate automáticos
```

Guía completa del flujo (zonas del monolito, ciclos de vida de conceptos,
`--sync`/`--no-sync`, `concept harvest` + `import`):
[Fleeting-Monolith Flow](Fleeting-Monolith-Flow.md).

### d. PRISMA — aceptar a nota

```text
:WorkflowPrismaAcceptToNote
  → prompt "bibkey" (modo single) ó dejar en blanco + prompt "keyword-id" (bulk)

  Single:  workflow prisma bib accept-to-note <BIBKEY> --json
           → abre la nota resultante en vsplit; notifica "Created:" o
             "Already exists:" + ruta

  Bulk:    workflow prisma bib accept-to-note --all-accepted --keyword-id N --json
           → notifica "N created, M skipped"; si la lista no está vacía abre
             la primera nota en vsplit; lista vacía → WARN, no abre nada

  Error CLI → mostrado verbatim a nivel ERROR
```

Contexto de screening/keywords/reviews previo a este paso:
[PRISMA Review](PRISMA-Review.md).

## 5. Troubleshooting

- **El plugin no carga / `require("workflow")` falla**: confirmar que
  `dir` en el spec de lazy.nvim/packer apunta a `nvim-plugin/` dentro del
  repo, y que `workflow.setup({...})` corre en el `config` del spec.
- **"snacks.nvim is required for pickers"**: instalar
  https://github.com/folke/snacks.nvim. Sin él, todos los demás comandos
  (sync, validate, promote, capture, bib-import) siguen funcionando.
- **CLI `workflow` no está en PATH**: setear `workflow_cmd` explícitamente en
  `setup()` apuntando al binario del venv (p. ej.
  `vim.fn.expand("~/02-Projects/WorkFlow/.venv/bin/workflow")`), o activar el
  venv antes de lanzar Neovim.
- **La validación no dispara al guardar**: revisar que el archivo esté
  *dentro* del workspace/vault detectado — los tres autocmds de
  `autocmds.lua` (`sync`, `validate`, `graph-validate`) comprueban
  `is_in_workspace`/`is_in_workspace(vault_root)` antes de correr; un `.md`
  fuera de `<vault_root>` o de `.workflow/config.yaml` no dispara nada.
  Confirmar también las flags `auto_sync_on_save` / `auto_validate_on_save` /
  `auto_graph_validate_on_save` en la config activa.
- **"No vault root configured"**: setear `$WORKFLOW_VAULT_ROOT`, o verificar
  que exista un `.workflow/config.yaml` en algún directorio padre del cwd.
- **"Path outside workspace — refusing to open"**: guard de path-traversal;
  revisar que el campo `path` del frontmatter de la nota afectada no intente
  escapar del directorio del vault.
- **Diagnosticar cualquier error silencioso**: `:messages` muestra las
  notificaciones recientes (todas las funciones del plugin notifican vía
  `vim.notify` con `title = "workflow"`); para trazas completas de sync,
  correr `workflow notes sync --json` en una terminal.
