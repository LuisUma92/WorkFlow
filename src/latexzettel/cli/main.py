# src/latexzettel/cli/main.py
from __future__ import annotations

import click

from workflow.db.engine import init_global_db, get_global_engine

from latexzettel.config.settings import DEFAULT_SETTINGS

from latexzettel.cli.commands.notes import notes
from latexzettel.cli.commands.render import render
from latexzettel.cli.commands.sync import sync
from latexzettel.cli.commands.export import export
from latexzettel.cli.commands.analysis import analysis
from latexzettel.cli.context import CLIContext


def _init_db() -> None:
    """Inicializa tablas en la GlobalDB."""
    try:
        init_global_db(engine=get_global_engine())
    except Exception as e:
        raise click.ClickException(f"No se pudo inicializar la DB: {e}") from e


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--root",
    type=click.Path(file_okay=False, dir_okay=True, path_type=str),
    default=".",
    show_default=True,
    help="Root del proyecto (donde viven notes/, template/, projects/, etc.).",
)
@click.pass_context
def cli(ctx: click.Context, root: str) -> None:
    """
    CLI para gestionar el Zettelkasten LaTeX.
    """
    _init_db()
    settings = DEFAULT_SETTINGS
    ctx.obj = CLIContext(settings=settings)


cli.add_command(notes)
cli.add_command(render)
cli.add_command(sync)
cli.add_command(export)
cli.add_command(analysis)
# cli.add_command(misc)


def main() -> None:
    """
    Entry point para console_scripts.
    """
    cli()


if __name__ == "__main__":
    main()
