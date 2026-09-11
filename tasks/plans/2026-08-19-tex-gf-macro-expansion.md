# Implementation plan — `gf` con expansión de macros de ruta en `.tex`

> **Estado: SHIPPED** — `088dfe8` (`tex_macros.lua`), `84c5895` (wrapper `includeexpr`),
> `a7ac37a` (cableado + 2 fixes). Registrado 2026-09-10
> (`tasks/audit/2026-09-10-tasks-and-primer-audit.md` C).

Request: (ninguno todavía — nace de esta sesión)
ADR: no requiere ADR (feature aditiva de plugin Neovim, sin contrato CLI/DB)
Methodology: TDD (RED→GREEN→REFACTOR) con plenary, reviewer-esquema, sin migración.

---

## Verified anchors (confirmed in code)

- **vimtex ya está instalado y activo**: `/home/luis/.local/share/nvim/lazy/vimtex/autoload/vimtex/include.vim`.
  Con `set ft=tex` el buffer queda con:
  - `includeexpr=vimtex#include#expr()`
  - `suffixesadd=.tex,.sty,.cls`
  - `include=` regex que ya cubre `\input`, `\include`, `\subfile`, `\import`,
    `\subimport`, `\inputfrom`, `\usepackage`, `\RequirePackage` y `% !TeX root`.
  - `path=.,,`
- `vimtex#include#expr()` resuelve: coincidencia exacta, `\input/\include` (+`.tex`),
  `\bibliography/\addbibresource`, `$TEXINPUTS`, y `kpsewhich`.
  **NO expande macros de usuario** — esa es exactamente la brecha.
- **Las macros de ruta reales NO viven en el buffer**:
  `share/latex/sty/SetCommands.sty:8-10`
  ```latex
  \newcommand{\FisicaDir}{/home/luis/01-U}
  \newcommand{\IMGfolder}{\FisicaDir/0000II-ImagesFigures}
  \newcommand{\EEfolder}{\FisicaDir/0000EE-ExamplesExercises}
  ```
  Son **anidadas** (`\IMGfolder` depende de `\FisicaDir`) y llegan por `\usepackage`,
  no por `\def` local. El ejemplo `\def\FSfolder{...}` del usuario es el caso fácil.
- `share/latex/templates/TNN.tex:250-251` tiene una definición **comentada** justo
  debajo de la activa (`% \newcommand{\AAfolder}{/mnt/c/...}`).
- Plugin: `nvim-plugin/lua/workflow/` — `config.lua` (schema `M.defaults`),
  `autocmds.lua` (augroup `Workflow`), `keymaps.lua` (prefix `<leader>z`),
  `init.lua`. Tests en `nvim-plugin/tests/plenary/*_spec.lua` (minimal_init.lua).
- Los `.sty` se distribuyen por symlink desde `~/.local/share/workflow/sty/`
  (= `share/latex/sty/` en el setup vivo). ADR ITEP-0005.

---

## Veredicto sobre el snippet propuesto

**La idea es correcta y vale la pena. La implementación tal cual, no.** Seis defectos:

| # | Defecto | Consecuencia |
|---|---------|--------------|
| 1 | Solo escanea el buffer actual | **Falla en el 100 % del caso real** (`\FisicaDir`, `\IMGfolder`, `\EEfolder` viven en `SetCommands.sty`) |
| 2 | Remapea `gf` | Pelea con vimtex; pierde `gF`, `[f`, `<C-w>f`, `:checkpath`, `<C-x><C-i>`, `$TEXINPUTS`, `kpsewhich`, `\bibliography`, `\subimport` |
| 3 | No filtra comentarios `%` | `TNN.tex:251` (def comentada, última en ganar) **sobrescribe** la buena |
| 4 | `repeat … until path == previous` sin tope | Bucle infinito con `\def\A{\A/x}` (auto-referencia, aunque sea por error de tipeo) |
| 5 | `gsub(vim.pesc(name), …)` sin frontera | `\FSfolder` también sustituye dentro de `\FSfolderTwo` → ruta corrupta |
| 6 | Usa la línea del cursor, no la columna | Con dos `\input` en una línea siempre gana el primero |

Menores: `[^}]*` rompe con llaves anidadas; no contempla `\providecommand` ni
`\renewcommand`; no rechaza `\newcommand{\F}[1]{…}` con argumentos (falla en silencio, aceptable).

---

## Target / design

En vez de secuestrar `gf`, **envolver `includeexpr`**. Un `FileType tex` autocmd
guarda el `includeexpr` previo (típicamente `vimtex#include#expr()`) y lo
reemplaza por `workflow.tex_paths.includeexpr()`, que:

1. Expande macros sobre `v:fname`; si el resultado es `filereadable`, lo devuelve.
2. Si no, delega en el `includeexpr` guardado (vimtex intacto: kpsewhich,
   `$TEXINPUTS`, `.bib`, `\subimport`).
3. Sin vimtex, devuelve `v:fname` (comportamiento nativo).

Beneficio: `gf`, `gF`, `[f`, `]f`, `<C-w>f`, `:checkpath` y el completado
`<C-x><C-i>` funcionan todos, gratis. Cero keymaps nuevos.

### Fuentes de macros (en orden, primera definición no comentada gana)

1. Buffer actual (cubre `\def\FSfolder{…}`).
2. `% !TeX root` / main file del proyecto vimtex (`vimtex#state` si existe).
3. Directorio de `.sty` de WorkFlow: `~/.local/share/workflow/sty/*.sty`
   (configurable, resuelto con `vim.fn.expand`), escaneado **una vez** y cacheado
   por mtime — ahí viven `\FisicaDir`/`\IMGfolder`/`\EEfolder`.

### Config nueva (`config.lua`)

```lua
tex_gf = true,                    -- activar el wrapper de includeexpr
tex_macro_sty_dirs = { "~/.local/share/workflow/sty" },
```

---

## Resolved design rules

- **`includeexpr` wrapper, no remap de `gf`**: preserva vimtex y los ~6 comandos
  que usan `includeexpr`. Es la razón principal para rechazar el snippet.
- **Stripping de comentarios**: quitar desde `%` no escapado (respetar `\%`) antes de matchear.
- **Primera definición gana** (no la última): en LaTeX `\newcommand` duplicado es error;
  la primera es la efectiva.
- **Expansión con tope**: máx. 16 iteraciones de punto fijo; si no converge, se
  aborta y se delega en vimtex (nunca colgar el editor).
- **Frontera de control-word**: sustituir con `%f[%A]` tras el nombre (o expandir de
  nombre más largo a más corto) para que `\FSfolder` no muerda `\FSfolderTwo`.
- **Patrones soportados**: `\def\F{…}`, `\newcommand{\F}{…}`, `\newcommand\F{…}`,
  `\providecommand`, `\renewcommand`. Macros con argumentos (`[1]`) se ignoran.
- **Cache**: tabla por `sty_dir` invalidada por mtime; el buffer se re-escanea siempre.
- **Sin `.tex` forzado**: `suffixesadd` de vimtex ya lo hace; no reimplementarlo.

---

## Phases

### P0 — módulo puro `lua/workflow/tex_macros.lua` (TDD, sin Neovim API)
`strip_comments(line)`, `scan_macros(lines) -> {["\\F"]=value}`, `expand(str, macros)`.
Tests: `tests/plenary/tex_macros_spec.lua` — def comentada ignorada, anidamiento
`\IMGfolder`→`\FisicaDir`, auto-referencia no cuelga, prefijo `\FSfolderTwo` intacto,
las 5 formas de definición, primera-gana.

### P1 — `lua/workflow/tex_paths.lua`
`collect_macros(bufnr)` (buffer + sty dirs con cache mtime) y `includeexpr()`
con delegación al `includeexpr` previo. Test con fixtures reales en `tests/outputs/tex_gf/`.

### P2 — cableado
`config.lua` (2 llaves nuevas), `autocmds.lua` (`FileType tex` → guardar y envolver
`vim.bo.includeexpr`), doc en `nvim-plugin/doc/workflow.txt` y `ARCHITECTURE.md`.

### P3 — verificación manual
`gf` sobre `\input{\FSfolder/…}` (buffer), sobre `\includegraphics{\IMGfolder/…}`
(sty), y regresión: `gf` sobre `\usepackage{amsmath}` sigue yendo por kpsewhich.

---

## Riesgos

- Si vimtex cambia `includeexpr` después de nuestro autocmd, el wrapper se pierde →
  registrar el autocmd con `pattern="tex"` y prioridad posterior; verificar en P3.
- `\FisicaDir` es una ruta absoluta hardcodeada en `SetCommands.sty`; si migra a
  `\WORKFLOW_WORKSPACE_ROOT` la expansión textual deja de resolver. [UNCLEAR] no bloquea.
