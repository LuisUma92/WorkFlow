"""Tests for workflow.db.errors / @with_schema_guard (ITEP-0010)."""

from __future__ import annotations

import click
import pytest
from click.testing import CliRunner
from sqlalchemy.exc import OperationalError

from workflow.db.errors import (
    SchemaOutOfDateError,
    translate_operational_error,
    with_schema_guard,
)


def _op_error(msg: str) -> OperationalError:
    """Build a fake OperationalError mirroring sqlite3 wording."""
    return OperationalError(statement="SELECT", params=None, orig=Exception(msg))


def test_translate_recognises_missing_column():
    exc = _op_error("no such column: evaluation_template.description")
    err = translate_operational_error(exc)

    assert isinstance(err, SchemaOutOfDateError)
    assert err.kind == "column"
    assert err.table == "evaluation_template"
    assert err.name == "description"


def test_translate_recognises_missing_table():
    exc = _op_error("no such table: schema_version")
    err = translate_operational_error(exc)

    assert err.kind == "table"
    assert err.table == "schema_version"
    assert err.name == "schema_version"


def test_translate_returns_none_for_unknown_message():
    exc = _op_error("some other operational issue")
    assert translate_operational_error(exc) is None


def test_schema_out_of_date_message_mentions_runner():
    err = SchemaOutOfDateError(
        kind="column", table="evaluation_template", name="description"
    )
    msg = str(err)
    assert "evaluation_template" in msg
    assert "description" in msg
    assert "workflow db migrate" in msg


def test_with_schema_guard_translates_to_click_exception():
    @click.command()
    @with_schema_guard
    def cmd():
        raise _op_error("no such column: evaluation_template.description")

    runner = CliRunner()
    result = runner.invoke(cmd)

    assert result.exit_code == 1
    assert "workflow db migrate" in result.output
    assert "Traceback" not in result.output
    assert "evaluation_template" in result.output
    assert "description" in result.output


def test_with_schema_guard_passes_through_unrelated_operational_errors():
    """Non-schema operational errors must NOT be swallowed."""
    other = _op_error("database is locked")

    @click.command()
    @with_schema_guard
    def cmd():
        raise other

    runner = CliRunner()
    result = runner.invoke(cmd)

    # Re-raised, not converted to clean ClickException
    assert result.exit_code != 0
    assert result.exception is other


def test_with_schema_guard_passes_through_normal_returns():
    @click.command()
    @with_schema_guard
    def cmd():
        click.echo("ok")

    runner = CliRunner()
    result = runner.invoke(cmd)

    assert result.exit_code == 0
    assert "ok" in result.output


def test_with_schema_guard_preserves_command_metadata():
    @click.command(name="mycmd", help="my help")
    @with_schema_guard
    def cmd():
        pass

    assert cmd.name == "mycmd"
    assert "my help" in (cmd.help or "")


def test_translate_recognises_missing_column_without_table_prefix():
    exc = _op_error("no such column: description")
    err = translate_operational_error(exc)

    assert err is not None
    assert err.kind == "column"
    assert err.name == "description"


@pytest.mark.parametrize(
    "msg",
    [
        "no such column: evaluation_template.description",
        "no such table: schema_version",
    ],
)
def test_translated_error_str_is_actionable(msg):
    exc = _op_error(msg)
    err = translate_operational_error(exc)
    assert err is not None
    assert "Run: workflow db migrate" in str(err)
