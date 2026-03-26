# Lectures Workflow

Herramientas para integrar proyectos de cursos con el sistema de notas, referencias cruzadas y el banco de ejercicios.

## Comandos

### scan — Registrar archivos

```bash
workflow lectures scan /ruta/al/curso/ --project-root /ruta/al/curso/
```

Descubre archivos `.tex` en `lect/tex/` y `eval/tex/`, y registra cada uno como `Note` en la base de datos local (`slipbox.db`). Es idempotente.

**Que hace internamente:**
1. Busca `*.tex` en los subdirectorios `lect/tex/` y `eval/tex/`
2. Para cada archivo, genera una referencia unica (ruta relativa con `-` en lugar de `/`)
3. Crea un registro `Note` en `slipbox.db` si no existe
4. Reporta nuevos vs ya registrados

### link — Construir referencias cruzadas

```bash
workflow lectures link /ruta/al/curso/ --project-root /ruta/al/curso/
```

Escanea los archivos registrados buscando patrones LaTeX:

| Patron | Tipo | Resultado |
|--------|------|-----------|
| `\cite{clave}` | citation | Registra en tabla `Citation` |
| `\cite{a,b,c}` | citation | Una entrada por cada clave |
| `\label{nombre}` | label | Registra en tabla `Label` |
| `\ref{nombre}` | ref | Crea `Link` (nota origen → etiqueta destino) |
| `\eqref{nombre}` | ref | Igual que `\ref` |

**Dos pasadas:**
1. **Pasada 1**: Registra todas las etiquetas (`\label`) y citas (`\cite`)
2. **Pasada 2**: Resuelve referencias (`\ref`) a etiquetas existentes, creando enlaces `Link`

Los comentarios LaTeX (`% ...`) se ignoran — una referencia comentada no se registra.

### split — Dividir notas

```bash
workflow lectures split archivo.tex -d directorio/salida/
```

Toma un archivo con marcadores `%>ruta/archivo.tex` y divide en subarchivos:

```latex
%>tex/tema01/intro.tex
\section{Introduccion}
Contenido...

%>tex/tema01/teoria.tex
\section{Teoria}
Mas contenido...

%>END
```

Resultado:
- `directorio/salida/tex/tema01/intro.tex` — con el contenido de la seccion
- `directorio/salida/tex/tema01/teoria.tex` — con el contenido de la seccion
- Lineas `\input{./tex/tema01/intro.tex}` generadas para el archivo principal

Opciones:
- `--overwrite` — sobreescribir archivos existentes (por defecto se omiten)
- Incluye proteccion contra path traversal (`%>../../` se bloquea)

### build-eval — Construir evaluacion

```bash
workflow lectures build-eval \
  -l "Usar-Aplicar" \
  -l "Recordar" \
  -n 5 -p 10 \
  --title "Parcial 1" \
  -o examen.tex \
  --moodle
```

Puente entre los templates de evaluacion (taxonomia Bloom) y el banco de ejercicios:

1. Construye especificaciones de slots desde los parametros CLI
2. Consulta la DB global por ejercicios `complete` que coincidan
3. Selecciona ejercicios (sin repetir) usando `workflow.exercise.selector`
4. Ensambla el documento con `workflow.exercise.exam_builder`
5. Si `--moodle`, tambien exporta a Moodle XML

---

## Flujo tipico de un semestre

### Inicio del ciclo

```bash
# Crear el proyecto
inittex                              # Seleccionar lecture, institucion, curso

# Primera clase — escribir notas
vim lect/tex/001-Cinematica/posicion.tex

# Registrar
workflow lectures scan . --project-root .
```

### Durante el ciclo

```bash
# Cada sesion de trabajo
vim lect/tex/002-Dinamica/newton.tex    # Escribir
workflow lectures scan . --project-root .   # Registrar
workflow lectures link . --project-root .   # Actualizar enlaces

# Verificar estado
workflow graph stats --project .
workflow graph orphans --type note --project .
```

### Preparar evaluaciones

```bash
# Sincronizar el banco de ejercicios
workflow exercise sync 00EE-ExamplesExercises/

# Construir examen
workflow lectures build-eval \
  -l "Usar-Aplicar" -n 5 -p 10 \
  --title "Examen Parcial 1" \
  -o eval/tex/parcial1.tex \
  --moodle

# El archivo Moodle XML se genera junto al .tex
```

### Clonar para siguiente ciclo

```bash
inittex --clone 42    # Clona el lecture_instance a nuevo anno/ciclo
```

Hereda curso, temas, libros y evaluaciones. Solo cambia anno, ciclo y primer lunes.

---

## Diferencias por institucion

| Aspecto | UCR | UFide | UCIMED |
|---------|-----|-------|--------|
| Ciclo | 18 sem (Semestre) | 15 sem (Cuatrimestre) | 24 sem (Semestre) |
| Duracion examen | 1h 45min | Variable | 70 min |
| Formato instrucciones | Simple | Minimo | Detallado (7 puntos) |
| Enumeracion ejercicios | Estandar | "Desempeno 1, 2..." | Estandar |
| Headers | Logo universidad + escuela | Solo universidad | Universidad centrado |

Estas diferencias se manejan via `SetProfiles.sty` y `SetHeaders.sty` ([ADR STY-0008](../ADR/STY-0008-set-profiles.md), [ADR STY-0009](../ADR/STY-0009-set-headers.md)).

---

## Relacion con otros modulos

- Usa `workflow.exercise.selector` y `exam_builder` para evaluaciones
- Alimenta `workflow.graph` con datos de notas y enlaces
- Los archivos `.tex` siguen los macros de `shared/sty/` ([LaTeX Macros](LaTeX-Macros.md))
- La estructura de proyecto viene de ITeP ([ADR ITEP-0004](../ADR/ITEP-0004-two-project-types.md))
