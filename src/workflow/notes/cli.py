"""Notes CLI — Zettelkasten note management commands."""

from __future__ import annotations

import json
from pathlib import Path

import click

from workflow.db.errors import with_schema_guard
from workflow.notes.formatters import (
    format_note_json,
    format_note_table,
    format_notes_list_json,
    format_notes_list_table,
)
from workflow.notes.init import init_workspace
from workflow.notes.service import (
    AmbiguousNoteId,
    NoteNotFound,
    NoteValidationError,
    _SAFE_ID_RE,
    add_link,
    create_note,
    list_notes,
    read_note,
    update_tags,
    walk_connections,
)
from workflow.validation.schemas import validate_note_frontmatter

__all__ = ["notes"]


def _validate_cli_id(note_id: str) -> None:
    """Reject ids with path traversal or invalid characters (lessons.md rows 14, 18)."""
    if not _SAFE_ID_RE.match(note_id):
        raise click.UsageError(
            f"note_id {note_id!r} contains invalid characters. "
            "Use only letters, digits, dots, underscores, hyphens."
        )


@click.group()
def notes() -> None:
    """Zettelkasten note management."""


@notes.command(name="init")
@click.argument("workspace", type=click.Path(), default=".")
@with_schema_guard
def init_cmd(workspace: str) -> None:
    """Initialize a WorkFlow workspace with note directories."""
    workspace_path = Path(workspace).resolve()

    if not workspace_path.exists():
        raise click.ClickException(f"Directory does not exist: {workspace_path}")

    result = init_workspace(workspace_path)

    # Also create type subdirectories at the workspace root for direct note storage
    type_subdirs = ("permanent", "literature", "fleeting")
    for subdir_name in type_subdirs:
        subdir = workspace_path / subdir_name
        if not subdir.exists():
            subdir.mkdir(parents=True, exist_ok=True)
            click.echo(f"  + {subdir_name}/")

    if result.directories_created:
        click.echo("Created:")
        for d in result.directories_created:
            click.echo(f"  + {d}")

    if result.already_existed and not result.directories_created:
        click.echo("Workspace already initialized — nothing to do.")

    for w in result.warnings:
        click.echo(f"  [WARN] {w}")


@notes.command(name="new")
@click.option("--id", "note_id", required=True, help="Slug/ID for the note.")
@click.option("--title", required=True)
@click.option(
    "--type",
    "note_type",
    type=click.Choice(["permanent", "literature", "fleeting"]),
    default="permanent",
)
@click.option("--tags", default="", help="Comma-separated tags.")
@click.option("--concepts", default="", help="Comma-separated concepts.")
@click.option(
    "--candidate-project",
    "candidate_project",
    default=None,
    help="Forward reference DDTTAA-YYPP.",
)
@click.option("--dir", "target_dir", type=click.Path(file_okay=False), default=".")
@click.option("--force", is_flag=True, help="Overwrite if exists.")
@click.option("--json", "as_json", is_flag=True)
@with_schema_guard
def new_cmd(
    note_id: str,
    title: str,
    note_type: str,
    tags: str,
    concepts: str,
    candidate_project: str | None,
    target_dir: str,
    force: bool,
    as_json: bool,
) -> None:
    """Create a new Markdown note file."""
    _validate_cli_id(note_id)

    tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    concepts_list = (
        [c.strip() for c in concepts.split(",") if c.strip()] if concepts else []
    )

    fm_dict: dict = {
        "id": note_id,
        "title": title,
        "type": note_type,
        "tags": tags_list,
        "concepts": concepts_list,
        "references": [],
        "exercises": [],
        "images": [],
        "candidate_project": candidate_project,
    }
    fm_obj, errors = validate_note_frontmatter(fm_dict)
    if errors or fm_obj is None:
        raise click.ClickException(
            "Frontmatter validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    target = Path(target_dir).resolve()
    try:
        path = create_note(target, fm_obj, force=force)
    except FileExistsError as exc:
        raise click.ClickException(str(exc))
    except NoteValidationError as exc:
        raise click.ClickException(str(exc))

    if as_json:
        click.echo(json.dumps({"id": note_id, "path": str(path)}, ensure_ascii=False))
    else:
        click.echo(str(path))


@notes.command(name="list")
@click.argument("note_id", required=False, default=None)
@click.option("--tag", default=None)
@click.option("--concept", default=None)
@click.option("--candidate-project", "candidate_project", default=None)
@click.option(
    "--type",
    "note_type",
    type=click.Choice(["permanent", "literature", "fleeting"]),
    default=None,
)
@click.option(
    "--depth",
    type=int,
    default=None,
    help="Max traversal depth (only with <note_id>). Default: unlimited.",
)
@click.option(
    "--edge-types",
    "edge_types",
    default="wikilinks",
    help="Comma-separated edge types to follow when <note_id> given. Default: wikilinks. "
    "Note: concepts/references/exercises are slug keys, not note ids; "
    "their resolver is deferred to Phase B/ITEP-0012.",
)
@click.option(
    "--dir",
    "root_dir",
    type=click.Path(exists=True, file_okay=False),
    default=".",
)
@click.option("--json", "as_json", is_flag=True)
@with_schema_guard
def list_cmd(
    note_id: str | None,
    tag: str | None,
    concept: str | None,
    candidate_project: str | None,
    note_type: str | None,
    depth: int | None,
    edge_types: str,
    root_dir: str,
    as_json: bool,
) -> None:
    """List notes, or walk connections from a given note id."""
    root = Path(root_dir).resolve()
    edge_set = {e.strip() for e in edge_types.split(",") if e.strip()}

    if note_id is not None:
        _validate_cli_id(note_id)
        try:
            items = walk_connections(root, note_id, depth=depth, edge_types=edge_set)
        except NoteNotFound as exc:
            raise click.ClickException(str(exc))
        except AmbiguousNoteId as exc:
            raise click.ClickException(str(exc))
    else:
        items = list_notes(
            root,
            tag=tag,
            concept=concept,
            candidate_project=candidate_project,
            note_type=note_type,
        )

    if as_json:
        click.echo(format_notes_list_json(items))
    else:
        click.echo(format_notes_list_table(items))


@notes.command(name="show")
@click.argument("note_id")
@click.option(
    "--dir",
    "root_dir",
    type=click.Path(exists=True, file_okay=False),
    default=".",
)
@click.option("--json", "as_json", is_flag=True)
@with_schema_guard
def show_cmd(note_id: str, root_dir: str, as_json: bool) -> None:
    """Show details of a single note."""
    _validate_cli_id(note_id)
    root = Path(root_dir).resolve()
    try:
        path, fm, body = read_note(root, note_id)
    except NoteNotFound as exc:
        raise click.ClickException(str(exc))
    except AmbiguousNoteId as exc:
        raise click.ClickException("ambiguous id: " + str(exc))

    if as_json:
        click.echo(format_note_json(path, fm))
    else:
        click.echo(format_note_table(path, fm))


@notes.command(name="tag")
@click.argument("note_id")
@click.option("--add", "add_tags", multiple=True)
@click.option("--remove", "remove_tags", multiple=True)
@click.option(
    "--dir",
    "root_dir",
    type=click.Path(exists=True, file_okay=False),
    default=".",
)
@click.option("--json", "as_json", is_flag=True)
@with_schema_guard
def tag_cmd(
    note_id: str,
    add_tags: tuple[str, ...],
    remove_tags: tuple[str, ...],
    root_dir: str,
    as_json: bool,
) -> None:
    """Add or remove tags on a note."""
    _validate_cli_id(note_id)
    root = Path(root_dir).resolve()
    try:
        path, new_fm = update_tags(root, note_id, add=add_tags, remove=remove_tags)
    except NoteNotFound as exc:
        raise click.ClickException(str(exc))
    except AmbiguousNoteId as exc:
        raise click.ClickException("ambiguous id: " + str(exc))
    except NoteValidationError as exc:
        raise click.ClickException(str(exc))

    if as_json:
        click.echo(format_note_json(path, new_fm))
    else:
        click.echo(format_note_table(path, new_fm))


@notes.command(name="sync")
@click.option("--dry-run", is_flag=True, default=False, help="Report changes without writing.")
@click.option("--project", "project_filter", default=None, help="Restrict to project subtree.")
@click.pass_context
@with_schema_guard
def sync_cmd(ctx: click.Context, dry_run: bool, project_filter: str | None) -> None:
    """Sync notes vault: upsert Note/Label/Link rows from .md files."""
    from sqlalchemy.orm import Session

    from workflow.db.engine import get_engine_from_ctx
    from workflow.notes.sync import sync_vault
    from workflow.vault.paths import resolve_vault_root

    engine = get_engine_from_ctx(ctx)
    vault_root = resolve_vault_root()
    with Session(engine) as session:
        report = sync_vault(vault_root, session, dry_run=dry_run, project_filter=project_filter)
        if not dry_run:
            session.commit()
    suffix = " (dry run)" if dry_run else ""
    click.echo(
        f"Sync complete{suffix}: {report.notes_scanned} notes scanned, "
        f"{report.labels_registered} labels registered, "
        f"{report.links_created} links created, "
        f"{report.orphans_dropped} orphans dropped."
    )


@notes.command(name="link")
@click.argument("note_id")
@click.option("--concept", "concept", default=None)
@click.option("--reference", "reference", default=None)
@click.option("--exercise", "exercise", default=None)
@click.option(
    "--dir",
    "root_dir",
    type=click.Path(exists=True, file_okay=False),
    default=".",
)
@click.option("--json", "as_json", is_flag=True)
@with_schema_guard
def link_cmd(
    note_id: str,
    concept: str | None,
    reference: str | None,
    exercise: str | None,
    root_dir: str,
    as_json: bool,
) -> None:
    """Append a concept, reference, or exercise link to a note."""
    _validate_cli_id(note_id)

    # Mutex: exactly one of --concept/--reference/--exercise required
    targets = [x for x in (concept, reference, exercise) if x is not None]
    if len(targets) != 1:
        raise click.UsageError(
            "Exactly one of --concept, --reference, or --exercise is required."
        )

    root = Path(root_dir).resolve()
    try:
        path, new_fm = add_link(
            root, note_id, concept=concept, reference=reference, exercise=exercise
        )
    except NoteNotFound as exc:
        raise click.ClickException(str(exc))
    except AmbiguousNoteId as exc:
        raise click.ClickException("ambiguous id: " + str(exc))
    except NoteValidationError as exc:
        raise click.ClickException(str(exc))

    if as_json:
        click.echo(format_note_json(path, new_fm))
    else:
        click.echo(format_note_table(path, new_fm))
