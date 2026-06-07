"""Notes CLI — Zettelkasten note management commands."""

from __future__ import annotations

import json
from pathlib import Path

import click

from workflow.db.errors import with_schema_guard
from workflow.notes.formatters import (
    format_edge_json,
    format_edge_table,
    format_edges_list_json,
    format_edges_list_table,
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


@notes.command(name="create")
@click.option(
    "--type",
    "note_type",
    type=click.Choice(["literature"]),
    default="literature",
    show_default=True,
    help="Note type to create (only 'literature' is supported via bibkey).",
)
@click.option("--bibkey", required=True, help="Bibliography key for the literature note.")
@click.option("--bib-entry-id", "bib_entry_id", type=int, default=None,
              help="Disambiguate when bibkey matches multiple entries.")
@click.option("--origin", default="manual", show_default=True,
              help="Origin label written verbatim to frontmatter origin: field.")
@click.option("--vault-root", "vault_root", type=click.Path(file_okay=False), default=None,
              help="Override vault root directory.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Compute note content without writing any file.")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
@with_schema_guard
def create_cmd(
    ctx: click.Context,
    note_type: str,
    bibkey: str,
    bib_entry_id: int | None,
    origin: str,
    vault_root: str | None,
    dry_run: bool,
    as_json: bool,
) -> None:
    """Create a literature note from a bibliography key (no PRISMA context required)."""
    from pathlib import Path as _Path

    from sqlalchemy.orm import Session

    from workflow.bibliography.service import BibKeyAmbiguous
    from workflow.db.engine import get_engine_from_ctx
    from workflow.prisma.accept_to_note import accept_to_note, accept_to_note_json

    vault_path = _Path(vault_root).resolve() if vault_root else None
    engine = get_engine_from_ctx(ctx)
    try:
        with Session(engine) as session:
            result = accept_to_note(
                session,
                bibkey=bibkey,
                bib_entry_id=bib_entry_id,
                origin=origin,
                vault_root=vault_path,
                dry_run=dry_run,
            )
    except BibKeyAmbiguous:
        raise click.ClickException(
            f"bibkey {bibkey!r} matches multiple entries. "
            "Use --bib-entry-id to select the correct one."
        )
    except ValueError as exc:
        raise click.ClickException(str(exc))

    if as_json:
        click.echo(accept_to_note_json(result))
    elif result.created:
        click.echo(str(result.note_path))
    else:
        click.echo(f"exists: {result.note_path}")


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
@click.option(
    "--strict-concepts",
    "strict_concepts",
    is_flag=True,
    default=False,
    help="Treat unknown concept codes as errors (abort sync).",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON report.")
@click.pass_context
@with_schema_guard
def sync_cmd(
    ctx: click.Context,
    dry_run: bool,
    project_filter: str | None,
    strict_concepts: bool,
    as_json: bool,
) -> None:
    """Sync notes vault: upsert Note/Label/Link rows from .md files."""
    import json as _json
    import sys

    from sqlalchemy.orm import Session

    from workflow.db.engine import get_engine_from_ctx
    from workflow.notes.sync import sync_vault
    from workflow.vault.paths import resolve_vault_root

    engine = get_engine_from_ctx(ctx)
    vault_root = resolve_vault_root()
    with Session(engine) as session:
        report = sync_vault(
            vault_root,
            session,
            dry_run=dry_run,
            project_filter=project_filter,
            strict_concepts=strict_concepts,
        )
        if not dry_run:
            session.commit()

    # Emit report
    if as_json:
        data = {
            "notes_scanned": report.notes_scanned,
            "labels_registered": report.labels_registered,
            "links_created": report.links_created,
            "citations_registered": report.citations_registered,
            "edges_created": report.edges_created,
            "orphans_dropped": report.orphans_dropped,
            "concept_links_created": report.concept_links_created,
            "concept_issues": report.concept_issues,
            "dry_run": dry_run,
        }
        click.echo(_json.dumps(data, ensure_ascii=False, indent=2))
    else:
        suffix = " (dry run)" if dry_run else ""
        click.echo(
            f"Sync complete{suffix}: {report.notes_scanned} notes scanned, "
            f"{report.labels_registered} labels registered, "
            f"{report.links_created} links created, "
            f"{report.citations_registered} citations registered, "
            f"{report.edges_created} edges registered, "
            f"{report.orphans_dropped} orphans dropped, "
            f"{report.concept_links_created} concept links created."
        )
        if report.concept_issues:
            for issue in report.concept_issues:
                click.echo(f"  [{issue['severity'].upper()}] {issue['message']}", err=True)

    # Non-zero exit when strict concept errors present
    if report.concept_issues and any(i["severity"] == "error" for i in report.concept_issues):
        sys.exit(1)


@notes.group(name="edges")
def edges_group() -> None:
    """Query note relation edges stored in the DB."""


@edges_group.command(name="list")
@click.option("--source", "source_zettel_id", default=None, help="Filter by source note zettel_id.")
@click.option(
    "--edge-class",
    "edge_class",
    type=click.Choice(["structural", "associative"]),
    default=None,
)
@click.option(
    "--relation-type",
    "relation_type",
    type=click.Choice([
        "continuation", "refines", "branches", "synthesis", "rebuttal",
        "supports", "contradicts", "expands", "see_also",
    ]),
    default=None,
)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
@with_schema_guard
def edges_list_cmd(
    ctx: click.Context,
    source_zettel_id: str | None,
    edge_class: str | None,
    relation_type: str | None,
    as_json: bool,
) -> None:
    """List note relation edges, with optional filters."""
    from sqlalchemy.orm import Session

    from workflow.db.engine import get_engine_from_ctx
    from workflow.notes.edges_service import list_edges

    engine = get_engine_from_ctx(ctx)
    with Session(engine) as session:
        edges = list_edges(
            session,
            source_zettel_id=source_zettel_id,
            edge_class=edge_class,
            relation_type=relation_type,
        )

    if as_json:
        click.echo(format_edges_list_json(edges))
    else:
        click.echo(format_edges_list_table(edges))


@edges_group.command(name="show")
@click.argument("edge_id", type=int)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
@with_schema_guard
def edges_show_cmd(ctx: click.Context, edge_id: int, as_json: bool) -> None:
    """Show details of a single edge by ID."""
    from sqlalchemy.orm import Session

    from workflow.db.engine import get_engine_from_ctx
    from workflow.notes.edges_service import get_edge

    engine = get_engine_from_ctx(ctx)
    with Session(engine) as session:
        edge = get_edge(session, edge_id)
        if edge is None:
            raise click.ClickException(f"Edge {edge_id} not found.")
        if as_json:
            output = format_edge_json(edge)
        else:
            output = format_edge_table(edge)
        click.echo(output)


@edges_group.command(name="check")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
@with_schema_guard
def edges_check_cmd(ctx: click.Context, as_json: bool) -> None:
    """Detect cycles in structural edges. Exits 1 if cycles found."""
    from sqlalchemy.orm import Session

    from workflow.db.engine import get_engine_from_ctx
    from workflow.notes.dag import detect_structural_cycles

    engine = get_engine_from_ctx(ctx)
    with Session(engine) as session:
        cycles = detect_structural_cycles(session)

    if as_json:
        click.echo(json.dumps({"cycles": cycles}, ensure_ascii=False))
    else:
        if not cycles:
            click.echo("No cycles found in structural edges.")
        else:
            click.echo(f"Cycles detected in structural edges: {len(cycles)}\n")
            for i, cycle in enumerate(cycles, 1):
                path = " → ".join(str(n) for n in cycle)
                click.echo(f"  Cycle {i}: {path}")

    if cycles:
        raise click.exceptions.Exit(1)


@edges_group.command(name="resolve")
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
@with_schema_guard
def edges_resolve_cmd(ctx: click.Context, dry_run: bool, as_json: bool) -> None:
    """Resolve unresolved edge targets (target_zettel_id → target_id FK)."""
    from sqlalchemy.orm import Session

    from workflow.db.engine import get_engine_from_ctx
    from workflow.notes.resolve import resolve_edge_targets

    engine = get_engine_from_ctx(ctx)
    with Session(engine) as session:
        report = resolve_edge_targets(session, dry_run=dry_run)
        if not dry_run:
            session.commit()

    if as_json:
        click.echo(json.dumps(
            {"resolved": report.resolved, "unresolved": report.unresolved, "dry_run": dry_run},
            ensure_ascii=False,
        ))
    else:
        suffix = " (dry run)" if dry_run else ""
        click.echo(
            f"Resolution complete{suffix}: {report.resolved} resolved, "
            f"{report.unresolved} unresolved."
        )


@notes.command(name="enums")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
@with_schema_guard
def enums_cmd(as_json: bool) -> None:
    """Emit the closed-set vocabulary: note types, edge classes, and relation types."""
    from workflow.db.models.notes import (
        _STRUCTURAL_RELATION_TYPES_ORDERED,
        _ASSOCIATIVE_RELATION_TYPES_ORDERED,
        _EDGE_CLASSES_ORDERED,
    )
    from workflow.validation.schemas import _VALID_NOTE_TYPES

    if as_json:
        data = {
            "edge_class": list(_EDGE_CLASSES_ORDERED),
            "relation_type": {
                "structural": list(_STRUCTURAL_RELATION_TYPES_ORDERED),
                "associative": list(_ASSOCIATIVE_RELATION_TYPES_ORDERED),
            },
            "note_type": sorted(_VALID_NOTE_TYPES),
            "zettel_id_format": {
                "library": "nanoid",
                "alphabet": "A-Za-z0-9_-",
                "default_length": 12,
                "min_length": 8,
                "max_length": 21,
                "validation_regex": "^[A-Za-z0-9_-]{8,21}$",
                "filename_convention": "<zettel_id>-<slug>.md",
                "alias_template": ["<zettel_id>-<slug>", "<slug>", "<zettel_id>"],
            },
        }
        click.echo(json.dumps(data, ensure_ascii=False))
    else:
        click.echo("Edge classes:")
        for ec in _EDGE_CLASSES_ORDERED:
            click.echo(f"  {ec}")
        click.echo("\nRelation types (structural):")
        for rt in _STRUCTURAL_RELATION_TYPES_ORDERED:
            click.echo(f"  {rt}")
        click.echo("\nRelation types (associative):")
        for rt in _ASSOCIATIVE_RELATION_TYPES_ORDERED:
            click.echo(f"  {rt}")
        click.echo("\nNote types:")
        for nt in sorted(_VALID_NOTE_TYPES):
            click.echo(f"  {nt}")
        click.echo("\nZettel ID format:")
        click.echo("  library: nanoid  alphabet: A-Za-z0-9_-  length: 8–21 (default 12)")


@notes.command(name="new-id")
@click.option(
    "--length",
    type=int,
    default=12,
    show_default=True,
    help="ID length (8–21).",
)
@with_schema_guard
def new_id_cmd(length: int) -> None:
    """Emit a fresh zettel_id matching ^[A-Za-z0-9_-]{8,21}$."""
    from workflow.notes.ids import generate_zettel_id

    try:
        zid = generate_zettel_id(length)
    except ValueError as exc:
        raise click.UsageError(str(exc))
    click.echo(zid)


@notes.command(name="link")
@click.argument("note_id")
@click.option("--concept", "concept", default=None)
@click.option("--reference", "reference", default=None)
@click.option("--exercise", "exercise", default=None)
@click.option("--main-topic", "main_topic", default=None,
              help="Rewrite frontmatter main_topic: key and set Note.main_topic_id FK.")
@click.option(
    "--dir",
    "root_dir",
    type=click.Path(exists=True, file_okay=False),
    default=".",
)
@click.option("--json", "as_json", is_flag=True)
@click.option("--remove", "remove", is_flag=True, default=False,
              help="Remove the link instead of adding it.")
@click.option("--strict", "strict", is_flag=True, default=False,
              help="Treat unknown concept/main_topic codes as errors.")
@click.pass_context
@with_schema_guard
def link_cmd(
    ctx: click.Context,
    note_id: str,
    concept: str | None,
    reference: str | None,
    exercise: str | None,
    main_topic: str | None,
    root_dir: str,
    as_json: bool,
    remove: bool,
    strict: bool,
) -> None:
    """Append (or remove) a concept, reference, exercise, or main_topic link to a note."""
    from sqlalchemy.orm import Session

    from workflow.db.engine import get_engine_from_ctx

    _validate_cli_id(note_id)

    # Mutex: exactly one of --concept/--reference/--exercise/--main-topic required
    targets = [x for x in (concept, reference, exercise, main_topic) if x is not None]
    if len(targets) != 1:
        raise click.UsageError(
            "Exactly one of --concept, --reference, --exercise, or --main-topic is required."
        )

    root = Path(root_dir).resolve()
    engine = get_engine_from_ctx(ctx)
    try:
        with Session(engine) as session:
            path, new_fm, issues = add_link(
                root, note_id,
                concept=concept, reference=reference, exercise=exercise,
                main_topic=main_topic,
                session=session, strict=strict, remove=remove,
            )
            session.commit()
    except NoteNotFound as exc:
        raise click.ClickException(str(exc))
    except AmbiguousNoteId as exc:
        raise click.ClickException("ambiguous id: " + str(exc))
    except NoteValidationError as exc:
        raise click.ClickException(str(exc))

    for issue in issues:
        click.echo(f"Warning: {issue['message']}", err=True)

    if as_json:
        click.echo(format_note_json(path, new_fm))
    else:
        click.echo(format_note_table(path, new_fm))
