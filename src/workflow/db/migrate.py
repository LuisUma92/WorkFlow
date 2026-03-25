"""
Data migration scripts for the WorkFlow unified database.

Phase 1c: migrate existing data from:
  - ITEP's old SQLite (itep.db) → workflow.db
  - PRISMAreview's MariaDB (via SQLite dump) → workflow.db

Usage (CLI):
    python -m workflow.db.migrate itep /path/to/old_itep.db
    python -m workflow.db.migrate prisma /path/to/prisma_dump.db
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from workflow.db.engine import get_global_engine, init_global_db, get_global_session
from workflow.db.seed import seed_reference_data
from workflow.db.models.academic import (
    Institution,
    MainTopic,
    Topic,
    Content,
    BibContent,
    Course,
    CourseContent,
    EvaluationTemplate,
    Item,
    EvaluationItem,
    CourseEvaluation,
)
from workflow.db.models.bibliography import (
    Author,
    AuthorType,
    BibEntry,
    BibAuthor,
)
from workflow.db.models.project import (
    GeneralProject,
    GeneralProjectBib,
    GeneralProjectTopic,
    LectureInstance,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _get_or_create(session: Session, model, defaults: dict | None = None, **kwargs):
    """Return existing row or create a new one. Returns (instance, created)."""
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    params = dict(kwargs)
    if defaults:
        params.update(defaults)
    instance = model(**params)
    session.add(instance)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        instance = session.query(model).filter_by(**kwargs).first()
        return instance, False
    return instance, True


def _rows_as_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    """Return all rows from cursor as a list of dicts."""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# ── ITEP migration ─────────────────────────────────────────────────────────


def migrate_itep_db(old_db_path: Path, session: Session) -> dict:
    """
    Read the old ITEP SQLite database and insert its data into the unified
    workflow.db via the given SQLAlchemy Session.

    Old schema tables consumed:
        institution, main_topic, author, book, book_author, book_content,
        topic, content, course, course_content, evaluation_template, item,
        evaluation_item, course_evaluation, lecture_instance,
        general_project, general_project_book, general_project_topic

    Key schema differences handled:
        book       → BibEntry  (name→title, entry_type fixed to 'book')
        book_author→ BibAuthor (author_type str → AuthorType lookup)
        book_content→BibContent (book_id → bib_entry_id)
        general_project_book → GeneralProjectBib (book_id → bib_entry_id)

    Returns a summary dict with counts of rows inserted per entity.
    """
    old_db_path = Path(old_db_path)
    if not old_db_path.exists():
        raise FileNotFoundError(f"Old ITEP database not found: {old_db_path}")

    summary: dict[str, int] = {}

    # ── Ensure reference data is present ──────────────────────────────────
    seed_reference_data(session)

    # ── id remapping tables (old id → new id) ─────────────────────────────
    inst_map: dict[int, int] = {}
    mt_map: dict[int, int] = {}
    author_map: dict[int, int] = {}
    book_map: dict[int, int] = {}  # old book.id → new BibEntry.id
    topic_map: dict[int, int] = {}
    content_map: dict[int, int] = {}
    course_map: dict[int, int] = {}
    eval_tmpl_map: dict[int, int] = {}
    item_map: dict[int, int] = {}
    gp_map: dict[int, int] = {}

    conn = sqlite3.connect(old_db_path)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 1. Institutions (match by short_name — seed already inserted them)
        cur.execute("SELECT * FROM institution")
        for row in _rows_as_dicts(cur):
            inst, _ = _get_or_create(
                session,
                Institution,
                short_name=row["short_name"],
                defaults={
                    "full_name": row["full_name"],
                    "cycle_weeks": row["cycle_weeks"],
                    "cycle_name": row["cycle_name"],
                    "moodle_url": row.get("moodle_url", ""),
                },
            )
            inst_map[row["id"]] = inst.id
        session.commit()
        summary["institutions"] = len(inst_map)

        # 2. MainTopics (match by code)
        cur.execute("SELECT * FROM main_topic")
        for row in _rows_as_dicts(cur):
            mt, _ = _get_or_create(
                session,
                MainTopic,
                code=row["code"],
                defaults={"name": row["name"], "ddc_mds": row.get("ddc_mds", "")},
            )
            mt_map[row["id"]] = mt.id
        session.commit()
        summary["main_topics"] = len(mt_map)

        # 3. Authors
        inserted_authors = 0
        cur.execute("SELECT * FROM author")
        for row in _rows_as_dicts(cur):
            author, created = _get_or_create(
                session,
                Author,
                first_name=row["first_name"],
                last_name=row["last_name"],
                defaults={
                    "alias": row.get("alias"),
                    "affiliation": row.get("affiliation"),
                },
            )
            author_map[row["id"]] = author.id
            if created:
                inserted_authors += 1
        session.commit()
        summary["authors"] = inserted_authors

        # 4. Books → BibEntry (entry_type='book', name→title)
        inserted_bib = 0
        cur.execute("SELECT * FROM book")
        for row in _rows_as_dicts(cur):
            bib, created = _get_or_create(
                session,
                BibEntry,
                title=row["name"],
                year=row.get("year"),
                volume=None,
                defaults={
                    "entry_type": "book",
                    "edition": row.get("edition"),
                },
            )
            book_map[row["id"]] = bib.id
            if created:
                inserted_bib += 1
        session.commit()
        summary["bib_entries"] = inserted_bib

        # 5. BookAuthor → BibAuthor
        #    old author_type is a plain string; look up / create AuthorType
        inserted_bib_authors = 0
        cur.execute("SELECT * FROM book_author")
        for row in _rows_as_dicts(cur):
            old_book_id = row["book_id"]
            old_author_id = row["author_id"]
            if old_book_id not in book_map or old_author_id not in author_map:
                continue
            type_str = row.get("author_type") or "author"
            at, _ = _get_or_create(session, AuthorType, type_of_author=type_str)
            _, created = _get_or_create(
                session,
                BibAuthor,
                bib_entry_id=book_map[old_book_id],
                author_id=author_map[old_author_id],
                author_type_id=at.id,
                defaults={"first_author": bool(row.get("first_author", False))},
            )
            if created:
                inserted_bib_authors += 1
        session.commit()
        summary["bib_authors"] = inserted_bib_authors

        # 6. Topics
        inserted_topics = 0
        cur.execute("SELECT * FROM topic")
        for row in _rows_as_dicts(cur):
            if row["main_topic_id"] not in mt_map:
                continue
            topic, created = _get_or_create(
                session,
                Topic,
                main_topic_id=mt_map[row["main_topic_id"]],
                serial_number=row["serial_number"],
                defaults={"name": row["name"]},
            )
            topic_map[row["id"]] = topic.id
            if created:
                inserted_topics += 1
        session.commit()
        summary["topics"] = inserted_topics

        # 7. Contents
        inserted_contents = 0
        cur.execute("SELECT * FROM content")
        for row in _rows_as_dicts(cur):
            if row["topic_id"] not in topic_map:
                continue
            content, created = _get_or_create(
                session,
                Content,
                topic_id=topic_map[row["topic_id"]],
                chapter_number=row["chapter_number"],
                section_number=row["section_number"],
                defaults={
                    "name": row["name"],
                    "first_page": row["first_page"],
                    "last_page": row["last_page"],
                    "first_exercise": row.get("first_exercise"),
                    "last_exercise": row.get("last_exercise"),
                },
            )
            content_map[row["id"]] = content.id
            if created:
                inserted_contents += 1
        session.commit()
        summary["contents"] = inserted_contents

        # 8. BookContent → BibContent
        inserted_bib_content = 0
        cur.execute("SELECT * FROM book_content")
        for row in _rows_as_dicts(cur):
            if row["book_id"] not in book_map or row["content_id"] not in content_map:
                continue
            _, created = _get_or_create(
                session,
                BibContent,
                bib_entry_id=book_map[row["book_id"]],
                content_id=content_map[row["content_id"]],
            )
            if created:
                inserted_bib_content += 1
        session.commit()
        summary["bib_contents"] = inserted_bib_content

        # 9. Courses
        inserted_courses = 0
        cur.execute("SELECT * FROM course")
        for row in _rows_as_dicts(cur):
            if row["institution_id"] not in inst_map:
                continue
            course, created = _get_or_create(
                session,
                Course,
                institution_id=inst_map[row["institution_id"]],
                code=row["code"],
                defaults={
                    "name": row["name"],
                    "lectures_per_week": row.get("lectures_per_week", 3),
                    "hours_per_lecture": row.get("hours_per_lecture", 2),
                },
            )
            course_map[row["id"]] = course.id
            if created:
                inserted_courses += 1
        session.commit()
        summary["courses"] = inserted_courses

        # 10. CourseContent
        inserted_cc = 0
        cur.execute("SELECT * FROM course_content")
        for row in _rows_as_dicts(cur):
            if row["course_id"] not in course_map or row["content_id"] not in content_map:
                continue
            _, created = _get_or_create(
                session,
                CourseContent,
                course_id=course_map[row["course_id"]],
                content_id=content_map[row["content_id"]],
                lecture_week=row["lecture_week"],
            )
            if created:
                inserted_cc += 1
        session.commit()
        summary["course_contents"] = inserted_cc

        # 11. EvaluationTemplates
        inserted_eval_tmpl = 0
        cur.execute("SELECT * FROM evaluation_template")
        for row in _rows_as_dicts(cur):
            if row["institution_id"] not in inst_map:
                continue
            et, created = _get_or_create(
                session,
                EvaluationTemplate,
                institution_id=inst_map[row["institution_id"]],
                name=row["name"],
                defaults={"template_file": row.get("template_file", "")},
            )
            eval_tmpl_map[row["id"]] = et.id
            if created:
                inserted_eval_tmpl += 1
        session.commit()
        summary["evaluation_templates"] = inserted_eval_tmpl

        # 12. Items
        inserted_items = 0
        cur.execute("SELECT * FROM item")
        for row in _rows_as_dicts(cur):
            item, created = _get_or_create(
                session,
                Item,
                name=row["name"],
                taxonomy_level=row["taxonomy_level"],
                taxonomy_domain=row["taxonomy_domain"],
                defaults={"template_file": row.get("template_file", "")},
            )
            item_map[row["id"]] = item.id
            if created:
                inserted_items += 1
        session.commit()
        summary["items"] = inserted_items

        # 13. EvaluationItems
        inserted_ei = 0
        cur.execute("SELECT * FROM evaluation_item")
        for row in _rows_as_dicts(cur):
            if row["evaluation_id"] not in eval_tmpl_map or row["item_id"] not in item_map:
                continue
            _, created = _get_or_create(
                session,
                EvaluationItem,
                evaluation_id=eval_tmpl_map[row["evaluation_id"]],
                item_id=item_map[row["item_id"]],
                defaults={
                    "total_amount": row.get("total_amount", 1),
                    "points_per_item": row.get("points_per_item", 1),
                },
            )
            if created:
                inserted_ei += 1
        session.commit()
        summary["evaluation_items"] = inserted_ei

        # 14. CourseEvaluations
        inserted_ce = 0
        cur.execute("SELECT * FROM course_evaluation")
        for row in _rows_as_dicts(cur):
            if (
                row["course_id"] not in course_map
                or row["evaluation_id"] not in eval_tmpl_map
            ):
                continue
            _, created = _get_or_create(
                session,
                CourseEvaluation,
                course_id=course_map[row["course_id"]],
                evaluation_id=eval_tmpl_map[row["evaluation_id"]],
                serial_number=row.get("serial_number", 1),
                defaults={
                    "percentage": row.get("percentage", 0.0),
                    "evaluation_week": row.get("evaluation_week", 1),
                },
            )
            if created:
                inserted_ce += 1
        session.commit()
        summary["course_evaluations"] = inserted_ce

        # 15. LectureInstances
        inserted_li = 0
        cur.execute("SELECT * FROM lecture_instance")
        for row in _rows_as_dicts(cur):
            if row["course_id"] not in course_map:
                continue
            _, created = _get_or_create(
                session,
                LectureInstance,
                course_id=course_map[row["course_id"]],
                year=row["year"],
                cycle=row["cycle"],
                defaults={
                    "first_monday": row["first_monday"],
                    "abs_parent_dir": row.get("abs_parent_dir", ""),
                    "abs_src_dir": row.get("abs_src_dir", ""),
                    "version": row.get("version", "1.0.0"),
                },
            )
            if created:
                inserted_li += 1
        session.commit()
        summary["lecture_instances"] = inserted_li

        # 16. GeneralProjects
        inserted_gp = 0
        cur.execute("SELECT * FROM general_project")
        for row in _rows_as_dicts(cur):
            if row["main_topic_id"] not in mt_map:
                continue
            gp, created = _get_or_create(
                session,
                GeneralProject,
                main_topic_id=mt_map[row["main_topic_id"]],
                defaults={
                    "abs_parent_dir": row.get("abs_parent_dir", ""),
                    "abs_src_dir": row.get("abs_src_dir", ""),
                    "version": row.get("version", "1.0.0"),
                },
            )
            gp_map[row["id"]] = gp.id
            if created:
                inserted_gp += 1
        session.commit()
        summary["general_projects"] = inserted_gp

        # 17. GeneralProjectBook → GeneralProjectBib
        inserted_gpb = 0
        cur.execute("SELECT * FROM general_project_book")
        for row in _rows_as_dicts(cur):
            if row["general_project_id"] not in gp_map or row["book_id"] not in book_map:
                continue
            _, created = _get_or_create(
                session,
                GeneralProjectBib,
                general_project_id=gp_map[row["general_project_id"]],
                bib_entry_id=book_map[row["book_id"]],
            )
            if created:
                inserted_gpb += 1
        session.commit()
        summary["general_project_bibs"] = inserted_gpb

        # 18. GeneralProjectTopic (same structure, just id remapping)
        inserted_gpt = 0
        cur.execute("SELECT * FROM general_project_topic")
        for row in _rows_as_dicts(cur):
            if row["general_project_id"] not in gp_map or row["topic_id"] not in topic_map:
                continue
            _, created = _get_or_create(
                session,
                GeneralProjectTopic,
                general_project_id=gp_map[row["general_project_id"]],
                topic_id=topic_map[row["topic_id"]],
            )
            if created:
                inserted_gpt += 1
        session.commit()
        summary["general_project_topics"] = inserted_gpt

    finally:
        conn.close()
    return summary


# ── PRISMAreview migration ─────────────────────────────────────────────────


def migrate_prisma_dump(dump_db_path: Path, session: Session) -> dict:
    """
    Migrate PRISMAreview data from a SQLite dump of the MariaDB database.

    To create the dump from MariaDB:
        mysqldump --compatible=ansi --skip-extended-insert prismadb | \
            sqlite3 prisma_dump.db

    Or use a tool like mysql2sqlite:
        mysql2sqlite prismadb | sqlite3 prisma_dump.db

    Tables consumed from the dump:
        prismadb_bib_entries  → BibEntry
        prismadb_author       → Author
        prismadb_bib_author   → BibAuthor
        prismadb_isn_list     → IsnType
        prismadb_tags         → BibTag
        prismadb_referenced_databases → ReferencedDatabase
        prismadb_url_list     → BibUrl
        prismadb_keyword      → BibKeyword

    Returns a summary dict with counts of rows inserted per entity.
    """
    # TODO: implement when MariaDB dump is available
    # Rough field mappings for reference:
    #
    # prismadb_isn_list: id, code  → IsnType: id, code
    # prismadb_author: id, first_name, last_name, alias, affiliation
    #     → Author (same fields)
    # prismadb_bib_entries: id, entry_type, bibkey, title, year, volume,
    #     publisher, journal, doi, isn, isn_type_id, abstract_text, ...
    #     → BibEntry (most fields map directly)
    # prismadb_bib_author: id, bib_entry_id, author_id, author_type, first_author
    #     → BibAuthor (author_type str → AuthorType lookup)
    # prismadb_tags: id, tag → BibTag: id, tag
    # prismadb_referenced_databases: id, name, proxy, aliases
    #     → ReferencedDatabase (same fields)
    # prismadb_url_list: id, bib_entry_id, database_id, url_string, main_url
    #     → BibUrl (same fields)
    # prismadb_keyword: id, keyword_list → BibKeyword (same fields)
    raise NotImplementedError(
        "migrate_prisma_dump() is not yet implemented. "
        "Dump the MariaDB database to SQLite and re-run after implementation."
    )


# ── CLI entry point ────────────────────────────────────────────────────────


def _print_summary(summary: dict, label: str) -> None:
    print(f"\n{label} migration complete:")
    for key, count in summary.items():
        print(f"  {key}: {count} rows inserted")


def main(argv: list[str] | None = None) -> None:
    import sys

    args = argv if argv is not None else sys.argv[1:]

    if len(args) < 2:
        print("Usage:")
        print("  python -m workflow.db.migrate itep /path/to/old_itep.db")
        print("  python -m workflow.db.migrate prisma /path/to/prisma_dump.db")
        sys.exit(1)

    command, db_path_str = args[0], args[1]
    db_path = Path(db_path_str)

    engine = get_global_engine()
    init_global_db(engine)
    session = get_global_session(engine)

    try:
        if command == "itep":
            summary = migrate_itep_db(db_path, session)
            _print_summary(summary, "ITEP")
        elif command == "prisma":
            summary = migrate_prisma_dump(db_path, session)
            _print_summary(summary, "PRISMAreview")
        else:
            print(f"Unknown command '{command}'. Use 'itep' or 'prisma'.")
            sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
