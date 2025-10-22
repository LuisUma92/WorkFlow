# src/itep/structures.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, date, timezone, timedelta
from enum import StrEnum, Enum
from typing import Dict, List, Tuple
from pathlib import Path

from itep.utils import code_format, ensure_dir, gather_input, select_enum_type
from itep.utils import create_links, write_yaml

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

DEF_TEX_CONFIG = {
    "0-packages.sty": "{src_dir}/sty/SetFormat.sty",
    "1-loyaut.sty": "{src_dir}/sty/SetLoyaut.sty",
    "2-commands.sty": "{src_dir}/sty/SetCommands.sty",
    "2-partial.sty": "{src_dir}/sty/PartialCommands.sty",
    "3-units.sty": "{src_dir}/sty/SetUnits.sty",
    "3-symbols.sty": "{src_dir}/sty/SetSymbols.sty",
    "5-profiles.sty": "{src_dir}/sty/SetProfiles.sty",
    "6-headers.sty": "{src_dir}/sty/SetHeaders.sty",
    "title.tex": "{src_dir}/template/title.tex",
    "instructions.tex": "{src_dir}/template/{institution}-PPI.tex",
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
        "tree": [
            "bib",
            "config",
            "img",
            "projects",
            "tex",
            "tex/000-0-Glossaries",
            "tex/000-1-Summaries",
            "tex/000-2-Notes",
            "tex/{t_idx:03}-{t_name}",  #  for T in topics
        ],
        "links": {
            "config": DEF_TEX_CONFIG,
            "bib/": {
                "{main_t}": "{parent_dir}/{bib}/{main_t}",
                "{t_idx:03d}-{t_name}": "{parent_dir}/{bib}/{main_t}/{t_name}",
            },  # BIB for T in topics
            "img/": {
                "{b_dir}": "{parent_dir}/{img}/{b_dir}",
                "{root}": "{parent_dir}/{img}/{root}",
            },  # IMG for B in books
            "tex/{t_idx}-{t_name}": {
                "{b_dir}-{ch:02d}": "{parent_dir}/{exe}/{b_dir}/C{ch:02d}",
            },  # EXE for B in books
        },
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
        "tree": [
            "admin",
            "eval",
            "eval/config",
            "eval/img",
            "eval/tex",
            "eval/tex/{t_idx:03d}-{t_name}",  # ->mainT for T in topics
            "lect",
            "lect/bib",
            "lect/config",
            "lect/img",
            "lect/svg",
            "lect/tex",
            "lect/tex/{t_idx_03d}-{t_name}",  # ->mainT for T in topics
        ],
        "links": {
            "eval/config": DEF_TEX_CONFIG,
            "eval/img/": {
                "{b_dir}": "{def_parent_dir}/{img}/{b_dir}",
                "{main_t}": "{def_parent_dir}/{img}/{main_t}",
            },  # IMG for B in books
            "eval/tex/{t_idx:03d}-{t_name}": {
                "{b_dir}-{ch:02d}": "{def_parent_dir}/{exe}/{b_dir}/{ch:02d}",
            },  # EXE for B in books
            "lect/config": DEF_TEX_CONFIG,
            "lect/bib/": {
                "{main_bib}": "{def_parent_dir}/{bib}/{main_bib}",
                "{t_idx:03d}-{t_name}": "{def_parent_dir}/{bib}/{main_bib}/{t_name}",
            },  # BIB for T in topics
            "lect/img/": {
                "{b_dir}": "{def_parent_dir}/{img}/{b_dir}",
                "{main_t}": "{def_parent_dir}/{img}/{main_t}",
            },  # IMG for B in books
            "lect/tex/{t_idx:03d}-{t_name}": {
                "{b_dir}-{ch:02d}": "{def_parent_dir}/{exe}/{b_dir}/{ch:02d}",
                "notes": "{def_parent_dir}/{main_t}/tex/{t_idx:03d}-{t_name}",
            },  # EXE for B in books
        },
    }


# ==================== Dataclass base ====================


@dataclass
class WeekDay:
    week_number: int
    lecture_day: int
    first_monday: date
    init_time: int
    tmz: int
    code: str = field(init=False)
    day_date: datetime = field(init=False)

    def __post_init__(self):
        self.day_date = datetime.fromisocalendar(
            self.first_monday.isocalendar()[0],
            self.first_monday.isocalendar()[1] + self.week_number,
            self.lecture_day,
        )
        self.day_date = self.day_date.replace(
            hour=self.init_time,
            tzinfo=timezone(timedelta(hours=self.tmz)),
        )
        self.code = code_format("W", self.week_number)
        self.code += code_format("L", self.lecture_day)
        self.code += f"D{self.day_date.isoformat()}"

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

    @classmethod
    def enter_hours(cls, name: str) -> Tuple:
        msn = f"Enter the scheldule time for {name}\n"
        msn += "hour,timezone (ej: 13,-6)\n"
        msn += "\t<< "
        hours = gather_input(msn, "^([0-9]|[12][0-9]),([+-])([0-9]|[12][0-9])")
        hour, tmz = hours.split(",")
        return int(hour), int(tmz)


@dataclass
class ConfigData:
    name: str
    directory: str
    src: str
    termination: str
    number: int | None

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


@dataclass
class Evaluation:
    amount: int
    duedate: List[WeekDay]

    @classmethod
    def gather_info(cls, name: str, first: date) -> Evaluation:
        amount = int(
            gather_input(
                f"Enter the amount of {name}\n\t<< ",
                "^[0-9]{1,2}",
            )
        )
        duedate = []
        for app in range(1, amount + 1):
            temp_date = gather_input(
                f"Enter the date for the {name} number {app}\n\t<< ",
                "^([0-9]{4})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])",
            )
            init_time, tmz = WeekDay.enter_hours(f"{name} number {app}")
            duedate.append(
                WeekDay.fromisoformat(
                    temp_date,
                    init_time,
                    tmz,
                    first,
                )
            )
        return cls(amount, duedate)


@dataclass
class EvalInstruments:
    partial: Evaluation | None = None
    quiz: Evaluation | None = None
    homework: Evaluation | None = None
    project: Evaluation | None = None

    @classmethod
    def gather_info(cls, first: date) -> EvalInstruments:
        parms = []
        attr_list = ["partial", "quiz", "homework", "project"]
        for atrr in attr_list:
            parms.append(Evaluation.gather_info(atrr, first))
        return cls(
            parms[0],
            parms[1],
            parms[2],
            parms[3],
        )


@dataclass
class Admin:
    institution: Enum
    total_week_count: int
    lectures_per_week: int
    year: int
    cycle: int
    first_monday: date
    week_day: List[int]
    evaluation: EvalInstruments

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
        assigned = gather_input(
            DEF_ADMIN_PATTERNS["first_monday"]["msn"],
            DEF_ADMIN_PATTERNS["first_monday"]["pattern"],
        )
        isoC = [int(d) for d in assigned.split("-")]
        self.first_monday = date.fromisocalendar(
            isoC[0],
            isoC[1],
            1,
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
            if var != "week_day" or var != "first_monday":
                var_dic[var] = content["type"](
                    gather_input(
                        content["msn"],
                        content["pattern"],
                    )
                )
            elif var == "first_monday":
                temp = content["type"](
                    gather_input(
                        content["msn"],
                        content["pattern"],
                    )
                )
                var_dic[var] = date.fromisocalendar(
                    temp.year, temp.isocalendar().week, 1
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
        eval = EvalInstruments(var_dic["first_monday"])
        return cls(
            institution,
            var_dic["total_week_count"],
            var_dic["lectures_per_week"],
            var_dic["year"],
            var_dic["cycle"],
            var_dic["first_monday"],
            var_dic["week_day"],
            eval,
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
        book_list = [b.name for b in path.iterdir() if b.is_file()]
        selected_book = select_enum_type("book", book_list)
        if not selected_book:
            return None
        book_name = selected_book.split("_")
        return cls(book_name[0], book_name[1], int(book_name[2]))


@dataclass
class Topic:
    name: str
    root: str
    chapters: List[str] | None = field(default_factory=lambda: None)
    weeks: List[WeekDay] | None = field(default_factory=lambda: None)

    @classmethod
    def from_directory(cls, path: Path) -> Topic:
        topics_list = [t.name for t in path.iterdir() if t.is_dir()]
        selected_topic = select_enum_type("topic", topics_list)
        if not selected_topic:
            return None
        return cls(selected_topic, path.name)

    @classmethod
    def create_directory(cls, path: Path) -> Topic:
        name = gather_input(
            f"Enter your new {path.name} topic\n\t<< ",
            "^[A-Z][A-Za-z0-9_-]+",
        )
        ensure_dir(path / name, forced=True)
        return cls(name, path.name)

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
    project_type: ProjectType | None = field(default_factory=lambda: None)
    root: str = field(init=False)
    data: MetaData = field(default_factory=MetaData)
    admin: Admin | None = None
    main_topic_root: List[str] = field(default_factory=list)
    books: Dict[str, Book] = field(default_factory=dict)
    topics: Dict[str, Topic] = field(default_factory=dict)
    configs: Dict[str, List[ConfigData]] = field(default_factory=dict)

    def init_root(self):
        institution = None
        if self.admin:
            institution = self.admin.institution.value
        self.root = self.project_type.value["root"].format(
            name=self.name,
            code=self.code,
            institution=institution,
        )

    def init_directories(self) -> None:
        for directory in self.project_type.value["tree"]:
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

    def init_links(self) -> None:
        for link_dir, relations in self.project_type.value["links"].items():
            create_links(
                self.data.abs_parent_dir / self.root / link_dir,
                relations,
            )
            pass

    def save(self) -> None:
        this = self.__dict__
        print(this)
        write_yaml(
            self.data.abs_parent_dir / self.root / "config.yaml",
            this,
        )
