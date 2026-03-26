# LaTeX Macros Reference

Referencia de los macros personalizados definidos en `shared/sty/`. Estos archivos se distribuyen via symlinks a cada proyecto.

Cada macro esta documentado en su ADR correspondiente (ver enlaces en cada seccion).

## Macros de ejercicios

Definidos en `SetCommands.sty` y `PartialCommands.sty` ([ADR STY-0002](../ADR/STY-0002-set-commands.md), [ADR STY-0003](../ADR/STY-0003-partial-commands.md), [ADR-0005](../ADR/0005-exercise-dsl-extends-macros.md)).

### Estructura de pregunta

| Macro | Argumentos | Uso |
|-------|-----------|-----|
| `\question{stem}{solution}` | 2 | Pregunta principal. 1er arg: enunciado. 2do arg: solucion (se muestra si `\boolean{solutions}` es true) |
| `\qpart{instruccion}{solucion}` | 2 | Parte de una pregunta. 1er arg: instruccion especifica (puede incluir puntos). 2do arg: solucion |
| `\exa[cap]{num}` | 1+opt | Referencia a ejercicio de libro. [cap] opcional = capitulo |
| `\exacs{num}` | 1 | Variante con numeracion capitulo.seccion.ejemplo |

### Puntos y opciones

| Macro | Argumentos | Resultado |
|-------|-----------|-----------|
| `\pts{n}` | 1 (+opt) | `(n pts.)` — asigna puntos. Acepta [add] opcional |
| `\upt` | 0 (+opt) | `(1 pt.)` |
| `\ptscu{n}` | 1 | `(n pts. c/u.)` — puntos cada uno |
| `\uptcu` | 0 | `(1 pt. c/u.)` |
| `\rightoption` | 0 | Marca la siguiente `\qpart` como opcion correcta |
| `\inputline` | 0 | Linea para rellenar (______) |
| `\completeline{texto}` | 1 | Muestra la respuesta en la linea |

### Macros para CLI (SetExercises.sty)

| Macro | Argumentos | Uso |
|-------|-----------|-----|
| `\qfeedback{texto}` | 1 | Retroalimentacion general. Se muestra en modo soluciones. En Moodle: `<generalfeedback>` |
| `\qdiagram{id}` | 1 | Referencia a diagrama TikZ del pipeline (Phase 2). No-op en LaTeX |

---

## Macros de fisica

### Vectores y notacion ([ADR STY-0005](../ADR/STY-0005-set-symbols.md))

| Macro | Argumentos | Resultado | Descripcion |
|-------|-----------|-----------|-------------|
| `\vc{X}` | 1 | `\vec{\symbf{X}}` | Vector en negrita con flecha |
| `\vi` | 0 | `\hat{\imath}` | Vector unitario i |
| `\vj` | 0 | `\hat{\jmath}` | Vector unitario j |
| `\vk` | 0 | `\hat{k}` | Vector unitario k |
| `\scrp{X}` | 1 | `_{\mbox{\scriptsize{X}}}` | Subindice en tamano script |

### Notacion nuclear

| Macro | Argumentos | Resultado | Contexto |
|-------|-----------|-----------|----------|
| `\nc{A}{X}` | 2 | `$^{A}$X` | Notacion nuclear (modo texto) |
| `\ncm{A}{X}` | 2 | `^{A}\text{X}` | Notacion nuclear (modo math) |

### Constantes fisicas ([ADR STY-0011](../ADR/STY-0011-set-constant.md))

| Macro | Resultado | Constante |
|-------|-----------|-----------|
| `\vcs` | `$c$` | Velocidad de la luz |
| `\hps` | `$h$` | Constante de Planck |
| `\hbs` | `$\hbar$` | Constante de Planck reducida |
| `\ecs` | `$e$` | Carga elemental |
| `\kbs` | `$k_{\scriptsize B}$` | Constante de Boltzmann |
| `\nas` | `$N_{\scriptsize A}$` | Numero de Avogadro |

---

## Macros de formato

### General ([ADR STY-0002](../ADR/STY-0002-set-commands.md))

| Macro | Argumentos | Resultado |
|-------|-----------|-----------|
| `\then` | 0 | `=` (operador de implicacion) |
| `\ifpause` | 0 | Vacio (placeholder para beamer) |
| `\mailto{email}` | 1 | `\href{mailto:email}{email}` |
| `\minitab{cols}{contenido}` | 2 | Mini-tabla inline |

### Unidades SI ([ADR STY-0004](../ADR/STY-0004-set-units.md))

Usa el paquete `siunitx`. Los macros estan en `SetUnits.sty`.

### Colores ([ADR STY-0006](../ADR/STY-0006-colors.md))

Colores definidos por institucion en archivos separados:
- `colors-UCR.sty`
- `colors-Ufide.sty`
- `colors-UCIMED.sty`
- `ColorsLight.sty` (colores claros compartidos)

### Pagina centrada ([ADR STY-0010](../ADR/STY-0010-centred-page.md))

```latex
\CentredPage[primary-color=blue]{Titulo principal}[Subtitulo]
\CentredPage*[align=raggedright]{Texto}  % mantiene estilo de pagina
```

Configuracion global:
```latex
\CentredPageSetup{primary-font=\Huge\bfseries, line-spread=1.5}
```

---

## Normalizacion para Moodle ([ADR-0012](../ADR/0012-moodle-xml-export-mapping.md))

Cuando se exporta a Moodle XML, los macros personalizados se expanden automaticamente a LaTeX estandar que cualquier MathJax puede renderizar:

| Original | Expandido |
|----------|-----------|
| `\vc{E}` | `\vec{\mathbf{E}}` |
| `\scrp{enc}` | `_{\mbox{\scriptsize{enc}}}` |
| `\nc{2}{H}` | `$^{2}$H` |
| `\ncm{2}{H}` | `^{2}\text{H}` |
| `\then` | `=` |
| `\pts{5}` | `(5 pts.)` |
| `\upt` | `(1 pt.)` |
| `\ptscu{3}` | `(3 pts. c/u.)` |
| `\rightoption` | *(eliminado)* |
| `\textcolor{color}{texto}` | `texto` |
| `\symbf{X}` | `\mathbf{X}` |
| `$...$` | `\(...\)` |
| `$$...$$` | `\[...\]` |

La normalizacion es multi-pasada (hasta 10 iteraciones) para resolver macros anidados como `\vc{\scrp{x}}`.

El mapa de normalizacion esta en `src/workflow/latex/normalize.py` (`DEFAULT_MACRO_MAP`).

---

## Archivos .sty

| Archivo | ADR | Contenido principal |
|---------|-----|---------------------|
| SetFormat.sty | [STY-0000](../ADR/STY-0000-set-format.md) | Carga de paquetes, setup de documento |
| SetLoyaut.sty | [STY-0001](../ADR/STY-0001-set-loyaut.md) | Geometria de pagina, entornos |
| SetCommands.sty | [STY-0002](../ADR/STY-0002-set-commands.md) | Macros core: \question, \exa, \vc, CentredPage |
| PartialCommands.sty | [STY-0003](../ADR/STY-0003-partial-commands.md) | Macros de examen: \pts, \rightoption, tracking |
| SetUnits.sty | [STY-0004](../ADR/STY-0004-set-units.md) | Unidades SI (siunitx) |
| SetSymbols.sty | [STY-0005](../ADR/STY-0005-set-symbols.md) | Simbolos de fisica, vectores |
| colors-*.sty | [STY-0006](../ADR/STY-0006-colors.md) | Esquemas de color por institucion |
| VectorPGF.sty | [STY-0007](../ADR/STY-0007-vector-pgf.md) | Macros TikZ 3D |
| SetProfiles.sty | [STY-0008](../ADR/STY-0008-set-profiles.md) | Metadata institucional, instrucciones PPI |
| SetHeaders.sty | [STY-0009](../ADR/STY-0009-set-headers.md) | Headers/footers por institucion |
| SetExercises.sty | — | Macros para CLI: \qfeedback, \qdiagram |
| SetConstant.sty | [STY-0011](../ADR/STY-0011-set-constant.md) | Constantes fisicas |
