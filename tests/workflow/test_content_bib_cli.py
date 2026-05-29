"""workflow content bib-link CLI tests — link-bib, bib-links, unlink-bib."""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from sqlalchemy.orm import Session

from workflow.db.engine import init_global_db
from workflow.db.models.knowledge import DisciplineArea, Topic, Content


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_global_db(tmp_path_factory, monkeypatch):
    base = tmp_path_factory.mktemp("xdg_content_bib_cli")
    monkeypatch.setenv("XDG_DATA_HOME", str(base))
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(base / "workflow"))


def _seed_topic(da_code: str = "FI0001", serial: int = 1) -> int:
    engine = init_global_db()
    with Session(engine) as session:
        from sqlalchemy import select
        da = session.scalars(
            select(DisciplineArea).where(DisciplineArea.code == da_code)
        ).first()
        if da is None:
            da = DisciplineArea(
                code=da_code, name=f"Area {da_code}",
                discipline_num=1, topic_num=serial, area_initials=da_code[:2],
            )
            session.add(da)
            session.flush()
        tp = Topic(discipline_area_id=da.id, name=f"Topic {serial}", serial_number=serial)
        session.add(tp)
        session.commit()
        return tp.id


def _seed_content(topic_id: int, name: str = "MRU") -> int:
    engine = init_global_db()
    with Session(engine) as session:
        c = Content(topic_id=topic_id, name=name)
        session.add(c)
        session.commit()
        return c.id


def _seed_bib(bibkey: str = "test2024", title: str | None = None, year: int = 2024) -> int:
    engine = init_global_db()
    with Session(engine) as session:
        from workflow.db.models.bibliography import BibEntry
        be = BibEntry(bibkey=bibkey, title=title or f"Title {bibkey}", year=year)
        session.add(be)
        session.commit()
        return be.id


# ── link-bib ──────────────────────────────────────────────────────────────


def test_link_bib_success_text(runner):
    """link-bib creates a BibContent row and exits 0 (text output)."""
    tid = _seed_topic()
    cid = _seed_content(tid)
    _seed_bib("smith2024")

    from workflow.content.cli import content

    result = runner.invoke(content, [
        "link-bib",
        "--content-id", str(cid),
        "--bibkey", "smith2024",
        "--chapter", "1",
        "--section", "2",
        "--first-page", "10",
        "--last-page", "20",
    ])
    assert result.exit_code == 0, result.output
    assert "smith2024" in result.output


def test_link_bib_success_json(runner):
    """link-bib --json emits bib_entry_bibkey in output."""
    tid = _seed_topic()
    cid = _seed_content(tid)
    _seed_bib("jones2024")

    from workflow.content.cli import content

    result = runner.invoke(content, [
        "link-bib",
        "--content-id", str(cid),
        "--bibkey", "jones2024",
        "--chapter", "3",
        "--section", "1",
        "--first-page", "30",
        "--last-page", "45",
        "--json",
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["bib_entry_bibkey"] == "jones2024"
    assert data["content_id"] == cid
    assert data["chapter_number"] == 3
    assert data["section_number"] == 1
    assert data["first_page"] == 30
    assert data["last_page"] == 45


def test_link_bib_unknown_bibkey_exits_1(runner):
    """link-bib with unknown bibkey exits 1."""
    tid = _seed_topic()
    cid = _seed_content(tid)

    from workflow.content.cli import content

    result = runner.invoke(content, [
        "link-bib",
        "--content-id", str(cid),
        "--bibkey", "noexist9999",
        "--chapter", "1",
        "--section", "1",
        "--first-page", "1",
        "--last-page", "5",
    ])
    assert result.exit_code == 1


def test_link_bib_unknown_content_exits_1(runner):
    """link-bib with unknown content_id exits 1."""
    _seed_bib("ok2024")

    from workflow.content.cli import content

    result = runner.invoke(content, [
        "link-bib",
        "--content-id", "99999",
        "--bibkey", "ok2024",
        "--chapter", "1",
        "--section", "1",
        "--first-page", "1",
        "--last-page", "5",
    ])
    assert result.exit_code == 1


def test_link_bib_ambiguous_bibkey_exits_1(runner):
    """link-bib with ambiguous bibkey (multiple BibEntry rows) exits 1."""
    tid = _seed_topic()
    cid = _seed_content(tid)
    # Same bibkey, different titles to avoid unique constraint on (title, year, volume)
    _seed_bib("dup2024", title="Title A", year=2024)
    _seed_bib("dup2024", title="Title B", year=2024)

    from workflow.content.cli import content

    result = runner.invoke(content, [
        "link-bib",
        "--content-id", str(cid),
        "--bibkey", "dup2024",
        "--chapter", "1",
        "--section", "1",
        "--first-page", "1",
        "--last-page", "5",
    ])
    assert result.exit_code == 1


# ── bib-links ─────────────────────────────────────────────────────────────


def test_bib_links_json_shape(runner):
    """bib-links --json returns array with correct fields."""
    tid = _seed_topic()
    cid = _seed_content(tid)
    _seed_bib("alpha2024")

    from workflow.content.cli import content

    runner.invoke(content, [
        "link-bib",
        "--content-id", str(cid),
        "--bibkey", "alpha2024",
        "--chapter", "2",
        "--section", "3",
        "--first-page", "50",
        "--last-page", "60",
    ])

    result = runner.invoke(content, ["bib-links", "--content-id", str(cid), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["bib_entry_bibkey"] == "alpha2024"
    assert data[0]["content_id"] == cid


def test_bib_links_empty_returns_empty_array(runner):
    """bib-links for content with no links returns empty array."""
    tid = _seed_topic()
    cid = _seed_content(tid)

    from workflow.content.cli import content

    result = runner.invoke(content, ["bib-links", "--content-id", str(cid), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data == []


# ── unlink-bib ────────────────────────────────────────────────────────────


def test_unlink_bib_success(runner):
    """unlink-bib removes the BibContent row and exits 0."""
    tid = _seed_topic()
    cid = _seed_content(tid)
    _seed_bib("beta2024")

    from workflow.content.cli import content

    runner.invoke(content, [
        "link-bib",
        "--content-id", str(cid),
        "--bibkey", "beta2024",
        "--chapter", "1",
        "--section", "1",
        "--first-page", "1",
        "--last-page", "10",
    ])

    result = runner.invoke(content, [
        "unlink-bib",
        "--content-id", str(cid),
        "--bibkey", "beta2024",
    ])
    assert result.exit_code == 0, result.output

    # Verify gone
    list_result = runner.invoke(content, ["bib-links", "--content-id", str(cid), "--json"])
    data = json.loads(list_result.output)
    assert data == []


def test_unlink_bib_not_linked_exits_1(runner):
    """unlink-bib when no link exists exits 1."""
    tid = _seed_topic()
    cid = _seed_content(tid)
    _seed_bib("gamma2024")

    from workflow.content.cli import content

    result = runner.invoke(content, [
        "unlink-bib",
        "--content-id", str(cid),
        "--bibkey", "gamma2024",
    ])
    assert result.exit_code == 1


def test_link_bib_duplicate_link_exits_nonzero(runner):
    """Second identical link-bib call exits non-zero (BibLinkAlreadyExists → UsageError)."""
    tid = _seed_topic()
    cid = _seed_content(tid)
    _seed_bib("dup_link2024")

    from workflow.content.cli import content

    args = [
        "link-bib",
        "--content-id", str(cid),
        "--bibkey", "dup_link2024",
        "--chapter", "1",
        "--section", "1",
        "--first-page", "1",
        "--last-page", "10",
    ]
    first = runner.invoke(content, args)
    assert first.exit_code == 0, first.output
    second = runner.invoke(content, args)
    assert second.exit_code != 0


def test_link_bib_with_exercise_range_json(runner):
    """link-bib with --first-exercise/--last-exercise exits 0 and reflects exercise range in JSON."""
    tid = _seed_topic()
    cid = _seed_content(tid)
    _seed_bib("exrange2024")

    from workflow.content.cli import content

    result = runner.invoke(content, [
        "link-bib",
        "--content-id", str(cid),
        "--bibkey", "exrange2024",
        "--chapter", "2",
        "--section", "1",
        "--first-page", "5",
        "--last-page", "15",
        "--first-exercise", "1",
        "--last-exercise", "5",
        "--json",
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["first_exercise"] == 1
    assert data["last_exercise"] == 5
