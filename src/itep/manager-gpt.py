"""
This manager manages de CUDA operations for the strc.ProjectStructure
"""

import itep.structure as strc


from pathlib import Path
from typing import Optional, List, Tuple
from datetime import date


def load_config(file_name: str) -> strc.ProjectStructure:
    """load_config(file_name:str) -> strc.ProjectStructure"""
    pass


def change_parent(old_cfg: strc.ProjectStructure) -> strc.ProjectStructure:
    pass


# ---------- ProjectStructure (meta / core) ----------
def create_project(
    code: str,
    name: str,
    project_type: strc.ProjectType,
    admin: Optional[strc.Admin] = None,
) -> strc.ProjectStructure:
    return strc.ProjectStructure(
        code=code,
        name=name,
        project_type=project_type,
        admin=admin,
    )


def set_code(cfg: strc.ProjectStructure, code: str) -> strc.ProjectStructure:
    cfg.code = code
    return cfg


def set_name(cfg: strc.ProjectStructure, name: str) -> strc.ProjectStructure:
    pass


def set_project_type(
    cfg: strc.ProjectStructure, project_type: strc.ProjectType
) -> strc.ProjectStructure:
    pass


def init_root(cfg: strc.ProjectStructure) -> strc.ProjectStructure:
    pass


def resolve_root_path(cfg: strc.ProjectStructure) -> Path:
    pass


def save_config(cfg: strc.ProjectStructure, file_name: Optional[Path] = None) -> Path:
    pass


def export_yaml(cfg: strc.ProjectStructure) -> str:
    pass


def validate(cfg: strc.ProjectStructure) -> Tuple[bool, List[str]]:
    pass


# ---------- MetaData ----------
def set_abs_parent_dir(cfg: strc.ProjectStructure, path: Path) -> strc.ProjectStructure:
    pass


def set_abs_src_dir(cfg: strc.ProjectStructure, path: Path) -> strc.ProjectStructure:
    pass


def set_version(cfg: strc.ProjectStructure, version: str) -> strc.ProjectStructure:
    pass


def touch_last_modification(cfg: strc.ProjectStructure) -> strc.ProjectStructure:
    pass


# ---------- Admin (high-level attach/detach) ----------
def set_admin(cfg: strc.ProjectStructure, admin: strc.Admin) -> strc.ProjectStructure:
    pass


def clear_admin(cfg: strc.ProjectStructure) -> strc.ProjectStructure:
    pass


# ---------- Admin fields (CUDA) ----------
def set_admin_institution(
    cfg: strc.ProjectStructure, institution: strc.Institution
) -> strc.ProjectStructure:
    pass


def set_admin_total_week_count(
    cfg: strc.ProjectStructure, total: int
) -> strc.ProjectStructure:
    pass


def set_admin_lectures_per_week(
    cfg: strc.ProjectStructure, lpw: int
) -> strc.ProjectStructure:
    pass


def set_admin_year(cfg: strc.ProjectStructure, year: int) -> strc.ProjectStructure:
    pass


def set_admin_cycle(cfg: strc.ProjectStructure, cycle: int) -> strc.ProjectStructure:
    pass


def set_admin_first_monday(
    cfg: strc.ProjectStructure, first_monday: date
) -> strc.ProjectStructure:
    pass


def set_admin_week_days(
    cfg: strc.ProjectStructure, week_days: List[int]
) -> strc.ProjectStructure:
    pass


# ---------- Evaluation & instruments ----------
def set_eval_instruments(
    cfg: strc.ProjectStructure, instruments: strc.EvalInstruments
) -> strc.ProjectStructure:
    pass


def set_evaluation(
    cfg: strc.ProjectStructure, name: str, evaluation: strc.Evaluation
) -> strc.ProjectStructure:
    pass


def create_evaluation(amount: int, duedates: List[strc.WeekDay]) -> strc.Evaluation:
    pass


def add_evaluation_due(
    cfg: strc.ProjectStructure, name: str, due: strc.WeekDay
) -> strc.ProjectStructure:
    pass


def remove_evaluation_due(
    cfg: strc.ProjectStructure, name: str, code: str
) -> strc.ProjectStructure:
    pass


# ---------- WeekDay helpers ----------
def create_weekday(
    week_number: int, lecture_day: int, first_monday: date, init_time: int, tmz: int
) -> strc.WeekDay:
    pass


def weekday_from_iso(
    date_str: str, init_time: int, tmz: int, first: date
) -> strc.WeekDay:
    pass


# ---------- Main topic roots ----------
def set_main_topic_roots(
    cfg: strc.ProjectStructure, roots: List[str]
) -> strc.ProjectStructure:
    pass


def add_main_topic_root(cfg: strc.ProjectStructure, root: str) -> strc.ProjectStructure:
    pass


def remove_main_topic_root(
    cfg: strc.ProjectStructure, root: str
) -> strc.ProjectStructure:
    pass


def list_main_topic_roots(cfg: strc.ProjectStructure) -> List[str]:
    pass


# ---------- Books (CRUD) ----------
def add_book(cfg: strc.ProjectStructure, book: strc.Book) -> strc.ProjectStructure:
    pass


def remove_book(cfg: strc.ProjectStructure, book_code: str) -> strc.ProjectStructure:
    pass


def get_book(cfg: strc.ProjectStructure, book_code: str) -> Optional[strc.Book]:
    pass


def list_books(cfg: strc.ProjectStructure) -> List[str]:
    pass


def set_book_name(
    cfg: strc.ProjectStructure, book_code: str, name: str
) -> strc.ProjectStructure:
    pass


def set_book_edition(
    cfg: strc.ProjectStructure, book_code: str, edition: int
) -> strc.ProjectStructure:
    pass


# ---------- Topics (CRUD) ----------
def add_topic(
    cfg: strc.ProjectStructure, key: str, topic: strc.Topic
) -> strc.ProjectStructure:
    pass


def remove_topic(cfg: strc.ProjectStructure, key: str) -> strc.ProjectStructure:
    pass


def get_topic(cfg: strc.ProjectStructure, key: str) -> Optional[strc.Topic]:
    pass


def list_topics(cfg: strc.ProjectStructure) -> List[str]:
    pass


def rename_topic_key(
    cfg: strc.ProjectStructure, old_key: str, new_key: str
) -> strc.ProjectStructure:
    pass


def set_topic_name(
    cfg: strc.ProjectStructure, key: str, name: str
) -> strc.ProjectStructure:
    pass


def set_topic_chapters(
    cfg: strc.ProjectStructure, key: str, chapters: Optional[List[str]]
) -> strc.ProjectStructure:
    pass


def add_topic_chapter(
    cfg: strc.ProjectStructure, key: str, book_id: int, chapter_id: int
) -> strc.ProjectStructure:
    pass


def clear_topic_chapters(cfg: strc.ProjectStructure, key: str) -> strc.ProjectStructure:
    pass


def set_topic_weeks(
    cfg: strc.ProjectStructure, key: str, weeks: Optional[List[strc.WeekDay]]
) -> strc.ProjectStructure:
    pass


def append_topic_week(
    cfg: strc.ProjectStructure, key: str, week: strc.WeekDay
) -> strc.ProjectStructure:
    pass


def remove_topic_week(
    cfg: strc.ProjectStructure, key: str, week_code: str
) -> strc.ProjectStructure:
    pass


# ---------- ConfigData (per section) ----------
def list_config_sections(cfg: strc.ProjectStructure) -> List[str]:
    pass


def get_config_section(
    cfg: strc.ProjectStructure, section: str
) -> List[strc.ConfigData]:
    pass


def set_config_section(
    cfg: strc.ProjectStructure, section: str, relations: List[strc.ConfigData]
) -> strc.ProjectStructure:
    pass


def add_config_relation(
    cfg: strc.ProjectStructure, section: str, relation: strc.ConfigData
) -> strc.ProjectStructure:
    pass


def remove_config_relation(
    cfg: strc.ProjectStructure, section: str, link_name: str
) -> strc.ProjectStructure:
    pass


def parse_config_relation(link: str, target: str) -> strc.ConfigData:
    pass


# ---------- Filesystem actions (directories / links) ----------
def ensure_tree(cfg: strc.ProjectStructure) -> None:
    pass


def ensure_links(cfg: strc.ProjectStructure) -> None:
    pass


def link_section(cfg: strc.ProjectStructure, section: str) -> None:
    pass


def unlink_section(cfg: strc.ProjectStructure, section: str) -> None:
    pass


def resolve_dir(cfg: strc.ProjectStructure, relative: str) -> Path:
    pass


# ---------- Mutations / migrations ----------
def change_code(cfg: strc.ProjectStructure, new_code: str) -> strc.ProjectStructure:
    pass


def change_name(cfg: strc.ProjectStructure, new_name: str) -> strc.ProjectStructure:
    pass


def change_project_type(
    cfg: strc.ProjectStructure, new_type: strc.ProjectType
) -> strc.ProjectStructure:
    pass


def migrate_parent(
    cfg: strc.ProjectStructure, new_parent: Path
) -> strc.ProjectStructure:
    pass


# ---------- Rebuild / reload ----------
def rebuild_from_config(file_name: Path) -> strc.ProjectStructure:
    pass
