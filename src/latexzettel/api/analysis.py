# src/latexzettel/api/analysis.py
"""
API de análisis del grafo de notas.

Este módulo incorpora la funcionalidad del archivo legacy `analysis.py`,
que calcula una matriz de adyacencia basada en enlaces (references) entre notas.

Diferencias respecto al legacy:
- No usa `Note.id` (tu modelo actual no define id explícito); en Peewee existe
  un PK implícito `id` si no se define otro, pero para estabilidad usamos una
  clave determinística: el orden por `Note.filename` o `Note.reference`.
- No imprime ni ejecuta main().
- Devuelve estructuras listas para usar por CLI o notebooks.

Requisitos:
- numpy instalado (igual que legacy).
- Se espera un módulo DB externo (modularidad), con modelos SQLAlchemy:
  Note y la relación Note.references -> Link -> target(Label) -> note(Note).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select

from latexzettel.domain.errors import DomainError
from latexzettel.domain.types import DbModule
from latexzettel.infra.db import ensure_tables, db_session


# =============================================================================
# Resultados
# =============================================================================


@dataclass(frozen=True)
class AdjacencyMatrixResult:
    """
    notes:
      lista de instancias Note en el orden usado para indexar la matriz.
    adjacency:
      numpy.ndarray NxN donde adjacency[i, j] cuenta la cantidad de links
      desde notes[i] hacia notes[j].
    index_by:
      criterio de ordenamiento ('filename' o 'reference' o 'id').
    """

    notes: list
    adjacency: np.ndarray
    index_by: str


# =============================================================================
# API
# =============================================================================


def calculate_adjacency_matrix(
    *,
    db: DbModule,
    index_by: str = "filename",
) -> AdjacencyMatrixResult:
    """
    Calcula matriz de adyacencia del grafo de referencias entre notas.

    Basado en el legacy:
        ids = [note.id for note in Note]
        adjacency_matrix = zeros([len(ids), len(ids)])
        for note in Note:
            for reference in note.references:
                adjacency_matrix[ids.index(note.id), ids.index(reference.target.note.id)] += 1

    Parámetros:
    - db: módulo externo (modularidad), con:
        - Note iterable via SQLAlchemy session
        - Link accesible vía note.references
        - reference.target.note en cada link
    - index_by: cómo ordenar notas para indexación:
        - "filename" (recomendado, estable)
        - "reference"
        - "id" (usa PK)

    Retorna:
    - AdjacencyMatrixResult
    """
    health = ensure_tables(db)
    if not health.ok:
        raise DomainError(f"DB no disponible: {health.error}")

    with db_session(db) as session:
        # Obtener notas en orden estable
        if index_by == "filename":
            notes = list(
                session.scalars(select(db.Note).order_by(db.Note.filename)).all()
            )
            key = lambda n: n.filename
        elif index_by == "reference":
            notes = list(
                session.scalars(select(db.Note).order_by(db.Note.reference)).all()
            )
            key = lambda n: n.reference
        elif index_by == "id":
            notes = list(
                session.scalars(select(db.Note).order_by(db.Note.id)).all()
            )
            key = lambda n: n.id
        else:
            raise ValueError("index_by debe ser 'filename', 'reference' o 'id'")

        n = len(notes)
        adjacency = np.zeros((n, n), dtype=float)

        # Mapa clave->índice para O(1) en lugar de ids.index(...)
        index = {key(note): i for i, note in enumerate(notes)}

        for src in notes:
            src_i = index[key(src)]
            for link in src.references:
                tgt_note = link.target.note
                tgt_k = key(tgt_note)
                # Es posible que el target no esté en el conjunto (DB inconsistente),
                # aunque en la práctica debería estarlo.
                tgt_i = index.get(tgt_k)
                if tgt_i is None:
                    continue
                adjacency[src_i, tgt_i] += 1.0

    return AdjacencyMatrixResult(notes=notes, adjacency=adjacency, index_by=index_by)


def list_unreferenced_notes(
    *,
    db: DbModule,
    index_by: str = "filename",
) -> list:
    """
    Retorna una lista de notas que NO son referenciadas por ninguna otra nota
    (grado de entrada = 0).

    Esto es el equivalente funcional de Helper.list_unreferenced() que usaba
    calculate_adjacency_matrix() y sumaba columnas.
    """
    res = calculate_adjacency_matrix(db=db, index_by=index_by)
    referenced_by = np.sum(res.adjacency, axis=0)  # entradas a cada nodo
    return [note for note, indeg in zip(res.notes, referenced_by) if indeg == 0]


def remove_duplicate_citations(
    *,
    db: DbModule,
) -> int:
    """
    Elimina instancias duplicadas de Citation (misma note + citationkey),
    replicando Helper.remove_duplicate_citations().

    Retorna el número de filas eliminadas.
    """
    health = ensure_tables(db)
    if not health.ok:
        raise DomainError(f"DB no disponible: {health.error}")

    deleted = 0

    with db_session(db) as session:
        all_notes = session.scalars(select(db.Note)).all()

        for note in all_notes:
            tracked = [c for c in note.citations]
            keys = [c.citationkey for c in tracked]
            uniq = set(keys)

            if len(uniq) == len(keys):
                continue

            for key in uniq:
                citations = session.scalars(
                    select(db.Citation).where(
                        (db.Citation.note_id == note.id)
                        & (db.Citation.citationkey == key)
                    )
                ).all()
                # Mantener 1, borrar el resto
                first = True
                for c in citations:
                    if first:
                        first = False
                        continue
                    session.delete(c)
                    deleted += 1

        session.flush()

    return deleted
