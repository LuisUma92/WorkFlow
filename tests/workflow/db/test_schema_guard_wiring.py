"""Integration test: every Click subcommand under wired CLIs is guarded.

Verifies ITEP-0010's MUST rule: any Click command that opens a DB
session is wrapped with ``@with_schema_guard``. Done by walking each
group's ``commands`` and asserting the underlying callback chain
mentions ``with_schema_guard`` in its closure.
"""

from __future__ import annotations

import click
import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from workflow.evaluation.cli import course, evaluations, item
from workflow.exercise.cli import exercise
from workflow.graph.cli import graph
from workflow.lecture.cli import lectures
from workflow.notes.cli import notes
from workflow.prisma.cli import prisma
from workflow.project.cli import project


def _all_commands(group: click.Group) -> list[click.Command]:
    out: list[click.Command] = []
    for c in group.commands.values():
        if isinstance(c, click.Group):
            out.extend(_all_commands(c))
        else:
            out.append(c)
    return out


def _is_guarded(cmd: click.Command) -> bool:
    """Walk the callback's __wrapped__ chain looking for the guard marker."""
    cb = cmd.callback
    seen: set = set()
    while cb is not None and id(cb) not in seen:
        seen.add(id(cb))
        if getattr(cb, "_schema_guarded", False):
            return True
        cb = getattr(cb, "__wrapped__", None)
    return False


@pytest.mark.parametrize(
    "group",
    [evaluations, item, course, prisma, exercise, project, lectures, graph, notes],
    ids=lambda g: g.name or repr(g),
)
def test_every_subcommand_is_guarded(group):
    cmds = _all_commands(group)
    assert cmds, f"group {group.name} has no commands"
    unguarded = [c.name for c in cmds if not _is_guarded(c)]
    assert not unguarded, f"unguarded commands in {group.name}: {unguarded}"


def test_evaluations_list_emits_friendly_error_on_missing_table(monkeypatch):
    """End-to-end: out-of-date DB → ClickException, not traceback."""
    engine = create_engine("sqlite:///:memory:")
    # No metadata.create_all — every table is "missing".
    monkeypatch.setattr("workflow.evaluation.cli._get_engine", lambda ctx: engine)

    runner = CliRunner()
    result = runner.invoke(evaluations, ["list"])

    assert result.exit_code == 1
    assert "workflow db migrate" in result.output
    assert "Traceback" not in result.output


def test_unrelated_operational_error_is_not_swallowed(monkeypatch):
    """Genuine DB bugs must still surface."""
    from sqlalchemy.exc import OperationalError

    def boom(_ctx):
        raise OperationalError("SELECT", None, Exception("database is locked"))

    monkeypatch.setattr("workflow.evaluation.cli._get_engine", boom)

    runner = CliRunner()
    result = runner.invoke(evaluations, ["list"])

    assert result.exit_code != 0
    # Not translated to the friendly message
    assert "workflow db migrate" not in result.output


# Quiet unused-import warnings in some envs
_ = Session
