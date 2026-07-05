---
id: <semanaNN-tema-parteN>
aliases:
  - "<Notas fleeting — Semana NN>"
tags: []
concepts: []
created: <YYYY-MM-DD>
entry_point: false
exercises: []
images: []
references: []
relations:
  derived_from: []
  links: []
title: "<Notas fleeting — Semana NN: Título del tema (parte N)>"
type: permanent
---

<!--
  MONOLITO — Semana <NN>: <título del tema> (parte <N>).

  DOS ZONAS:
   1. STAGING (antes del 1.er `%>`): mapa de contenidos + esqueleto del deck.
      `workflow lectures split` la ignora por completo.
   2. NOTAS (`%>id.md … %>END`): cada bloque -> una nota independiente al dividir.
  Dividir:  workflow lectures split <este-archivo>.md   # -> notes/permanent/, sync por defecto
  Ver: docs/wiki/Fleeting-Monolith-Flow.md para el flujo completo (harvest de conceptos, etc.)
  Subdivisiones (admin/MapeoUnidadCapitulo.md): <CNNSNN-NN>.
-->

# Semana <NN> — <Título del tema> (parte <N>)

## Mapa de contenidos (Contenido;Semana;Sección)

- <Nombre del contenido>;<NN>;<sección del libro>

## Esqueleto de la presentación (deck `.tex`)

```latex
%==< <CNNSNN-NN>: <Título del tema> >==========
\CentredPage*[primary-font=\bfseries\Large]{<Título del tema>}
\newpage
% \input{tex/<CNNSNN-NN-carpeta>/<archivo>.tex}
\newpage
```

---

# Notas fuente (zona divisible)

## <CNNSNN-NN> · <Título del tema> — <sección del libro>

%><YYYYMMDD-NombreNota>.md
---
id: <YYYYMMDD-NombreNota>
title: "<Título legible de la nota>"
aliases:
  - "<Título legible de la nota>"
type: permanent
created: <YYYY-MM-DD>
tags: [<tag-tema>, <tag-área>]
concepts: [<slug-concepto>]
relations:
  derived_from: []
  links: []
entry_point: <true|false>
---

<Cuerpo de la nota. Un concepto por nota, autocontenida.>

%>END
