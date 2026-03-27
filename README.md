# WorkFlow

[![Python package](https://github.com/LuisUma92/WorkFlow/actions/workflows/python-package.yml/badge.svg)](https://github.com/LuisUma92/WorkFlow/actions/workflows/python-package.yml)

Toolkit CLI en Python para gestionar proyectos LaTeX y un sistema unificado de Zettelkasten para escritura academica (tesis, cursos, ejercicios). Integra notas en Markdown, renderizado LaTeX, diagramas TikZ, banco de ejercicios, exportacion a Moodle, y gestion bibliografica a traves de multiples instituciones (UCR, UFide, UCIMED).

**Wiki**: [Getting Started](docs/wiki/Getting-Started.md) | [Zettelkasten](docs/wiki/Zettelkasten-Notes.md) | [Exercises](docs/wiki/Exercise-Workflow.md) | [Lectures](docs/wiki/Lectures-Workflow.md) | [Graph](docs/wiki/Knowledge-Graph.md) | [Macros](docs/wiki/LaTeX-Macros.md) | [Architecture](docs/wiki/Architecture.md)

## Instalacion

```bash
# Con uv (recomendado)
uv sync

# O con pip (editable)
pip install -e .
```

### Dependencias

`appdirs`, `bibtexparser`, `click`, `pyyaml`, `sqlalchemy`

Opcional: `networkx` (para clustering en el grafo de conocimiento)

Python >= 3.12

## Vista general

WorkFlow organiza el trabajo academico en torno a seis pilares:

1. **Zettelkasten** (`workflow notes`) — Notas en Markdown (Obsidian-compatible), inicializacion de workspace, enlaces wiki
2. **Proyectos LaTeX** (`inittex`, `relink`) — Scaffolding y gestion de directorios para cursos y tesis
3. **Banco de ejercicios** (`workflow exercise`) — Parseo, indexacion, generacion, seleccion y exportacion de ejercicios
4. **Gestion de cursos** (`workflow lectures`) — Escaneo de archivos, enlaces cruzados, construccion de evaluaciones
5. **Grafo de conocimiento** (`workflow graph`) — Analisis de conexiones entre notas, ejercicios, bibliografia y cursos
6. **Pipeline TikZ** (`workflow tikz`) — Compilacion incremental de diagramas standalone a PDF/SVG

## Arquitectura

### Base de datos hibrida

WorkFlow usa una arquitectura de dos bases de datos SQLite:

- **Global** (`~/.local/share/workflow/workflow.db`) — Datos de referencia: instituciones, cursos, libros, ejercicios, evaluaciones, bibliografia
- **Local** (`<proyecto>/slipbox.db`) — Notas, enlaces, etiquetas y citas por proyecto

SQLAlchemy 2.0 con `Mapped[]` es el unico ORM. El acceso a datos pasa por interfaces Protocol (`workflow.db.repos.protocols`).

### Principios clave

- **Archivo como fuente de verdad**: Los archivos `.tex` contienen el contenido de ejercicios y notas. La DB almacena solo metadatos e indices (ADR-0010)
- **Markdown como capa canonica**: Las notas se escriben en Markdown con YAML frontmatter; LaTeX es formato derivado (ADR-0002)
- **Extender, nunca reemplazar**: Los macros de ejercicio (`\question`, `\qpart`, `\pts`) extienden los existentes en `shared/latex/sty/` (ADR-0005). `\zlink` es alias de `\excref` (ADR-0014)
- **Normalizacion LaTeX**: Macros personalizados se expanden a LaTeX estandar antes de exportar a Moodle (ADR-0012)
- **Layout XDG**: Configuracion en `~/.config/workflow/`, datos en `~/.local/share/workflow/` (ADR-0008)
- **Inmutabilidad**: Todos los tipos de dominio usan `@dataclass(frozen=True)` con `tuple` en lugar de `list`

## Comandos CLI

### Entry points directos

| Comando    | Modulo              | Descripcion                             |
| ---------- | ------------------- | --------------------------------------- |
| `workflow` | `main:cli`          | CLI principal (notes, exercise, lectures, graph, tikz, validate) |
| `inittex`  | `itep.create:cli`   | Crear o clonar un proyecto LaTeX        |
| `relink`   | `itep.links:cli`    | Recrear symlinks desde la base de datos |
| `cleta`    | `lectkit.cleta:cli` | Limpiar archivos auxiliares de TeX      |

### workflow notes — Zettelkasten

Inicializacion del workspace y gestion de notas en Markdown (Obsidian-compatible).

```bash
# Inicializar workspace con directorios de notas por proyecto
workflow notes init ~/Documents/01-U/
```

Crea la estructura:

```
~/Documents/01-U/
  .workflow/config.yaml              # Marcador de workspace
  00ZZ-Vault/                        # Zona de triage global
    inbox/                           # Notas fugaces sin asignar
    templates/                       # Templates: permanent.md, literature.md, fleeting.md
  10MC-ClassicalMechanics/
    notes/                           # Vault Obsidian por proyecto
    slipbox.db                       # DB local de notas
  40EM-Electromagnetism/
    notes/
    slipbox.db
```

Cada `MainTopic` (10MC, 40EM, 50MQ) funciona como:
- Un **GeneralProject** de ITeP (salida LaTeX)
- Un **vault Zettelkasten** (notas Markdown que alimentan los documentos)

#### Macros Zettelkasten

| Macro | Archivo | Uso |
|-------|---------|-----|
| `\zlink{id}` | SetZettelkasten.sty | Referencia cruzada entre notas (alias de `\excref`) |
| `\zlabel{id}` | SetZettelkasten.sty | Ancla ligera para un punto de referencia |
| `\begin{zettelnote}{id}{Titulo}` | SetZettelkasten.sty | Entorno semantico de nota |

En Markdown, las referencias usan wiki-links: `[[20260326-gauss-law]]` o `[[id|texto]]`.
El pipeline Pandoc convierte `[[id]]` → `\zlink{id}` al compilar a LaTeX.

#### Tipos de nota

| Tipo | Uso | Formato frontmatter |
|------|-----|---------------------|
| `permanent` | Ideas propias, conceptos consolidados | `type: permanent` |
| `literature` | Notas sobre lecturas y articulos | `type: literature`, `bibkey: serway2019` |
| `fleeting` | Ideas rapidas, pendientes de procesar | `type: fleeting` |

### workflow exercise — Banco de ejercicios

Gestion completa del banco de ejercicios: parseo de archivos `.tex`, sincronizacion con la DB, generacion de placeholders, seleccion por taxonomia, ensamblaje de examenes y exportacion a Moodle XML.

```bash
# Parsear archivos .tex y mostrar estructura
workflow exercise parse ruta/a/ejercicios/

# Listar ejercicios en la DB con filtros
workflow exercise list --status complete --difficulty medium --type multichoice

# Sincronizar archivos .tex con la DB (crear/actualizar registros)
workflow exercise sync ruta/a/ejercicios/

# Limpiar registros huerfanos (archivos borrados)
workflow exercise gc --yes

# Exportar a Moodle XML
workflow exercise export-moodle ruta/ --output quiz.xml --status complete --tag physics

# Crear un archivo placeholder de ejercicio
workflow exercise create mi-ejercicio-001 -d ruta/salida/ --type multichoice --tag physics

# Crear multiples placeholders desde un rango de libro
workflow exercise create-range -d ruta/salida/ --book serway --chapter 1 --first 1 --last 20

# Construir un examen seleccionando del banco
workflow exercise build-exam -l "Usar-Aplicar" -n 5 -p 10 --title "Parcial 1" -o examen.tex
```

#### Flujo de trabajo tipico de ejercicios

```
1. Crear placeholders     →  workflow exercise create-range ...
2. Editar archivos .tex   →  (editor de texto / Neovim)
3. Sincronizar con DB     →  workflow exercise sync ruta/
4. Verificar estado       →  workflow exercise list --status complete
5. Construir examen       →  workflow exercise build-exam ...
6. Exportar a Moodle      →  workflow exercise export-moodle ruta/ -o quiz.xml
```

#### Formato de archivo de ejercicio

Cada ejercicio es un archivo `.tex` con metadatos YAML en comentarios:

```latex
% ---
% id: phys-gauss-001
% type: multichoice
% difficulty: medium
% taxonomy_level: Usar-Aplicar
% taxonomy_domain: Procedimiento Mental
% tags: [physics, electrostatics]
% status: complete
% ---
\ifthenelse{\boolean{main}}{
  \exa[1]{5} % \cite{serway}
}{
}
\question{
  Dado un campo electrico $\vec{E}$, calcule el flujo.
  \begin{enumerate}[a)]
    \qpart{\rightoption \pts{5} Opcion correcta}{
      Solucion detallada aqui.
    }
    \qpart{\pts{5} Opcion incorrecta}{
      Por que esta opcion es incorrecta.
    }
  \end{enumerate}
}{
  Solucion general del ejercicio.
}
\qfeedback{Retroalimentacion despues de contestar.}
```

#### Exportacion a Moodle XML

La exportacion normaliza automaticamente los macros personalizados:

- `\vc{E}` se expande a `\vec{\mathbf{E}}`
- `\scrp{enc}` se expande a `_{\mbox{\scriptsize{enc}}}`
- `$...$` se convierte a `\(...\)` (MathJax compatible)
- Colores (`\textcolor{red}{texto}`) se eliminan, conservando el contenido
- Imagenes se codifican en base64 e incrustan en el XML

Esto asegura que el XML funcione en **cualquier** instancia de Moodle, sin depender de configuracion institucional de MathJax.

### workflow lectures — Gestion de cursos

Herramientas para integrar proyectos de cursos con el sistema de notas y el banco de ejercicios.

```bash
# Escanear directorio de curso y registrar archivos .tex como notas
workflow lectures scan ruta/al/curso/ --project-root .

# Dividir un archivo de notas en subarchivos (marcadores %>)
workflow lectures split archivo.tex --output-dir tex/

# Escanear referencias (\cite, \ref, \label) y actualizar enlaces en DB
workflow lectures link ruta/al/curso/ --project-root .

# Construir evaluacion desde el banco de ejercicios
workflow lectures build-eval -l "Usar-Aplicar" -n 5 -p 10 --title "Parcial 1" -o examen.tex --moodle
```

#### Flujo de trabajo tipico de curso

```
1. Crear proyecto         →  inittex (seleccionar lecture, institucion, curso)
2. Escribir notas/clases  →  Editar archivos .tex en lect/tex/
3. Registrar notas        →  workflow lectures scan ruta/
4. Construir enlaces      →  workflow lectures link ruta/
5. Preparar evaluacion    →  workflow lectures build-eval ...
6. Exportar a Moodle      →  workflow exercise export-moodle ...
```

### workflow graph — Grafo de conocimiento

Analiza las conexiones entre todos los elementos del sistema: notas, ejercicios, bibliografia, contenidos y cursos.

```bash
# Ver estadisticas del grafo
workflow graph stats --project .

# Encontrar nodos huerfanos (sin conexiones)
workflow graph orphans --type note --project .

# Exportar a Graphviz DOT
workflow graph export-dot --project . -o grafo.dot --highlight-orphans

# Exportar a TikZ para LaTeX
workflow graph export-tikz --project . -o grafo.tex --standalone

# Ver clusters tematicos (requiere networkx)
workflow graph clusters --project .

# Ver vecinos de un nodo especifico
workflow graph neighbors note:42 --depth 2 --project .
```

#### Fuentes del grafo

El grafo unifica datos de ambas bases de datos:

| Fuente | Tipo de nodo | Tipo de arista |
|--------|-------------|----------------|
| Notas (slipbox.db) | `note` | `link` (nota→nota via Label) |
| Citas (slipbox.db) | — | `citation` (nota→bib_entry) |
| Ejercicios (workflow.db) | `exercise` | `exercise_content`, `exercise_book` |
| Contenidos (workflow.db) | `content`, `topic` | `bib_content`, `course_content` |
| Bibliografia (workflow.db) | `bib_entry` | — |
| Cursos (workflow.db) | `course` | — |

### workflow tikz — Pipeline de diagramas

Compilacion incremental de diagramas TikZ standalone a PDF y SVG.

```bash
# Compilar todos los diagramas en assets/tikz/
workflow tikz build --assets-dir assets/tikz --output-dir assets/figures

# Listar fuentes TikZ
workflow tikz list --assets-dir assets/tikz

# Limpiar artefactos compilados
workflow tikz clean --output-dir assets/figures
```

### workflow validate — Validacion de metadatos

Valida la estructura de frontmatter YAML en notas Markdown y ejercicios LaTeX.

```bash
# Validar notas
workflow validate notes ruta/a/notas/

# Validar ejercicios
workflow validate exercises ruta/a/ejercicios/
```

## ITeP — Init TeX Project

Modulo para crear y administrar proyectos LaTeX. Usa la base de datos global como fuente de verdad para instituciones, cursos, temas y evaluaciones.

```bash
# Crear un proyecto nuevo (interactivo)
inittex

# Clonar un ciclo existente
inittex --clone 42

# Recrear symlinks
relink
```

### Estructura de proyecto lecture

```
UCR-FS0121/
  config.yaml          # Puntero a DB: {project_type: lecture, project_id: 42}
  admin/               # Documentos administrativos
  eval/                # Evaluaciones
    config/ img/ tex/
      001-Cinematica/
  lect/                # Material de clase
    bib/ config/ img/ svg/
    tex/
      001-Cinematica/
```

### Estructura de proyecto general

```
10MC-MecanicaClasica/
  config.yaml
  bib/ config/ img/ projects/
  tex/
    000-0-Glossaries/
    000-1-Summaries/
    001-Cinematica/
```

## Esquema de base de datos

### Base global (workflow.db) — 4 capas

**Capa 1 — Datos de referencia:**
- `institution` — UCR (18 sem), UFide (15 cuatri), UCIMED (24 sem)
- `main_topic` — Temas principales con codigo Dewey

**Capa 2 — Entidades maestras:**
- `bib_entry`, `bib_author` — Bibliografia completa (40+ campos BibLaTeX)
- `topic`, `content`, `bib_content` — Contenido academico

**Capa 3 — Templates de curso:**
- `course`, `course_content` — Cursos con contenidos por semana
- `evaluation_template`, `item`, `evaluation_item` — Evaluaciones con taxonomia Bloom
- `exercise`, `exercise_option` — Indice de metadatos del banco de ejercicios

**Capa 4 — Instancias:**
- `lecture_instance` — Curso en ciclo/anno concreto
- `general_project` — Proyecto asociado a un tema principal

### Base local (slipbox.db) — por proyecto

- `note` — Archivo registrado con referencia unica
- `citation` — Citas bibliograficas en notas
- `label`, `link` — Etiquetas y enlaces entre notas
- `tag`, `note_tag` — Sistema de etiquetas M2M

## Macros LaTeX

Los macros de ejercicio se definen en `shared/sty/`:

| Macro | Archivo | Uso |
|-------|---------|-----|
| `\question{stem}{solution}` | SetCommands.sty | Pregunta con stem y solucion |
| `\qpart{instruccion}{solucion}` | SetCommands.sty | Parte de pregunta |
| `\pts{n}` | PartialCommands.sty | Puntos asignados |
| `\rightoption` | PartialCommands.sty | Marca opcion correcta |
| `\exa[ch]{num}` | SetCommands.sty | Referencia a ejercicio de libro |
| `\qfeedback{texto}` | SetExercises.sty | Retroalimentacion (para Moodle) |
| `\qdiagram{id}` | SetExercises.sty | Referencia a diagrama TikZ |

### Normalizacion para Moodle

Los macros personalizados se expanden a LaTeX estandar antes de exportar:

| Original | Expandido |
|----------|-----------|
| `\vc{E}` | `\vec{\mathbf{E}}` |
| `\scrp{enc}` | `_{\mbox{\scriptsize{enc}}}` |
| `\ncm{2}{H}` | `^{2}\text{H}` |
| `\pts{5}` | `(5 pts.)` |
| `\textcolor{red}{texto}` | `texto` |
| `$x^2$` | `\(x^2\)` |

## Decisiones de arquitectura (ADRs)

Documentadas en `docs/ADR/` (ver [INDEX.md](docs/ADR/INDEX.md)):

| ADR  | Titulo | Estado |
|------|--------|--------|
| 0001 | Capa semantica de notas Zettelkasten | Aceptado |
| 0002 | Markdown como capa canonica de conocimiento | Aceptado |
| 0003 | Base de datos hibrida (global + local) | Aceptado |
| 0004 | SQLAlchemy 2.0 como unico ORM | Aceptado |
| 0005 | DSL de ejercicios extiende macros existentes | Aceptado |
| 0006 | Pipeline de activos TikZ standalone | Aceptado |
| 0007 | Modulo de DB compartido con API de repositorio | Aceptado |
| 0008 | Layout de directorios XDG | Aceptado |
| 0009 | Frontera del modulo de ejercicios + parsing LaTeX compartido | Aceptado |
| 0010 | Persistencia: archivo como verdad, DB como indice | Aceptado |
| 0011 | Parser LaTeX con extraccion por conteo de llaves | Aceptado |
| 0012 | Exportacion Moodle XML con normalizacion LaTeX | Aceptado |
| 0013 | Consolidacion: sesiones, desacople, CLI split | Aceptado |
| 0014 | Implementacion Zettelkasten: macros, modelo Note, workspace init | Aceptado |
| LZK-0000..0004 | Motor LaTeXZettel (5 ADRs: arquitectura, RPC, Pandoc, refs, DI) | Aceptado |
| PRISMA-0000..0004 | PRISMAreview (5 ADRs: arquitectura, router, import, screening, modelo) | Aceptado |

## Estructura del modulo

```
src/
  workflow/
    db/           # Base de datos unificada (SQLAlchemy 2.0, repos Protocol)
    notes/        # Zettelkasten: inicializacion de workspace, gestion de notas
    exercise/     # Banco de ejercicios (parser, moodle, generator, selector, exam_builder, service)
    lecture/      # Integracion de cursos (scanner, splitter, linker, eval_builder)
    graph/        # Grafo de conocimiento (dominio, collectors, analisis, DOT, TikZ, clustering)
    latex/        # Parsing compartido (llaves, comentarios, normalizacion)
    tikz/         # Pipeline de diagramas TikZ
    validation/   # Validacion de frontmatter
  itep/           # Scaffolding de proyectos LaTeX
  latexzettel/    # Motor Zettelkasten + servidor JSONL/RPC (24 rutas) + cliente Neovim
  lectkit/        # Utilidades (cleta)
  PRISMAreview/   # App web Django para revision sistematica PRISMA
  appfunc/        # Utilidades compartidas
shared/
  latex/
    sty/          # 18 archivos de estilo LaTeX (incl. SetZettelkasten.sty)
    cls/          # texnote.cls y preambulos
    templates/    # Templates para notas, ejercicios, clases
    pandoc/       # Pipeline Pandoc: filter.lua, template.tex, preprocess.py
```

## Tests

```bash
# Todos los tests (484 tests)
uv run pytest

# Solo un modulo
uv run pytest tests/workflow/exercise/
uv run pytest tests/workflow/graph/
uv run pytest tests/workflow/lecture/
uv run pytest tests/workflow/notes/

# Con cobertura
uv run pytest --cov=src/workflow --cov-report=term-missing
```

## Lint

```bash
# Errores criticos (CI gate)
uv run flake8 src/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics

# Completo (informativo)
uv run flake8 src/ tests/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

## CI

GitHub Actions en push/PR a `master`. Tests en Python 3.12, 3.13, 3.14.
