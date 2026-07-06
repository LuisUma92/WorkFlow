"""workflow.concept.harvest — read-only concept-slug harvest from notes (D3).

Scans .md notes' ``concepts:`` frontmatter, partitions the slugs into known
(already a ``Concept.code``) vs unknown against the DB (reusing
``resolve_concepts``, never re-implementing the lookup), and emits a
skyfolding-delta YAML for the unknown ones only, grouped by an inferred
``DisciplineArea`` bucket (trailing AA-letter-pair match on the slug prefix).

Harvest NEVER writes to the DB — no ``session.add``/``session.commit`` here.
``workflow import`` (``workflow.importer.engine.import_hierarchy``) remains the
sole concept-creation path (ADR-0018). See design spec:
docs/superpowers/specs/2026-07-05-fleeting-harvest-design.md (D3).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from workflow.concept.service import resolve_concepts
from workflow.db.models.knowledge import DisciplineArea
from workflow.notes.sync import _parse_md

__all__ = [
    "UNRECOGNIZED_BUCKET",
    "AMBIGUOUS_PREFIX_BUCKET",
    "ScannedNote",
    "HarvestResult",
    "scan_notes",
    "partition_concepts",
    "match_discipline_area",
    "match_discipline_areas_bulk",
    "build_delta_yaml",
    "harvest",
]

UNRECOGNIZED_BUCKET = "UNRECOGNIZED-PREFIX"
AMBIGUOUS_PREFIX_BUCKET = "AMBIGUOUS-PREFIX"
_DEFAULT_OUT_DIR = Path("tasks") / "harvest"


@dataclass(frozen=True)
class ScannedNote:
    """One well-formed .md note as scanned by `scan_notes`."""

    path: Path
    note_id: str
    concepts: tuple[str, ...]


@dataclass(frozen=True)
class HarvestResult:
    """Outcome of a `harvest` run.

    `yaml_text`/`out_path` are both None when there are zero unknown concepts
    (nothing is written to disk in that case, per the design's error table).
    They are also both None when the unknown concepts split across more than
    one `DisciplineArea` bucket — in that case each bucket is written to its
    own file (importer's `load_yaml`/`yaml.safe_load` only reads the first
    document, so a single multi-doc file would silently lose buckets 2+) and
    `files` carries every path written, in bucket-sorted order. For the
    single-bucket case `out_path`/`yaml_text` describe that one file and
    `files` is a 1-tuple of the same path (byte-compatible with the
    pre-multi-file behavior).
    """

    unknown_concepts: int
    notes_scanned: int
    out_path: str | None
    yaml_text: str | None
    files: tuple[str, ...] = ()


def _iter_md_files(paths: list[Path]) -> list[Path]:
    """Expand a list of dirs/files into a sorted flat list of .md files."""
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files.extend(sorted(p.rglob("*.md")))
        elif p.is_file():
            files.append(p)
    return files


def scan_notes(paths: list[Path]) -> list[ScannedNote]:
    """Parse frontmatter of every .md file under `paths`; skip malformed ones.

    Reuses `workflow.notes.sync._parse_md` (do not fork the YAML-boundary
    logic). A file is skipped — with a stderr warning naming the path,
    scanning continues — when: frontmatter is missing/unparseable, `id:` is
    missing/non-string, or `concepts:` is present but not a list of strings.
    A well-formed note with no `concepts:` key still yields a ScannedNote
    with an empty `concepts` tuple.
    """
    notes: list[ScannedNote] = []
    for path in _iter_md_files(paths):
        parsed = _parse_md(path)
        if parsed is None:
            print(f"warning: skipping {path} — malformed or missing frontmatter", file=sys.stderr)
            continue

        fm, _body = parsed
        note_id = fm.get("id")
        if not isinstance(note_id, str) or not note_id:
            print(f"warning: skipping {path} — missing 'id' in frontmatter", file=sys.stderr)
            continue

        raw_concepts = fm.get("concepts") or []
        if not isinstance(raw_concepts, list) or not all(isinstance(c, str) for c in raw_concepts):
            print(
                f"warning: skipping {path} — 'concepts:' is not a list of strings",
                file=sys.stderr,
            )
            continue

        notes.append(ScannedNote(path=path, note_id=note_id, concepts=tuple(raw_concepts)))

    return notes


def partition_concepts(slugs: list[str], session: Session) -> tuple[set[str], set[str]]:
    """Partition `slugs` into (known, unknown) via `resolve_concepts` (read-only)."""
    if not slugs:
        return set(), set()

    unique = sorted(set(slugs))
    found, _issues = resolve_concepts(unique, session, strict=False)
    known = {c.code for c in found}
    unknown = {s for s in unique if s not in known}
    return known, unknown


def _resolve_bucket(prefix: str, area_codes: list[str]) -> tuple[str, list[str]]:
    """Resolve `prefix` against a pre-fetched, already-`order_by`-sorted list
    of `DisciplineArea.code`. Returns `(bucket, ambiguous_candidates)`:

    - exactly one match  -> `(that code, [])`
    - 2+ matches         -> `(f"AMBIGUOUS-PREFIX-{prefix}", sorted candidates)`
      — the human must pick one; nothing is silently guessed (AA-collision,
      e.g. 7 live codes end in `MC`: 10MC..16MC).
    - 0 matches          -> `(UNRECOGNIZED_BUCKET, [])`
    """
    prefix_upper = prefix.upper()
    matches = sorted(code for code in area_codes if code[-2:].upper() == prefix_upper)
    if len(matches) == 1:
        return matches[0], []
    if len(matches) > 1:
        return f"{AMBIGUOUS_PREFIX_BUCKET}-{prefix_upper}", matches
    return UNRECOGNIZED_BUCKET, []


def match_discipline_area(prefix: str, session: Session) -> str:
    """Match `prefix` against the trailing AA letter-pair of `DisciplineArea.code`.

    Case-insensitive. Returns:
    - the matching `DisciplineArea.code` when exactly one area matches;
    - `AMBIGUOUS-PREFIX-<aa>` when 2+ areas share the trailing pair (human
      must disambiguate — see `build_delta_yaml`'s header comment);
    - the literal `UNRECOGNIZED-PREFIX` bucket when no area matches.

    Nothing is silently dropped or arbitrarily picked. Ordered by
    `DisciplineArea.code` for deterministic candidate listing.
    """
    areas = session.scalars(select(DisciplineArea).order_by(DisciplineArea.code)).all()
    bucket, _candidates = _resolve_bucket(prefix, [area.code for area in areas])
    return bucket


def match_discipline_areas_bulk(
    prefixes: set[str], session: Session,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Bulk variant of `match_discipline_area` — loads `DisciplineArea` ONCE
    (single query, `order_by(DisciplineArea.code)` for determinism) instead
    of once per unknown slug (was an N+1 in `harvest`).

    Returns `(buckets, ambiguous_candidates)`:
    - `buckets`: every `prefix` -> its resolved bucket (single code,
      `AMBIGUOUS-PREFIX-<aa>`, or `UNRECOGNIZED-PREFIX`).
    - `ambiguous_candidates`: only the ambiguous bucket names -> their sorted
      candidate `DisciplineArea.code` list (consumed by `build_delta_yaml`'s
      header comment).
    """
    areas = session.scalars(select(DisciplineArea).order_by(DisciplineArea.code)).all()
    area_codes = [area.code for area in areas]

    buckets: dict[str, str] = {}
    ambiguous_candidates: dict[str, list[str]] = {}
    for prefix in prefixes:
        bucket, candidates = _resolve_bucket(prefix, area_codes)
        buckets[prefix] = bucket
        if candidates:
            ambiguous_candidates[bucket] = candidates
    return buckets, ambiguous_candidates


def _deslugify_label(slug: str) -> str:
    """Naive hyphen->space + capitalize placeholder label (no accent restoration)."""
    return slug.replace("-", " ").capitalize()


def build_delta_yaml(
    unknown_slugs: set[str],
    provenance: dict[str, list[str]],
    buckets: dict[str, str],
    ambiguous_candidates: dict[str, list[str]] | None = None,
) -> str:
    """Emit skyfolding-delta YAML text for `unknown_slugs`.

    `provenance` maps slug -> list of citing note ids. `buckets` maps slug ->
    discipline_area_code (or `UNRECOGNIZED-PREFIX` / `AMBIGUOUS-PREFIX-<aa>`).
    `ambiguous_candidates` maps an `AMBIGUOUS-PREFIX-<aa>` bucket name -> its
    sorted list of candidate `DisciplineArea.code`s, surfaced in that bucket's
    header comment so the human can pick one (AA-collision, e.g. 10MC..16MC
    all end in `MC`). Shape matches
    `data/templates/concept-skyfolding-template.yml` (valid `workflow import`
    input), except `domain: TODO-REVIEW` is deliberately invalid — import's
    `add_concept`/`_validate_domain` rejects it until a human fixes it (the
    intended forcing function). One skyfolding document per bucket. `harvest`
    now writes ONE FILE PER BUCKET (never joins them in a single file) since
    the importer's `load_yaml`/`yaml.safe_load` only reads the first `---`
    document — a joined multi-doc file would silently lose buckets 2+. This
    function still supports being called directly with multiple buckets
    (joined with `---`) for callers other than `harvest` itself.
    """
    if not unknown_slugs:
        return ""

    by_bucket: dict[str, list[str]] = {}
    for slug in sorted(unknown_slugs):
        by_bucket.setdefault(buckets[slug], []).append(slug)

    bucket_keys = sorted(by_bucket)
    multi = len(bucket_keys) > 1
    docs: list[str] = []

    for bucket in bucket_keys:
        lines: list[str] = [
            f"# Skyfolding delta — harvested by `workflow concept harvest` (bucket: {bucket})",
            "# Human review required: fix label/domain/content before `workflow import`.",
        ]
        if bucket.startswith(f"{AMBIGUOUS_PREFIX_BUCKET}-"):
            candidates = sorted((ambiguous_candidates or {}).get(bucket, []))
            lines.append(
                f"# AMBIGUOUS: {len(candidates)} DisciplineArea codes share this prefix: "
                f"{', '.join(candidates)} — pick the correct one and fix "
                "discipline_area_code below before import."
            )
        if multi:
            lines.append(
                "# NOTE: multiple discipline-area buckets were present in this batch — "
                "`workflow concept harvest` writes each to its own file (each is "
                "importable alone); this combined view is only produced when "
                "build_delta_yaml is called directly with several buckets."
            )
        lines.extend([
            f"discipline_area_code: {bucket}",
            f'discipline_area_name: "<TODO: assign real DisciplineArea name for {bucket}>"',
            'dewey: "<TODO-REVIEW>"',
            "topics:",
            '  - name: "<TODO: assign real Topic>"',
            "    serial: 1",
            "    contents:",
            '      - name: "<TODO: assign real Content>"',
            "        concepts:",
        ])
        for slug in by_bucket[bucket]:
            citing = ", ".join(sorted(provenance.get(slug, [])))
            lines.append(f"          # cited by: {citing}")
            lines.append(f"          - code: {slug}")
            lines.append(f'            label: "{_deslugify_label(slug)}"  # REVIEW')
            lines.append("            domain: TODO-REVIEW")
        docs.append("\n".join(lines))

    return "\n---\n".join(docs) + "\n"


def _default_out_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return _DEFAULT_OUT_DIR / f"{timestamp}-delta.yaml"


def _bucket_out_path(base: Path, bucket: str) -> Path:
    """`PATH.yaml` -> `PATH-<bucket>.yaml` (used only when >1 bucket)."""
    return base.with_name(f"{base.stem}-{bucket}{base.suffix}")


def harvest(
    notes: list[Path] | None,
    out: Path | None,
    session: Session,
) -> HarvestResult:
    """Scan -> partition -> emit delta YAML. Never writes to the DB.

    `notes=None` resolves the note set via `resolve_vault_root()`. `out=None`
    defaults to `tasks/harvest/<timestamp>-delta.yaml`. When there are zero
    unknown concepts, no file is written and the result carries
    `out_path=None`/`yaml_text=None`/`files=()`.

    When the unknown slugs span exactly one `DisciplineArea` bucket, `out` is
    written byte-for-byte as before (`out_path`/`yaml_text` describe it,
    `files` is a 1-tuple). When they span 2+ buckets, ONE FILE PER BUCKET is
    written instead — `out`'s stem gains a `-<bucket>` suffix per file (e.g.
    `PATH-0040EM.yaml`, `PATH-AMBIGUOUS-PREFIX-mc.yaml`,
    `PATH-UNRECOGNIZED-PREFIX.yaml`) — because the importer's `load_yaml`
    (`yaml.safe_load`) only reads the first `---` document, so a single
    joined multi-bucket file would silently lose buckets 2+. The literal
    `out` path itself is NOT written in that case; `out_path`/`yaml_text` are
    None and `files` carries every path written (bucket-sorted). Every file
    written is also announced on stderr.
    """
    if notes is None:
        from workflow.vault.paths import resolve_vault_root  # noqa: PLC0415

        notes = [resolve_vault_root()]

    scanned = scan_notes(notes)

    provenance: dict[str, list[str]] = {}
    all_slugs: list[str] = []
    for note in scanned:
        for slug in note.concepts:
            all_slugs.append(slug)
            provenance.setdefault(slug, []).append(note.note_id)

    _known, unknown = partition_concepts(all_slugs, session)

    if not unknown:
        return HarvestResult(
            unknown_concepts=0,
            notes_scanned=len(scanned),
            out_path=None,
            yaml_text=None,
            files=(),
        )

    prefixes = {slug.split("-", 1)[0] for slug in unknown}
    prefix_buckets, ambiguous_candidates = match_discipline_areas_bulk(prefixes, session)
    slug_buckets = {slug: prefix_buckets[slug.split("-", 1)[0]] for slug in unknown}

    by_bucket: dict[str, set[str]] = {}
    for slug in unknown:
        by_bucket.setdefault(slug_buckets[slug], set()).add(slug)

    base_out = out if out is not None else _default_out_path()
    bucket_keys = sorted(by_bucket)
    single_bucket = len(bucket_keys) == 1

    files: list[str] = []
    texts: list[str] = []
    for bucket in bucket_keys:
        text = build_delta_yaml(
            by_bucket[bucket], provenance, slug_buckets,
            ambiguous_candidates=ambiguous_candidates,
        )
        path = base_out if single_bucket else _bucket_out_path(base_out, bucket)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        files.append(str(path))
        texts.append(text)
        if not single_bucket:
            print(f"wrote {path}", file=sys.stderr)

    return HarvestResult(
        unknown_concepts=len(unknown),
        notes_scanned=len(scanned),
        out_path=files[0] if single_bucket else None,
        yaml_text=texts[0] if single_bucket else None,
        files=tuple(files),
    )
