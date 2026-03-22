---
adr: 0309
title: "Definición del comando \\CentredPage"
status: Accepted
date: 2026-03-20
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - LaTeX
  - Presetation
  - Visual flow control
decision_scope: component
supersedes: null
superseded_by: null
related_adrs: []
---

## Estado

Accepted

## Contexto

Se requiere un mecanismo reusable para generar páginas dedicadas cuyo contenido
principal y secundario estén **centrados vertical y horizontalmente respecto a
la página completa**, no únicamente respecto al área de texto.

El objetivo es:

- Definir un **comando de alto nivel** (no un ambiente)
- Permitir contenido **inline LaTeX flexible**
- Mantener **compatibilidad con footnotes**
- Proveer una **API configurable** (colores, estilos, espaciado, alineación)
- Evitar soluciones frágiles basadas en overlay (e.g. TikZ con
  `current page.center`)
- Diseñar una base extensible para futuros “page blocks”

Casos de uso esperados:

- `{Título} []`
- `{Título} [Subtítulo]`
- `{Logo} [Título]`
- `{Título} [Epígrafe¹]`
- `{Concepto} [Definición¹]`

---

## Decisión

Se define `\CentredPage` como un **comando (`\NewDocumentCommand`)** que genera
una página completa, centrando su contenido mediante
**flujo vertical controlado con `\vbox`**,
no mediante posicionamiento absoluto.

---

## Diseño del comando

### Firma

```latex
\CentredPage{<principal>}[<secundario>]
```

- `<principal>`: obligatorio
- `<secundario>`: opcional

Se define una versión estrella:

```latex
\CentredPage*{...}[...]
```

---

## Comportamiento

### Flujo de ejecución

1. `\par`
2. `\clearpage`
3. Aplicación de estilo de página:
   - default: `\thispagestyle{empty}`
   - versión estrella: no modifica pagestyle

4. Contenido envuelto en `\begingroup ... \endgroup`
5. Construcción del bloque centrado
6. `\null`
7. `\clearpage`

---

## Modelo de centrado

El centrado se implementa mediante:

```latex
\makebox[\paperwidth][c]{%
  \vbox to \paperheight{%
    \vfill
    <contenido>
    \vfill
  }
}
```

### Justificación

- Centrado respecto a **toda la página** (`\paperwidth`, `\paperheight`)
- Independiente de márgenes
- Compatible con flujo LaTeX estándar
- Permite mejor interacción con footnotes que soluciones overlay

---

## Estructura del contenido

El contenido se organiza como:

```latex
\vbox{
  <alineación>
  <principal>\par
  \vspace{<separación>}
  <secundario>\par
}
```

---

## Contenido soportado

### Permitido

- Texto inline
- Comandos LaTeX inline
- Múltiples párrafos (`\par`)
- Saltos de línea manuales (`\\[<dim>]`)
- Inclusión de imágenes inline (`\includegraphics`)

### No soportado (por contrato)

- Entornos flotantes (`figure`, `table`)
- Contenido que dependa de posicionamiento flotante

---

## Footnotes

- Se permite el uso de `\footnote` dentro del contenido
- Funcionan en la mayoría de los casos
- En escenarios complejos puede requerirse:
  - `\footnotemark` + `\footnotetext`

---

## Configuración

Se implementa un sistema **key–value basado en `l3keys`**

### Parámetros configurables

- Color principal
- Color secundario
- Estilo de fuente principal
- Estilo de fuente secundario
- Tamaño de fuente
- Interlineado
- Separación entre bloques
- Ancho del contenido (`\CentredPageWidth`)
- Offset vertical (`\CentredPageVOffset`)
- Alineación interna

---

## Variables clave

### Dimensiones

```latex
\CentredPageWidth
\CentredPageVOffset
```

- `Width`: controla ancho del bloque de contenido
- `VOffset`: permite ajustar desplazamiento vertical respecto al centro geométrico

---

## Alineación

Por defecto:

```latex
\centering
```

Se define un comando para cambiar a:

- `\raggedright`
- `\raggedleft`
- `\centering` (default)

---

## Dependencias

- `xcolor`
- Kernel moderno de LaTeX (`\NewDocumentCommand`, `l3keys`)

No depende de:

- TikZ
- positioning overlay

---

## Compatibilidad

Clases soportadas:

- `article`
- `report`
- `book`
- `memoir` (compatibilidad funcional, no integración profunda)

Mapeo semántico sugerido:

| Clase                 | Principal | Secundario |
| --------------------- | --------- | ---------- |
| article/report/memoir | section   | subsection |
| book (default)        | section   | subsection |
| book (configurable)   | chapter   | section    |

---

## Justificación de decisiones clave

### Uso de `\NewDocumentCommand`

- API moderna
- Mejor manejo de argumentos opcionales
- Preparado para evolución

---

### Abandono de overlay (TikZ)

- Evita fragilidad estructural
- Mejora compatibilidad con footnotes
- Permite contenido más rico

---

### Uso de `\paperwidth` / `\paperheight`

- Centrado geométrico real
- Independencia de márgenes

---

### Uso de flujo vertical (`\vbox`)

- Compatible con modelo TeX
- Más robusto que posicionamiento absoluto

---

### Versión estrella

Permite:

- Mantener headers/footers del usuario
- Mayor flexibilidad editorial

---

## Consecuencias

### Positivas

- Diseño robusto y extensible
- API clara y semántica
- Compatibilidad amplia
- Control fino del layout

### Negativas

- No soporta floats
- Footnotes no 100% garantizadas en todos los casos
- Requiere disciplina en el uso del contenido

---

## Decisiones futuras

- Variantes del comando:
  - `\QuotePage`
  - `\SectionDivider`
  - `\ConceptPage`

- Posible integración con sistemas tipográficos más complejos
- Publicación como paquete independiente

---

## Notas

Este comando se diseña inicialmente como parte de una **librería interna**,
con posibilidad de evolución a paquete público.

El diseño prioriza:

- robustez
- claridad semántica
- extensibilidad

sobre minimalismo extremo.
