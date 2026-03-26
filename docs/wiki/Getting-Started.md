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

Deberias ver los 5 grupos de comandos: `exercise`, `graph`, `lectures`, `tikz`, `validate`.

## Estructura del sistema

WorkFlow usa dos bases de datos SQLite:

```
~/.local/share/workflow/workflow.db    # Global: instituciones, cursos, libros, ejercicios
<proyecto>/slipbox.db                  # Local: notas, enlaces, etiquetas (por proyecto)
```

Los archivos de estilo LaTeX se comparten via symlinks:

```
~/.local/share/workflow/sty/           # 17 archivos .sty
```

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

### 2. Registrar notas en la base de datos local

```bash
workflow lectures scan /ruta/al/proyecto/ --project-root /ruta/al/proyecto/
```

Esto descubre todos los `.tex` en `lect/tex/` y `eval/tex/`, y registra cada uno como `Note` en `slipbox.db`. Es idempotente — ejecutar de nuevo no duplica registros.

```
Discovered: 15 .tex file(s)
  Registered (new): 15
  Already registered: 0
```

### 3. Construir enlaces cruzados

```bash
workflow lectures link /ruta/al/proyecto/ --project-root /ruta/al/proyecto/
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

Cada seccion se convierte en su propio archivo. Se generan lineas `\input{}` automaticamente.

### 5. Verificar el estado

```bash
# Ver estadisticas del grafo de conocimiento
workflow graph stats --project /ruta/al/proyecto/

# Encontrar notas huerfanas (sin conexiones)
workflow graph orphans --project /ruta/al/proyecto/
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

- [Exercise Workflow](Exercise-Workflow.md) — Como crear, gestionar y exportar ejercicios
- [LaTeX Macros](LaTeX-Macros.md) — Referencia de todos los macros disponibles
