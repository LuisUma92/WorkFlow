"""Tests for workflow.vault.unify — ITEP-0011 P2."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from workflow.db.base import GlobalBase, LocalBase
import workflow.db.models.academic  # noqa: F401
import workflow.db.models.notes  # noqa: F401
from workflow.db.models.notes import Citation, Label, Link, Note, Tag
from workflow.vault.unify import VAULT_POINTER_FILE, unify


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def global_session():
    engine = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(engine)
    LocalBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session


@pytest.fixture()
def vault_root(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    for sub in ("permanent", "literature", "fleeting"):
        (root / "notes" / sub).mkdir(parents=True)
    return root


@pytest.fixture()
def backup_dir(tmp_path: Path) -> Path:
    d = tmp_path / "backups"
    d.mkdir()
    return d


def _make_project(
    tmp_path: Path,
    name: str = "01PHTH-2503-thesis",
    notes: list[dict] | None = None,
    labels: list[dict] | None = None,
    links: list[dict] | None = None,
    citations: list[dict] | None = None,
    tags: list[dict] | None = None,
    note_tags: list[dict] | None = None,
    md_files: list[tuple[str, str]] | None = None,
) -> Path:
    project = tmp_path / name
    project.mkdir()
    db_path = project / "slipbox.db"

    # Mirror only the legacy fields the reader queries.
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE note (
            id INTEGER PRIMARY KEY,
            filename TEXT NOT NULL UNIQUE,
            reference TEXT NOT NULL UNIQUE,
            last_build_date_html TEXT,
            last_build_date_pdf TEXT,
            last_edit_date TEXT,
            created TEXT,
            title TEXT,
            note_type TEXT,
            source_format TEXT,
            zettel_id TEXT UNIQUE
        );
        CREATE TABLE citation (
            id INTEGER PRIMARY KEY, note_id INTEGER, citationkey TEXT
        );
        CREATE TABLE label (
            id INTEGER PRIMARY KEY, note_id INTEGER, label TEXT
        );
        CREATE TABLE link (
            id INTEGER PRIMARY KEY, source_id INTEGER, target_id INTEGER
        );
        CREATE TABLE tag (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
        CREATE TABLE note_tag (note_id INTEGER, tag_id INTEGER);
        """
    )
    for n in notes or []:
        conn.execute(
            "INSERT INTO note (id, filename, reference, title, note_type, "
            "source_format, zettel_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                n["id"],
                n["filename"],
                n["reference"],
                n.get("title"),
                n.get("note_type"),
                n.get("source_format", "md"),
                n.get("zettel_id"),
            ),
        )
    for lab in labels or []:
        conn.execute(
            "INSERT INTO label VALUES (?, ?, ?)",
            (lab["id"], lab["note_id"], lab["label"]),
        )
    for ln in links or []:
        conn.execute(
            "INSERT INTO link VALUES (?, ?, ?)",
            (ln["id"], ln["source_id"], ln["target_id"]),
        )
    for c in citations or []:
        conn.execute(
            "INSERT INTO citation VALUES (?, ?, ?)",
            (c["id"], c["note_id"], c["citationkey"]),
        )
    for t in tags or []:
        conn.execute("INSERT INTO tag VALUES (?, ?)", (t["id"], t["name"]))
    for nt in note_tags or []:
        conn.execute(
            "INSERT INTO note_tag VALUES (?, ?)", (nt["note_id"], nt["tag_id"])
        )
    conn.commit()
    conn.close()

    if md_files:
        notes_dir = project / "notes"
        notes_dir.mkdir(exist_ok=True)
        for filename, body in md_files:
            (notes_dir / filename).write_text(body, encoding="utf-8")

    return project


# ── Tests ───────────────────────────────────────────────────────────────────


def test_unify_empty_slipbox(tmp_path, vault_root, backup_dir, global_session):
    project = _make_project(tmp_path, notes=[])
    report = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        dry_run=False,
    )
    assert report.notes_migrated == 0
    assert (project / VAULT_POINTER_FILE).exists()


def test_unify_single_project_round_trip(
    tmp_path, vault_root, backup_dir, global_session
):
    project = _make_project(
        tmp_path,
        notes=[
            {
                "id": 1,
                "filename": "n1.md",
                "reference": "ref-001",
                "title": "First",
                "note_type": "permanent",
            }
        ],
        labels=[{"id": 1, "note_id": 1, "label": "lab1"}],
        citations=[{"id": 1, "note_id": 1, "citationkey": "smith2020"}],
        tags=[{"id": 1, "name": "physics"}],
        note_tags=[{"note_id": 1, "tag_id": 1}],
    )
    report = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        dry_run=False,
    )
    global_session.commit()
    assert report.notes_migrated == 1
    assert report.labels_migrated == 1
    assert report.citations_migrated == 1
    assert report.tags_migrated == 1
    assert report.note_tags_migrated == 1
    assert global_session.query(Note).count() == 1
    assert global_session.query(Label).count() == 1
    assert global_session.query(Citation).count() == 1
    assert global_session.query(Tag).filter_by(name="physics").one()


def test_unify_id_collision_with_project_prefix(
    tmp_path, vault_root, backup_dir, global_session
):
    global_session.add(Note(filename="existing.md", reference="ref-dup"))
    global_session.commit()
    project = _make_project(
        tmp_path,
        notes=[
            {
                "id": 1,
                "filename": "n.md",
                "reference": "ref-dup",
                "note_type": "permanent",
            }
        ],
    )
    report = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        rename_strategy="project-prefix",
        dry_run=False,
    )
    global_session.commit()
    assert "ref-dup" in report.collisions
    assert report.notes_migrated == 1
    refs = {r for (r,) in global_session.query(Note.reference).all()}
    assert any(r.endswith(":ref-dup") for r in refs)


def test_unify_id_collision_abort(tmp_path, vault_root, backup_dir, global_session):
    global_session.add(Note(filename="x.md", reference="ref-dup"))
    global_session.commit()
    project = _make_project(
        tmp_path,
        notes=[{"id": 1, "filename": "n.md", "reference": "ref-dup"}],
    )
    with pytest.raises(ValueError):
        unify(
            project,
            vault_root,
            backup_dir=backup_dir,
            global_session=global_session,
            rename_strategy="abort",
            dry_run=False,
        )
    assert global_session.query(Note).count() == 1
    assert not (project / VAULT_POINTER_FILE).exists()


def test_unify_dry_run_no_writes(tmp_path, vault_root, backup_dir, global_session):
    project = _make_project(
        tmp_path,
        notes=[
            {
                "id": 1,
                "filename": "n.md",
                "reference": "ref-1",
                "note_type": "permanent",
            }
        ],
        md_files=[("n.md", "# n")],
    )
    report = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        dry_run=True,
    )
    global_session.commit()
    assert report.dry_run
    assert global_session.query(Note).count() == 0
    assert (project / "notes" / "n.md").exists()
    assert not (project / VAULT_POINTER_FILE).exists()
    assert list(backup_dir.iterdir()) == []


def test_unify_idempotent(tmp_path, vault_root, backup_dir, global_session):
    project = _make_project(
        tmp_path,
        notes=[
            {
                "id": 1,
                "filename": "n.md",
                "reference": "ref-x",
                "note_type": "permanent",
            }
        ],
    )
    unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        dry_run=False,
    )
    global_session.commit()
    report2 = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        dry_run=False,
    )
    assert report2.skipped
    assert global_session.query(Note).count() == 1


def test_unify_backup_created(tmp_path, vault_root, backup_dir, global_session):
    project = _make_project(
        tmp_path,
        notes=[{"id": 1, "filename": "n.md", "reference": "ref-b"}],
    )
    report = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        dry_run=False,
    )
    assert report.backup_path is not None
    assert report.backup_path.exists()
    assert report.backup_path.stat().st_size > 0


def test_unify_rewrites_link_fks(tmp_path, vault_root, backup_dir, global_session):
    project = _make_project(
        tmp_path,
        notes=[
            {"id": 1, "filename": "a.md", "reference": "a"},
            {"id": 2, "filename": "b.md", "reference": "b"},
        ],
        labels=[{"id": 10, "note_id": 2, "label": "tgt"}],
        links=[{"id": 1, "source_id": 1, "target_id": 10}],
    )
    report = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        dry_run=False,
    )
    global_session.commit()
    assert report.links_migrated == 1
    link = global_session.query(Link).one()
    note_a = global_session.query(Note).filter_by(reference="a").one()
    label_t = global_session.query(Label).filter_by(label="tgt").one()
    assert link.source_id == note_a.id
    assert link.target_id == label_t.id


def test_unify_moves_md_files(tmp_path, vault_root, backup_dir, global_session):
    project = _make_project(
        tmp_path,
        notes=[
            {
                "id": 1,
                "filename": "n1.md",
                "reference": "r-1",
                "note_type": "literature",
            }
        ],
        md_files=[("n1.md", "# n1")],
    )
    report = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        dry_run=False,
    )
    global_session.commit()
    assert report.files_moved == 1
    assert (vault_root / "notes" / "literature" / "n1.md").exists()
    assert not (project / "notes" / "n1.md").exists()
    assert (project / VAULT_POINTER_FILE).exists()


def test_unify_orphan_link_detection(tmp_path, vault_root, backup_dir, global_session):
    project = _make_project(
        tmp_path,
        notes=[{"id": 1, "filename": "a.md", "reference": "a"}],
        links=[{"id": 1, "source_id": 1, "target_id": 999}],
    )
    report = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        dry_run=False,
    )
    global_session.commit()
    assert report.orphans == [1]
    assert global_session.query(Link).count() == 0


# ── Post-review additions ───────────────────────────────────────────────────


def test_unify_manual_strategy_records_skipped(
    tmp_path, vault_root, backup_dir, global_session
):
    """Manual strategy records colliding refs in skipped_collisions and skips
    them — they must NOT silently land in the global DB."""
    global_session.add(Note(filename="x.md", reference="ref-dup"))
    global_session.commit()
    before = global_session.query(Note).count()
    project = _make_project(
        tmp_path,
        notes=[
            {"id": 1, "filename": "n.md", "reference": "ref-dup"},
            {"id": 2, "filename": "ok.md", "reference": "ref-ok"},
        ],
    )
    report = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        rename_strategy="manual",
        dry_run=False,
    )
    global_session.commit()
    assert "ref-dup" in report.collisions
    assert "ref-dup" in report.skipped_collisions
    assert report.notes_migrated == 1  # only ref-ok migrated
    assert global_session.query(Note).count() == before + 1


def test_unify_partial_collision_mixed_batch(
    tmp_path, vault_root, backup_dir, global_session
):
    """project-prefix renames the collider; clean refs migrate verbatim."""
    global_session.add(Note(filename="x.md", reference="ref-1"))
    global_session.commit()
    project = _make_project(
        tmp_path,
        notes=[
            {"id": 1, "filename": "a.md", "reference": "ref-1"},  # collides
            {"id": 2, "filename": "b.md", "reference": "ref-2"},  # clean
            {"id": 3, "filename": "c.md", "reference": "ref-3"},  # clean
        ],
    )
    report = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        rename_strategy="project-prefix",
        dry_run=False,
    )
    global_session.commit()
    assert report.notes_migrated == 3
    assert report.skipped_collisions == []
    refs = {r for (r,) in global_session.query(Note.reference).all()}
    assert "ref-2" in refs and "ref-3" in refs
    assert any(r.endswith(":ref-1") for r in refs)


def test_unify_md_target_already_exists(
    tmp_path, vault_root, backup_dir, global_session
):
    """Pre-existing target file → incoming file gets a project-prefixed name."""
    (vault_root / "notes" / "permanent" / "n1.md").write_text("existing")
    project = _make_project(
        tmp_path,
        notes=[
            {"id": 1, "filename": "n1.md", "reference": "r-1", "note_type": "permanent"}
        ],
        md_files=[("n1.md", "# new")],
    )
    report = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        dry_run=False,
    )
    assert report.files_moved == 1
    assert (vault_root / "notes" / "permanent" / "n1.md").read_text() == "existing"
    moved = list((vault_root / "notes" / "permanent").glob("*-n1.md"))
    assert len(moved) == 1
    assert moved[0].read_text() == "# new"


def test_unify_slipbox_missing_skips_gracefully(
    tmp_path, vault_root, backup_dir, global_session
):
    project = tmp_path / "no-db-project"
    project.mkdir()
    report = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        dry_run=False,
    )
    assert report.skipped
    assert "slipbox" in report.skip_reason


def test_unify_vault_root_missing_raises(tmp_path, backup_dir, global_session):
    project = _make_project(tmp_path, notes=[])
    with pytest.raises(FileNotFoundError):
        unify(
            project,
            tmp_path / "does-not-exist",
            backup_dir=backup_dir,
            global_session=global_session,
        )


def test_unify_sanitizes_unsafe_project_name(
    tmp_path, vault_root, backup_dir, global_session
):
    """A project_root.name with shell/glob characters and whitespace
    must be reduced to filesystem-safe characters before composition
    into backup filenames or Note.filename."""
    project = _make_project(
        tmp_path,
        name="proj:weird name * with $shell",
        notes=[{"id": 1, "filename": "n.md", "reference": "r-x"}],
    )
    report = unify(
        project,
        vault_root,
        backup_dir=backup_dir,
        global_session=global_session,
        dry_run=False,
    )
    unsafe = {":", " ", "*", "$"}
    assert not any(ch in report.project_name for ch in unsafe)
    assert report.backup_path is not None
    assert not any(ch in report.backup_path.name for ch in unsafe)
