"""workflow import — bulk DisciplineArea→Topic→Content→Concept hierarchy importer."""
from __future__ import annotations

import click
from sqlalchemy.orm import Session

from workflow.db.engine import get_engine_from_ctx
from workflow.db.errors import with_schema_guard
from workflow.importer.engine import ImportSchemaError, import_hierarchy, load_yaml
from workflow.importer.formatters import format_import_json, format_import_table
from workflow.topic.service import DisciplineAreaNotFound

__all__ = ["import_cmd", "run_import"]

_get_engine = get_engine_from_ctx


def run_import(
    ctx: click.Context,
    file: str,
    discipline_area_code: str | None,
    dry_run: bool,
    as_json: bool,
) -> None:
    """Shared body for `workflow import` and the deprecated `topic import` alias."""
    try:
        data = load_yaml(file)
    except ImportSchemaError as exc:
        click.echo(str(exc), err=True)
        ctx.exit(1)
        return

    engine = _get_engine(ctx)
    with Session(engine) as session:
        try:
            result = import_hierarchy(
                session,
                data,
                discipline_area_override=discipline_area_code,
                dry_run=dry_run,
            )
        except ImportSchemaError as exc:
            click.echo(str(exc), err=True)
            ctx.exit(1)
            return
        except DisciplineAreaNotFound as exc:
            click.echo(str(exc), err=True)
            ctx.exit(2)
            return

    click.echo(format_import_json(result) if as_json else format_import_table(result))
    ctx.exit(3 if result.has_errors else 0)


@click.command(name="import")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--discipline-area", "discipline_area_code", default=None,
              help="Override discipline_area_code in the file.")
@click.option("--dry-run", "dry_run", is_flag=True,
              help="Validate + report without writing.")
@click.option("--json", "as_json", is_flag=True, help="JSON summary output.")
@click.pass_context
@with_schema_guard
def import_cmd(
    ctx: click.Context,
    file: str,
    discipline_area_code: str | None,
    dry_run: bool,
    as_json: bool,
) -> None:
    """Bulk-import a DisciplineArea → Topic → Content → Concept hierarchy from YAML.

    Idempotent: existing Topics (by serial) and Contents (by name within a topic)
    are reused, not duplicated.

    CONCEPT GLOBAL-SKIP: a concept `code` is globally unique. A `code` that already
    exists is silently skipped (counted under "skipped"), even when the YAML places
    it under a DIFFERENT content — it is NOT re-linked to the new content. To move a
    concept, edit it explicitly with `workflow concept` rather than re-importing.

    Exit codes: 0 success / clean --dry-run · 1 schema or YAML error (no writes) ·
    2 unknown discipline_area_code (no writes) · 3 partial failure (some rows
    created, row-level errors collected)."""
    run_import(ctx, file, discipline_area_code, dry_run, as_json)
