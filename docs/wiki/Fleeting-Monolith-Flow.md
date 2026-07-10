---
title: Fleeting-Monolith Flow
parent: Wiki
---
# Fleeting-Monolith Flow

> Nota de ubicación: `docs/guides/` no existe en este repo; esta guía vive junto
> a las demás páginas prácticas en `docs/wiki/` (ver `Lectures-Workflow.md`,
> `Zettelkasten-Notes.md` en el mismo directorio).

Convención real de trabajo semanal para capturar notas fleeting de clase en un
único archivo ("monolito"), dividirlas en notas permanentes, e indexarlas en la
base de datos sin perder la regla de oro: **`Concept.code` es slug-only,
estricto, y solo existe vía import** (ITEP-0012, decisión #18).

## 1. El monolito: dos zonas

Cada semana se crea un archivo en `inbox/`, por ejemplo
`semanaNN-tema-parte.md`, con frontmatter propio de nota (`id`, `type`,
`tags`, `concepts`, etc. — aunque para el monolito en sí casi siempre queda
vacío/plantilla, ver `data/templates/fleeting-monolith-template.md`) y **dos
zonas** en el cuerpo:

### Zona 1 — STAGING (antes del primer `%>`)

Todo lo que va antes del primer marcador `%>` **se ignora al dividir**
(`workflow.lecture.note_splitter.split_notes_file` solo actúa dentro de un
bloque activo — fuera de un marcador, las líneas simplemente no se acumulan a
ningún archivo). Aquí van dos cosas:

- **Mapa de contenidos**: tabla rápida `Contenido;Semana;Sección` — referencia
  cruzada al mapeo curricular (p. ej. `admin/MapeoUnidadCapitulo.md`).
- **Esqueleto del deck** `.tex`: el bloque `latex` con los `\CentredPage*` /
  `\input{}` que luego se pega al deck de la presentación de la semana. Vive
  aquí temporalmente mientras se arma el deck; no es una nota.

### Zona 2 — NOTAS (bloques `%>id.md ... %>END`)

Cada bloque delimitado por `%>ruta/nota.md` (inicio) y `%>END` (fin) se
convierte en **un archivo independiente** al correr split. El contenido entre
ambos marcadores —incluido el frontmatter YAML de la nota— se escribe tal cual
en el archivo de salida.

Frontmatter esperado por nota (igual al de cualquier nota permanente):

```yaml
---
id: 20260618-Magnetizacion
title: "Magnetización"
aliases: ["Magnetización"]
type: permanent
created: 2026-06-18
tags: [propiedades-magneticas, electromagnetismo]
concepts: [em-magnetizacion]
entry_point: true
---
```

- `concepts:` — lista de slugs `Concept.code` (nunca labels — ver §3).
- Relaciones a otras notas (opcional; desde 2026-07-09, ITEP-0013 amendment) —
  9 claves planas `derived_from_{continuation,refines,branches,synthesis,rebuttal}`
  / `links_{supports,contradicts,expands,see_also}`, cada una una lista de
  `zettel_id`. `derived_from_continuation` documenta que "esta nota continúa
  el hilo de la anterior" dentro de la misma sesión de captura. Una nota sin
  relaciones **no lleva ninguna de estas claves** (se omiten, nunca `[]`) —
  ver [Zettelkasten-Notes.md](Zettelkasten-Notes.md#claves-planas-de-relacion-en-frontmatter-canonico-desde-2026-07-09)
  para el esquema completo y el comando de migración de notas legadas.
- `entry_point: true/false` — top-level, no confundir con las claves de relación.

## 2. Dividir el monolito

```bash
workflow lectures split inbox/semanaNN-tema.md
```

Por defecto escribe en `<vault_root>/notes/permanent/` y (con el diseño D1,
`--sync` es el default) **también sincroniza cada archivo emitido**: registra
la `Note`, sus `Tag`/`Label`, los `NoteConcept` (contra slugs ya existentes en
la DB), y los `NoteEdge` desde las claves planas `derived_from_*`. Es idempotente — correr
`split` dos veces sobre el mismo monolito no duplica nada.

Si querés revisar los archivos antes de tocar la DB: `--no-sync`.

## 3. Dos ciclos de vida para conceptos

Hay dos formas legítimas de que un `Concept.code` llegue a existir — nunca hay
una tercera (nunca se resuelve por label, nunca se crea implícitamente desde
una nota):

### (a) Skyfolding-first (el caso normal)

Antes de escribir notas de un tema nuevo, alguien ya corrió
`workflow import <área>-contents-skyfolding.yml` (ver
`templates/0010MC-contents-skyfolding.yml`, `0040EM-contents-skyfolding.yml`
en el vault) y el árbol `DisciplineArea → Topic → Content → Concept` para ese
tema ya existe. Las notas de la semana simplemente referencian esos slugs —
`split --sync` los resuelve sin warnings.

### (b) Harvest-later (cuando el concepto nace en la nota)

A veces se escribe una nota fleeting con un slug nuevo que todavía no está en
ningún skyfolding (p. ej. un puente entre temas, como
`em-nps-magneticas` en el ejemplo de abajo). Eso genera un warning en
`split --sync` / `notes sync` — no un error, no bloquea nada — hasta que se
cierra el ciclo:

```bash
workflow concept harvest --notes notes/permanent/ --out delta.yaml
#  -> revisa/edita delta.yaml a mano (label, domain, content)
workflow import delta.yaml
#  -> el warning desaparece la próxima vez que se sincroniza
```

`harvest` **nunca escribe a la DB** — solo lee slugs de frontmatter y arma un
YAML de delta en el mismo formato de un skyfolding, para que `workflow import`
(el único camino de escritura, ADR-0018) lo procese como siempre.

## 4. Mini-ejemplo (recortado de semana05)

```markdown
---
id: semana05-propiedades-magneticas-2
tags: []
concepts: []
type: permanent
title: "Notas fleeting — Semana 05: Propiedades magnéticas (parte 2)"
---

# Semana 05 — Propiedades magnéticas de los materiales (parte 2)

## Mapa de contenidos (Contenido;Semana;Sección)
- Propiedades magnéticas de los materiales;5;32.3-32.4

## Esqueleto de la presentación (deck .tex)
​```latex
%==< C32S03-04: Propiedades magnéticas de los materiales >==
\CentredPage*{Propiedades magnéticas de los materiales}
​```
---
# Notas fuente (zona divisible)

%>20260618-Magnetizacion.md
---
id: 20260618-Magnetizacion
title: "Magnetización"
type: permanent
tags: [propiedades-magneticas, electromagnetismo]
concepts: [em-magnetizacion]
entry_point: true
---
La magnetización M es el momento dipolar magnético por unidad de volumen...
%>END

%>20260624-NanoparticulasMagneticasBio.md
---
id: 20260624-NanoparticulasMagneticasBio
title: "Puente: nanopartículas magnéticas en biomateriales"
type: permanent
tags: [propiedades-magneticas, electromagnetismo, biomateriales, puente]
concepts: [em-nps-magneticas]
derived_from_continuation:
  - 20260618-MaterialesMagneticos
entry_point: false
---
Las SPION son el biomaterial magnético más usado...
%>END
```

`em-nps-magneticas` es exactamente el tipo de slug que puede no existir aún
(concepto "puente" entre temas) — candidato natural para el ciclo harvest-later.

## 5. Cadencia semanal

1. Durante/después de clase: capturar en `inbox/semanaNN-*.md`, zona STAGING
   primero (mapa + deck), luego los bloques `%>...%>END`.
2. `workflow lectures split inbox/semanaNN-*.md` (sync por defecto).
3. Si hay warnings de concepto desconocido: `workflow concept harvest` →
   revisar delta → `workflow import`.
4. Repetir sync (`lectures split --sync` de nuevo, o `notes sync` si se
   prefiere apuntar a todo el directorio) para confirmar que los warnings
   desaparecieron.
5. El monolito en `inbox/` puede quedar como historial o moverse/archivarse —
   las notas ya viven independientes en `notes/permanent/`.

## Ver también

- `docs/superpowers/specs/2026-07-05-fleeting-harvest-design.md` — diseño
  técnico completo (D1–D4), anchors de código, tests, manejo de errores.
- `data/templates/fleeting-monolith-template.md` — plantilla para empezar un
  monolito nuevo.
- `docs/ADR/ITEP-0012-concept-orm.md` — contrato slug-only (decisión #18).
- `docs/ADR/0018-bulk-import-contract.md` — contrato de `workflow import`.
- `docs/wiki/Concept-Skyfolding.md` — qué es un skyfolding, esquema de
  campos completo, y su plantilla (`data/templates/concept-skyfolding-template.yml`).
