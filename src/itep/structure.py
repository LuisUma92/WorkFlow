# src/itep/structures.py
from __future__ import annotations
from dataclasses import dataclass, field, fields
from datetime import datetime, date, timezone, timedelta
from enum import StrEnum, EnumType
from typing import Dict, List
from pathlib import Path


from itep.utils import code_format, ensure_dir
from itep.defaults import DEF_ABS_PARENT_DIR, DEF_ABS_SRC_DIR
from appfunc.options import select_enum_type
from appfunc.iofunc import spec, ask, gather_dataclass

# --- Constantes por defecto ---


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


# ==================== Dataclass base ====================


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


@dataclass
class MetaData:
    # absolute routes
    abs_parent_dir: Path = DEF_ABS_PARENT_DIR
    abs_src_dir: Path = DEF_ABS_SRC_DIR
    # Metadata and patterns
    created_at: datetime = field(default_factory=datetime.now)
    last_modification: datetime = field(default_factory=datetime.now)
    version: str = "1.0.0"

    def __iter__(self):
        yield from ((f.name, getattr(self, f.name)) for f in fields(self))


@dataclass
class Evaluation:
    name: str = field(
        metadata={
            "input": spec(
                "Enter evaluation name",
                r".+",
                str,
            )
        }
    )
    amount: int = field(
        default=1,
        metadata={
            "input": spec(
                "Enter the amount of evaluations",
                r"[0-9]{1,2}",
                int,
            )
        },
    )
    duedate: List[WeekDay] = field(init=False, default_factory=list)

    def __post_init__(self):
        for i in range(self.amount):
            print(f"\n>> duedate[{i}]:")
            self.duedate.append(gather_dataclass(WeekDay))

    def __iter__(self):
        yield from ((f.name, getattr(self, f.name)) for f in fields(self))


@dataclass
class Admin:
    institution: Institution = field(
        metadata={
            "input": spec(
                "Enter your insntitution name",
                r".+",
                Institution,
            )
        }
    )
    total_week_count: int = field(
        metadata={
            "input": spec(
                "Enter the total number of weeks",
                r"[0-9]+",
                int,
            )
        }
    )
    lectures_per_week: int = field(
        metadata={
            "input": spec(
                "Enter the total amount of lectures per week",
                r"[0-5]",
                int,
            )
        }
    )
    year: int = field(
        metadata={
            "input": spec(
                "Enter the year of the lecture",
                r"2([0-9]{3})",
                int,
            )
        }
    )
    cycle: int = field(
        metadata={
            "input": spec(
                "Enter current cycle for the lecture",
                r"[1-3]",
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
    week_day: List[int] = field(
        init=False,
        default_factory=list,
    )
    evaluation: List[Evaluation] = field(
        init=False,
        default_factory=list,
    )

    def __post_init__(self):
        for i in range(self.lectures_per_week):
            print(f"\n>> lecture day [{i}]:")
            self.week_day.append(
                ask(
                    spec(
                        "Enter weed day assosiated (Mon=1,...,Sat=6)",
                        r"[1-6]",
                        int,
                    )
                )
            )
        evals = ["partial", "homework", "project", "quiz"]
        for eval in evals:
            if (input(f"Want to add {eval} (Y/n): ").lower() or "y") == "y":
                self.evaluation.append(gather_dataclass(Evaluation))

    def __iter__(self):
        yield from ((f.name, getattr(self, f.name)) for f in fields(self))


@dataclass
class Book:
    code: str
    name: str
    edition: int

    def __iter__(self):
        yield from ((f.name, getattr(self, f.name)) for f in fields(self))

    def get_dir_name(self):
        return f"{self.code}_{self.name.capitalize()}_{self.edition}"

    @classmethod
    def from_directory(cls, path: Path) -> Book:
        book_list = [b.name for b in path.iterdir() if b.is_file()]
        selected_book = select_enum_type("book", book_list)
        if not selected_book:
            raise StopIteration
        book_name = selected_book.split("_")
        return cls(book_name[0], book_name[1], int(book_name[2]))


@dataclass
class Topic:
    name: str = field(
        metadata={
            "input": spec(
                "Enter topic name",
                r"\S(.|\s){1,}\S",
                str,
            )
        }
    )
    root: str = field(
        metadata={
            "input": spec(
                "Enter root directory",
                r".+",
                str,
            )
        }
    )
    chapters: List[str] | None = field(default=None)
    weeks: List[WeekDay] | None = field(default=None)

    @classmethod
    def from_directory(cls, path: Path) -> Topic:
        topics_list = [t.name for t in path.iterdir() if t.is_dir()]
        selected_topic = str(select_enum_type("topic", topics_list))
        if not selected_topic:
            raise StopIteration
        return cls(selected_topic, path.name)

    @classmethod
    def create_directory(cls, path: Path) -> Topic:
        name = (ask(f.metadata["input"]) for f in fields(cls) if f.name == "name")
        ensure_dir(path / name, forced=True)
        return cls(name, path.name)

    def __iter__(self):
        yield from ((f.name, getattr(self, f.name)) for f in fields(self))

    def add_book_chapter(self, book_id: int, chapter_id: int) -> None:
        chapter_code = code_format("B", book_id, max=3)
        chapter_code += code_format("C", chapter_id)
        if not self.chapters:
            self.chapters = [chapter_code]
        else:
            self.chapters.append(chapter_code)


@dataclass
class ProjectStructure:
    """
    This is a general structure that every project file should implement this
    to its specific needs
    """

    code: str = field(default_factory=str)
    name: str = field(default_factory=str)
    project_type: ProjectModel = field(default_factory=ProjectModel)
    root: str = field(init=False)
    data: MetaData = field(default_factory=MetaData)
    admin: Admin | None = field(default=None)
    main_topic_root: List[str] = field(default_factory=list)
    books: Dict[str, Book] = field(default_factory=dict)
    topics: Dict[str, Topic] = field(default_factory=dict)
    configs: Dict[str, List[ConfigData]] = field(default_factory=dict)

    def __post_init__(self):
        institution = None
        if self.admin:
            institution = self.admin.institution.value
        self.root = self.project_type.root.format(
            name=self.name,
            code=self.code,
            institution=institution,
        )

    def __iter__(self):
        yield from ((f.name, getattr(self, f.name)) for f in fields(self))

    def init_directories(self) -> None:
        for directory in self.project_type.tree:
            if "{" in directory:
                for idx, topic in self.topics.items():
                    ensure_dir(
                        self.data.abs_parent_dir
                        / self.root
                        / directory.format(t_idx=idx, t_name=topic.name),
                        forced=True,
                    )

            else:
                ensure_dir(
                    self.data.abs_parent_dir / self.root / directory,
                    forced=True,
                )
