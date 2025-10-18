# src/itep/structures.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Dict, List, Optional
from pathlib import Path

from itep.utils import code_format


class ProjectType(StrEnum):
    LECT = "lecture"
    GENE = "general"


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


# --- Constantes por defecto ---
DEF_ABS_PARENT_DIR = Path("/home/luis/Documents/01-U/00-Fisica")
DEF_ABS_SRC_DIR = Path("/home/luis/.config/mytex")


# ==================== Patrón híbrido: base + overrides ====================
BASE_DESCRIPTIONS: Dict[str, str] = {
    "code": "Alfanumeric code",
    "name": "Name of the project",
    "root": "{code}-{name}",
    "data": "Dictionary with metadata",
    "main_topic_root": "List of topics",
    "books": "List of book codes related to the project (si aplica)",
    "topics": "Topics mapping (T## → metadata) o lista según configuración",
}

OVERRIDES: Dict[str, Dict[str, str]] = {
    "general": {
        "main_topic_list": "List of directories names on 00BB-Library",
        "topics": "General theme areas",
        "books": "Reference books usados de forma transversal",
    },
    "course": {
        "main_topic_list": "List of directories names on abs_parent_dir",
        "topics": "Course topics (sílabos; with metadata: chapters/weeks)",
        "books": "Course-specific textbooks/references",
    },
}

# ==================== Dataclass base ====================


@dataclass
class ConfigData:
    name: str
    type: str
    src: Any[str, List]
    termination: str
    number: int

    def get_relation(sefl):
        target_file = ".".joint([src, termination])
        link_file = f"{number}-{name}.{termination}"
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
    abs_parent_dir: str = DEF_ABS_PARENT_DIR
    abs_src_dir: str = DEF_ABS_SRC_DIR
    # 00II-ImagesFigures
    figures_base_dir: List[str] = field(default_factory=list)
    # 00EE-ExamplesExercises
    exercises_base_dir: List[str] = field(default_factory=list)
    # Metadata and patterns
    descriptions: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now())
    last_modification: datetime = field(default_factory=datetime.now())
    version: str = "1.0.0"
    # Generic patterns (optional)
    named_patterns: Dict[str, str] = field(default_factory=dict)


@dataclass
class Admin:
    institution: Institution
    total_week_count: int
    lectures_per_week: int
    year: int
    cycle: int
    first_monday: datetime
    week_day: List[int]


@dataclass
class Book:
    code: str
    name: str
    edition: int

    def get_dir_name(self):
        return f"{self.code}_{self.name.capitalize()}_{self.edition}"


@dataclass
class WeekDay:
    weed_number: int
    lecture_day: int
    admin: Admin
    code: str = field(init=False)
    date: datetime = field(init=False)

    def __post__init__(self):
        self.date = datetime.fromisocalendar(
            self.admin.year,
            self.admmin.first_monday.isocalendar()[1] + self.weed_number,
            self.admin.week_day[self.lecture_day - 1],
        )
        self.code = code_format("W", self.weed_number)
        self.code += code_format("L", self.lecture_day)


@dataclass
class Topic:
    name: str
    chapters: List[str]
    weeks: List[WeekDay] | None = None


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
    proyect_type: ProyectType
    root: str = field(init=False)
    data: MetaData = field(default_factory=MetaData)
    admin: Admin | None = None
    main_topic_root: List[str] = field(default_factory=list)
    books: Dict[str, Book] = field(default_factory=dict)
    topics: Dict[str, Topic] = field(default_factory=dict)

    def __post__init__(self):
        if proyect_type == ProyectType.GENE:
            self.root = f"{self.code}-{self.name}"
        elif proyect_type == ProyectType.LECT:
            self.root = f"{self.admin.institution}-{self.code}"
        else:
            raise ValueError(f"proyect_type {proyect_type} not defined")

    # ---- API amigable ----
    def get_description(self, var_name: str) -> str:
        return self.data.descriptions.get(
            var_name, f"ERROR: {var_name} is not in {self.__class__.__name__}"
        )


# ==================== Factory (híbrido) ====================


def make_structure(
    struct_type: str = "general",
    override_descriptions: Optional[Dict[str, str]] = None,
) -> ProjectStructure:
    desc = {**BASE_DESCRIPTIONS, **OVERRIDES.get(struct_type, {})}
    if override_descriptions:
        desc.update(override_descriptions)
    thisStructure = ProjectStructure(type=struct_type)
    thisStructure.data.descriptions = desc
    return thisStructure
