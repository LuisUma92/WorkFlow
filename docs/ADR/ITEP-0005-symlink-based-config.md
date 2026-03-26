---
adr: "0005"
title: "Configuración LaTeX basada en symlinks"
status: Accepted
date: 2026-03-20
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - filesystem
  - symlinks
  - LaTeX
decision_scope: module
supersedes: null
superseded_by: null
related_adrs:
  - "ITEP-0004"
---

## Context

Los proyectos LaTeX comparten paquetes `.sty` y templates desde un directorio central (`~/.config/mytex/`). Copiar estos archivos en cada proyecto causaría duplicación y dificultaría actualizaciones globales.

Además, los proyectos de curso necesitan acceder a imágenes y bibliografías de múltiples temas principales ubicados en directorios hermanos.

---

## Decision Drivers

- Actualizaciones globales de paquetes LaTeX sin tocar cada proyecto
- Acceso transparente a recursos compartidos (imágenes, bibliografías)
- Compatibilidad con compiladores LaTeX que resuelven rutas relativas

---

## Decision

Usar symlinks para vincular archivos compartidos:

1. **Config links**: archivos `.sty` y `title.tex` en `config/` apuntan a `~/.config/mytex/`.
2. **Image links**: directorios en `img/` apuntan a `00II-ImagesFigures/`.
3. **Bibliography links**: directorios en `bib/` apuntan a `00BB-Library/`.
4. **Exercise links** (lecture): directorios en `eval/T##/` apuntan a `00EE-ExamplesExercises/`.

El mapeo de config links se define en `DEF_TEX_CONFIG` (`defaults.py`):

```python
DEF_TEX_CONFIG = {
    "0-packages.sty": "{src_dir}/sty/SetFormat.sty",
    "1-loyaut.sty": "{src_dir}/sty/SetLoyaut.sty",
    # ...
}
```

El helper `safe_symlink()` en `links.py` crea los symlinks de forma idempotente.

---

## Architectural Rules

### MUST

- Los archivos `.sty` compartidos **MUST** ser symlinks, nunca copias.
- `relink` **MUST** poder recrear todos los symlinks de un proyecto desde la DB.

### SHOULD

- `safe_symlink()` **SHOULD** verificar que el target existe antes de crear el link.
- Nuevos tipos de links **SHOULD** registrarse en `DEF_TEX_CONFIG` o en la lógica de `relink`.

### MAY

- Proyectos **MAY** contener archivos propios (no symlinks) como `4_biber.sty`.

---

## Implementation Notes

- `itep/links.py`: `safe_symlink()`, `relink_lecture()`, `relink_general()`.
- `itep/defaults.py`: `DEF_TEX_CONFIG` con patrones de ruta.
- `itep/structure.py`: `ConfigData` dataclass para resolver pares link-target.
- `itep/structure.py`: `GeneralDirectory` enum con nombres de directorios compartidos.

---

## Consequences

### Benefits

- Un solo punto de actualización para paquetes LaTeX
- Proyectos ligeros en disco
- `relink` como herramienta de reparación

### Costs

- Dependencia en que las rutas absolutas sean estables
- Los symlinks rotos requieren ejecutar `relink`

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-20 | Initial ADR |
