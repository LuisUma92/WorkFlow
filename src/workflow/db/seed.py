"""
Reference data seed for the WorkFlow global database.

Provides INSTITUTIONS_SEED and seed_reference_data(). MainTopic rows are
no longer seeded statically; they are created on-demand by inittex from
DisciplineArea catalog rows (ADR ITEP-0008, ITEP-0010 amendment 0002).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from workflow.db import seed_codes
from workflow.db.models.academic import Institution


INSTITUTIONS_SEED: list[dict] = [
    {
        "short_name": "UCR",
        "full_name": "Universidad de Costa Rica",
        "cycle_weeks": 18,
        "cycle_name": "Semestre",
        "moodle_url": "mv.mediacionvirtual.ucr.ac.cr",
    },
    {
        "short_name": "UFide",
        "full_name": "Universidad Fidélitas",
        "cycle_weeks": 15,
        "cycle_name": "Cuatrimestre",
        "moodle_url": "www.fidevirtual.org",
    },
    {
        "short_name": "UCIMED",
        "full_name": "Universidad de las Ciencias Médicas",
        "cycle_weeks": 24,
        "cycle_name": "Semestre",
        "moodle_url": "uvirtual.ucimed.com",
    },
]


def seed_reference_data(
    session: Session,
    *,
    data_dir: Path | None = None,
    import_discipline_codes: bool = True,
) -> None:
    """Insert institutions and discipline-area codes if absent.

    Discipline codes are loaded from ``data/DD-*Codes.csv`` via
    :func:`workflow.db.seed_codes.upsert_all_csvs` (idempotent UPSERT).
    MainTopic rows are created on-demand by ``inittex`` (ADR ITEP-0008).
    """
    for data in INSTITUTIONS_SEED:
        exists = (
            session.query(Institution).filter_by(short_name=data["short_name"]).first()
        )
        if not exists:
            session.add(Institution(**data))

    session.commit()

    if import_discipline_codes:
        target = data_dir or seed_codes.default_data_dir()
        if target.exists():
            seed_codes.upsert_all_csvs(session, target)
