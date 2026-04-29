"""
Discipline taxonomy registry (ADR ITEP-0009 Part I).

Single source of truth for the human-readable name attached to each two-digit
``DD`` discipline code. The codes themselves and the area/topic tree are
defined by ``data/DD-*Codes.csv`` files, loaded into the
:class:`workflow.db.models.academic.DisciplineArea` table by
``workflow.db.seed_codes`` (see ITEP-0008 Phase B).

This module deliberately stays thin: it exposes the registry as a constant,
joins it with the bundled CSV files for agent consumption, and offers no
write operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workflow.db.seed_codes import default_data_dir, discover_csvs


DISCIPLINES: dict[int, str] = {
    0: "Física",
    1: "Filosofía",
    2: "Informática",
    3: "Docencia",
    4: "Lingüística",
    5: "Ciencias de la Salud",
    6: "Ingeniería Práctica",
    7: "Música",
    8: "Artes Visuales",
    9: "Agronomía y Sostenibilidad",
}

HOBBY_DD_THRESHOLD = 4
"""Disciplines with ``dd >= HOBBY_DD_THRESHOLD`` use hobby maturation
thresholds per ADR ITEP-0009 Part II."""


@dataclass(frozen=True)
class DisciplineInfo:
    dd: int
    name: str
    csv_path: Path | None
    hobby: bool

    @property
    def code_prefix(self) -> str:
        return f"{self.dd:02d}"


def discover_disciplines(data_dir: Path | None = None) -> list[DisciplineInfo]:
    """Join :data:`DISCIPLINES` with bundled CSVs.

    A registry entry without a matching ``DD-*Codes.csv`` returns
    ``csv_path=None`` so agents can flag the gap without crashing.
    """
    target = data_dir if data_dir is not None else default_data_dir()
    csv_by_dd: dict[int, Path] = {}
    if target.exists():
        for path in discover_csvs(target):
            try:
                dd = int(path.name[:2])
            except ValueError:
                continue
            csv_by_dd.setdefault(dd, path)
    return [
        DisciplineInfo(
            dd=dd,
            name=name,
            csv_path=csv_by_dd.get(dd),
            hobby=dd >= HOBBY_DD_THRESHOLD,
        )
        for dd, name in sorted(DISCIPLINES.items())
    ]


def is_hobby(dd: int) -> bool:
    """Return True if discipline ``dd`` falls under the hobby thresholds."""
    return dd >= HOBBY_DD_THRESHOLD
