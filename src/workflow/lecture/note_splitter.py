"""Lecture note splitter — Phase 5d.

Clean reimplementation of lectkit.nofi: splits a single .tex file
at ``%>path`` markers into multiple files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SplitFile:
    """A file produced by splitting."""

    output_path: Path
    line_count: int
    created: bool  # False if file already existed and was not overwritten


@dataclass(frozen=True)
class SplitResult:
    """Result of splitting a notes file."""

    source_path: Path
    files: tuple[SplitFile, ...]
    import_lines: tuple[str, ...]  # \\input{} lines for the main file
    warnings: tuple[str, ...]


def split_notes_file(
    source_path: Path,
    output_dir: Path | None = None,
    *,
    flag: str = "%>",
    end_marker: str = "END",
    overwrite: bool = False,
) -> SplitResult:
    """Split a .tex file at %>path markers.

    Each ``%>path/to/file.tex`` line starts a new section.
    Lines between markers are written to that file.
    ``%>END`` stops the current section without starting a new one.

    Parameters
    ----------
    source_path:
        Path to the source .tex file to split.
    output_dir:
        Directory to resolve relative marker paths against.
        Defaults to ``source_path.parent``.
    flag:
        Prefix that marks a split point (default ``%>``).
    end_marker:
        Suffix (after the flag) that terminates without writing (default ``END``).
    overwrite:
        If False, existing output files are left unchanged.

    Returns
    -------
    SplitResult
        Immutable result with all produced SplitFile records and \\input{} lines.
    """
    if output_dir is None:
        output_dir = source_path.parent

    source_path = source_path.resolve()
    output_dir = Path(output_dir).resolve()

    lines = source_path.read_text(encoding="utf-8").splitlines(keepends=True)

    # State
    current_rel: str | None = None  # relative path string from the marker
    current_lines: list[str] = []
    split_files: list[SplitFile] = []
    import_lines: list[str] = []
    warnings: list[str] = []

    def _flush(rel_path: str, section_lines: list[str]) -> None:
        """Write accumulated section_lines to output_dir/rel_path."""
        target = (output_dir / rel_path).resolve()
        if not str(target).startswith(str(output_dir.resolve())):
            warnings.append(f"Path traversal blocked: {rel_path}")
            return
        line_count = len(section_lines)

        if target.exists() and not overwrite:
            split_files.append(SplitFile(output_path=target, line_count=line_count, created=False))
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(section_lines), encoding="utf-8")
        split_files.append(SplitFile(output_path=target, line_count=line_count, created=True))

    for raw_line in lines:
        stripped = raw_line.rstrip("\n").rstrip("\r")

        if stripped.startswith(flag):
            marker_value = stripped[len(flag):]

            # Flush the previous section if one was active
            if current_rel is not None and current_rel != end_marker:
                _flush(current_rel, current_lines)
                current_lines = []

            if marker_value == end_marker:
                # Terminate current section; do not start a new one
                current_rel = end_marker
                current_lines = []
            else:
                # Start a new section
                current_rel = marker_value
                current_lines = []
                import_lines.append(f"  \\input{{{marker_value}}}\n")
        else:
            # Accumulate line if inside an active (non-END) section
            if current_rel is not None and current_rel != end_marker:
                current_lines.append(raw_line if raw_line.endswith("\n") else raw_line + "\n")

    # Flush the last section
    if current_rel is not None and current_rel != end_marker:
        _flush(current_rel, current_lines)

    return SplitResult(
        source_path=source_path,
        files=tuple(split_files),
        import_lines=tuple(import_lines),
        warnings=tuple(warnings),
    )
