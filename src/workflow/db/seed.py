"""
Reference data seed for the WorkFlow global database.

Provides INSTITUTIONS_SEED, MAIN_TOPICS_SEED, and seed_reference_data().
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from workflow.db.models.academic import Institution, MainTopic


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

MAIN_TOPICS_SEED: list[dict] = [
    {"name": "Métodos Matemáticos", "code": "01MM", "ddc_mds": "530.15"},
    {"name": "Métodos Numéricos", "code": "02MM", "ddc_mds": "530.15"},
    {"name": "Mecánica Clásica", "code": "10MC", "ddc_mds": "531"},
    {"name": "Ondas", "code": "14MC", "ddc_mds": "534.1"},
    {"name": "Termodinamica", "code": "20TD", "ddc_mds": "536.7"},
    {"name": "Estadística", "code": "21TD", "ddc_mds": "530.13"},
    {"name": "Física Computacional", "code": "22TD", "ddc_mds": "530.0285"},
    {"name": "Optica", "code": "30MO", "ddc_mds": "535"},
    {"name": "Electromagnetismo", "code": "40EM", "ddc_mds": "537.1"},
    {"name": "Mecánica Cuántica", "code": "50MQ", "ddc_mds": "530.12"},
    {"name": "Física Nuclear", "code": "60FN", "ddc_mds": "539.7"},
    {"name": "Estado Sólido", "code": "70ES", "ddc_mds": "531.2"},
    {"name": "Relatividad", "code": "80MR", "ddc_mds": "530.11"},
    {"name": "Relatividad Especial", "code": "81MR", "ddc_mds": "530.11"},
    {"name": "Relatividad General", "code": "82MR", "ddc_mds": "530.11"},
    {"name": "Meteorología", "code": "90FM", "ddc_mds": "532"},
]


def seed_reference_data(session: Session) -> None:
    """Insert institutions and main topics if they do not exist yet."""
    for data in INSTITUTIONS_SEED:
        exists = session.query(Institution).filter_by(
            short_name=data["short_name"]
        ).first()
        if not exists:
            session.add(Institution(**data))

    for data in MAIN_TOPICS_SEED:
        exists = session.query(MainTopic).filter_by(code=data["code"]).first()
        if not exists:
            session.add(MainTopic(**data))

    session.commit()
