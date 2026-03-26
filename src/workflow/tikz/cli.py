"""
TikZ standalone asset pipeline — Click CLI layer.
"""

from __future__ import annotations

from pathlib import Path

import click

from workflow.tikz.builder import build_all, find_tikz_sources, _STATE_FILE, _load_state

__all__ = ["tikz"]


@click.group()
def tikz() -> None:
    """TikZ standalone asset pipeline."""


@tikz.command()
@click.option(
    "--assets-dir",
    type=click.Path(file_okay=False),
    default="assets/tikz",
    show_default=True,
    help="Directory containing TikZ .tex sources.",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False),
    default="assets/figures",
    show_default=True,
    help="Directory for compiled PDF/SVG output.",
)
@click.option("--force", is_flag=True, help="Rebuild all, ignoring cache.")
@click.option("--no-svg", is_flag=True, help="Skip SVG conversion.")
def build(assets_dir: str, output_dir: str, force: bool, no_svg: bool) -> None:
    """Compile TikZ sources to PDF (and optionally SVG)."""
    assets = Path(assets_dir)
    out = Path(output_dir)

    if not assets.exists():
        raise click.ClickException(f"Assets directory not found: {assets}")

    results = build_all(assets, out, force=force, svg=not no_svg)

    if not results:
        click.echo("No TikZ sources found.")
        return

    ok = sum(1 for r in results if r.error is None)
    skipped = sum(1 for r in results if not r.compiled)
    failed = sum(1 for r in results if r.error is not None)

    for r in results:
        status = "SKIP" if not r.compiled else ("OK  " if r.error is None else "FAIL")
        click.echo(f"  [{status}] {r.source.name}")
        if r.error:
            click.echo(f"         {r.error}", err=True)

    click.echo(f"\nDone: {ok} ok, {skipped} skipped, {failed} failed.")
    if failed:
        raise click.ClickException(f"{failed} source(s) failed to compile.")


@tikz.command(name="list")
@click.option(
    "--assets-dir",
    type=click.Path(file_okay=False),
    default="assets/tikz",
    show_default=True,
    help="Directory containing TikZ .tex sources.",
)
def list_sources(assets_dir: str) -> None:
    """List all TikZ source files."""
    assets = Path(assets_dir)
    if not assets.exists():
        raise click.ClickException(f"Assets directory not found: {assets}")

    sources = find_tikz_sources(assets)
    if not sources:
        click.echo("No TikZ sources found.")
        return

    for s in sources:
        click.echo(str(s))


@tikz.command()
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False),
    default="assets/figures",
    show_default=True,
    help="Directory containing compiled artifacts.",
)
def clean(output_dir: str) -> None:
    """Remove compiled artifacts and state file."""
    out = Path(output_dir)
    if not out.exists():
        click.echo("Output directory does not exist — nothing to clean.")
        return

    state_path = out / _STATE_FILE
    if not state_path.exists():
        click.echo("No state file found — nothing to clean.", err=True)
        return

    state = _load_state(out)

    removed = 0
    # Remove only the PDF/SVG files that were produced by the pipeline.
    for source_path_str in state:
        source = Path(source_path_str)
        for suffix in (".pdf", ".svg"):
            artifact = out / source.with_suffix(suffix).name
            if artifact.exists():
                artifact.unlink()
                removed += 1

    # Remove the state file itself.
    state_path.unlink()
    removed += 1

    click.echo(f"Cleaned {removed} file(s) from {out}.")
