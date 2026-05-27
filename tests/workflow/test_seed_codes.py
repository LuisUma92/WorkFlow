"""Tests for ADR ITEP-0008 Phase B: discipline-codes UPSERT loader."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import DisciplineArea
from workflow.db import seed_codes


CSV_HEADER = "Rama,código,Dewey\n"


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    GlobalBase.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


def _write_csv(path: Path, body: str) -> Path:
    path.write_text(CSV_HEADER + body, encoding="utf-8")
    return path


# ── parse_csv ──────────────────────────────────────────────────────────


def test_parse_csv_valid_rows(tmp_path):
    csv = _write_csv(
        tmp_path / "00-PhysicsCodes.csv",
        "Mecánica Clásica,10MC,531-00\nNewton,11MC,531-00\n",
    )
    rows, skipped = seed_codes.parse_csv(csv)
    assert skipped == []
    assert [r.code for r in rows] == ["0010MC", "0011MC"]
    r0 = rows[0]
    assert r0.name == "Mecánica Clásica"
    assert r0.dewey == "531-00"
    assert r0.discipline_num == 0
    assert r0.topic_num == 10
    assert r0.area_initials == "MC"


def test_parse_csv_skips_invalid_codes(tmp_path):
    csv = _write_csv(
        tmp_path / "00-PhysicsCodes.csv",
        "Good,10MC,\nBad,XYZ,\nEmpty,,\n",
    )
    rows, skipped = seed_codes.parse_csv(csv)
    assert [r.code for r in rows] == ["0010MC"]
    assert len(skipped) == 2


def test_parse_csv_blank_lines_ignored(tmp_path):
    csv = _write_csv(
        tmp_path / "00-PhysicsCodes.csv",
        "Mecánica,10MC,\n\n,,\nNewton,11MC,\n",
    )
    rows, skipped = seed_codes.parse_csv(csv)
    assert [r.code for r in rows] == ["0010MC", "0011MC"]
    assert skipped == []


def test_parse_csv_bad_header_raises(tmp_path):
    csv = tmp_path / "00-Bad.csv"
    csv.write_text("foo,bar,baz\nMec,10MC,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected header"):
        seed_codes.parse_csv(csv)


# ── UPSERT semantics ───────────────────────────────────────────────────


def test_upsert_inserts_new_row(session, tmp_path):
    csv = _write_csv(tmp_path / "00-PhysicsCodes.csv", "Mecánica,10MC,531-00\n")
    report = seed_codes.upsert_from_csv(session, csv)
    assert report.inserted == ["0010MC"]
    assert report.updated == []
    row = session.query(DisciplineArea).filter_by(code="0010MC").one()
    assert row.name == "Mecánica"
    assert row.dewey == "531-00"
    assert row.discipline_num == 0
    assert row.area_initials == "MC"


def test_upsert_idempotent_second_run(session, tmp_path):
    csv = _write_csv(tmp_path / "00-PhysicsCodes.csv", "Mecánica,10MC,531-00\n")
    seed_codes.upsert_from_csv(session, csv)
    report = seed_codes.upsert_from_csv(session, csv)
    assert report.inserted == []
    assert report.updated == []
    assert report.unchanged == ["0010MC"]
    assert session.query(DisciplineArea).count() == 1


def test_upsert_updates_changed_name(session, tmp_path):
    csv = _write_csv(tmp_path / "00-PhysicsCodes.csv", "Mecánica,10MC,531-00\n")
    seed_codes.upsert_from_csv(session, csv)
    csv2 = _write_csv(
        tmp_path / "00-PhysicsCodes.csv", "Mecánica Clásica,10MC,531-00\n"
    )
    report = seed_codes.upsert_from_csv(session, csv2)
    assert report.updated == ["0010MC"]
    row = session.query(DisciplineArea).filter_by(code="0010MC").one()
    assert row.name == "Mecánica Clásica"


def test_upsert_updates_changed_dewey(session, tmp_path):
    csv = _write_csv(tmp_path / "00-PhysicsCodes.csv", "Mecánica,10MC,531-00\n")
    seed_codes.upsert_from_csv(session, csv)
    csv2 = _write_csv(tmp_path / "00-PhysicsCodes.csv", "Mecánica,10MC,531-99\n")
    report = seed_codes.upsert_from_csv(session, csv2)
    assert report.updated == ["0010MC"]
    row = session.query(DisciplineArea).filter_by(code="0010MC").one()
    assert row.dewey == "531-99"


def test_upsert_never_deletes_missing_row(session, tmp_path):
    csv1 = _write_csv(
        tmp_path / "00-PhysicsCodes.csv",
        "Mecánica,10MC,\nNewton,11MC,\n",
    )
    seed_codes.upsert_from_csv(session, csv1)
    # Second run drops 11MC from CSV — DB row must persist.
    csv2 = _write_csv(tmp_path / "00-PhysicsCodes.csv", "Mecánica,10MC,\n")
    seed_codes.upsert_from_csv(session, csv2)
    codes = {r.code for r in session.query(DisciplineArea).all()}
    assert codes == {"0010MC", "0011MC"}


# ── upsert_all_csvs ────────────────────────────────────────────────────


def test_upsert_all_csvs_loads_every_file(session, tmp_path):
    _write_csv(tmp_path / "00-PhysicsCodes.csv", "Mecánica,10MC,\n")
    _write_csv(tmp_path / "01-PhilosophyCodes.csv", "Lógica,10LO,\n")
    # Non-matching file should be ignored.
    (tmp_path / "books.json").write_text("{}", encoding="utf-8")
    report = seed_codes.upsert_all_csvs(session, tmp_path)
    assert set(report.inserted) == {"0010MC", "0110LO"}
    assert session.query(DisciplineArea).count() == 2


def test_default_data_dir_exists():
    assert seed_codes.default_data_dir().is_dir()


# ── seed_reference_data wiring ─────────────────────────────────────────


def test_seed_reference_data_imports_discipline_codes(session, tmp_path):
    from workflow.db.seed import seed_reference_data

    _write_csv(tmp_path / "00-PhysicsCodes.csv", "Mecánica,10MC,531-00\n")
    seed_reference_data(session, data_dir=tmp_path)
    assert (
        session.query(DisciplineArea).filter_by(code="0010MC").one().name == "Mecánica"
    )


def test_seed_reference_data_skip_codes(session, tmp_path):
    from workflow.db.seed import seed_reference_data

    _write_csv(tmp_path / "00-PhysicsCodes.csv", "Mecánica,10MC,\n")
    seed_reference_data(session, data_dir=tmp_path, import_discipline_codes=False)
    assert session.query(DisciplineArea).count() == 0
