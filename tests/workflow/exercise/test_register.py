"""Tests for workflow exercise register and register-batch commands.

TDD RED → GREEN for Task 1B.
"""

from __future__ import annotations

import json
import textwrap

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.models.exercises import Exercise
from workflow.db.repos.sqlalchemy import SqlExerciseRepo
from workflow.exercise.cli import exercise


def _enable_fk(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk)
    GlobalBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def runner():
    return CliRunner()


# ── Minimal valid .tex for register ─────────────────────────────────────────

_TEX_CONTENT = textwrap.dedent("""\
    % ---
    % id: register-test-ssu-001
    % type: SSU
    % difficulty: medium
    % taxonomy_level: Usar-Aplicar
    % taxonomy_domain: Procedimiento Mental
    % status: complete
    % ---
    \\question{What is force?}{F=ma}
""")

_TEX_CONTENT_2 = textwrap.dedent("""\
    % ---
    % id: register-test-ssu-002
    % type: SSU
    % difficulty: easy
    % taxonomy_level: Recordar
    % taxonomy_domain: Información
    % status: complete
    % ---
    \\question{Define mass.}{Mass is the amount of matter.}
""")

_TEX_CONTENT_3 = textwrap.dedent("""\
    % ---
    % id: register-test-ssu-003
    % type: SSU
    % difficulty: hard
    % taxonomy_level: Analizar
    % taxonomy_domain: Procedimiento Mental
    % status: complete
    % ---
    \\question{Derive Newton's law.}{F=ma from dp/dt.}
""")


# ── Task 1B: register single file ───────────────────────────────────────────


class TestRegisterCommand:
    def test_register_existing_tex_exits_zero(self, runner, tmp_path, db_engine):
        """Registering an existing .tex file exits 0."""
        tex = tmp_path / "EnergiaFuerzas-UCIMED2026C1-P02SSUP011.tex"
        tex.write_text(_TEX_CONTENT)

        result = runner.invoke(
            exercise,
            [
                "register",
                "--path", str(tex),
                "--type", "SSU",
                "--course", "CB0009",
                "--cycle", "2026C1",
                "--partial", "P02",
                "--points", "2",
            ],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output

    def test_register_inserts_db_row(self, runner, tmp_path, db_engine):
        """After register, a row appears in the exercise table."""
        tex = tmp_path / "register-test-ssu-001.tex"
        tex.write_text(_TEX_CONTENT)

        runner.invoke(
            exercise,
            [
                "register",
                "--path", str(tex),
                "--type", "SSU",
                "--course", "CB0009",
                "--cycle", "2026C1",
                "--partial", "P02",
                "--points", "2",
            ],
            obj={"engine": db_engine},
        )

        with Session(db_engine) as s:
            repo = SqlExerciseRepo(s)
            ex = repo.get_by_exercise_id("register-test-ssu-001")
        assert ex is not None

    def test_register_type_enum_scm(self, runner, tmp_path, db_engine):
        """--type SCM is accepted without error."""
        tex = tmp_path / "scm-test.tex"
        scm_content = _TEX_CONTENT.replace("id: register-test-ssu-001", "id: register-scm-001")
        tex.write_text(scm_content)

        result = runner.invoke(
            exercise,
            ["register", "--path", str(tex), "--type", "SCM",
             "--course", "CB0009", "--cycle", "2026C1", "--partial", "P02", "--points", "1"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output

    def test_register_type_enum_sde(self, runner, tmp_path, db_engine):
        """--type SDE is accepted without error."""
        tex = tmp_path / "sde-test.tex"
        sde_content = _TEX_CONTENT.replace("id: register-test-ssu-001", "id: register-sde-001")
        tex.write_text(sde_content)

        result = runner.invoke(
            exercise,
            ["register", "--path", str(tex), "--type", "SDE",
             "--course", "CB0009", "--cycle", "2026C1", "--partial", "P02", "--points", "1"],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output

    def test_register_json_output(self, runner, tmp_path, db_engine):
        """--json emits list with registered, db_row_id, path, course fields."""
        tex = tmp_path / "register-test-ssu-001.tex"
        tex.write_text(_TEX_CONTENT)

        result = runner.invoke(
            exercise,
            [
                "register",
                "--path", str(tex),
                "--type", "SSU",
                "--course", "CB0009",
                "--cycle", "2026C1",
                "--partial", "P02",
                "--points", "2",
                "--json",
            ],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        row = data[0]
        assert row["registered"] is True
        assert "db_row_id" in row
        assert row["course"] == "CB0009"
        assert row["cycle"] == "2026C1"
        assert row["partial"] == "P02"
        assert row["type"] == "SSU"

    def test_register_missing_path_exits_one(self, runner, db_engine):
        """Nonexistent path exits 1 with 'not found' message."""
        result = runner.invoke(
            exercise,
            [
                "register",
                "--path", "/nonexistent/exercise.tex",
                "--type", "SSU",
                "--course", "CB0009",
                "--cycle", "2026C1",
                "--partial", "P02",
                "--points", "2",
            ],
            obj={"engine": db_engine},
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "not found" in (result.exception and str(result.exception) or "")

    def test_register_collision_exits_one(self, runner, tmp_path, db_engine):
        """Re-registering the same path exits 1 with 'already registered'."""
        tex = tmp_path / "register-test-ssu-001.tex"
        tex.write_text(_TEX_CONTENT)

        args = [
            "register",
            "--path", str(tex),
            "--type", "SSU",
            "--course", "CB0009",
            "--cycle", "2026C1",
            "--partial", "P02",
            "--points", "2",
        ]

        # First registration — should succeed
        r1 = runner.invoke(exercise, args, obj={"engine": db_engine})
        assert r1.exit_code == 0, r1.output

        # Second registration — should fail
        r2 = runner.invoke(exercise, args, obj={"engine": db_engine})
        assert r2.exit_code != 0
        assert "already registered" in r2.output.lower()


# ── Task 1B: register-batch ──────────────────────────────────────────────────


class TestRegisterBatchCommand:
    def test_register_batch_glob_three_files(self, runner, tmp_path, db_engine):
        """Glob matching 3 files registers all 3."""
        (tmp_path / "register-test-ssu-001.tex").write_text(_TEX_CONTENT)
        (tmp_path / "register-test-ssu-002.tex").write_text(_TEX_CONTENT_2)
        (tmp_path / "register-test-ssu-003.tex").write_text(_TEX_CONTENT_3)

        result = runner.invoke(
            exercise,
            [
                "register-batch",
                str(tmp_path / "register-test-ssu-*.tex"),
                "--course", "CB0009",
                "--cycle", "2026C1",
                "--partial", "P02",
                "--json",
            ],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_register_batch_all_registered_true(self, runner, tmp_path, db_engine):
        """Each entry in batch JSON output has registered=True."""
        (tmp_path / "register-test-ssu-001.tex").write_text(_TEX_CONTENT)
        (tmp_path / "register-test-ssu-002.tex").write_text(_TEX_CONTENT_2)

        result = runner.invoke(
            exercise,
            [
                "register-batch",
                str(tmp_path / "register-test-ssu-*.tex"),
                "--course", "CB0009",
                "--cycle", "2026C1",
                "--partial", "P02",
                "--json",
            ],
            obj={"engine": db_engine},
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert all(d["registered"] is True for d in data)

    def test_register_batch_inserts_rows(self, runner, tmp_path, db_engine):
        """After batch register, rows appear in DB."""
        (tmp_path / "register-test-ssu-001.tex").write_text(_TEX_CONTENT)
        (tmp_path / "register-test-ssu-002.tex").write_text(_TEX_CONTENT_2)

        runner.invoke(
            exercise,
            [
                "register-batch",
                str(tmp_path / "register-test-ssu-*.tex"),
                "--course", "CB0009",
                "--cycle", "2026C1",
                "--partial", "P02",
            ],
            obj={"engine": db_engine},
        )

        with Session(db_engine) as s:
            repo = SqlExerciseRepo(s)
            assert repo.get_by_exercise_id("register-test-ssu-001") is not None
            assert repo.get_by_exercise_id("register-test-ssu-002") is not None

    def test_register_batch_no_match_exits_nonzero(self, runner, tmp_path, db_engine):
        """Glob matching no files exits non-zero."""
        result = runner.invoke(
            exercise,
            [
                "register-batch",
                str(tmp_path / "nonexistent-*.tex"),
                "--course", "CB0009",
                "--cycle", "2026C1",
                "--partial", "P02",
            ],
            obj={"engine": db_engine},
        )
        assert result.exit_code != 0
