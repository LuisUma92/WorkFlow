"""0009_normalize_models — align live DB with ADR ITEP-0002 ORM reshape.

Changes applied (all tables had 0 data rows except exercise):
  1. concept     — rebuild: swap main_topic_id→content_id, add domain+CHECK
  2. content     — rebuild: drop locus columns (chapter/section/page/exercise)
  3. bib_content — rebuild: add locus columns (chapter/section/page/exercise)
  4. exercise    — table-swap to drop concepts+content_id columns (2983 rows kept)
                   orphan exercise.concepts JSON dumped before drop
  5. exercise_concept — create M2M table (was previously missing)

All steps are individually idempotent: each probes the current schema before
making any changes and returns early if the target state is already present.
"""

from __future__ import annotations

import datetime

from sqlalchemy.engine import Connection

revision: str = "0009_normalize_models"
description: str = (
    "Concept→Content, BibContent gains locus columns, "
    "ExerciseConcept M2M, drop Exercise.concepts+content_id "
    "(ADR ITEP-0002 refresh)"
)
base: str = "global"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _col_names(connection: Connection, table: str) -> set[str]:
    """Return the set of column names for *table* (empty set if table absent)."""
    rows = connection.exec_driver_sql(
        f"PRAGMA table_info({table})"
    ).fetchall()
    return {row[1] for row in rows}


def _table_exists(connection: Connection, name: str) -> bool:
    row = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _index_exists(connection: Connection, name: str) -> bool:
    row = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Idempotency probe
# ---------------------------------------------------------------------------

def _already_applied(connection: Connection) -> bool:
    """Return True if the migration has already been fully applied."""
    exercise_cols = _col_names(connection, "exercise")
    bib_content_cols = _col_names(connection, "bib_content")
    concept_cols = _col_names(connection, "concept")

    already = (
        "concepts" not in exercise_cols          # dropped
        and "content_id" not in exercise_cols    # dropped
        and "chapter_number" in bib_content_cols  # added
        and "content_id" in concept_cols         # rebuilt
        and "main_topic_id" not in concept_cols  # removed
    )
    return already


# ---------------------------------------------------------------------------
# Main upgrade
# ---------------------------------------------------------------------------

def upgrade(connection: Connection) -> None:  # noqa: C901
    if _already_applied(connection):
        return  # fully idempotent

    connection.exec_driver_sql("PRAGMA foreign_keys = OFF")

    # ── Step 1: concept table rebuild (0 rows) ────────────────────────────
    # Old shape: (id, main_topic_id, code, label, description, parent_id, created_at)
    # New shape: (id, content_id NOT NULL→content(id), domain VARCHAR(40) NOT NULL,
    #             code UNIQUE, label NOT NULL, description, parent_id→SET NULL, created_at)
    # + CHECK constraint ck_taxonomy_domain
    _rebuild_concept(connection)

    # ── Step 2: content column drop (0 rows) ──────────────────────────────
    # Remove: chapter_number, section_number, first_page, last_page,
    #         first_exercise, last_exercise  (those move to bib_content)
    # Keep: id, topic_id, name
    _rebuild_content(connection)

    # ── Step 3: bib_content table rebuild (0 rows) ────────────────────────
    # Old shape: (bib_entry_id PK, content_id PK)  — bare link table
    # New shape: adds chapter_number, section_number, first_page, last_page,
    #            first_exercise (nullable), last_exercise (nullable)
    _rebuild_bib_content(connection)

    # ── Step 4: exercise — drop concepts + content_id columns (2983 rows) ─
    # Dump orphan concept JSON first, then table-swap to preserve all rows.
    _dump_orphan_exercise_concepts(connection)
    _rebuild_exercise(connection)

    # ── Step 5: exercise_concept M2M table ────────────────────────────────
    _create_exercise_concept(connection)

    connection.exec_driver_sql("PRAGMA foreign_keys = ON")


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------

def _rebuild_concept(connection: Connection) -> None:
    """Rebuild concept table with new shape (0 rows — safe drop+recreate)."""
    cols = _col_names(connection, "concept")
    if "content_id" in cols and "main_topic_id" not in cols:
        return  # already rebuilt

    # Drop old table (0 rows, no dependants at this point; note_concept was
    # already handled by migration 0008; exercise_concept doesn't exist yet)
    if _table_exists(connection, "concept"):
        connection.exec_driver_sql("DROP TABLE concept")

    connection.exec_driver_sql(
        """
        CREATE TABLE concept (
            id          INTEGER NOT NULL PRIMARY KEY,
            content_id  INTEGER NOT NULL
                            REFERENCES content(id) ON DELETE RESTRICT,
            domain      VARCHAR(40) NOT NULL,
            code        VARCHAR(32) UNIQUE,
            label       VARCHAR(255) NOT NULL,
            description TEXT,
            parent_id   INTEGER
                            REFERENCES concept(id) ON DELETE SET NULL,
            created_at  DATETIME,
            CONSTRAINT ck_taxonomy_domain CHECK (
                domain IN (
                    'Información',
                    'Procedimiento Mental',
                    'Procedimiento Psicomotor',
                    'Metacognitivo'
                )
            )
        )
        """
    )


def _rebuild_content(connection: Connection) -> None:
    """Slim content down to (id, topic_id, name) — drop locus columns."""
    cols = _col_names(connection, "content")
    if "chapter_number" not in cols:
        return  # already rebuilt (or never had those columns)

    connection.exec_driver_sql(
        """
        CREATE TABLE content_new (
            id          INTEGER NOT NULL PRIMARY KEY,
            topic_id    INTEGER NOT NULL
                            REFERENCES topic(id),
            name        VARCHAR(200) NOT NULL
        )
        """
    )
    connection.exec_driver_sql(
        "INSERT INTO content_new (id, topic_id, name) "
        "SELECT id, topic_id, name FROM content"
    )
    connection.exec_driver_sql("DROP TABLE content")
    connection.exec_driver_sql(
        "ALTER TABLE content_new RENAME TO content"
    )


def _rebuild_bib_content(connection: Connection) -> None:
    """Add locus columns to bib_content (0 rows — safe drop+recreate)."""
    cols = _col_names(connection, "bib_content")
    if "chapter_number" in cols:
        return  # already has the new columns

    if _table_exists(connection, "bib_content"):
        connection.exec_driver_sql("DROP TABLE bib_content")

    connection.exec_driver_sql(
        """
        CREATE TABLE bib_content (
            bib_entry_id    INTEGER NOT NULL
                                REFERENCES bib_entry(id),
            content_id      INTEGER NOT NULL
                                REFERENCES content(id),
            chapter_number  INTEGER NOT NULL,
            section_number  INTEGER NOT NULL,
            first_page      INTEGER NOT NULL,
            last_page       INTEGER NOT NULL,
            first_exercise  INTEGER,
            last_exercise   INTEGER,
            PRIMARY KEY (bib_entry_id, content_id)
        )
        """
    )


def _dump_orphan_exercise_concepts(connection: Connection) -> None:
    """Write dangling exercise.concepts JSON to a log file before the column is dropped."""
    cols = _col_names(connection, "exercise")
    if "concepts" not in cols:
        return  # column already gone — nothing to dump

    rows = connection.exec_driver_sql(
        "SELECT id, exercise_id, concepts FROM exercise "
        "WHERE concepts IS NOT NULL AND concepts != '' AND concepts != '[]'"
    ).fetchall()

    if not rows:
        return

    # Lazy import to avoid circular imports in the migration module.
    from workflow import paths as _paths  # lazy: avoids import cycle in migration module

    dump_path = _paths.data_dir() / "migration-0009-orphan-exercise-concepts.txt"
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    with dump_path.open("a", encoding="utf-8") as fh:
        fh.write(
            f"# migration 0009 — orphan exercise.concepts entries — "
            f"{datetime.datetime.now().isoformat(timespec='seconds')}\n"
        )
        for row in rows:
            fh.write(f"{row[0]}\t{row[1]}\t{row[2]}\n")


def _rebuild_exercise(connection: Connection) -> None:
    """Table-swap exercise to drop concepts + content_id columns; preserve all rows."""
    cols = _col_names(connection, "exercise")
    if "concepts" not in cols and "content_id" not in cols:
        return  # already rebuilt

    # Re-create existing non-idempotent indexes so we can recreate them after swap
    # Known indexes on exercise from ORM: ix_exercise_exercise_id (unique)
    # We check dynamically in case the live DB has extras.
    index_rows = connection.exec_driver_sql(
        "PRAGMA index_list(exercise)"
    ).fetchall()
    # index_rows columns: seq, name, unique, origin, partial
    existing_indexes = []
    for idx_row in index_rows:
        idx_name = idx_row[1]
        idx_unique = bool(idx_row[2])
        # Skip auto-created indexes (sqlite_autoindex_*)
        if idx_name.startswith("sqlite_autoindex"):
            continue
        # Get columns for this index
        idx_cols = connection.exec_driver_sql(
            f"PRAGMA index_info({idx_name})"
        ).fetchall()
        # index_info columns: seqno, cid, name
        col_names_for_idx = [c[2] for c in idx_cols]
        # Skip any index that covers a column we're dropping
        if any(c in ("concepts", "content_id") for c in col_names_for_idx):
            continue
        existing_indexes.append((idx_name, idx_unique, col_names_for_idx))

    # Columns to keep (verbatim from ORM, minus concepts and content_id)
    connection.exec_driver_sql(
        """
        CREATE TABLE exercise_new (
            id              INTEGER NOT NULL PRIMARY KEY,
            exercise_id     VARCHAR(100) UNIQUE,
            source_path     TEXT,
            file_hash       VARCHAR(64),
            status          VARCHAR(20),
            type            VARCHAR(20),
            difficulty      VARCHAR(10),
            taxonomy_level  VARCHAR(30),
            taxonomy_domain VARCHAR(30),
            tags            TEXT,
            book_id         INTEGER REFERENCES bib_entry(id),
            default_grade   FLOAT,
            penalty         FLOAT,
            has_images      BOOLEAN,
            image_refs      TEXT,
            diagram_id      VARCHAR(100),
            option_count    INTEGER,
            created_at      DATETIME,
            updated_at      DATETIME
        )
        """
    )
    connection.exec_driver_sql(
        """
        INSERT INTO exercise_new (
            id, exercise_id, source_path, file_hash, status, type,
            difficulty, taxonomy_level, taxonomy_domain, tags, book_id,
            default_grade, penalty, has_images, image_refs, diagram_id,
            option_count, created_at, updated_at
        )
        SELECT
            id, exercise_id, source_path, file_hash, status, type,
            difficulty, taxonomy_level, taxonomy_domain, tags, book_id,
            default_grade, penalty, has_images, image_refs, diagram_id,
            option_count, created_at, updated_at
        FROM exercise
        """
    )
    connection.exec_driver_sql("DROP TABLE exercise")
    connection.exec_driver_sql(
        "ALTER TABLE exercise_new RENAME TO exercise"
    )

    # Recreate indexes that survived the column filter
    for idx_name, idx_unique, col_names_for_idx in existing_indexes:
        unique_kw = "UNIQUE " if idx_unique else ""
        cols_sql = ", ".join(col_names_for_idx)
        connection.exec_driver_sql(
            f"CREATE {unique_kw}INDEX IF NOT EXISTS {idx_name} ON exercise ({cols_sql})"
        )


def _create_exercise_concept(connection: Connection) -> None:
    """Create exercise_concept M2M table if absent."""
    if _table_exists(connection, "exercise_concept"):
        return

    connection.exec_driver_sql(
        """
        CREATE TABLE exercise_concept (
            exercise_id INTEGER NOT NULL
                            REFERENCES exercise(id) ON DELETE CASCADE,
            concept_id  INTEGER NOT NULL
                            REFERENCES concept(id)  ON DELETE CASCADE,
            PRIMARY KEY (exercise_id, concept_id)
        )
        """
    )
    if not _index_exists(connection, "ix_exercise_concept_concept"):
        connection.exec_driver_sql(
            "CREATE INDEX ix_exercise_concept_concept "
            "ON exercise_concept (concept_id)"
        )
