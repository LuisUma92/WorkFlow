"""Tests for workflow.exercise.service — business logic layer."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.engine import _enable_fk_pragma
from workflow.db.models.exercises import Exercise
from workflow.exercise.service import (
    SyncResult,
    delete_orphans,
    file_hash,
    gc_orphans,
    parse_and_filter,
    sync_exercises,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def mem_engine():
    """In-memory SQLite engine with GlobalBase tables."""
    import workflow.db.models.exercises  # noqa: F401 — populate metadata

    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk_pragma)
    GlobalBase.metadata.create_all(engine)
    return engine


@pytest.fixture()
def session(mem_engine):
    with Session(mem_engine) as sess:
        yield sess


# ── SyncResult ───────────────────────────────────────────────────────────────


class TestSyncResult:
    def test_sync_result_frozen(self) -> None:
        """SyncResult is immutable (frozen dataclass)."""
        result = SyncResult(new=1, updated=2, unchanged=3, skipped=4)
        with pytest.raises((AttributeError, TypeError)):
            result.new = 99  # type: ignore[misc]

    def test_sync_result_fields(self) -> None:
        """SyncResult stores all four counter fields."""
        result = SyncResult(new=1, updated=2, unchanged=3, skipped=4)
        assert result.new == 1
        assert result.updated == 2
        assert result.unchanged == 3
        assert result.skipped == 4


# ── file_hash ────────────────────────────────────────────────────────────────


class TestFileHash:
    def test_file_hash_deterministic(self, tmp_path: Path) -> None:
        """Same file contents always produce the same hash."""
        f = tmp_path / "ex.tex"
        f.write_bytes(b"% exercise content")

        h1 = file_hash(f)
        h2 = file_hash(f)

        assert h1 == h2

    def test_file_hash_changes_with_content(self, tmp_path: Path) -> None:
        """Different content produces a different hash."""
        f = tmp_path / "ex.tex"
        f.write_bytes(b"version 1")
        h1 = file_hash(f)

        f.write_bytes(b"version 2")
        h2 = file_hash(f)

        assert h1 != h2

    def test_file_hash_is_hex_string(self, tmp_path: Path) -> None:
        """file_hash returns a lowercase hex string."""
        f = tmp_path / "ex.tex"
        f.write_bytes(b"data")

        h = file_hash(f)

        assert isinstance(h, str)
        assert all(c in "0123456789abcdef" for c in h)


# ── gc_orphans ───────────────────────────────────────────────────────────────


class TestGcOrphans:
    def test_gc_orphans_empty_db(self, session: Session) -> None:
        """No records → empty lists."""
        ids, paths = gc_orphans(session)
        assert ids == []
        assert paths == []

    def test_gc_orphans_returns_missing_file_ids(
        self, session: Session, tmp_path: Path
    ) -> None:
        """Exercises pointing to non-existent files are returned as orphans."""
        ex = Exercise(
            exercise_id="orphan-01",
            source_path=str(tmp_path / "missing.tex"),
            file_hash="abc123",
            status="complete",
        )
        session.add(ex)
        session.flush()

        ids, paths = gc_orphans(session)

        assert "orphan-01" in ids

    def test_gc_orphans_skips_existing_files(
        self, session: Session, tmp_path: Path
    ) -> None:
        """Exercises pointing to existing files are NOT returned."""
        f = tmp_path / "present.tex"
        f.write_text("% content")

        ex = Exercise(
            exercise_id="present-01",
            source_path=str(f),
            file_hash="abc123",
            status="complete",
        )
        session.add(ex)
        session.flush()

        ids, _ = gc_orphans(session)

        assert "present-01" not in ids


# ── delete_orphans ───────────────────────────────────────────────────────────


class TestDeleteOrphans:
    def test_delete_orphans_removes_records(
        self, session: Session, tmp_path: Path
    ) -> None:
        """delete_orphans deletes each listed ID and returns count."""
        ex = Exercise(
            exercise_id="del-01",
            source_path=str(tmp_path / "gone.tex"),
            file_hash="abc",
            status="complete",
        )
        session.add(ex)
        session.flush()

        count = delete_orphans(session, ["del-01"])

        assert count == 1

    def test_delete_orphans_ignores_unknown_ids(self, session: Session) -> None:
        """delete_orphans returns 0 for IDs that don't exist."""
        count = delete_orphans(session, ["nonexistent-id"])
        assert count == 0


# ── sync_exercises ────────────────────────────────────────────────────────────


class TestSyncExercises:
    def _make_tex(self, path: Path, exercise_id: str = "ex-001") -> Path:
        """Write a minimal valid exercise .tex file."""
        content = (
            "% ---\n"
            f"% id: {exercise_id}\n"
            "% type: essay\n"
            "% difficulty: medium\n"
            "% taxonomy_level: Usar-Aplicar\n"
            "% taxonomy_domain: Procedimiento Mental\n"
            "% status: complete\n"
            "% ---\n"
            "\\begin{question}\nSolve this.\n\\end{question}\n"
        )
        path.write_text(content, encoding="utf-8")
        return path

    def test_sync_empty_file_list(self, session: Session) -> None:
        """Syncing no files returns zero counts and no messages."""
        result, messages = sync_exercises(session, [])
        assert result == SyncResult(new=0, updated=0, unchanged=0, skipped=0)
        assert messages == []

    def test_sync_skips_oversized_file(
        self, session: Session, tmp_path: Path
    ) -> None:
        """Files exceeding max_file_bytes are counted as skipped."""
        f = tmp_path / "big.tex"
        f.write_bytes(b"x")

        result, messages = sync_exercises(session, [f], max_file_bytes=0)

        assert result.skipped == 1
        assert any("SKIP" in m for m in messages)

    def test_sync_new_exercise(self, session: Session, tmp_path: Path) -> None:
        """A new .tex file with valid metadata is counted as new and stored in DB."""
        tex = tmp_path / "svc-001.tex"
        tex.write_text(
            "% ---\n"
            "% id: svc-test-001\n"
            "% type: essay\n"
            "% difficulty: easy\n"
            "% taxonomy_level: Recordar\n"
            "% taxonomy_domain: Información\n"
            "% tags: [physics]\n"
            "% status: complete\n"
            "% ---\n"
            "\\question{What is force?}{F = ma}\n",
            encoding="utf-8",
        )

        result, _ = sync_exercises(session, [tex])

        assert result.new == 1
        from workflow.db.repos.sqlalchemy import SqlExerciseRepo
        repo = SqlExerciseRepo(session)
        assert repo.get_by_exercise_id("svc-test-001") is not None

    def test_sync_updated_exercise(self, session: Session, tmp_path: Path) -> None:
        """Syncing a changed file increments updated counter."""
        tex = tmp_path / "svc-002.tex"
        tex.write_text(
            "% ---\n"
            "% id: svc-test-002\n"
            "% type: essay\n"
            "% difficulty: easy\n"
            "% taxonomy_level: Recordar\n"
            "% taxonomy_domain: Información\n"
            "% tags: [physics]\n"
            "% status: complete\n"
            "% ---\n"
            "\\question{First version?}{answer}\n",
            encoding="utf-8",
        )
        sync_exercises(session, [tex])

        tex.write_text(
            "% ---\n"
            "% id: svc-test-002\n"
            "% type: essay\n"
            "% difficulty: medium\n"
            "% taxonomy_level: Recordar\n"
            "% taxonomy_domain: Información\n"
            "% tags: [physics]\n"
            "% status: complete\n"
            "% ---\n"
            "\\question{Modified version?}{answer}\n",
            encoding="utf-8",
        )
        result, _ = sync_exercises(session, [tex])

        assert result.updated == 1

    def test_sync_unchanged_exercise(self, session: Session, tmp_path: Path) -> None:
        """Syncing an unmodified file increments unchanged counter."""
        tex = tmp_path / "svc-003.tex"
        tex.write_text(
            "% ---\n"
            "% id: svc-test-003\n"
            "% type: essay\n"
            "% difficulty: easy\n"
            "% taxonomy_level: Recordar\n"
            "% taxonomy_domain: Información\n"
            "% tags: [physics]\n"
            "% status: complete\n"
            "% ---\n"
            "\\question{Unchanged?}{same}\n",
            encoding="utf-8",
        )
        sync_exercises(session, [tex])
        result, _ = sync_exercises(session, [tex])

        assert result.unchanged == 1

    def test_sync_skips_parse_errors(self, session: Session, tmp_path: Path) -> None:
        """A .tex file with no \\question macro is counted as skipped."""
        tex = tmp_path / "no_question.tex"
        tex.write_text("% just a comment, no question macro\n", encoding="utf-8")

        result, messages = sync_exercises(session, [tex])

        assert result.skipped == 1

    def test_sync_skips_no_metadata(self, session: Session, tmp_path: Path) -> None:
        """A .tex file with \\question but no YAML metadata is counted as skipped."""
        tex = tmp_path / "no_meta.tex"
        tex.write_text(
            "\\question{No metadata here.}{answer}\n",
            encoding="utf-8",
        )

        result, _ = sync_exercises(session, [tex])

        assert result.skipped == 1


# ── parse_and_filter ──────────────────────────────────────────────────────────


COMPLETE_TEX = """\
% ---
% id: {ex_id}
% type: essay
% difficulty: easy
% taxonomy_level: Recordar
% taxonomy_domain: Información
% tags: [{tags}]
% status: {status}
% ---
\\question{{What is force?}}{{F = ma}}
"""


class TestParseAndFilter:
    def _write_tex(
        self,
        path: Path,
        ex_id: str,
        status: str = "complete",
        tags: str = "physics",
    ) -> Path:
        path.write_text(
            COMPLETE_TEX.format(ex_id=ex_id, status=status, tags=tags),
            encoding="utf-8",
        )
        return path

    def test_parse_and_filter_by_status(self, tmp_path: Path) -> None:
        """Only exercises whose status matches the filter are returned."""
        f_complete = self._write_tex(tmp_path / "a.tex", "paf-001", status="complete")
        f_placeholder = self._write_tex(
            tmp_path / "b.tex", "paf-002", status="placeholder"
        )

        exercises, _, skipped = parse_and_filter(
            [f_complete, f_placeholder], status="complete", tag=()
        )

        ids = [ex.metadata.id for ex in exercises if ex.metadata]
        assert "paf-001" in ids
        assert "paf-002" not in ids
        assert skipped == 0

    def test_parse_and_filter_by_tag(self, tmp_path: Path) -> None:
        """Only exercises whose tags overlap with the filter tag are returned."""
        f_physics = self._write_tex(tmp_path / "c.tex", "paf-003", tags="physics")
        f_math = self._write_tex(tmp_path / "d.tex", "paf-004", tags="math")

        exercises, _, skipped = parse_and_filter(
            [f_physics, f_math], status="complete", tag=("physics",)
        )

        ids = [ex.metadata.id for ex in exercises if ex.metadata]
        assert "paf-003" in ids
        assert "paf-004" not in ids
        assert skipped == 0
