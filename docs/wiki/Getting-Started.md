---
id: 
parent: Wiki
title: Getting Started
aliases: []
type: permanent
created: 
tags: []
concepts: []
references: []
exercises: []
images: []
---

# Getting Started

Esta guia cubre la instalacion, creacion de tu primer proyecto, y como agregar notas y ejercicios.

## Requisitos

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) (recomendado) o pip
- LaTeX (texlive o similar) para compilar documentos
- Opcional: `networkx` para clustering en el grafo de conocimiento

## Instalacion

```bash
git clone git@github.com:LuisUma92/WorkFlow.git
cd WorkFlow

# Con uv (recomendado)
uv sync

# O con pip
pip install -e .
```

Verifica la instalacion:

```bash
workflow --help
```

Deberias ver **18 grupos de comandos**:

| Grupo | Proposito | Guia |
|-------|-----------|------|
| `notes` | Notas Zettelkasten: crear, capturar, promover, buscar, sincronizar | [Zettelkasten Notes](Zettelkasten-Notes.md) |
| `vault` | Info/validacion/migracion del vault unificado (ITEP-0011) | [Zettelkasten Notes](Zettelkasten-Notes.md) |
| `concept` | Taxonomia de conceptos (slug-only, ITEP-0012) | [Concept Skyfolding](Concept-Skyfolding.md) |
| `import` | Import masivo YAML: DisciplineArea → Topic → Content → Concept | [Concept Skyfolding](Concept-Skyfolding.md) |
| `topic` | CRUD de Topic (rooted en DisciplineArea) | [Architecture](Architecture.md) |
| `content` | CRUD de Content + vinculos bibliograficos (`link-bib`) | [Architecture](Architecture.md) |
| `exercise` | Banco de ejercicios: parse, sync, build-exam, export-moodle | [Exercise Workflow](Exercise-Workflow.md) |
| `exam` | Scaffolding y validacion de examenes Moodle XML (legacy + weekly) | [Exercise Workflow](Exercise-Workflow.md) |
| `lectures` | Escaneo de cursos, enlaces cruzados, split de notas grandes | [Lectures Workflow](Lectures-Workflow.md) |
| `graph` | Grafo de conocimiento: stats, orphans, export-dot/tikz, clusters, resume/trace | [Knowledge Graph](Knowledge-Graph.md) |
| `evaluations` | Plantillas de evaluacion | [Evaluation CLI](Evaluation-CLI.md) |
| `item` | Items taxonomicos (Bloom) | [Evaluation CLI](Evaluation-CLI.md) |
| `course` | Cursos, practicas (`add-practice`) | [Evaluation CLI](Evaluation-CLI.md) |
| `prisma` | Revision sistematica: bibliografia, keywords, screening | [PRISMA Review](PRISMA-Review.md) |
| `validate` | Lint de frontmatter de notas y metadatos/unidades de ejercicios | [Zettelkasten Notes](Zettelkasten-Notes.md) |
| `db` | Migraciones de esquema, disciplinas, import-codes | [Architecture](Architecture.md) |
| `project` | Reportes de maduracion de proyecto | [Architecture](Architecture.md) |
| `tikz` | Pipeline de diagramas TikZ standalone | [LaTeX Macros](LaTeX-Macros.md) |

## Estructura del sistema

WorkFlow centraliza el conocimiento en el **vault unificado** (ITEP-0011): todas las notas, citas, etiquetas, conceptos y ejercicios viven en una unica base de datos global (`GlobalBase`), no en una DB por proyecto.

```
~/.local/share/workflow/workflow.db      # GlobalBase: notas, citas, conceptos, ejercicios,
                                          #   instituciones, cursos, libros
~/01-U/0000AV-Vault/                     # Vault: archivos .md en notes/{permanent,literature,fleeting}
<proyecto>/slipbox.db                    # LocalBase: solo ProjectNote (ideas/hipotesis) y PrismaDecision
```

La configuracion vive en `~/.config/workflow/config.yaml`:

```yaml
vault_path: ~/01-U/0000AV-Vault
default_institution: UCR
default_timezone: America/Costa_Rica
```

`WORKFLOW_VAULT_ROOT` y `WORKFLOW_DATA_DIR` (env) tienen prioridad sobre `config.yaml`, que a su vez tiene prioridad sobre el default. Verifica el vault resuelto con:

```bash
workflow vault info
```

Los archivos de estilo LaTeX se comparten via symlinks:

```
~/.local/share/workflow/sty/           # 18 archivos .sty
```

---

## Quickstart: tu primera nota

No necesitas un proyecto LaTeX para empezar a usar el vault. El flujo minimo es: instalar → configurar → capturar → buscar.

```bash
# 1. Instalar (ver arriba)
uv sync

# 2. Configurar el vault (opcional si usas el default)
mkdir -p ~/.config/workflow
cat > ~/.config/workflow/config.yaml <<'EOF'
vault_path: ~/01-U/0000AV-Vault
EOF

# 3. Capturar una idea (crea el .md + la registra en la DB en un solo paso)
workflow notes capture --title "Ley de Gauss" --type fleeting --tags physics,electrostatics

# 4. Buscarla (full-text, FTS5)
workflow notes search "gauss"
```

`notes capture` es el atajo recomendado para el dia a dia — ver [Zettelkasten Notes](Zettelkasten-Notes.md#capturar-crear-y-promover-notas) para el resto del ciclo (`new`, `create` desde bibkey, `promote`, `link`, `sync`).

---

## Crear tu primer proyecto

### Proyecto de curso (lecture)

```bash
inittex
```

El flujo interactivo:

1. Seleccionar tipo: **lecture**
2. Seleccionar institucion: UCR, UFide, o UCIMED
3. Seleccionar o crear un curso (ej: FS0121 - Fisica General I)
4. Ingresar anno, ciclo, y primer lunes del semestre
5. Se crea la estructura de directorios y el registro en la DB

Resultado:

```
UCR-FS0121/
  config.yaml              # Puntero a la DB: {project_type: lecture, project_id: 42}
  admin/                   # Documentos administrativos
  eval/                    # Evaluaciones
    config/ img/ tex/
      001-Cinematica/      # Subdirectorio por tema
  lect/                    # Material de clase
    bib/ config/ img/ svg/
    tex/
      001-Cinematica/      # Subdirectorio por tema
```

### Proyecto general (tesis, investigacion)

```bash
inittex    # seleccionar "general"
```

Resultado:

```
10MC-MecanicaClasica/
  config.yaml
  bib/ config/ img/ projects/
  tex/
    000-0-Glossaries/
    001-Cinematica/
```

### Restaurar symlinks

Si los symlinks se rompen (mover proyecto, nuevo equipo):

```bash
cd UCR-FS0121/
relink
```

---

## Agregar notas

### 1. Escribir el archivo .tex

Crea tu archivo en el directorio correspondiente del proyecto:

```bash
# Para un curso
vim lect/tex/001-Cinematica/posicion.tex

# Para un proyecto general
vim tex/001-Cinematica/posicion.tex
```

Usa los macros de `shared/sty/` normalmente:

```latex
\section{Posicion y desplazamiento}

La posicion se describe con el vector $\vc{r}$.
Para un movimiento unidimensional, $x(t)$.

Ver ecuacion \ref{eq:posicion} y \cite{serway2019}.

\label{eq:posicion}
\begin{equation}
  \vc{r} = x\vi + y\vj + z\vk
\end{equation}
```

### 2. Registrar notas en la base de datos global

```bash
workflow lectures scan /ruta/al/proyecto/
```

Esto descubre todos los `.tex` en `lect/tex/` y `eval/tex/`, y registra cada uno como `Note` en el **GlobalBase** (`workflow.db`), no en una DB por proyecto — ITEP-0011 P3 unifico esta capa. Es idempotente — ejecutar de nuevo no duplica registros. `--project-root` sigue existiendo en la firma del comando pero esta **reservado para ITEP-0011 P5** (capa de notas por proyecto) y actualmente se ignora — no hace falta pasarlo.

```
Discovered: 15 .tex file(s)
  Registered (new): 15
  Already registered: 0
```

### 3. Construir enlaces cruzados

```bash
workflow lectures link /ruta/al/proyecto/
```

Escanea los archivos registrados buscando:
- `\cite{clave}` — registra citas bibliograficas
- `\label{nombre}` — registra etiquetas
- `\ref{nombre}` / `\eqref{nombre}` — registra enlaces entre notas

```
Processed: 15 files
  References found: 42
  Citations found: 18
  Links created: 24
```

### 4. Dividir archivos grandes de notas

Si escribes notas con marcadores `%>`:

```latex
%>tex/C1/intro.tex
\section{Introduccion}
Contenido de la introduccion...

%>tex/C1/metodos.tex
\section{Metodos}
Descripcion de los metodos...

%>END
```

Divide en archivos separados:

```bash
workflow lectures split notas.tex -d /ruta/al/proyecto/
```

Cada seccion se convierte en su propio archivo. Se generan lineas `\input{}` automaticamente. Desde la version con vault unificado, `split` **sincroniza por default** (`--sync`, default `sync`) — indexa los archivos generados (Note/Label/Link/Edge/Concept) sin necesitar un `notes sync` aparte; usa `--no-sync` para solo escribir los archivos.

### 5. Verificar el estado

```bash
# Ver estadisticas del grafo de conocimiento
workflow graph stats --project /ruta/al/proyecto/

# Encontrar notas huerfanas (sin conexiones)
workflow graph orphans --project /ruta/al/proyecto/

# Ver relaciones entre notas (declaradas en frontmatter, claves derived_from_*/links_*)
workflow notes edges list [--source ZETTEL_ID] [--edge-class structural|associative]
```

---

## Ciclo diario de trabajo

```
Manana:
  1. Escribir/editar archivos .tex
  2. workflow lectures scan .         # registrar archivos nuevos
  3. workflow lectures link .         # actualizar referencias

Antes de evaluacion:
  4. workflow exercise sync 00EE/     # indexar ejercicios
  5. workflow exercise build-exam ... # seleccionar y ensamblar examen
  6. workflow exercise export-moodle  # exportar para Moodle

Revision periodica:
  7. workflow graph stats .           # revisar conectividad
  8. workflow graph orphans .         # identificar notas aisladas
```

---

## Siguiente paso

- [Zettelkasten Notes](Zettelkasten-Notes.md) — Ciclo completo de notas: capture/new/create/promote/search/sync/link
- [Knowledge Graph](Knowledge-Graph.md) — Analizar conectividad, filtros por taxonomia y tags
- [Exercise Workflow](Exercise-Workflow.md) — Como crear, gestionar y exportar ejercicios
- [LaTeX Macros](LaTeX-Macros.md) — Referencia de todos los macros disponibles
