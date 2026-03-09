"""Tests for itep.manager — CRUD operations."""

import pytest
from datetime import date

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from itep.database import (
    Base,
    Institution,
    MainTopic,
    Book,
    _enable_fk_pragma,
    seed_reference_data,
)
from itep import manager


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    event.listen(eng, "connect", _enable_fk_pragma)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    factory = sessionmaker(bind=engine)
    sess = factory()
    yield sess
    sess.close()


@pytest.fixture
def seeded(session):
    """Session with seed data loaded."""
    seed_reference_data(session)
    return session


class TestInstitutionCRUD:
    def test_create_and_lookup(self, session):
        inst = manager.create_institution(
            session, "TEST", "Test University", 16, "Trimestre",
        )
        assert inst.id is not None
        found = manager.get_institution_by_short_name(session, "TEST")
        assert found.full_name == "Test University"

    def test_list_all(self, seeded):
        all_inst = manager.list_all(seeded, Institution)
        assert len(all_inst) == 3


class TestMainTopicCRUD:
    def test_create_and_lookup(self, session):
        mt = manager.create_main_topic(session, "TestTopic", "99TT", "999")
        assert mt.id is not None
        found = manager.get_main_topic_by_code(session, "99TT")
        assert found.name == "TestTopic"


class TestAuthorBookCRUD:
    def test_create_author_and_book(self, session):
        author = manager.create_author(session, "Albert", "Einstein")
        book = manager.create_book(session, "Relativity", 1916, 1)
        ba = manager.add_book_author(
            session, book.id, author.id, "author", True,
        )
        assert ba.first_author is True

        loaded = manager.get_by_id(session, Book, book.id)
        assert len(loaded.author_links) == 1


class TestTopicContentCRUD:
    def test_create_topic_and_content(self, seeded):
        mt = manager.get_main_topic_by_code(seeded, "10MC")
        topic = manager.create_topic(seeded, mt.id, "Cinemática", 1)
        content = manager.create_content(
            seeded, topic.id, 1, 1, "Posición", 1, 25,
        )
        assert content.id is not None
        assert content.topic.name == "Cinemática"

    def test_link_book_content(self, seeded):
        mt = manager.get_main_topic_by_code(seeded, "10MC")
        topic = manager.create_topic(seeded, mt.id, "T1", 1)
        content = manager.create_content(
            seeded, topic.id, 1, 1, "C1", 1, 10,
        )
        book = manager.create_book(seeded, "B1", 2020)
        bc = manager.link_book_content(seeded, book.id, content.id)
        assert bc.book_id == book.id


class TestCourseCRUD:
    def test_create_course_with_content(self, seeded):
        ucr = manager.get_institution_by_short_name(seeded, "UCR")
        course = manager.create_course(
            seeded, ucr.id, "FS0121", "Física General I",
        )
        mt = manager.get_main_topic_by_code(seeded, "10MC")
        topic = manager.create_topic(seeded, mt.id, "Cin", 1)
        content = manager.create_content(
            seeded, topic.id, 1, 1, "Pos", 1, 10,
        )
        cc = manager.add_course_content(seeded, course.id, content.id, 1)
        assert cc.lecture_week == 1

    def test_create_evaluation_for_course(self, seeded):
        ucr = manager.get_institution_by_short_name(seeded, "UCR")
        course = manager.create_course(seeded, ucr.id, "FS0121", "FG1")
        et = manager.create_evaluation_template(seeded, ucr.id, "Parcial")
        ce = manager.add_course_evaluation(
            seeded, course.id, et.id, 1, 0.25, 6,
        )
        assert ce.percentage == 0.25


class TestLectureInstanceCRUD:
    def test_create_and_clone(self, seeded):
        ucr = manager.get_institution_by_short_name(seeded, "UCR")
        course = manager.create_course(seeded, ucr.id, "FS0121", "FG1")

        li = manager.create_lecture_instance(
            seeded, course.id, 2025, 1, date(2025, 3, 10),
            "/home/user/docs", "/home/user/.config/mytex",
        )
        assert li.root_dir == "UCR-FS0121"

        cloned = manager.clone_lecture_instance(
            seeded, li.id, 2025, 2, date(2025, 8, 11),
        )
        assert cloned.course_id == li.course_id
        assert cloned.cycle == 2
        assert cloned.id != li.id

    def test_clone_nonexistent_raises(self, seeded):
        with pytest.raises(ValueError, match="not found"):
            manager.clone_lecture_instance(
                seeded, 999, 2025, 1, date(2025, 1, 1),
            )


class TestGeneralProjectCRUD:
    def test_create_with_topics_and_books(self, seeded):
        mt = manager.get_main_topic_by_code(seeded, "10MC")
        topic = manager.create_topic(seeded, mt.id, "T1", 1)
        book = manager.create_book(seeded, "B1", 2020)

        gp = manager.create_general_project(
            seeded, mt.id, "/a", "/b",
            topic_ids=[topic.id], book_ids=[book.id],
        )
        assert gp.root_dir == "10MC-Mecánica Clásica"
        assert len(gp.topic_links) == 1
        assert len(gp.book_links) == 1


class TestDeleteOperations:
    def test_delete_by_id(self, seeded):
        mt = manager.create_main_topic(seeded, "ToDelete", "DEL1")
        assert manager.delete_by_id(seeded, MainTopic, mt.id) is True
        assert manager.get_by_id(seeded, MainTopic, mt.id) is None

    def test_delete_nonexistent(self, seeded):
        assert manager.delete_by_id(seeded, MainTopic, 9999) is False


class TestUpdateTimestamp:
    def test_update_project_timestamp(self, seeded):
        mt = manager.get_main_topic_by_code(seeded, "10MC")
        gp = manager.create_general_project(seeded, mt.id, "/a", "/b")
        old_ts = gp.last_modification
        manager.update_project_timestamp(seeded, gp)
        assert gp.last_modification >= old_ts
