# Exercise Workflow

El banco de ejercicios permite crear, parsear, indexar, seleccionar y exportar ejercicios LaTeX. Los archivos `.tex` son la fuente de verdad — la base de datos almacena solo metadatos e indices ([ADR-0010](../ADR/0010-exercise-persistence-model.md)).

## Conceptos clave

### Formato de archivo de ejercicio

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
  Dado un campo electrico $\vc{E}$, calcule el flujo a traves
  de una superficie gaussiana esferica de radio $r$.

  \includegraphics[width=0.4\textwidth]{img/gauss-sphere.pdf}

  \begin{enumerate}[a)]
    \qpart{\rightoption \pts{5} $\Phi = \frac{Q}{\epsilon_0}$}{
      Correcto. Por la ley de Gauss, el flujo total depende
      solo de la carga encerrada.
    }
    \qpart{\pts{5} $\Phi = E \cdot A$}{
      Incorrecto para una distribucion no uniforme.
    }
    \qpart{\pts{5} $\Phi = 0$}{
      Incorrecto. La carga encerrada es no nula.
    }
  \end{enumerate}
}{
  La clave es la simetria esferica. Aplicar $\oint \vc{E} \cdot d\vc{A}$.
}
\qfeedback{Revise la seccion 24.3 de Serway para mas detalles sobre la ley de Gauss.}
```

### Campos de metadatos YAML

| Campo | Requerido | Valores | Descripcion |
|-------|-----------|---------|-------------|
| `id` | Si | string | Identificador unico (ej: `phys-gauss-001`) |
| `type` | Si | `multichoice`, `essay`, `shortanswer`, `numerical`, `truefalse` | Tipo de pregunta |
| `difficulty` | Si | `easy`, `medium`, `hard` | Nivel de dificultad |
| `taxonomy_level` | Si | Bloom (ver abajo) | Nivel taxonomico |
| `taxonomy_domain` | Si | Bloom (ver abajo) | Dominio taxonomico |
| `tags` | No | lista | Etiquetas para filtrar |
| `concepts` | No | lista | IDs de notas relacionadas |
| `status` | No | `placeholder`, `in_progress`, `complete` | Estado del archivo |

### Taxonomia de Bloom ([ADR ITEP-0006](../ADR/ITEP-0006-taxonomy-enums.md))

**Niveles:** Recordar, Comprender, Analisis, Usar-Aplicar, Usar-Evaluar, Usar-Crear, Metacognitivo, Sistema interno

**Dominios:** Informacion, Procedimiento Mental, Procedimiento Psicomotor, Metacognitivo

### Macros de ejercicio

| Macro | Archivo .sty | Funcion |
|-------|-------------|---------|
| `\question{stem}{solution}` | SetCommands | Pregunta principal |
| `\qpart{instruccion}{solucion}` | SetCommands | Parte/opcion de pregunta |
| `\pts{n}` | PartialCommands | Asignar puntos |
| `\rightoption` | PartialCommands | Marcar opcion correcta |
| `\exa[cap]{num}` | SetCommands | Referencia a ejercicio de libro |
| `\qfeedback{texto}` | SetExercises | Retroalimentacion (para Moodle) |
| `\qdiagram{id}` | SetExercises | Referencia a diagrama TikZ |

Ver [LaTeX Macros](LaTeX-Macros.md) para la referencia completa.

---

## Comandos

### Crear ejercicios

```bash
# Crear un placeholder individual
workflow exercise create phys-gauss-001 \
  -d 00EE-ExamplesExercises/ \
  --type multichoice \
  --difficulty medium \
  --taxonomy-level "Usar-Aplicar" \
  --taxonomy-domain "Procedimiento Mental" \
  --tag physics --tag electrostatics \
  --book serway --chapter 24 --exercise-num 5

# Crear un rango desde un libro
workflow exercise create-range \
  -d 00EE-ExamplesExercises/ \
  --book serway --chapter 1 --first 1 --last 20 \
  --tag physics
```

Los placeholders se crean con `status: placeholder` y un esqueleto `\question{...}{}`.

### Parsear y verificar

```bash
# Parsear archivos y mostrar estructura
workflow exercise parse 00EE-ExamplesExercises/

# Salida:
#   [OK] phys-gauss-001.tex: phys-gauss-001
#        status: complete, options: 3
#        type: multichoice, difficulty: medium
```

### Sincronizar con la base de datos

```bash
workflow exercise sync 00EE-ExamplesExercises/
```

Compara el hash SHA-256 de cada archivo con la DB. Solo actualiza registros que cambiaron:

```
Sync complete: 5 new, 2 updated, 13 unchanged, 0 skipped.
```

### Listar con filtros

```bash
workflow exercise list --status complete --difficulty medium --type multichoice
workflow exercise list --taxonomy-level "Usar-Aplicar"
```

### Limpiar registros huerfanos

```bash
# Ver que se borraria
workflow exercise gc

# Borrar sin confirmar
workflow exercise gc --yes
```

Elimina registros cuyo `source_path` apunta a archivos que ya no existen.

### Construir un examen

```bash
workflow exercise build-exam \
  -l "Usar-Aplicar" \
  -l "Recordar" \
  -n 5 \
  -p 10 \
  --title "Parcial 1" \
  -o examen.tex
```

Selecciona ejercicios del banco que coincidan con los niveles taxonomicos solicitados. Nunca selecciona el mismo ejercicio dos veces. Advierte si no hay suficientes ejercicios.

### Exportar a Moodle XML

```bash
workflow exercise export-moodle 00EE-ExamplesExercises/ \
  -o quiz.xml \
  --status complete \
  --tag physics
```

#### Normalizacion automatica ([ADR-0012](../ADR/0012-moodle-xml-export-mapping.md))

Antes de exportar, los macros personalizados se expanden a LaTeX estandar:

| Original | Expandido |
|----------|-----------|
| `\vc{E}` | `\vec{\mathbf{E}}` |
| `\scrp{enc}` | `_{\mbox{\scriptsize{enc}}}` |
| `\pts{5}` | `(5 pts.)` |
| `$x^2$` | `\(x^2\)` |
| `\textcolor{red}{texto}` | `texto` |

Esto asegura que el XML funcione en **cualquier** Moodle sin depender de MathJax institucional.

Las imagenes se codifican en base64 e incrustan directamente en el XML.

---

## Ciclo de vida de un ejercicio

```
placeholder  ──→  in_progress  ──→  complete
   (create)        (editando)       (listo para usar)
```

- **placeholder**: Archivo creado por `create`/`create-range`, esqueleto vacio
- **in_progress**: Tiene contenido pero faltan metadatos o solucion
- **complete**: Metadatos completos, stem y solucion presentes

El status se infiere automaticamente al parsear, o se puede fijar en el YAML.

---

## Arquitectura

- **Parser** (`workflow.exercise.parser`) — Extraccion por conteo de llaves ([ADR-0011](../ADR/0011-latex-exercise-parser-strategy.md))
- **Normalizacion** (`workflow.latex.normalize`) — Expansion de macros ([ADR-0012](../ADR/0012-moodle-xml-export-mapping.md))
- **Selector** (`workflow.exercise.selector`) — Seleccion por taxonomia con prevencion de duplicados
- **Moodle** (`workflow.exercise.moodle`) — XML via `xml.etree.ElementTree` con CDATA

Ver [Architecture](Architecture.md) para detalles del modulo.
