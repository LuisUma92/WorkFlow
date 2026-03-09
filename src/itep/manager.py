"""
CRUD operations over the ITeP database.

Provides functions for creating, reading, updating, and deleting
entities across all four layers of the schema.
"""

from datetime import datetime
from typing import Type, TypeVar

from sqlalchemy.orm import Session

from itep.database import (
    Author,
    Book,
    BookAuthor,
    BookContent,
    Content,
    Course,
    CourseContent,
    CourseEvaluation,
    EvaluationItem,
    EvaluationTemplate,
    GeneralProject,
    GeneralProjectBook,
    GeneralProjectTopic,
    Institution,
    Item,
    LectureInstance,
    MainTopic,
    Topic,
)


T = TypeVar("T")


# ── Generic helpers ────────────────────────────────────────────────────


def list_all(session: Session, model: Type[T]) -> list[T]:
    return session.query(model).all()


def get_by_id(session: Session, model: Type[T], record_id: int) -> T | None:
    return session.get(model, record_id)


def delete_by_id(session: Session, model: Type[T], record_id: int) -> bool:
    obj = session.get(model, record_id)
    if obj is None:
        return False
    session.delete(obj)
    session.commit()
    return True


# ── Institution ────────────────────────────────────────────────────────


def create_institution(
    session: Session,
    short_name: str,
    full_name: str,
    cycle_weeks: int,
    cycle_name: str,
    moodle_url: str = "",
) -> Institution:
    inst = Institution(
        short_name=short_name,
        full_name=full_name,
        cycle_weeks=cycle_weeks,
        cycle_name=cycle_name,
        moodle_url=moodle_url,
    )
    session.add(inst)
    session.commit()
    return inst


def get_institution_by_short_name(
    session: Session, short_name: str,
) -> Institution | None:
    return (
        session.query(Institution)
        .filter_by(short_name=short_name)
        .first()
    )


# ── MainTopic ──────────────────────────────────────────────────────────


def create_main_topic(
    session: Session,
    name: str,
    code: str,
    ddc_mds: str = "",
) -> MainTopic:
    mt = MainTopic(name=name, code=code, ddc_mds=ddc_mds)
    session.add(mt)
    session.commit()
    return mt


def get_main_topic_by_code(session: Session, code: str) -> MainTopic | None:
    return session.query(MainTopic).filter_by(code=code).first()


# ── Author ─────────────────────────────────────────────────────────────


def create_author(
    session: Session,
    first_name: str,
    last_name: str,
    alias: str | None = None,
    affiliation: str | None = None,
) -> Author:
    author = Author(
        first_name=first_name,
        last_name=last_name,
        alias=alias,
        affiliation=affiliation,
    )
    session.add(author)
    session.commit()
    return author


# ── Book ───────────────────────────────────────────────────────────────


def create_book(
    session: Session,
    name: str,
    year: int,
    edition: int = 1,
) -> Book:
    book = Book(name=name, year=year, edition=edition)
    session.add(book)
    session.commit()
    return book


def add_book_author(
    session: Session,
    book_id: int,
    author_id: int,
    author_type: str = "author",
    first_author: bool = False,
) -> BookAuthor:
    ba = BookAuthor(
        book_id=book_id,
        author_id=author_id,
        author_type=author_type,
        first_author=first_author,
    )
    session.add(ba)
    session.commit()
    return ba


# ── Topic ──────────────────────────────────────────────────────────────


def create_topic(
    session: Session,
    main_topic_id: int,
    name: str,
    serial_number: int,
) -> Topic:
    topic = Topic(
        main_topic_id=main_topic_id,
        name=name,
        serial_number=serial_number,
    )
    session.add(topic)
    session.commit()
    return topic


# ── Content ────────────────────────────────────────────────────────────


def create_content(
    session: Session,
    topic_id: int,
    chapter_number: int,
    section_number: int,
    name: str,
    first_page: int,
    last_page: int,
    first_exercise: int | None = None,
    last_exercise: int | None = None,
) -> Content:
    content = Content(
        topic_id=topic_id,
        chapter_number=chapter_number,
        section_number=section_number,
        name=name,
        first_page=first_page,
        last_page=last_page,
        first_exercise=first_exercise,
        last_exercise=last_exercise,
    )
    session.add(content)
    session.commit()
    return content


def link_book_content(
    session: Session,
    book_id: int,
    content_id: int,
) -> BookContent:
    bc = BookContent(book_id=book_id, content_id=content_id)
    session.add(bc)
    session.commit()
    return bc


# ── Course ─────────────────────────────────────────────────────────────


def create_course(
    session: Session,
    institution_id: int,
    code: str,
    name: str,
    lectures_per_week: int = 3,
    hours_per_lecture: int = 2,
) -> Course:
    course = Course(
        institution_id=institution_id,
        code=code,
        name=name,
        lectures_per_week=lectures_per_week,
        hours_per_lecture=hours_per_lecture,
    )
    session.add(course)
    session.commit()
    return course


def add_course_content(
    session: Session,
    course_id: int,
    content_id: int,
    lecture_week: int,
) -> CourseContent:
    cc = CourseContent(
        course_id=course_id,
        content_id=content_id,
        lecture_week=lecture_week,
    )
    session.add(cc)
    session.commit()
    return cc


def add_course_evaluation(
    session: Session,
    course_id: int,
    evaluation_id: int,
    serial_number: int = 1,
    percentage: float = 0.0,
    evaluation_week: int = 1,
) -> CourseEvaluation:
    ce = CourseEvaluation(
        course_id=course_id,
        evaluation_id=evaluation_id,
        serial_number=serial_number,
        percentage=percentage,
        evaluation_week=evaluation_week,
    )
    session.add(ce)
    session.commit()
    return ce


# ── EvaluationTemplate ─────────────────────────────────────────────────


def create_evaluation_template(
    session: Session,
    institution_id: int,
    name: str,
    template_file: str = "",
) -> EvaluationTemplate:
    et = EvaluationTemplate(
        institution_id=institution_id,
        name=name,
        template_file=template_file,
    )
    session.add(et)
    session.commit()
    return et


def add_evaluation_item(
    session: Session,
    evaluation_id: int,
    item_id: int,
    total_amount: int = 1,
    points_per_item: int = 1,
) -> EvaluationItem:
    ei = EvaluationItem(
        evaluation_id=evaluation_id,
        item_id=item_id,
        total_amount=total_amount,
        points_per_item=points_per_item,
    )
    session.add(ei)
    session.commit()
    return ei


# ── Item ───────────────────────────────────────────────────────────────


def create_item(
    session: Session,
    name: str,
    template_file: str = "",
    taxonomy_level: str = "",
    taxonomy_domain: str = "",
) -> Item:
    item = Item(
        name=name,
        template_file=template_file,
        taxonomy_level=taxonomy_level,
        taxonomy_domain=taxonomy_domain,
    )
    session.add(item)
    session.commit()
    return item


# ── LectureInstance ────────────────────────────────────────────────────


def create_lecture_instance(
    session: Session,
    course_id: int,
    year: int,
    cycle: int,
    first_monday,
    abs_parent_dir: str,
    abs_src_dir: str,
    version: str = "1.0.0",
) -> LectureInstance:
    li = LectureInstance(
        course_id=course_id,
        year=year,
        cycle=cycle,
        first_monday=first_monday,
        abs_parent_dir=abs_parent_dir,
        abs_src_dir=abs_src_dir,
        version=version,
    )
    session.add(li)
    session.commit()
    return li


def clone_lecture_instance(
    session: Session,
    source_id: int,
    year: int,
    cycle: int,
    first_monday,
    abs_parent_dir: str | None = None,
    abs_src_dir: str | None = None,
) -> LectureInstance:
    """Clone a lecture instance to a new cycle, inheriting the course."""
    source = session.get(LectureInstance, source_id)
    if source is None:
        raise ValueError(f"LectureInstance {source_id} not found.")

    new = LectureInstance(
        course_id=source.course_id,
        year=year,
        cycle=cycle,
        first_monday=first_monday,
        abs_parent_dir=abs_parent_dir or source.abs_parent_dir,
        abs_src_dir=abs_src_dir or source.abs_src_dir,
    )
    session.add(new)
    session.commit()
    return new


# ── GeneralProject ─────────────────────────────────────────────────────


def create_general_project(
    session: Session,
    main_topic_id: int,
    abs_parent_dir: str,
    abs_src_dir: str,
    topic_ids: list[int] | None = None,
    book_ids: list[int] | None = None,
    version: str = "1.0.0",
) -> GeneralProject:
    gp = GeneralProject(
        main_topic_id=main_topic_id,
        abs_parent_dir=abs_parent_dir,
        abs_src_dir=abs_src_dir,
        version=version,
    )
    session.add(gp)
    session.flush()

    for tid in (topic_ids or []):
        session.add(GeneralProjectTopic(
            general_project_id=gp.id, topic_id=tid,
        ))
    for bid in (book_ids or []):
        session.add(GeneralProjectBook(
            general_project_id=gp.id, book_id=bid,
        ))

    session.commit()
    return gp


def update_project_timestamp(
    session: Session,
    project,
) -> None:
    """Touch last_modification on a project instance."""
    project.last_modification = datetime.now()
    session.commit()
