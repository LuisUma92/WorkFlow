"""
ITeP relational database models (SQLAlchemy).

Four layers:
  1. Reference data   — Institution, MainTopic
  2. Master entities   — Author, Book, BookAuthor, Topic, Content, BookContent
  3. Course templates  — Course, CourseContent, EvaluationTemplate, Item,
                         EvaluationItem, CourseEvaluation
  4. Project instances — LectureInstance, GeneralProject (+association tables)
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from itep.defaults import DB_PATH


# ── Base ────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Layer 1: Reference data ────────────────────────────────────────────

class Institution(Base):
    __tablename__ = "institution"

    id: Mapped[int] = mapped_column(primary_key=True)
    short_name: Mapped[str] = mapped_column(String(10), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    cycle_weeks: Mapped[int] = mapped_column(Integer)
    cycle_name: Mapped[str] = mapped_column(String(30))
    moodle_url: Mapped[str] = mapped_column(String(200), default="")

    courses: Mapped[list["Course"]] = relationship(back_populates="institution")
    evaluation_templates: Mapped[list["EvaluationTemplate"]] = relationship(
        back_populates="institution"
    )

    def __repr__(self):
        return f"<Institution {self.short_name}>"


class MainTopic(Base):
    __tablename__ = "main_topic"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(10), unique=True)
    ddc_mds: Mapped[str] = mapped_column(String(20), default="")

    topics: Mapped[list["Topic"]] = relationship(back_populates="main_topic")
    general_project: Mapped["GeneralProject | None"] = relationship(
        back_populates="main_topic"
    )

    def __repr__(self):
        return f"<MainTopic {self.code} {self.name}>"


# ── Layer 2: Master entities ───────────────────────────────────────────

class Author(Base):
    __tablename__ = "author"
    __table_args__ = (
        UniqueConstraint("first_name", "last_name", name="uq_author_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(200))
    alias: Mapped[str | None] = mapped_column(String(80), default=None)
    affiliation: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    book_links: Mapped[list["BookAuthor"]] = relationship(back_populates="author")

    def __repr__(self):
        return f"<Author {self.last_name}, {self.first_name}>"


class Book(Base):
    __tablename__ = "book"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    year: Mapped[int] = mapped_column(Integer)
    edition: Mapped[int] = mapped_column(Integer, default=1)

    author_links: Mapped[list["BookAuthor"]] = relationship(back_populates="book")
    content_links: Mapped[list["BookContent"]] = relationship(back_populates="book")
    general_project_links: Mapped[list["GeneralProjectBook"]] = relationship(
        back_populates="book"
    )

    def __repr__(self):
        return f"<Book {self.name} ({self.year})>"


class BookAuthor(Base):
    __tablename__ = "book_author"
    __table_args__ = (
        UniqueConstraint(
            "book_id", "author_id", "author_type",
            name="uq_book_author_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("book.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("author.id"))
    author_type: Mapped[str] = mapped_column(String(20), default="author")
    first_author: Mapped[bool] = mapped_column(Boolean, default=False)

    book: Mapped["Book"] = relationship(back_populates="author_links")
    author: Mapped["Author"] = relationship(back_populates="book_links")


class Topic(Base):
    __tablename__ = "topic"

    id: Mapped[int] = mapped_column(primary_key=True)
    main_topic_id: Mapped[int] = mapped_column(ForeignKey("main_topic.id"))
    name: Mapped[str] = mapped_column(String(120))
    serial_number: Mapped[int] = mapped_column(Integer)

    main_topic: Mapped["MainTopic"] = relationship(back_populates="topics")
    contents: Mapped[list["Content"]] = relationship(back_populates="topic")
    general_project_links: Mapped[list["GeneralProjectTopic"]] = relationship(
        back_populates="topic"
    )

    def __repr__(self):
        return f"<Topic {self.serial_number}: {self.name}>"


class Content(Base):
    __tablename__ = "content"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topic.id"))
    chapter_number: Mapped[int] = mapped_column(Integer)
    section_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    first_page: Mapped[int] = mapped_column(Integer)
    last_page: Mapped[int] = mapped_column(Integer)
    first_exercise: Mapped[int | None] = mapped_column(Integer, default=None)
    last_exercise: Mapped[int | None] = mapped_column(Integer, default=None)

    topic: Mapped["Topic"] = relationship(back_populates="contents")
    book_links: Mapped[list["BookContent"]] = relationship(back_populates="content")
    course_links: Mapped[list["CourseContent"]] = relationship(
        back_populates="content"
    )


class BookContent(Base):
    __tablename__ = "book_content"

    book_id: Mapped[int] = mapped_column(ForeignKey("book.id"), primary_key=True)
    content_id: Mapped[int] = mapped_column(
        ForeignKey("content.id"), primary_key=True
    )

    book: Mapped["Book"] = relationship(back_populates="content_links")
    content: Mapped["Content"] = relationship(back_populates="book_links")


# ── Layer 3: Course templates ──────────────────────────────────────────

class Course(Base):
    __tablename__ = "course"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institution.id"))
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    lectures_per_week: Mapped[int] = mapped_column(Integer, default=3)
    hours_per_lecture: Mapped[int] = mapped_column(Integer, default=2)

    institution: Mapped["Institution"] = relationship(back_populates="courses")
    course_contents: Mapped[list["CourseContent"]] = relationship(
        back_populates="course"
    )
    course_evaluations: Mapped[list["CourseEvaluation"]] = relationship(
        back_populates="course"
    )
    lecture_instances: Mapped[list["LectureInstance"]] = relationship(
        back_populates="course"
    )

    def __repr__(self):
        return f"<Course {self.code} {self.name}>"


class CourseContent(Base):
    __tablename__ = "course_content"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"))
    content_id: Mapped[int] = mapped_column(ForeignKey("content.id"))
    lecture_week: Mapped[int] = mapped_column(Integer)

    course: Mapped["Course"] = relationship(back_populates="course_contents")
    content: Mapped["Content"] = relationship(back_populates="course_links")


class EvaluationTemplate(Base):
    __tablename__ = "evaluation_template"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institution.id"))
    name: Mapped[str] = mapped_column(String(80))
    template_file: Mapped[str] = mapped_column(String(300), default="")

    institution: Mapped["Institution"] = relationship(
        back_populates="evaluation_templates"
    )
    evaluation_items: Mapped[list["EvaluationItem"]] = relationship(
        back_populates="evaluation"
    )
    course_evaluations: Mapped[list["CourseEvaluation"]] = relationship(
        back_populates="evaluation"
    )


class Item(Base):
    __tablename__ = "item"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    template_file: Mapped[str] = mapped_column(String(300), default="")
    taxonomy_level: Mapped[str] = mapped_column(String(30), default="")
    taxonomy_domain: Mapped[str] = mapped_column(String(40), default="")

    evaluation_links: Mapped[list["EvaluationItem"]] = relationship(
        back_populates="item"
    )


class EvaluationItem(Base):
    __tablename__ = "evaluation_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_template.id")
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"))
    total_amount: Mapped[int] = mapped_column(Integer, default=1)
    points_per_item: Mapped[int] = mapped_column(Integer, default=1)

    evaluation: Mapped["EvaluationTemplate"] = relationship(
        back_populates="evaluation_items"
    )
    item: Mapped["Item"] = relationship(back_populates="evaluation_links")


class CourseEvaluation(Base):
    __tablename__ = "course_evaluation"
    __table_args__ = (
        CheckConstraint("percentage >= 0 AND percentage <= 1", name="ck_pct_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"))
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_template.id")
    )
    serial_number: Mapped[int] = mapped_column(Integer, default=1)
    percentage: Mapped[float] = mapped_column(Float, default=0.0)
    evaluation_week: Mapped[int] = mapped_column(Integer, default=1)

    course: Mapped["Course"] = relationship(back_populates="course_evaluations")
    evaluation: Mapped["EvaluationTemplate"] = relationship(
        back_populates="course_evaluations"
    )


# ── Layer 4: Project instances ─────────────────────────────────────────

class LectureInstance(Base):
    __tablename__ = "lecture_instance"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"))
    year: Mapped[int] = mapped_column(Integer)
    cycle: Mapped[int] = mapped_column(Integer)
    first_monday: Mapped[date] = mapped_column(Date)
    abs_parent_dir: Mapped[str] = mapped_column(String(500))
    abs_src_dir: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_modification: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")

    course: Mapped["Course"] = relationship(back_populates="lecture_instances")

    @property
    def root_dir(self) -> str:
        return f"{self.course.institution.short_name}-{self.course.code}"

    def __repr__(self):
        return f"<LectureInstance {self.course.code} {self.year}-{self.cycle}>"


class GeneralProject(Base):
    __tablename__ = "general_project"

    id: Mapped[int] = mapped_column(primary_key=True)
    main_topic_id: Mapped[int] = mapped_column(
        ForeignKey("main_topic.id"), unique=True
    )
    abs_parent_dir: Mapped[str] = mapped_column(String(500))
    abs_src_dir: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_modification: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")

    main_topic: Mapped["MainTopic"] = relationship(back_populates="general_project")
    book_links: Mapped[list["GeneralProjectBook"]] = relationship(
        back_populates="general_project",
        cascade="all, delete-orphan",
    )
    topic_links: Mapped[list["GeneralProjectTopic"]] = relationship(
        back_populates="general_project",
        cascade="all, delete-orphan",
    )

    @property
    def root_dir(self) -> str:
        return f"{self.main_topic.code}-{self.main_topic.name}"

    def __repr__(self):
        return f"<GeneralProject {self.main_topic.code}>"


class GeneralProjectBook(Base):
    __tablename__ = "general_project_book"

    general_project_id: Mapped[int] = mapped_column(
        ForeignKey("general_project.id"), primary_key=True
    )
    book_id: Mapped[int] = mapped_column(ForeignKey("book.id"), primary_key=True)

    general_project: Mapped["GeneralProject"] = relationship(
        back_populates="book_links"
    )
    book: Mapped["Book"] = relationship(back_populates="general_project_links")


class GeneralProjectTopic(Base):
    __tablename__ = "general_project_topic"

    general_project_id: Mapped[int] = mapped_column(
        ForeignKey("general_project.id"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(ForeignKey("topic.id"), primary_key=True)

    general_project: Mapped["GeneralProject"] = relationship(
        back_populates="topic_links"
    )
    topic: Mapped["Topic"] = relationship(back_populates="general_project_links")


# ── Engine / Session helpers ───────────────────────────────────────────

def _enable_fk_pragma(dbapi_conn, connection_record):
    """Enable foreign-key enforcement for SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine(db_path=None, echo=False):
    if db_path is None:
        db_path = DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=echo)
    event.listen(engine, "connect", _enable_fk_pragma)
    return engine


def get_session(engine=None) -> Session:
    if engine is None:
        engine = get_engine()
    factory = sessionmaker(bind=engine)
    return factory()


def init_db(engine=None):
    """Create all tables."""
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


# ── Seed data ──────────────────────────────────────────────────────────

INSTITUTIONS_SEED = [
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

MAIN_TOPICS_SEED = [
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


def seed_reference_data(session: Session):
    """Insert institutions and main_topics if they don't exist yet."""
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
