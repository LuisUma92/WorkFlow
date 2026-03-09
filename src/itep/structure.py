# src/itep/structure.py
"""
Enums, filesystem helpers, and ProjectModel template.

Dataclasses that were previously used for persistence (Admin, Book, Topic,
MetaData, Evaluation, ProjectStructure) have been replaced by SQLAlchemy
models in itep.database.  This module keeps:

  - Enums: ConfigType, Institution, GeneralDirectory
  - ConfigData: helper for resolving symlink pairs
  - WeekDay: date/time computation for lecture scheduling
  - ProjectModel: template describing directory trees and link rules
"""

from __future__ import annotations
from dataclasses import dataclass, field, fields
from datetime import datetime, date, timezone, timedelta
from enum import StrEnum, EnumType
from typing import Dict, List
from pathlib import Path

from itep.utils import code_format
from appfunc.iofunc import spec


# ── Enums ───────────────────────────────────────────────────────────────


class FriendlyEnumMeta(EnumType):
    def __call__(cls: EnumType, value, *args, **kwargs):
        try:
            return super().__call__(value, *args, **kwargs)
        except ValueError as e:
            valid = ", ".join([m.value for m in cls])
            raise ValueError(
                f"'{value}' no es un valor válido para {cls.__name__}. "
                f"Valores permitidos: {valid}"
            ) from e


class ConfigType(StrEnum, metaclass=FriendlyEnumMeta):
    BASE = "base"
    EVAL = "eval"
    PRESS = "press"


class Institution(StrEnum, metaclass=FriendlyEnumMeta):
    UCR = "UCR"
    FIDE = "UFide"
    UCIMED = "UCIMED"


class GeneralDirectory(StrEnum, metaclass=FriendlyEnumMeta):
    LEC = "00AA-Lectures"
    IMG = "00II-ImagesFigures"
    BIB = "00BB-Library"
    EXE = "00EE-ExamplesExercises"


# ── ConfigData ──────────────────────────────────────────────────────────


@dataclass
class ConfigData:
    name: str
    directory: str
    src: str
    termination: str
    number: int | None

    def __iter__(self):
        yield from ((f.name, getattr(self, f.name)) for f in fields(self))

    def get_relation(self):
        target_file = f"{self.directory}/{self.src}.{self.termination}"
        if self.number:
            link_file = f"{self.number}-{self.name}.{self.termination}"
        else:
            link_file = f"{self.name}.{self.termination}"
        return {link_file: target_file}

    @classmethod
    def from_relations(cls, link: str, target: str) -> ConfigData:
        link_list = link.split("-")
        number = None
        if len(link_list) == 1:
            pass
        elif len(link_list) == 2:
            number = int(link_list[0])
            link = link_list[1]
        else:
            msn = f"invalid link file name {link}"
            raise ValueError(msn)

        name, termination = link.split(".")

        directory, target = target.split("/")
        src, term_test = target.split(".")

        if termination != term_test:
            raise ValueError("link and target have diferent termination")

        return cls(name, directory, src, termination, number)


# ── WeekDay ─────────────────────────────────────────────────────────────


@dataclass
class WeekDay:
    week_number: int = field(
        metadata={
            "input": spec(
                "Enter week number",
                r"[0-9]{1,2}",
                int,
            )
        }
    )
    lecture_day: int = field(
        metadata={
            "input": spec(
                "Enter weed day assosiated (Mon=1,...,Sat=6)",
                r"[1-6]",
                int,
            )
        }
    )
    first_monday: date = field(
        metadata={
            "input": spec(
                "Enter first monday for the lecture cycle as ISO (YYYY-MM-DD)",
                r"([0-9]{4})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])",
                date.fromisoformat,
            )
        }
    )
    init_time: int = field(
        metadata={
            "input": spec(
                "Enter the scheldule initial hour (0-23)",
                r"([01]?\d|2[0-3])",
                int,
            )
        }
    )
    tmz: int = field(
        metadata={
            "input": spec(
                "Enter time zone in range [-24,+24]",
                r"[+-]?([0-9]|[1][0-9]|2[0-4])",
                int,
            )
        }
    )
    code: str = field(init=False)
    day_date: datetime = field(init=False)

    def __post_init__(self):
        self.day_date = datetime.fromisocalendar(
            self.first_monday.isocalendar()[0],
            self.first_monday.isocalendar()[1] + self.week_number,
            self.lecture_day,
        ).replace(
            hour=self.init_time,
            tzinfo=timezone(timedelta(hours=self.tmz)),
        )
        self.code = code_format("W", self.week_number)
        self.code += code_format("L", self.lecture_day)
        self.code += f"D{self.day_date.isoformat()}"

    def __iter__(self):
        yield from ((f.name, getattr(self, f.name)) for f in fields(self))

    def __str__(self):
        return self.code

    def project_repr(self):
        return self.code

    @classmethod
    def fromisoformat(
        cls,
        date_str: str,
        init_time: int,
        tmz: int,
        first: date,
    ) -> WeekDay:
        assigned = date.fromisoformat(date_str)
        week_number = assigned.isocalendar().week - first.isocalendar().week
        lecture_day = assigned.isoweekday()
        return cls(week_number, lecture_day, first, init_time, tmz)


# ── ProjectModel ────────────────────────────────────────────────────────


@dataclass
class ProjectModel:
    name: str = field(default_factory=str)
    parent: Path = field(default_factory=Path)
    root: str = field(default_factory=str)
    patterns: Dict[str, str] = field(default_factory=dict)
    main_topics: Path = field(default_factory=Path)
    tree: List[str] = field(default_factory=list)
    links: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def __iter__(self):
        yield from ((f.name, getattr(self, f.name)) for f in fields(self))
