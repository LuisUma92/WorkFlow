# src/itep/structures.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import StrEnum, Enum
from typing import Any, Dict, List
from pathlib import Path

from itep.utils import code_format, gather_input, select_enum_type

# --- Constantes por defecto ---
DEF_ABS_PARENT_DIR = Path("/home/luis/Documents/01-U/00-Fisica")
DEF_ABS_SRC_DIR = Path("/home/luis/.config/mytex")

DEF_ADMIN_PATTERNS = {
    "total_week_count": {
        "type": int,
        "msn": "Enter the total number of weeks:\n\t<< ",
        "pattern": "^[0-9]+",
    },
    "lectures_per_week": {
        "type": int,
        "msn": "Enter the total amount of lectures per week\n\t<< ",
        "pattern": "^[0-5]{1}",
    },
    "year": {
        "type": int,
        "msn": "Enter the year of the lecture\n\t<< ",
        "pattern": "^[0-9]{4}",
    },
    "cycle": {
        "type": int,
        "msn": "Enter current cycle for the lecture\n\t<< ",
        "pattern": "^[1-3]{1}",
    },
    "first_monday": {
        "type": date.fromisoformat,
        "msn": "Enter the first monday for the lecture cycle\n\t<< ",
        "pattern": "^([0-9]{4})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])",
    },
    "week_day": {
        "type": int,
        "msn": "Enter the lecture day {day}:\n\t<< ",
        "pattern": "^[1-5]{1}",
    },
}


class ConfigType(StrEnum):
    BASE = "base"
    EVAL = "eval"
    PRESS = "press"


class Institution(StrEnum):
    UCR = "UCR"
    FIDE = "UFide"
    UCIMED = "UCIMED"


class GeneralDirectory(StrEnum):
    LEC = "00AA-Lectures"
    IMG = "00II-ImagesFigures"
    BIB = "00BB-Library"
    EXE = "00EE-ExamplesExercises"


class ProjectType(Enum):
    GENE = {
        "name": "general",
        "parent": DEF_ABS_PARENT_DIR,
        "root": "{code}-{name}",
        "patterns": {
            "numbering": "^[0-9]{2}",
            "initials": "^[A-Z]{2}",
        },
        "main_topics": DEF_ABS_PARENT_DIR / GeneralDirectory.BIB,
    }
    LECT = {
        "name": "lecture",
        "parent": DEF_ABS_PARENT_DIR / GeneralDirectory.LEC,
        "root": "{institution}-{code}",
        "patterns": {
            "numbering": "^[0-9]{4}",
            "initials": "^[A-Z]{2}",
        },
        "main_topics": DEF_ABS_PARENT_DIR,
    }


# ==================== Dataclass base ====================


@dataclass
class ConfigData:
    name: str
    type: str
    src: Any[str, List]
    termination: str
    number: int | None

    def get_relation(self):
        target_file = ".".join([self.src, self.termination])
        link_file = f"{self.number}-{self.name}.{self.termination}"
        return {link_file: target_file}


@dataclass
class TexConfig:
    defaults_config: List[ConfigData] = field(
        default_factory=lambda: [
            ConfigData(
                "packages",
                "sty",
                "SetFormat",
                "sty",
                0,
            ),
            ConfigData(
                "loyaut",
                "sty",
                "SetLoyaut",
                "sty",
                1,
            ),
            ConfigData(
                "commands",
                "sty",
                "SetCommands",
                "sty",
                2,
            ),
            ConfigData(
                "partial",
                "sty",
                "PartialCommands",
                "sty",
                2,
            ),
            ConfigData(
                "units",
                "sty",
                "SetUnits",
                "sty",
                3,
            ),
            ConfigData(
                "symbols",
                "sty",
                "SetSymbols",
                "sty",
                3,
            ),
            ConfigData(
                "profiles",
                "sty",
                "SetProfiles",
                "sty",
                5,
            ),
            ConfigData(
                "headers",
                "sty",
                "SetHeaders",
                "sty",
                6,
            ),
            ConfigData(
                "title",
                "template",
                "title",
                "tex",
                None,
            ),
            ConfigData(
                "instructions",
                "template",
                ["UCR-PPI", "UCIMED-PPI", "UFideCase"],
                "tex",
                None,
            ),
        ]
    )


@dataclass
class MetaData:
    # absolute routes
    abs_parent_dir: Path = DEF_ABS_PARENT_DIR
    abs_src_dir: Path = DEF_ABS_SRC_DIR
    # Metadata and patterns
    created_at: datetime = field(default_factory=datetime.now)
    last_modification: datetime = field(default_factory=datetime.now)
    version: str = "1.0.0"


@dataclass
class Admin:
    institution: Institution
    total_week_count: int
    lectures_per_week: int
    year: int
    cycle: int
    first_monday: date
    week_day: List[int]

    def set_institution(self) -> None:
        self.institution = select_enum_type(
            "institution name",
            Institution,
        )

    def set_total_week_count(self) -> None:
        self.total_week_count = int(
            gather_input(
                DEF_ADMIN_PATTERNS["total_week_count"]["msn"],
                DEF_ADMIN_PATTERNS["total_week_count"]["pattern"],
            )
        )

    def set_lectures_per_week(self) -> None:
        self.lectures_per_week = int(
            gather_input(
                DEF_ADMIN_PATTERNS["lectures_per_week"]["msn"],
                DEF_ADMIN_PATTERNS["lectures_per_week"]["pattern"],
            )
        )

    def set_year(self) -> None:
        self.year = int(
            gather_input(
                DEF_ADMIN_PATTERNS["year"]["msn"],
                DEF_ADMIN_PATTERNS["year"]["pattern"],
            )
        )

    def set_cycle(self) -> None:
        self.cycle = int(
            gather_input(
                DEF_ADMIN_PATTERNS["cycle"]["msn"],
                DEF_ADMIN_PATTERNS["cycle"]["pattern"],
            )
        )

    def set_first_monday(self) -> None:
        self.first_monday = date.fromisoformat(
            gather_input(
                DEF_ADMIN_PATTERNS["first_monday"]["msn"],
                DEF_ADMIN_PATTERNS["first_monday"]["pattern"],
            )
        )

    def set_week_day(self, lectures_per_week) -> None:
        self.week_day = []
        for d in range(lectures_per_week):
            self.week_day.append(
                int(
                    gather_input(
                        DEF_ADMIN_PATTERNS["week_day"]["msn"].format(day=d),
                        DEF_ADMIN_PATTERNS["week_day"]["pattern"],
                    )
                )
            )

    @classmethod
    def gather_info(cls) -> Admin:
        institution = select_enum_type(
            "institution name",
            Institution,
        )
        var_dic = {}
        for var, content in DEF_ADMIN_PATTERNS.items():
            if var != "week_day":
                var_dic[var] = content["type"](
                    gather_input(
                        content["msn"],
                        content["pattern"],
                    )
                )
            else:
                days_list = []
                for day in range(var_dic["lectures_per_week"]):
                    days_list.append(
                        content["type"](
                            gather_input(
                                content["msn"].format(day=day),
                                content["pattern"],
                            )
                        )
                    )
                    var_dic[var] = days_list

        return cls(
            institution,
            var_dic["total_week_count"],
            var_dic["lectures_per_week"],
            var_dic["year"],
            var_dic["cycle"],
            var_dic["first_monday"],
            var_dic["week_day"],
        )


@dataclass
class Book:
    code: str
    name: str
    edition: int

    def get_dir_name(self):
        return f"{self.code}_{self.name.capitalize()}_{self.edition}"

    @classmethod
    def from_directory(cls, path: Path) -> Book:
        book_list = StrEnum(
            "book",
            [b.name for b in path.iterdir() if b.is_file()],
        )
        print(book_list)
        selected_book = select_enum_type("book", book_list)
        book_name = selected_book.value.split("_")
        return cls(book_name[0], book_name[1], book_name[2])


@dataclass
class WeekDay:
    week_number: int
    lecture_day: int
    admin: Admin
    code: str = field(init=False)
    date: datetime = field(init=False)

    def __post_init__(self):
        self.date = datetime.fromisocalendar(
            self.admin.year,
            self.admin.first_monday.isocalendar()[1] + self.week_number,
            self.admin.week_day[self.lecture_day - 1],
        )
        self.code = code_format("W", self.week_number)
        self.code += code_format("L", self.lecture_day)


@dataclass
class Topic:
    name: str
    chapters: List[str]
    weeks: List[WeekDay] | None = None

    @classmethod
    def from_directory(cls, path: Path) -> Topic:
        return cls("", [], None)


@dataclass
class Evaluation:
    amount: int
    duedate: List[WeekDay]


@dataclass
class EvalInstruments:
    partial: Evaluation | None = None
    quiz: Evaluation | None = None
    homework: Evaluation | None = None
    project: Evaluation | None = None


@dataclass
class ProjectStructure:
    """
    This is a general structure that every project file should implement this
    to its specific needs
    """

    code: str
    name: str
    project_type: ProjectType
    root: str = field(init=False)
    data: MetaData = field(default_factory=MetaData)
    admin: Admin | None = None
    main_topic_root: List[str] = field(default_factory=list)
    books: Dict[str, Book] = field(default_factory=dict)
    topics: Dict[str, Topic] = field(default_factory=dict)

    def __post_init__(self):
        institution = None
        if self.admin:
            institution = self.admin.institution.value
        self.root = self.project_type.value["root"].format(
            name=self.name,
            code=self.code,
            institution=institution,
        )
