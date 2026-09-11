# src/latexzettel/api/sync.py
"""
API de sincronización de la base de datos con el filesystem.

Este módulo refactoriza principalmente:
- Helper.synchronize()
- Helper.force_synchronize()
- (parcialmente) Helper.sync_md() en lo que respecta a asegurar notas/DB y
  coordinar actualizaciones

del manage.py legacy.

Diseño:
- NO usa Click (sin prints/input), salvo que tú decidas inyectar confirmaciones
  desde cli/* usando util/io.py.
- Opera sobre un módulo DB externo (modularidad) compatible con infra/db.py.
- Usa infra/regexes.py para patrones consistentes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.db.models.notes import Note, Citation, Label, Link

from latexzettel.config.settings import NotesPaths, DEFAULT_SETTINGS
from latexzettel.domain.errors import (
    DomainError,
    NoteNotFound,
    DocumentsTexNotFound,
)
from latexzettel.domain.templates import min_tex_file
from latexzettel.infra.db import ensure_tables, db_session
from latexzettel.infra.regexes import (
    EXTERNALDOCUMENT_RE,
    LABEL_OR_CURRENTDOC_RE,
    CITATION_RE,
    EX_REF_RE,
)
from latexzettel.infra import fs as ifs
from latexzettel.util.time import (
    file_mtime,
    needs_update,
)


# =============================================================================
# Resultados
# =============================================================================


@dataclass(frozen=True)
class SyncResult:
    """
    Resultado de una sincronización incremental.

    updated_notes:
      lista de instancias Note cuyo contenido fue releído y procesado
      (labels/citations/links).
    new_or_modified_links:
      lista de instancias Link creadas o eliminadas durante la sync.
    run_biber:
      dict {note_instance: bool} para indicar si la nota requiere biber
      (por cambios en citas), replicando manage.py.
    """

    updated_notes: list
    new_or_modified_links: list
    run_biber: dict


@dataclass(frozen=True)
class ForceSyncResult:
    """
    Resultado de una sincronización completa (force).
    """

    tracked_notes: dict[str, str]  # filename -> reference
    added_notes: list
    updated_notes: list


# =============================================================================
# Helpers internos
# =============================================================================


def _note_tex_path(paths: NotesPaths, filename: str) -> Path:
    return paths.abs(paths.slipbox_dir / f"{filename}.tex")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _get_labels_from_file(note_file: Path) -> list[str]:
    labels: list[str] = []
    with note_file.open("r", encoding="utf-8") as f:
        for line in f:
            m = LABEL_OR_CURRENTDOC_RE.search(line)
            if m:
                labels.append(m.group(3))
    return labels


def _get_citation_keys_from_file(note_file: Path) -> set[str]:
    keys: set[str] = set()
    with note_file.open("r", encoding="utf-8") as f:
        for line in f:
            for m in CITATION_RE.finditer(line):
                keys.add(m.group(7))
    return keys


def _get_links_from_file(note_file: Path) -> list[tuple[str, str]]:
    """
    Retorna lista de (reference, label) apuntados por la nota.

    En manage.py, si no hay [label] se usa 'note'.
    """
    out: list[tuple[str, str]] = []
    with note_file.open("r", encoding="utf-8") as f:
        for line in f:
            for m in EX_REF_RE.finditer(line):
                ref = m.group(5)  # {Ref}
                label = m.group(4) if m.group(4) is not None else "note"
                out.append((ref, label))
    return out


def _sync_note_labels(session: Session, note, note_file: Path) -> None:
    file_labels = _get_labels_from_file(note_file)
    tracked_labels = [lbl.label for lbl in note.labels]

    for lbl in file_labels:
        if lbl not in tracked_labels:
            new_lbl = Label(label=lbl, note=note)
            session.add(new_lbl)

    # remover labels que ya no existen
    for lbl in list(note.labels):
        if lbl.label not in file_labels:
            session.delete(lbl)

    session.flush()


def _sync_note_citations(session: Session, note, note_file: Path) -> bool:
    """
    Sincroniza tabla Citation para la nota.
    Retorna True si hubo cambios (para decidir biber).
    """
    keys = _get_citation_keys_from_file(note_file)
    tracked = [c for c in note.citations]
    tracked_keys = [c.citationkey for c in tracked]

    changed = False

    for key in keys:
        if key not in tracked_keys:
            new_cit = Citation(note=note, citationkey=key)
            session.add(new_cit)
            changed = True

    for c in tracked:
        if c.citationkey not in keys:
            session.delete(c)
            changed = True

    session.flush()
    return changed


def _sync_note_links(session: Session, note, note_file: Path) -> list:
    """
    Sincroniza tabla Link para la nota.
    Retorna lista de instancias Link modificadas (creadas/eliminadas).
    """
    links = _get_links_from_file(note_file)
    modified: list = []

    tracked = [(lnk.target.note.reference, lnk.target.label) for lnk in note.references]

    # Crear links nuevos
    for link in links:
        if link in tracked:
            continue
        label = session.scalars(
            select(Label)
            .join(Label.note)
            .where(Note.reference == link[0])
            .where(Label.label == link[1])
        ).first()
        if label is None:
            continue
        lnk = Link(target=label, source=note)
        session.add(lnk)
        session.flush()
        modified.append(lnk)

    # Eliminar links que ya no existen en el archivo
    for lnk in list(note.references):
        if (lnk.target.note.reference, lnk.target.label) not in links:
            session.delete(lnk)
            session.flush()
            modified.append(lnk)

    return modified


def _update_note_from_file(
    session: Session, note, paths: NotesPaths
) -> tuple[bool, list]:
    """
    Relee el archivo de la nota y actualiza labels/citations/links.

    Retorna:
      - run_biber: bool (si cambiaron citas)
      - modified_links: list[Link]
    """
    note_file = _note_tex_path(paths, note.filename)
    if not note_file.exists():
        raise NoteNotFound(
            f"Archivo no encontrado para note '{note.filename}': {note_file}"
        )

    _sync_note_labels(session, note, note_file)
    run_biber = _sync_note_citations(session, note, note_file)
    modified_links = _sync_note_links(session, note, note_file)
    return run_biber, modified_links


# =============================================================================
# API pública: synchronize()
# =============================================================================


def synchronize(
    *,
    paths: NotesPaths = DEFAULT_SETTINGS.paths,
) -> SyncResult:
    """
    Sincronización incremental:
    - detecta notas editadas desde el último sync (mtime > note.last_edit_date)
    - reparsea labels/citations/links solo para las notas modificadas
    """
    health = ensure_tables()
    if not health.ok:
        raise DomainError(f"DB no disponible: {health.error}")

    with db_session() as session:
        all_notes = session.scalars(select(Note)).all()
        to_read: list = []

        # detectar notas modificadas
        for note in all_notes:
            try:
                fpath = _note_tex_path(paths, note.filename)

                if needs_update(
                    file_path=fpath,
                    last_edit_date=note.last_edit_date,
                ):
                    to_read.append(note)
                    note.last_edit_date = file_mtime(fpath)
                    session.flush()
            except FileNotFoundError:
                continue

        run_biber: dict = {}
        new_links: list = []

        for note in to_read:
            rb, modified_links = _update_note_from_file(session, note, paths)
            run_biber[note] = rb
            new_links.extend(modified_links)

    return SyncResult(
        updated_notes=to_read, new_or_modified_links=new_links, run_biber=run_biber
    )


# =============================================================================
# Helpers internos: force_synchronize()
# =============================================================================


def _resolve_documents_tex(
    paths: NotesPaths, create_documents_tex_if_missing: bool
) -> Path:
    """
    Garantiza que notes/documents.tex exista (creándolo si corresponde) y
    retorna su Path.
    """
    doc_path = paths.abs(paths.documents_tex)
    if not doc_path.exists():
        if create_documents_tex_if_missing:
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            doc_path.write_text("", encoding="utf-8")
        else:
            raise DocumentsTexNotFound(f"No existe: {doc_path}")
    return doc_path


def _parse_tracked_notes(doc_path: Path) -> dict[str, str]:
    """
    Parsea notes/documents.tex y retorna dict {filename: reference}.
    """
    tracked_notes: dict[str, str] = {}
    for line in doc_path.read_text(encoding="utf-8").splitlines():
        m = EXTERNALDOCUMENT_RE.search(line)
        if m:
            reference_name = m.group(2)
            filename = m.group(4)
            tracked_notes[filename] = reference_name
    return tracked_notes


def _ensure_tracked_note_files(
    paths: NotesPaths,
    tracked_notes: dict[str, str],
    create_missing_note_files: bool,
) -> None:
    """
    Garantiza (opcionalmente creando) que cada filename en tracked_notes
    exista como archivo físico en slipbox.
    """
    slipbox_files = ifs.rglob_files(paths.abs(paths.slipbox_dir), suffix=".tex")
    slipbox_names = {p.stem for p in slipbox_files}

    for filename in list(tracked_notes.keys()):
        if filename not in slipbox_names:
            if create_missing_note_files:
                # crea un archivo mínimo: delega a util/fs o api/notes; aquí hacemos mínimo
                f = _note_tex_path(paths, filename)
                f.parent.mkdir(parents=True, exist_ok=True)
                min_tex_file(f)
                slipbox_names.add(filename)
            else:
                # si no creamos, simplemente seguimos; DB puede seguir reflejando docs
                continue


def _stamp_existing_note(
    note, filename: str, reference_name: str, modified_dt: datetime, paths: NotesPaths
) -> None:
    """
    Actualiza timestamps/build-dates/reference de una nota existente en DB.
    """
    note.last_edit_date = modified_dt
    if note.created is None:
        note.created = note.last_edit_date

    # best-effort build dates
    html_path = paths.abs(paths.html_dir / f"{filename}.html")
    pdf_path = paths.abs(paths.pdf_dir / f"{filename}.pdf")

    if html_path.exists():
        note.last_build_date_html = file_mtime(html_path)
    if pdf_path.exists():
        note.last_build_date_pdf = file_mtime(pdf_path)

    # update reference si difiere
    if note.reference != reference_name:
        note.reference = reference_name


def _sync_tracked_note(
    session: Session,
    filename: str,
    reference_name: str,
    paths: NotesPaths,
    added_notes: list,
    updated_notes: list,
) -> None:
    """
    Sincroniza (crea o actualiza) la entrada Note para un (filename, reference)
    de tracked_notes, apendeando a added_notes/updated_notes según corresponda.
    """
    fpath = _note_tex_path(paths, filename)
    if not fpath.exists():
        return

    modified_dt = file_mtime(fpath)

    note = session.scalars(
        select(Note).where(Note.filename == filename)
    ).first()

    if note is not None:
        _stamp_existing_note(note, filename, reference_name, modified_dt, paths)
        session.flush()
        updated_notes.append(note)
        return

    # Si existe una nota con el mismo reference, reasignar filename
    note_by_ref = session.scalars(
        select(Note).where(Note.reference == reference_name)
    ).first()

    if note_by_ref is not None:
        note_by_ref.filename = filename
        note_by_ref.last_edit_date = modified_dt
        if note_by_ref.created is None:
            note_by_ref.created = modified_dt
        session.flush()
        updated_notes.append(note_by_ref)
        return

    new_note = Note(
        filename=filename,
        reference=reference_name,
        created=modified_dt,
        last_edit_date=modified_dt,
    )
    session.add(new_note)
    session.flush()
    added_notes.append(new_note)


def _sync_tracked_notes(
    session: Session, tracked_notes: dict[str, str], paths: NotesPaths
) -> tuple[list, list]:
    """
    Sincroniza entradas Note en DB para todos los tracked_notes.
    Retorna (added_notes, updated_notes).
    """
    added_notes: list = []
    updated_notes: list = []
    for filename, reference_name in tracked_notes.items():
        _sync_tracked_note(
            session, filename, reference_name, paths, added_notes, updated_notes
        )
    return added_notes, updated_notes


def _reparse_all_notes(session: Session, paths: NotesPaths) -> None:
    """
    Reparsea labels/citations/links para todas las notas presentes en DB.
    Notas sin archivo físico (NoteNotFound) se omiten silenciosamente.
    """
    all_notes = session.scalars(select(Note)).all()
    for note in all_notes:
        try:
            _update_note_from_file(session, note, paths)
        except NoteNotFound:
            continue


# =============================================================================
# API pública: force_synchronize()
# =============================================================================


def force_synchronize(
    *,
    paths: NotesPaths = DEFAULT_SETTINGS.paths,
    create_missing_note_files: bool = False,
    create_documents_tex_if_missing: bool = True,
    timestamp: Optional[datetime] = None,
) -> ForceSyncResult:
    """
    Sincronización completa (force).

    Flujo:
    1) Lee notes/documents.tex y determina tracked_notes (filename->reference)
    2) Valida que cada filename exista en slipbox; opcionalmente crea archivos faltantes
    3) Sincroniza/crea entradas Note en DB
    4) Reparsea labels/citations/links para todas las notas
    """
    health = ensure_tables()
    if not health.ok:
        raise DomainError(f"DB no disponible: {health.error}")

    doc_path = _resolve_documents_tex(paths, create_documents_tex_if_missing)
    tracked_notes = _parse_tracked_notes(doc_path)
    _ensure_tracked_note_files(paths, tracked_notes, create_missing_note_files)

    with db_session() as session:
        added_notes, updated_notes = _sync_tracked_notes(session, tracked_notes, paths)
        _reparse_all_notes(session, paths)

    return ForceSyncResult(
        tracked_notes=tracked_notes,
        added_notes=added_notes,
        updated_notes=updated_notes,
    )
