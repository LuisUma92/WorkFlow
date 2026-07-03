"""Tests for fail-loud validators: --strict-concepts, invalid status, unknown keys.

Covers tasks/requests/2026-07-03-exercise-failloud-validators.md acceptance criteria:
1. `workflow exercise sync PATH --strict-concepts` exits 1, listing every dropped
   concept code on stderr; without the flag, behavior is unchanged but the warning
   names the file and the code.
2. An explicit invalid `status:` value causes parse/sync/validate to record an
   error (never a raise, per ADR-0011) naming the file, value, and valid enum.
   Absent status still falls back to `_infer_status`.
3. `validate_exercise_metadata` warns (not errors) on unrecognized frontmatter
   keys, with a difflib closest-match suggestion.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from workflow.db.base import GlobalBase
from workflow.db.engine import _enable_fk_pragma
from workflow.db.models.knowledge import Concept, Content, DisciplineArea, MainTopic, Topic
from workflow.exercise.cli import exercise
from workflow.exercise.parser import parse_exercise
from workflow.exercise.service import sync_exercises
from workflow.validation.schemas import validate_exercise_metadata


# ── Shared fixtures ─────────────────────────────────────────────────────────


def _seed_concept_chain(session: Session, code: str = "test-concept") -> Concept:
    area = DisciplineArea(
        name="Test Area",
        code="TST",
        dewey="000",
        discipline_num=1,
        topic_num=1,
        area_initials="TA",
    )
    session.add(area)
    session.flush()
    main_topic = MainTopic(name="Test Topic", code="TST-001", discipline_area_id=area.id)
    session.add(main_topic)
    session.flush()
    subtopic = Topic(name="Sub Topic", serial_number=1, discipline_area_id=area.id)
    session.add(subtopic)
    session.flush()
    content = Content(name="Test Content", topic_id=subtopic.id)
    session.add(content)
    session.flush()
    concept = Concept(
        code=code,
        label=code.replace("-", " ").title(),
        domain="Información",
        content_id=content.id,
    )
    session.add(concept)
    session.flush()
    return concept


@pytest.fixture()
def mem_engine():
    import workflow.db.models.exercises  # noqa: F401 — populate metadata
    import workflow.db.models.knowledge  # noqa: F401 — populate metadata
    import workflow.db.models.bibliography  # noqa: F401 — populate metadata
    import workflow.db.models.notes  # noqa: F401 — populate metadata

    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk_pragma)
    GlobalBase.metadata.create_all(engine)
    return engine


@pytest.fixture()
def session(mem_engine):
    with Session(mem_engine) as sess:
        yield sess


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk_pragma)
    GlobalBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def runner():
    return CliRunner()


CONCEPT_TEX_TEMPLATE = """\
% ---
% id: {ex_id}
% type: essay
% difficulty: easy
% taxonomy_level: Recordar
% taxonomy_domain: Información
% tags: []
% concepts: [{concepts}]
% status: complete
% ---
\\question{{Concept test.}}{{answer}}
"""


def _make_concept_tex(path: Path, ex_id: str, concepts: str = "") -> Path:
    path.write_text(
        CONCEPT_TEX_TEMPLATE.format(ex_id=ex_id, concepts=concepts), encoding="utf-8"
    )
    return path


# ── 1. exercise sync --strict-concepts (CLI) ────────────────────────────────


class TestSyncStrictConceptsCli:
    def test_strict_concepts_exits_1_and_lists_dropped_code(
        self, runner, tmp_path, db_engine
    ):
        _make_concept_tex(tmp_path / "ex001.tex", "sc-001", "nonexistent-concept")

        result = runner.invoke(
            exercise,
            ["sync", str(tmp_path), "--strict-concepts"],
            obj={"engine": db_engine},
        )

        assert result.exit_code == 1
        assert "ex001.tex" in result.output
        assert "nonexistent-concept" in result.output

    def test_strict_concepts_lists_every_dropped_code_across_files(
        self, runner, tmp_path, db_engine
    ):
        _make_concept_tex(tmp_path / "ex001.tex", "sc-001", "unknown-one")
        _make_concept_tex(tmp_path / "ex002.tex", "sc-002", "unknown-two")

        result = runner.invoke(
            exercise,
            ["sync", str(tmp_path), "--strict-concepts"],
            obj={"engine": db_engine},
        )

        assert result.exit_code == 1
        assert "unknown-one" in result.output
        assert "unknown-two" in result.output

    def test_without_strict_flag_exits_0_and_warns_with_file_and_code(
        self, runner, tmp_path, db_engine
    ):
        _make_concept_tex(tmp_path / "ex001.tex", "sc-003", "unknown-lenient")

        result = runner.invoke(
            exercise,
            ["sync", str(tmp_path)],
            obj={"engine": db_engine},
        )

        assert result.exit_code == 0
        assert "ex001.tex" in result.output
        assert "unknown-lenient" in result.output
        assert "WARN" in result.output

    def test_strict_concepts_does_not_persist_on_failure(
        self, runner, tmp_path, db_engine
    ):
        """Strict-mode failure rolls back — nothing from the batch is committed."""
        _make_concept_tex(tmp_path / "ex001.tex", "sc-004", "nonexistent-again")

        runner.invoke(
            exercise,
            ["sync", str(tmp_path), "--strict-concepts"],
            obj={"engine": db_engine},
        )

        from workflow.db.repos.sqlalchemy import SqlExerciseRepo

        with Session(db_engine) as session:
            repo = SqlExerciseRepo(session)
            assert repo.get_by_exercise_id("sc-004") is None


# ── 1b. sync_exercises service-level: warning names file + codes ───────────


class TestSyncExercisesConceptMessages:
    def test_lenient_warning_names_file_and_code(self, session, tmp_path):
        session.commit()
        tex = _make_concept_tex(tmp_path / "ex-lenient.tex", "sl-001", "ghost-code")

        _, messages = sync_exercises(session, [tex], strict_concepts=False)

        joined = "\n".join(messages)
        assert "ex-lenient.tex" in joined
        assert "ghost-code" in joined

    def test_strict_raises_with_all_codes_in_batch(self, session, tmp_path):
        session.commit()
        tex1 = _make_concept_tex(tmp_path / "a.tex", "sl-002", "bad-a")
        tex2 = _make_concept_tex(tmp_path / "b.tex", "sl-003", "bad-b")

        with pytest.raises(ValueError) as excinfo:
            sync_exercises(session, [tex1, tex2], strict_concepts=True)

        message = str(excinfo.value)
        assert "bad-a" in message
        assert "bad-b" in message


# ── 2. Invalid explicit status → ParseResult.errors (never a raise) ────────


INVALID_STATUS_TEX = """\
% ---
% id: bad-status-001
% type: essay
% difficulty: easy
% taxonomy_level: Recordar
% taxonomy_domain: Información
% status: solved
% ---
\\question{Real stem.}{Real solution.}
"""

ABSENT_STATUS_TEX = """\
% ---
% id: absent-status-001
% type: essay
% difficulty: easy
% taxonomy_level: Recordar
% taxonomy_domain: Información
% ---
\\question{Real stem.}{Real solution.}
"""


class TestInvalidExplicitStatusParser:
    def test_invalid_status_recorded_as_parse_error(self):
        """ADR-0011: parser never raises — invalid status becomes a ParseResult error."""
        result = parse_exercise(INVALID_STATUS_TEX, source_path="bad-status.tex")

        assert result.exercise is not None  # parser must not abort
        assert any("solved" in e for e in result.errors)
        assert any("bad-status.tex" in e for e in result.errors)
        assert any("placeholder" in e and "in_progress" in e and "complete" in e
                    for e in result.errors)

    def test_invalid_status_still_falls_back_to_inference(self):
        result = parse_exercise(INVALID_STATUS_TEX, source_path="bad-status.tex")
        assert result.exercise.status == "complete"  # inferred, not "solved"

    def test_absent_status_no_error_uses_inference(self):
        result = parse_exercise(ABSENT_STATUS_TEX, source_path="absent-status.tex")
        assert result.errors == ()
        assert result.exercise.status == "complete"


class TestInvalidExplicitStatusCli:
    def test_parse_command_exits_nonzero_on_invalid_status(self, runner, tmp_path):
        tex_file = tmp_path / "bad_status.tex"
        tex_file.write_text(INVALID_STATUS_TEX)

        result = runner.invoke(exercise, ["parse", str(tex_file)])
        assert result.exit_code != 0

    def test_sync_command_exits_nonzero_on_invalid_status(
        self, runner, tmp_path, db_engine
    ):
        tex_file = tmp_path / "bad_status.tex"
        tex_file.write_text(INVALID_STATUS_TEX)

        result = runner.invoke(
            exercise, ["sync", str(tmp_path)], obj={"engine": db_engine}
        )
        assert result.exit_code != 0

    def test_sync_command_still_exits_0_for_generic_parse_error(
        self, runner, tmp_path, db_engine
    ):
        """Non-status parse errors (e.g. missing \\question) keep the old behavior."""
        bad_file = tmp_path / "no_question.tex"
        bad_file.write_text("No question macro here.")

        result = runner.invoke(
            exercise, ["sync", str(tmp_path)], obj={"engine": db_engine}
        )
        assert result.exit_code == 0


# ── 2b. validate_exercise_metadata: status enum check ───────────────────────


class TestValidateExerciseMetadataStatus:
    def _base_data(self, **overrides):
        data = {
            "id": "vs-001",
            "type": "essay",
            "difficulty": "easy",
            "taxonomy_level": "Recordar",
            "taxonomy_domain": "Información",
        }
        data.update(overrides)
        return data

    def test_invalid_status_is_error(self):
        result, errors, warnings = validate_exercise_metadata(
            self._base_data(status="solved")
        )
        assert result is None
        assert any("status" in e and "solved" in e for e in errors)

    def test_absent_status_is_valid(self):
        result, errors, warnings = validate_exercise_metadata(self._base_data())
        assert result is not None
        assert errors == []

    def test_valid_explicit_status_is_valid(self):
        result, errors, warnings = validate_exercise_metadata(
            self._base_data(status="complete")
        )
        assert result is not None
        assert errors == []


class TestValidateExercisesCli:
    VALIDATE_INVALID_STATUS_TEX = """\
% ---
% id: valcli-001
% type: essay
% difficulty: easy
% taxonomy_level: Recordar
% taxonomy_domain: Información
% status: solved
% ---
\\question{Stem.}{Solution.}
"""

    def test_validate_exercises_exits_nonzero_on_invalid_status(self, runner, tmp_path):
        from workflow.validation.cli import validate

        (tmp_path / "bad.tex").write_text(self.VALIDATE_INVALID_STATUS_TEX)

        result = runner.invoke(validate, ["exercises", str(tmp_path)])
        assert result.exit_code != 0
        assert "status" in result.output
        assert "solved" in result.output


# ── 3. Unknown frontmatter key warning (difflib suggestion) ────────────────


class TestUnknownFrontmatterKeyWarning:
    def _base_data(self, **overrides):
        data = {
            "id": "uk-001",
            "type": "essay",
            "difficulty": "easy",
            "taxonomy_level": "Recordar",
            "taxonomy_domain": "Información",
        }
        data.update(overrides)
        return data

    def test_unknown_key_warns_with_closest_match_suggestion(self):
        data = self._base_data(contents=["ghost"])
        result, errors, warnings = validate_exercise_metadata(data)

        assert errors == []  # warning, not error — exit stays 0
        assert result is not None
        assert any(
            "contents" in w and "concepts" in w for w in warnings
        )

    def test_known_keys_produce_no_warning(self):
        data = self._base_data(tags=["x"], concepts=["y"], status="complete")
        result, errors, warnings = validate_exercise_metadata(data)

        assert result is not None
        assert errors == []
        assert warnings == []

    def test_unknown_key_with_no_close_match_still_warns(self):
        data = self._base_data(**{"zzzzz_totally_unrelated": True})
        result, errors, warnings = validate_exercise_metadata(data)

        assert any("zzzzz_totally_unrelated" in w for w in warnings)


class TestUnknownFrontmatterKeyCli:
    UNKNOWN_KEY_TEX = """\
% ---
% id: valcli-002
% type: essay
% difficulty: easy
% taxonomy_level: Recordar
% taxonomy_domain: Información
% contents: [ghost]
% status: complete
% ---
\\question{Stem.}{Solution.}
"""

    def test_validate_exercises_warns_but_exits_0(self, runner, tmp_path):
        from workflow.validation.cli import validate

        (tmp_path / "typo.tex").write_text(self.UNKNOWN_KEY_TEX)

        result = runner.invoke(validate, ["exercises", str(tmp_path)])
        assert result.exit_code == 0
        assert "contents" in result.output
        assert "concepts" in result.output
