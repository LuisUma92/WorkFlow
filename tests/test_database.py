"""Tests for itep.database — SQLAlchemy models, engine, seed data, and CRUD."""

import pytest
from datetime import date

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from itep.database import (
    Base,
    Institution,
    MainTopic,
    Author,
    Book,
    BookAuthor,
    Topic,
    Content,
    BookContent,
    Course,
    CourseContent,
    EvaluationTemplate,
    Item,
    EvaluationItem,
    CourseEvaluation,
    LectureInstance,
    GeneralProject,
    GeneralProjectBook,
    GeneralProjectTopic,
    seed_reference_data,
    _enable_fk_pragma,
)


@pytest.fixture
def engine():
    """In-memory SQLite engine with FK support."""
    eng = create_engine("sqlite:///:memory:")
    event.listen(eng, "connect", _enable_fk_pragma)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    """Fresh session per test."""
    factory = sessionmaker(bind=engine)
    sess = factory()
    yield sess
    sess.close()


# ── Layer 1: Reference data ───────────────────────────────────────────


class TestInstitution:
    def test_create_institution(self, session):
        inst = Institution(
            short_name="UCR",
            full_name="Universidad de Costa Rica",
            cycle_weeks=18,
            cycle_name="Semestre",
            moodle_url="mv.mediacionvirtual.ucr.ac.cr",
        )
        session.add(inst)
        session.commit()

        loaded = session.query(Institution).filter_by(short_name="UCR").one()
        assert loaded.full_name == "Universidad de Costa Rica"
        assert loaded.cycle_weeks == 18

    def test_short_name_unique(self, session):
        session.add(Institution(
            short_name="UCR", full_name="A", cycle_weeks=1, cycle_name="S",
        ))
        session.commit()
        session.add(Institution(
            short_name="UCR", full_name="B", cycle_weeks=2, cycle_name="Q",
        ))
        with pytest.raises(Exception):
            session.commit()


class TestMainTopic:
    def test_create_main_topic(self, session):
        mt = MainTopic(name="Mecánica Clásica", code="10MC", ddc_mds="531")
        session.add(mt)
        session.commit()

        loaded = session.query(MainTopic).filter_by(code="10MC").one()
        assert loaded.name == "Mecánica Clásica"

    def test_code_unique(self, session):
        session.add(MainTopic(name="A", code="10MC"))
        session.commit()
        session.add(MainTopic(name="B", code="10MC"))
        with pytest.raises(Exception):
            session.commit()


# ── Layer 2: Master entities ──────────────────────────────────────────


class TestAuthorBook:
    def test_create_author(self, session):
        a = Author(first_name="Isaac", last_name="Newton")
        session.add(a)
        session.commit()
        assert a.id is not None
        assert repr(a) == "<Author Newton, Isaac>"

    def test_author_unique_constraint(self, session):
        session.add(Author(first_name="Isaac", last_name="Newton"))
        session.commit()
        session.add(Author(first_name="Isaac", last_name="Newton"))
        with pytest.raises(Exception):
            session.commit()

    def test_create_book_with_authors(self, session):
        a1 = Author(first_name="Herbert", last_name="Goldstein")
        a2 = Author(first_name="Charles", last_name="Poole")
        book = Book(name="Classical Mechanics", year=2002, edition=3)
        session.add_all([a1, a2, book])
        session.commit()

        ba1 = BookAuthor(
            book_id=book.id, author_id=a1.id,
            author_type="author", first_author=True,
        )
        ba2 = BookAuthor(
            book_id=book.id, author_id=a2.id,
            author_type="author", first_author=False,
        )
        session.add_all([ba1, ba2])
        session.commit()

        loaded = session.get(Book, book.id)
        assert len(loaded.author_links) == 2
        first_authors = [
            ba.author for ba in loaded.author_links if ba.first_author
        ]
        assert first_authors[0].last_name == "Goldstein"


class TestTopicContent:
    def test_topic_with_content(self, session):
        mt = MainTopic(name="Mecánica Clásica", code="10MC")
        session.add(mt)
        session.commit()

        t = Topic(main_topic_id=mt.id, name="Cinemática", serial_number=1)
        session.add(t)
        session.commit()

        c = Content(
            topic_id=t.id,
            chapter_number=1,
            section_number=1,
            name="Posición y velocidad",
            first_page=1,
            last_page=25,
        )
        session.add(c)
        session.commit()

        loaded = session.get(Topic, t.id)
        assert len(loaded.contents) == 1
        assert loaded.contents[0].name == "Posición y velocidad"
        assert loaded.main_topic.code == "10MC"

    def test_book_content_link(self, session):
        mt = MainTopic(name="MC", code="10MC")
        session.add(mt)
        session.commit()

        t = Topic(main_topic_id=mt.id, name="Cinemática", serial_number=1)
        b = Book(name="Goldstein", year=2002)
        session.add_all([t, b])
        session.commit()

        c = Content(
            topic_id=t.id, chapter_number=1, section_number=1,
            name="Intro", first_page=1, last_page=10,
        )
        session.add(c)
        session.commit()

        bc = BookContent(book_id=b.id, content_id=c.id)
        session.add(bc)
        session.commit()

        loaded_book = session.get(Book, b.id)
        assert len(loaded_book.content_links) == 1
        assert loaded_book.content_links[0].content.name == "Intro"


# ── Layer 3: Course templates ─────────────────────────────────────────


class TestCourse:
    @pytest.fixture
    def ucr(self, session):
        inst = Institution(
            short_name="UCR", full_name="UCR",
            cycle_weeks=18, cycle_name="Semestre",
        )
        session.add(inst)
        session.commit()
        return inst

    def test_create_course(self, session, ucr):
        course = Course(
            institution_id=ucr.id,
            code="FS0121",
            name="Física General I",
            lectures_per_week=3,
            hours_per_lecture=2,
        )
        session.add(course)
        session.commit()

        loaded = session.get(Course, course.id)
        assert loaded.institution.short_name == "UCR"
        assert loaded.code == "FS0121"

    def test_course_content_and_evaluation(self, session, ucr):
        # Setup full chain
        mt = MainTopic(name="MC", code="10MC")
        session.add(mt)
        session.commit()

        topic = Topic(main_topic_id=mt.id, name="Cinemática", serial_number=1)
        session.add(topic)
        session.commit()

        content = Content(
            topic_id=topic.id, chapter_number=1, section_number=1,
            name="Pos", first_page=1, last_page=10,
        )
        session.add(content)
        session.commit()

        course = Course(
            institution_id=ucr.id, code="FS0121", name="FG1",
        )
        session.add(course)
        session.commit()

        cc = CourseContent(
            course_id=course.id, content_id=content.id, lecture_week=1,
        )
        session.add(cc)
        session.commit()

        assert len(course.course_contents) == 1
        assert course.course_contents[0].content.topic.name == "Cinemática"

        # Evaluation
        et = EvaluationTemplate(
            institution_id=ucr.id, name="Parcial",
        )
        session.add(et)
        session.commit()

        ce = CourseEvaluation(
            course_id=course.id,
            evaluation_id=et.id,
            serial_number=1,
            percentage=0.25,
            evaluation_week=6,
        )
        session.add(ce)
        session.commit()

        assert len(course.course_evaluations) == 1
        assert course.course_evaluations[0].percentage == 0.25


class TestEvaluationItems:
    def test_evaluation_with_items(self, session):
        inst = Institution(
            short_name="UCR", full_name="UCR",
            cycle_weeks=18, cycle_name="Semestre",
        )
        session.add(inst)
        session.commit()

        et = EvaluationTemplate(
            institution_id=inst.id, name="Parcial",
        )
        item = Item(
            name="Problema", taxonomy_level="Comprender",
            taxonomy_domain="Procedimiento Mental",
        )
        session.add_all([et, item])
        session.commit()

        ei = EvaluationItem(
            evaluation_id=et.id, item_id=item.id,
            total_amount=5, points_per_item=4,
        )
        session.add(ei)
        session.commit()

        assert len(et.evaluation_items) == 1
        assert et.evaluation_items[0].item.name == "Problema"


# ── Layer 4: Project instances ────────────────────────────────────────


class TestLectureInstance:
    def test_create_and_root_dir(self, session):
        inst = Institution(
            short_name="UCR", full_name="UCR",
            cycle_weeks=18, cycle_name="Semestre",
        )
        session.add(inst)
        session.commit()

        course = Course(
            institution_id=inst.id, code="FS0121", name="FG1",
        )
        session.add(course)
        session.commit()

        li = LectureInstance(
            course_id=course.id,
            year=2026,
            cycle=1,
            first_monday=date(2026, 3, 9),
            abs_parent_dir="/home/user/docs",
            abs_src_dir="/home/user/.config/mytex",
        )
        session.add(li)
        session.commit()

        assert li.root_dir == "UCR-FS0121"
        assert li.year == 2026
        assert li.course.institution.short_name == "UCR"

    def test_multiple_instances_same_course(self, session):
        inst = Institution(
            short_name="UCR", full_name="UCR",
            cycle_weeks=18, cycle_name="S",
        )
        course = Course(institution_id=1, code="FS0121", name="FG1")
        session.add_all([inst, course])
        session.commit()

        li1 = LectureInstance(
            course_id=course.id, year=2025, cycle=1,
            first_monday=date(2025, 3, 10),
            abs_parent_dir="/a", abs_src_dir="/b",
        )
        li2 = LectureInstance(
            course_id=course.id, year=2025, cycle=2,
            first_monday=date(2025, 8, 11),
            abs_parent_dir="/a", abs_src_dir="/b",
        )
        session.add_all([li1, li2])
        session.commit()

        assert len(course.lecture_instances) == 2


class TestGeneralProject:
    def test_create_with_books_and_topics(self, session):
        mt = MainTopic(name="Mecánica Clásica", code="10MC")
        session.add(mt)
        session.commit()

        t1 = Topic(main_topic_id=mt.id, name="Cinemática", serial_number=1)
        t2 = Topic(main_topic_id=mt.id, name="Dinámica", serial_number=2)
        b = Book(name="Goldstein", year=2002, edition=3)
        session.add_all([t1, t2, b])
        session.commit()

        gp = GeneralProject(
            main_topic_id=mt.id,
            abs_parent_dir="/home/user/docs",
            abs_src_dir="/home/user/.config/mytex",
        )
        session.add(gp)
        session.flush()

        session.add(GeneralProjectTopic(
            general_project_id=gp.id, topic_id=t1.id,
        ))
        session.add(GeneralProjectTopic(
            general_project_id=gp.id, topic_id=t2.id,
        ))
        session.add(GeneralProjectBook(
            general_project_id=gp.id, book_id=b.id,
        ))
        session.commit()

        assert gp.root_dir == "10MC-Mecánica Clásica"
        assert len(gp.topic_links) == 2
        assert len(gp.book_links) == 1
        assert gp.book_links[0].book.name == "Goldstein"

    def test_main_topic_unique_per_project(self, session):
        mt = MainTopic(name="MC", code="10MC")
        session.add(mt)
        session.commit()

        gp1 = GeneralProject(
            main_topic_id=mt.id,
            abs_parent_dir="/a", abs_src_dir="/b",
        )
        session.add(gp1)
        session.commit()

        gp2 = GeneralProject(
            main_topic_id=mt.id,
            abs_parent_dir="/c", abs_src_dir="/d",
        )
        session.add(gp2)
        with pytest.raises(Exception):
            session.commit()

    def test_cascade_delete_links(self, session):
        mt = MainTopic(name="MC", code="10MC")
        session.add(mt)
        session.commit()

        t = Topic(main_topic_id=mt.id, name="T1", serial_number=1)
        b = Book(name="B1", year=2020)
        session.add_all([t, b])
        session.commit()

        gp = GeneralProject(
            main_topic_id=mt.id, abs_parent_dir="/a", abs_src_dir="/b",
        )
        session.add(gp)
        session.flush()
        session.add(GeneralProjectTopic(
            general_project_id=gp.id, topic_id=t.id,
        ))
        session.add(GeneralProjectBook(
            general_project_id=gp.id, book_id=b.id,
        ))
        session.commit()

        session.delete(gp)
        session.commit()

        # Association rows should be gone
        assert session.query(GeneralProjectTopic).count() == 0
        assert session.query(GeneralProjectBook).count() == 0
        # But topic and book still exist
        assert session.query(Topic).count() == 1
        assert session.query(Book).count() == 1


# ── Seed data ──────────────────────────────────────────────────────────


class TestSeed:
    def test_seed_reference_data(self, session):
        seed_reference_data(session)

        institutions = session.query(Institution).all()
        assert len(institutions) == 3
        codes = {i.short_name for i in institutions}
        assert codes == {"UCR", "UFide", "UCIMED"}

        main_topics = session.query(MainTopic).all()
        assert len(main_topics) == 16

    def test_seed_idempotent(self, session):
        seed_reference_data(session)
        seed_reference_data(session)

        assert session.query(Institution).count() == 3
        assert session.query(MainTopic).count() == 16


# ── Foreign key enforcement ───────────────────────────────────────────


class TestForeignKeys:
    def test_fk_on_course_rejects_bad_institution(self, session):
        course = Course(
            institution_id=999, code="XX0000", name="Bad",
        )
        session.add(course)
        with pytest.raises(Exception):
            session.commit()

    def test_fk_on_topic_rejects_bad_main_topic(self, session):
        topic = Topic(main_topic_id=999, name="Bad", serial_number=1)
        session.add(topic)
        with pytest.raises(Exception):
            session.commit()
