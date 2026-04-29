"""
Discipline area code loader (ADR ITEP-0008, Phase B).

Reads ``data/DD-*Codes.csv`` (header ``Rama,código,Dewey``) and UPSERTs rows
into the :class:`workflow.db.models.academic.DisciplineArea` reference table.

Semantics:
  * Insert when ``code`` not present.
  * Update ``name`` and/or ``dewey`` when the CSV row differs from the DB row.
  * Never DELETE — rows missing from the CSV are preserved.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from workflow.db.models.academic import DisciplineArea


CODE_FILE_GLOB = "[0-9][0-9]-*Codes.csv"
_CSV_CODE_RE = re.compile(r"^(\d{2})([A-Z]{2})$")
_FILENAME_RE = re.compile(r"^(\d{2})-")
_EXPECTED_HEADER = ("Rama", "código", "Dewey")


@dataclass(frozen=True)
class CodeRow:
    code: str
    name: str
    dewey: str

    @property
    def discipline_num(self) -> int:
        return int(self.code[0:2])

    @property
    def topic_num(self) -> int:
        return int(self.code[2:4])

    @property
    def area_initials(self) -> str:
        return self.code[4:6]


@dataclass
class UpsertReport:
    inserted: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped: list[tuple[int, str]] = field(default_factory=list)

    def merge(self, other: "UpsertReport") -> None:
        self.inserted.extend(other.inserted)
        self.updated.extend(other.updated)
        self.unchanged.extend(other.unchanged)
        self.skipped.extend(other.skipped)

    @property
    def changed(self) -> bool:
        return bool(self.inserted or self.updated)


def discipline_prefix_from_filename(csv_path: Path) -> str:
    """Extract the two-digit discipline prefix from a ``DD-*.csv`` filename."""
    m = _FILENAME_RE.match(csv_path.name)
    if not m:
        raise ValueError(f"{csv_path.name}: filename must start with two digits + '-'")
    return m.group(1)


def parse_csv(csv_path: Path) -> tuple[list[CodeRow], list[tuple[int, str]]]:
    """Parse a discipline-codes CSV file. Returns (rows, skipped).

    The CSV ``código`` column carries the 4-char ``TTAA`` portion; the
    2-char discipline prefix ``DD`` is taken from the filename. The full
    6-char ``DDTTAA`` code is stored on the resulting :class:`CodeRow`.
    """
    rows: list[CodeRow] = []
    skipped: list[tuple[int, str]] = []
    dd = discipline_prefix_from_filename(csv_path)
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            return rows, skipped
        if tuple(h.strip() for h in header[:3]) != _EXPECTED_HEADER:
            raise ValueError(
                f"{csv_path.name}: expected header {_EXPECTED_HEADER}, "
                f"got {tuple(header)}"
            )
        for lineno, raw in enumerate(reader, start=2):
            cells = [c.strip() for c in raw] if raw else []
            if not cells or all(c == "" for c in cells):
                continue
            if len(cells) < 2:
                skipped.append((lineno, f"too few columns: {raw!r}"))
                continue
            name, csv_code = cells[0], cells[1]
            dewey = cells[2] if len(cells) >= 3 else ""
            if not _CSV_CODE_RE.match(csv_code):
                skipped.append((lineno, f"invalid code {csv_code!r}"))
                continue
            if not name:
                skipped.append((lineno, "empty name"))
                continue
            full_code = f"{dd}{csv_code}"
            rows.append(CodeRow(code=full_code, name=name, dewey=dewey))
    return rows, skipped


def upsert_rows(session: Session, rows: Iterable[CodeRow]) -> UpsertReport:
    """UPSERT a batch of CodeRow into DisciplineArea. Caller commits."""
    report = UpsertReport()
    for row in rows:
        existing = session.query(DisciplineArea).filter_by(code=row.code).first()
        if existing is None:
            session.add(
                DisciplineArea(
                    code=row.code,
                    name=row.name,
                    dewey=row.dewey,
                    discipline_num=row.discipline_num,
                    topic_num=row.topic_num,
                    area_initials=row.area_initials,
                )
            )
            report.inserted.append(row.code)
            continue
        changed = False
        if existing.name != row.name:
            existing.name = row.name
            changed = True
        if existing.dewey != row.dewey:
            existing.dewey = row.dewey
            changed = True
        # Re-derive numeric fields in case prior import was wrong.
        if existing.discipline_num != row.discipline_num:
            existing.discipline_num = row.discipline_num
            changed = True
        if existing.topic_num != row.topic_num:
            existing.topic_num = row.topic_num
            changed = True
        if existing.area_initials != row.area_initials:
            existing.area_initials = row.area_initials
            changed = True
        if changed:
            report.updated.append(row.code)
        else:
            report.unchanged.append(row.code)
    return report


def upsert_from_csv(session: Session, csv_path: Path) -> UpsertReport:
    """Load one CSV and UPSERT into DisciplineArea. Commits on success."""
    rows, skipped = parse_csv(csv_path)
    report = upsert_rows(session, rows)
    report.skipped.extend(skipped)
    session.commit()
    return report


def discover_csvs(data_dir: Path) -> list[Path]:
    return sorted(data_dir.glob(CODE_FILE_GLOB))


def upsert_all_csvs(session: Session, data_dir: Path) -> UpsertReport:
    """UPSERT every ``DD-*Codes.csv`` under ``data_dir``. Single commit."""
    aggregate = UpsertReport()
    for csv_path in discover_csvs(data_dir):
        rows, skipped = parse_csv(csv_path)
        per_file = upsert_rows(session, rows)
        per_file.skipped.extend(skipped)
        aggregate.merge(per_file)
    session.commit()
    return aggregate


def default_data_dir() -> Path:
    """Return the repo's bundled ``data/`` directory."""
    return Path(__file__).resolve().parents[3] / "data"
