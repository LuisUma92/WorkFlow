"""D3 — `workflow concept harvest` tests (TDD RED -> GREEN).

Wave 0 harvest-loop plan, Phase 2 (tasks/plans/2026-07-05-wave0-harvest-loop-plan.md).
Spec: docs/superpowers/specs/2026-07-05-fleeting-harvest-design.md.

Harvest is read-only against the DB: it never calls session.add/session.commit.
`resolve_concepts` (slug-only strict, ITEP-0012 amendment) is reused, not
re-implemented.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from workflow.concept.cli import concept
from workflow.concept.harvest import (
    AMBIGUOUS_PREFIX_BUCKET,
    UNRECOGNIZED_BUCKET,
    build_delta_yaml,
    harvest,
    match_discipline_area,
    match_discipline_areas_bulk,
    partition_concepts,
    scan_notes,
)
from workflow.concept.service import add_concept
from workflow.db.base import GlobalBase
from workflow.db.models.knowledge import Concept, Content, DisciplineArea, MainTopic, Topic
from workflow.importer.engine import import_hierarchy, load_yaml


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _enable_fk(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture()
def engine():
    import workflow.db.models.bibliography  # noqa: F401
    import workflow.db.models.academic  # noqa: F401
    import workflow.db.models.project  # noqa: F401
    import workflow.db.models.notes  # noqa: F401
    import workflow.db.models.exercises  # noqa: F401

    eng = create_engine("sqlite:///:memory:")
    event.listen(eng, "connect", _enable_fk)
    GlobalBase.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_global_db(tmp_path_factory, monkeypatch):
    base = tmp_path_factory.mktemp("xdg_harvest_cli")
    monkeypatch.setenv("XDG_DATA_HOME", str(base))
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(base / "workflow"))


def _write_note(directory: Path, note_id: str, concepts) -> Path:
    fm = {
        "id": note_id,
        "title": f"Note {note_id}",
        "type": "permanent",
        "tags": [],
        "concepts": concepts,
        "references": [],
        "exercises": [],
        "images": [],
    }
    content = "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False) + "---\n\nBody.\n"
    path = directory / f"{note_id}.md"
    path.write_text(content, encoding="utf-8")
    return path


def _seed_em_area(session: Session, code: str = "0040EM") -> DisciplineArea:
    da = DisciplineArea(
        code=code, name="Electromagnetismo",
        discipline_num=0, topic_num=40, area_initials="EM",
    )
    session.add(da)
    session.flush()
    return da


def _seed_known_concept(session: Session, code: str, da_code: str = "0040EM") -> Concept:
    da = session.scalars(select(DisciplineArea).where(DisciplineArea.code == da_code)).first()
    if da is None:
        da = _seed_em_area(session, da_code)
    mt = MainTopic(code=da_code, name="Main Topic", discipline_area_id=da.id)
    session.add(mt)
    session.flush()
    tp = Topic(discipline_area_id=da.id, name="Topic", serial_number=1)
    session.add(tp)
    session.flush()
    ct = Content(topic_id=tp.id, name="Content")
    session.add(ct)
    session.flush()
    c = add_concept(session, code=code, label="Bar", content_id=ct.id, domain="Información")
    session.commit()
    return c


# ---------------------------------------------------------------------------
# scan_notes
# ---------------------------------------------------------------------------


def test_scan_notes_reads_concepts(tmp_path):
    _write_note(tmp_path, "note-a", ["em-foo"])
    _write_note(tmp_path, "note-b", ["mc-bar", "em-foo"])

    scanned = scan_notes([tmp_path])

    assert len(scanned) == 2
    ids = {n.note_id: set(n.concepts) for n in scanned}
    assert ids["note-a"] == {"em-foo"}
    assert ids["note-b"] == {"mc-bar", "em-foo"}


def test_scan_notes_skips_malformed_frontmatter(tmp_path, capsys):
    good = tmp_path / "good.md"
    good.write_text(
        "---\nid: good\nconcepts: [em-foo]\n---\n\nBody.\n", encoding="utf-8",
    )
    bad = tmp_path / "bad.md"
    bad.write_text("no frontmatter here at all\n", encoding="utf-8")

    scanned = scan_notes([tmp_path])

    assert len(scanned) == 1
    assert scanned[0].note_id == "good"
    captured = capsys.readouterr()
    assert "bad.md" in captured.err


def test_scan_notes_skips_missing_id(tmp_path, capsys):
    (tmp_path / "no-id.md").write_text(
        "---\nconcepts: [em-foo]\n---\n\nBody.\n", encoding="utf-8",
    )

    scanned = scan_notes([tmp_path])

    assert scanned == []
    assert "no-id.md" in capsys.readouterr().err


def test_scan_notes_skips_non_list_concepts(tmp_path, capsys):
    (tmp_path / "bad-shape.md").write_text(
        "---\nid: bad-shape\nconcepts: \"em-foo\"\n---\n\nBody.\n", encoding="utf-8",
    )

    scanned = scan_notes([tmp_path])

    assert scanned == []
    assert "bad-shape.md" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# partition_concepts
# ---------------------------------------------------------------------------


def test_partition_concepts_known_vs_unknown(session):
    _seed_known_concept(session, "mc-bar")

    known, unknown = partition_concepts(["mc-bar", "em-foo"], session)

    assert known == {"mc-bar"}
    assert unknown == {"em-foo"}


def test_partition_concepts_empty_input(session):
    known, unknown = partition_concepts([], session)
    assert known == set()
    assert unknown == set()


# ---------------------------------------------------------------------------
# match_discipline_area
# ---------------------------------------------------------------------------


def test_match_discipline_area_matches_trailing_pair(session):
    _seed_em_area(session, "0040EM")

    assert match_discipline_area("em", session) == "0040EM"
    assert match_discipline_area("EM", session) == "0040EM"


def test_match_discipline_area_unrecognized(session):
    _seed_em_area(session, "0040EM")

    assert match_discipline_area("zz", session) == UNRECOGNIZED_BUCKET


# ---------------------------------------------------------------------------
# build_delta_yaml
# ---------------------------------------------------------------------------


def test_build_delta_yaml_shape_and_provenance():
    text = build_delta_yaml(
        {"em-foo"},
        provenance={"em-foo": ["note-a", "note-b"]},
        buckets={"em-foo": "0040EM"},
    )

    assert "discipline_area_code: 0040EM" in text
    assert "code: em-foo" in text
    assert "domain: TODO-REVIEW" in text
    assert "# cited by: note-a, note-b" in text
    assert "Em foo" in text  # naive de-slugify placeholder label


def test_build_delta_yaml_empty_returns_empty_string():
    assert build_delta_yaml(set(), {}, {}) == ""


# ---------------------------------------------------------------------------
# harvest (end-to-end, function level)
# ---------------------------------------------------------------------------


def test_harvest_only_unknown_concepts_appear(tmp_path, session):
    _seed_known_concept(session, "mc-bar")
    _write_note(tmp_path, "note-a", ["em-foo"])
    _write_note(tmp_path, "note-b", ["mc-bar", "em-foo"])

    result = harvest(notes=[tmp_path], out=tmp_path / "out.yaml", session=session)

    assert result.unknown_concepts == 1
    assert result.notes_scanned == 2
    assert result.out_path == str(tmp_path / "out.yaml")
    text = (tmp_path / "out.yaml").read_text(encoding="utf-8")
    assert "em-foo" in text
    assert "mc-bar" not in text
    assert "discipline_area_code: 0040EM" in text
    assert "note-a" in text and "note-b" in text


def test_harvest_zero_unknowns_writes_no_file(tmp_path, session):
    _seed_known_concept(session, "mc-bar")
    _write_note(tmp_path, "note-a", ["mc-bar"])

    out_path = tmp_path / "out.yaml"
    result = harvest(notes=[tmp_path], out=out_path, session=session)

    assert result.unknown_concepts == 0
    assert result.out_path is None
    assert result.yaml_text is None
    assert not out_path.exists()


def test_harvest_never_writes_to_db(tmp_path, session):
    _seed_em_area(session, "0040EM")
    _write_note(tmp_path, "note-a", ["em-foo"])

    before = session.scalars(select(Concept)).all()
    harvest(notes=[tmp_path], out=tmp_path / "out.yaml", session=session)
    after = session.scalars(select(Concept)).all()

    assert len(before) == len(after) == 0


def test_harvest_default_notes_uses_vault_root(tmp_path, session, monkeypatch):
    monkeypatch.setenv("WORKFLOW_VAULT_ROOT", str(tmp_path))
    _seed_em_area(session, "0040EM")
    _write_note(tmp_path, "note-a", ["em-foo"])

    result = harvest(notes=None, out=tmp_path / "out.yaml", session=session)

    assert result.notes_scanned == 1
    assert result.unknown_concepts == 1


def test_harvest_unrecognized_prefix_bucket(tmp_path, session):
    _write_note(tmp_path, "note-a", ["zz-weird"])

    harvest(notes=[tmp_path], out=tmp_path / "out.yaml", session=session)

    text = (tmp_path / "out.yaml").read_text(encoding="utf-8")
    assert f"discipline_area_code: {UNRECOGNIZED_BUCKET}" in text
    assert "zz-weird" in text


def test_harvest_round_trip_yaml_valid_but_domain_rejected(tmp_path, session):
    """Delta YAML is valid YAML parseable by the importer's loader, but is
    rejected on domain validation (TODO-REVIEW is not a valid taxonomy
    domain) — the intended forcing function per the design spec.
    """
    da = _seed_em_area(session, "0040EM")
    session.commit()
    _write_note(tmp_path, "note-a", ["em-foo"])

    out_path = tmp_path / "delta.yaml"
    harvest(notes=[tmp_path], out=out_path, session=session)

    # Assertion 1: valid YAML, parseable by the importer's own loader.
    data = load_yaml(out_path)
    assert data["discipline_area_code"] == da.code

    # Assertion 2: rejected on domain validation at import time.
    result = import_hierarchy(session, data)
    assert result.has_errors
    assert any("domain" in err.reason.lower() or "TODO-REVIEW" in err.reason for err in result.errors)

    # No concept was actually created.
    assert session.scalars(select(Concept).where(Concept.code == "em-foo")).first() is None


def test_harvest_round_trip_after_human_fix_slug_resolves(tmp_path, session):
    """harvest -> hand-fix domain/content -> import -> re-harvest: the
    previously-unknown slug no longer appears in the new delta.
    """
    _seed_em_area(session, "0040EM")
    session.commit()
    _write_note(tmp_path, "note-a", ["em-foo"])

    out_path = tmp_path / "delta.yaml"
    harvest(notes=[tmp_path], out=out_path, session=session)

    data = load_yaml(out_path)
    # Human fix: valid domain + real content name (still synthetic here).
    data["topics"][0]["contents"][0]["concepts"][0]["domain"] = "Información"

    result = import_hierarchy(session, data)
    assert not result.has_errors
    assert result.created_concepts == 1

    # Re-run harvest on the same notes: em-foo now resolves, disappears from output.
    out_path_2 = tmp_path / "delta2.yaml"
    result2 = harvest(notes=[tmp_path], out=out_path_2, session=session)

    assert result2.unknown_concepts == 0
    assert not out_path_2.exists()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_harvest_json_shape(tmp_path, runner):
    _write_note(tmp_path, "note-a", ["em-foo"])

    result = runner.invoke(
        concept,
        ["harvest", "--notes", str(tmp_path), "--out", str(tmp_path / "out.yaml"), "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert set(payload.keys()) == {"unknown_concepts", "notes_scanned", "out_path", "files"}
    assert payload["unknown_concepts"] == 1
    assert payload["notes_scanned"] == 1
    assert payload["files"] == [payload["out_path"]]


def test_cli_harvest_zero_unknowns_message(tmp_path, runner):
    _write_note(tmp_path, "note-a", [])

    result = runner.invoke(concept, ["harvest", "--notes", str(tmp_path)])

    assert result.exit_code == 0
    assert "no unknown concepts found" in result.output


def test_cli_harvest_writes_to_explicit_out_path(tmp_path, runner):
    _write_note(tmp_path, "note-a", ["em-foo"])
    out_path = tmp_path / "custom-delta.yaml"

    invocation = runner.invoke(
        concept, ["harvest", "--notes", str(tmp_path), "--out", str(out_path)],
    )

    assert invocation.exit_code == 0, invocation.output
    assert out_path.exists()
    # No default-path fallback file also written.
    assert list(tmp_path.glob("*delta*.yaml")) == [out_path]


# ---------------------------------------------------------------------------
# AA-collision (director-decision MEDIUM #1): >1 area sharing a trailing
# letter-pair must route to an AMBIGUOUS-PREFIX-<aa> bucket, not silently
# pick the first match.
# ---------------------------------------------------------------------------


def test_match_discipline_area_ambiguous_prefix_bucket(session):
    _seed_em_area(session, "10MC")
    _seed_em_area(session, "11MC")

    assert match_discipline_area("mc", session) == f"{AMBIGUOUS_PREFIX_BUCKET}-MC"


def test_match_discipline_area_single_match_unchanged(session):
    _seed_em_area(session, "10MC")

    assert match_discipline_area("mc", session) == "10MC"


def test_match_discipline_areas_bulk_reports_ambiguous_candidates(session):
    _seed_em_area(session, "10MC")
    _seed_em_area(session, "11MC")
    _seed_em_area(session, "0040EM")

    buckets, ambiguous = match_discipline_areas_bulk({"mc", "em", "zz"}, session)

    assert buckets["mc"] == f"{AMBIGUOUS_PREFIX_BUCKET}-MC"
    assert buckets["em"] == "0040EM"
    assert buckets["zz"] == UNRECOGNIZED_BUCKET
    assert ambiguous[f"{AMBIGUOUS_PREFIX_BUCKET}-MC"] == ["10MC", "11MC"]
    assert f"{AMBIGUOUS_PREFIX_BUCKET}-EM" not in ambiguous


def test_match_discipline_areas_bulk_single_query(session, engine):
    _seed_em_area(session, "10MC")
    _seed_em_area(session, "11MC")
    session.commit()

    statements: list[str] = []

    def _counter(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "discipline_area" in statement:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", _counter)
    try:
        match_discipline_areas_bulk({"mc", "zz", "em"}, session)
    finally:
        event.remove(engine, "before_cursor_execute", _counter)

    assert len(statements) == 1


def test_build_delta_yaml_ambiguous_bucket_lists_candidates():
    text = build_delta_yaml(
        {"mc-newton"},
        provenance={"mc-newton": ["note-a"]},
        buckets={"mc-newton": f"{AMBIGUOUS_PREFIX_BUCKET}-MC"},
        ambiguous_candidates={f"{AMBIGUOUS_PREFIX_BUCKET}-MC": ["10MC", "11MC"]},
    )

    assert f"discipline_area_code: {AMBIGUOUS_PREFIX_BUCKET}-MC" in text
    assert "10MC" in text and "11MC" in text


def test_harvest_ambiguous_prefix_bucket_end_to_end(tmp_path, session):
    _seed_em_area(session, "10MC")
    _seed_em_area(session, "11MC")
    _write_note(tmp_path, "note-a", ["mc-newton"])

    result = harvest(notes=[tmp_path], out=tmp_path / "out.yaml", session=session)

    assert result.unknown_concepts == 1
    text = Path(result.files[0]).read_text(encoding="utf-8")
    assert f"discipline_area_code: {AMBIGUOUS_PREFIX_BUCKET}-MC" in text
    assert "10MC" in text and "11MC" in text


# ---------------------------------------------------------------------------
# Multi-bucket file split (director-decision MEDIUM #3): one file per
# bucket, since the importer only reads the first YAML document.
# ---------------------------------------------------------------------------


def test_harvest_multi_bucket_writes_one_file_per_bucket(tmp_path, session):
    _seed_em_area(session, "0040EM")
    _write_note(tmp_path, "note-a", ["em-foo"])
    _write_note(tmp_path, "note-b", ["zz-weird"])

    out_path = tmp_path / "delta.yaml"
    result = harvest(notes=[tmp_path], out=out_path, session=session)

    assert result.unknown_concepts == 2
    assert len(result.files) == 2
    expected_em = str(tmp_path / "delta-0040EM.yaml")
    expected_unrec = str(tmp_path / f"delta-{UNRECOGNIZED_BUCKET}.yaml")
    assert set(result.files) == {expected_em, expected_unrec}
    # The literal --out path itself is not written when buckets split.
    assert not out_path.exists()

    for f in result.files:
        data = load_yaml(Path(f))
        assert "discipline_area_code" in data
        assert data["discipline_area_code"] in {"0040EM", UNRECOGNIZED_BUCKET}


def test_harvest_single_bucket_path_byte_compatible(tmp_path, session):
    """Regression: single-bucket harvest still writes exactly --out PATH.yaml
    with unchanged content shape (no bucket-suffix renaming)."""
    _seed_em_area(session, "0040EM")
    _write_note(tmp_path, "note-a", ["em-foo"])

    out_path = tmp_path / "delta.yaml"
    result = harvest(notes=[tmp_path], out=out_path, session=session)

    assert result.out_path == str(out_path)
    assert result.files == (str(out_path),)
    assert out_path.exists()
    assert not (tmp_path / "delta-0040EM.yaml").exists()


def test_cli_harvest_multi_bucket_json_files_array(tmp_path, runner):
    from workflow.db.engine import init_global_db  # noqa: PLC0415

    engine = init_global_db()
    with Session(engine) as seed_session:
        _seed_em_area(seed_session, "0040EM")
        seed_session.commit()

    _write_note(tmp_path, "note-a", ["em-foo"])
    _write_note(tmp_path, "note-b", ["zz-weird"])
    out_path = tmp_path / "delta.yaml"

    result = runner.invoke(
        concept,
        ["harvest", "--notes", str(tmp_path), "--out", str(out_path), "--json"],
    )

    assert result.exit_code == 0, result.output
    # harvest() also announces each file written on stderr (mixed into
    # result.output by CliRunner); the JSON payload is the line starting `{`.
    json_line = next(line for line in result.output.splitlines() if line.startswith("{"))
    payload = json.loads(json_line)
    assert payload["unknown_concepts"] == 2
    assert len(payload["files"]) == 2
    assert payload["out_path"] is None
