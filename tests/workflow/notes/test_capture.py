"""Tests for `workflow notes capture` (Wave 1 Phase 1).

LOCKED contract (2026-07-05 user gate):
- `notes capture --title TEXT [--type fleeting|literature|permanent (default
  fleeting)] [--tags a,b] [--concepts slug1,slug2] [--bibkey KEY] [--json]`
- Creates the .md FLAT under resolve_vault_root() (no type subdirectory),
  pre-filled frontmatter, id/zettel_id via the existing generator
  (workflow.notes.ids.generate_zettel_id — same one new-id uses).
- Registers via sync_note_files([path], session) (Wave 0 D1).
- If the destination file already exists → clear error, never overwrite.
- --json → exactly {"note_path", "zettel_id", "created"}.
- --concepts is slug-only strict semantics: lenient default (warning, note
  still created, no NoteConcept row for unknown slug); --strict-concepts →
  exit 1 and NOTHING written (no file, no Note row).
"""

from __future__ import annotations

import json
import re

import yaml
from click.testing import CliRunner
from sqlalchemy import select

from workflow.db.models.knowledge import (
    Concept,
    Content,
    DisciplineArea,
    MainTopic,
    Topic,
)
from workflow.db.models.notes import Note, NoteConcept, NoteTag
from workflow.notes.cli import notes

_ZID_RE = re.compile(r"^[A-Za-z0-9_-]{8,21}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoke(global_engine, vault, args, *, catch_exceptions=False):
    """Run `notes capture <args>` with the in-memory engine + tmp vault root."""
    runner = CliRunner()
    return runner.invoke(
        notes,
        args,
        obj={"engine": global_engine},
        env={"WORKFLOW_VAULT_ROOT": str(vault)},
        catch_exceptions=catch_exceptions,
    )


def _seed_concept(session, code="known-concept"):
    da = DisciplineArea(
        code="SC0001", name="Science", discipline_num=1, topic_num=1,
        area_initials="SC",
    )
    session.add(da)
    session.flush()
    mt = MainTopic(code="SC0001", name="Physics", discipline_area_id=da.id)
    session.add(mt)
    session.flush()
    tp = Topic(discipline_area_id=da.id, name="Mechanics", serial_number=1)
    session.add(tp)
    session.flush()
    ct = Content(topic_id=tp.id, name="Classical Mechanics")
    session.add(ct)
    session.flush()
    c = Concept(
        code=code, label="Known", content_id=ct.id, domain="Información",
    )
    session.add(c)
    session.commit()
    return c


def _read_fm(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.index("\n---", 3)
    return yaml.safe_load(text[4:end])


# ---------------------------------------------------------------------------
# Basic creation
# ---------------------------------------------------------------------------


class TestCaptureBasic:
    def test_title_only_creates_fleeting_note_flat(
        self, global_engine, global_session, tmp_path
    ):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _invoke(global_engine, vault, ["capture", "--title", "Quick idea"])
        assert result.exit_code == 0, result.output

        md_files = list(vault.glob("*.md"))
        assert len(md_files) == 1, "note must be created FLAT under vault root"
        assert not (vault / "notes").exists(), "no type subdirectory allowed"

        fm = _read_fm(md_files[0])
        assert fm["title"] == "Quick idea"
        assert fm["type"] == "fleeting"
        assert _ZID_RE.match(fm["id"])
        # filename convention: <zettel_id>-<slug>.md
        assert md_files[0].name == f"{fm['id']}-quick-idea.md"

    def test_note_registered_in_db_via_sync(
        self, global_engine, global_session, tmp_path
    ):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _invoke(global_engine, vault, ["capture", "--title", "DB reg"])
        assert result.exit_code == 0, result.output

        note = global_session.scalars(select(Note)).first()
        assert note is not None
        assert note.title == "DB reg"
        assert note.note_type == "fleeting"
        assert _ZID_RE.match(note.zettel_id)

    def test_type_literature_with_bibkey_roundtrips(
        self, global_engine, global_session, tmp_path
    ):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _invoke(
            global_engine, vault,
            ["capture", "--title", "Paper X", "--type", "literature",
             "--bibkey", "smith2020"],
        )
        assert result.exit_code == 0, result.output
        fm = _read_fm(next(vault.glob("*.md")))
        assert fm["type"] == "literature"
        assert fm["bibkey"] == "smith2020"

    def test_type_permanent_allowed(self, global_engine, global_session, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _invoke(
            global_engine, vault,
            ["capture", "--title", "Perm", "--type", "permanent"],
        )
        assert result.exit_code == 0, result.output
        assert _read_fm(next(vault.glob("*.md")))["type"] == "permanent"

    def test_invalid_type_rejected(self, global_engine, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _invoke(
            global_engine, vault,
            ["capture", "--title", "Bad", "--type", "bogus"],
        )
        assert result.exit_code == 2

    def test_title_required(self, global_engine, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _invoke(global_engine, vault, ["capture"])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Tags + concepts
# ---------------------------------------------------------------------------


class TestCaptureTagsConcepts:
    def test_tags_and_known_concept_create_rows(
        self, global_engine, global_session, tmp_path
    ):
        _seed_concept(global_session)
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _invoke(
            global_engine, vault,
            ["capture", "--title", "Tagged", "--tags", "a,b",
             "--concepts", "known-concept"],
        )
        assert result.exit_code == 0, result.output

        fm = _read_fm(next(vault.glob("*.md")))
        assert fm["tags"] == ["a", "b"]
        assert fm["concepts"] == ["known-concept"]

        assert global_session.query(NoteTag).count() == 2
        assert global_session.query(NoteConcept).count() == 1

    def test_unknown_concept_lenient_warns_note_created(
        self, global_engine, global_session, tmp_path
    ):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _invoke(
            global_engine, vault,
            ["capture", "--title", "Warned", "--concepts", "no-such-slug"],
        )
        assert result.exit_code == 0, result.output
        assert "no-such-slug" in result.stderr

        assert len(list(vault.glob("*.md"))) == 1
        assert global_session.query(Note).count() == 1
        assert global_session.query(NoteConcept).count() == 0

    def test_unknown_concept_strict_writes_nothing(
        self, global_engine, global_session, tmp_path
    ):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _invoke(
            global_engine, vault,
            ["capture", "--title", "Strict", "--concepts", "no-such-slug",
             "--strict-concepts"],
        )
        assert result.exit_code == 1
        assert "no-such-slug" in (result.stderr + result.output)

        assert list(vault.glob("*.md")) == [], "strict failure must not write a file"
        assert global_session.query(Note).count() == 0


# ---------------------------------------------------------------------------
# JSON contract + collision
# ---------------------------------------------------------------------------


class TestCaptureJsonAndCollision:
    def test_json_exact_key_set(self, global_engine, global_session, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _invoke(
            global_engine, vault,
            ["capture", "--title", "Json note", "--json"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert set(data.keys()) == {"note_path", "zettel_id", "created"}
        assert data["created"] is True
        assert _ZID_RE.match(data["zettel_id"])
        assert data["note_path"].endswith(".md")

    def test_json_stdout_pure_with_lenient_warning(
        self, global_engine, global_session, tmp_path
    ):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = _invoke(
            global_engine, vault,
            ["capture", "--title", "Json warn", "--concepts", "ghost-slug",
             "--json"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)  # must parse — warnings go to stderr
        assert data["created"] is True
        assert "ghost-slug" in result.stderr

    def test_existing_destination_is_clear_error(
        self, global_engine, global_session, tmp_path, monkeypatch
    ):
        import workflow.notes.capture as capture_mod

        monkeypatch.setattr(
            capture_mod, "generate_zettel_id", lambda length=12: "FIXEDid12345"
        )
        vault = tmp_path / "vault"
        vault.mkdir()

        first = _invoke(global_engine, vault, ["capture", "--title", "Same day"])
        assert first.exit_code == 0, first.output
        content_before = (vault / "FIXEDid12345-same-day.md").read_text()

        second = _invoke(global_engine, vault, ["capture", "--title", "Same day"])
        assert second.exit_code == 1
        assert "exists" in (second.stderr + second.output).lower()
        # never overwrite
        assert (vault / "FIXEDid12345-same-day.md").read_text() == content_before


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------


class TestCaptureService:
    def test_capture_result_is_frozen(self, global_session, tmp_path):
        import dataclasses

        from workflow.notes.capture import CaptureResult, capture_note

        vault = tmp_path / "vault"
        vault.mkdir()
        result = capture_note(
            global_session, title="Svc note", vault_root=vault,
        )
        assert isinstance(result, CaptureResult)
        assert dataclasses.is_dataclass(result)
        assert result.created is True
        assert result.note_path.exists()
        try:
            result.created = False
        except dataclasses.FrozenInstanceError:
            pass
        else:
            raise AssertionError("CaptureResult must be frozen")

    def test_slug_fallback_for_symbol_title(self, global_session, tmp_path):
        from workflow.notes.capture import capture_note

        vault = tmp_path / "vault"
        vault.mkdir()
        result = capture_note(global_session, title="¡¿!?", vault_root=vault)
        assert result.note_path.name.endswith("-note.md")
