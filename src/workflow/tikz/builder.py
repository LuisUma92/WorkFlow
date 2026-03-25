"""
TikZ standalone asset pipeline — builder core.

Rules:
- No DB dependency (uses JSON state file for incremental builds).
- No Click dependency.
- No printing — returns structured results.
- subprocess.run with capture_output=True, no shell=True.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# =============================================================================
# Results
# =============================================================================


@dataclass(frozen=True)
class BuildResult:
    source: Path
    pdf: Optional[Path]
    svg: Optional[Path]
    compiled: bool  # True if actually compiled (not skipped)
    error: Optional[str]  # None on success


# =============================================================================
# Helpers — command availability
# =============================================================================


def _require_command(name: str) -> None:
    """Raise RuntimeError with a helpful message if *name* is not on PATH."""
    if shutil.which(name) is None:
        raise RuntimeError(
            f"Required command '{name}' not found on PATH. "
            f"Install it and ensure it is accessible before running the build."
        )


# =============================================================================
# Source discovery
# =============================================================================


def find_tikz_sources(assets_dir: Path) -> list[Path]:
    """Return all *.tex files under *assets_dir*, sorted for determinism."""
    return sorted(assets_dir.rglob("*.tex"))


# =============================================================================
# Hash
# =============================================================================


def compute_hash(path: Path) -> str:
    """Return SHA-256 hex digest of *path* contents."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# =============================================================================
# State file (incremental build cache)
# =============================================================================

_STATE_FILE = ".tikz-state.json"

_ALLOWED_ENGINES = {"latexmk", "pdflatex", "xelatex", "lualatex"}


def _load_state(output_dir: Path) -> dict[str, str]:
    state_path = output_dir / _STATE_FILE
    if state_path.exists():
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(output_dir: Path, state: dict[str, str]) -> None:
    state_path = output_dir / _STATE_FILE
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


# =============================================================================
# Compile a single TikZ file → PDF
# =============================================================================


def compile_tikz(
    source: Path,
    output_dir: Path,
    engine: str = "latexmk",
) -> BuildResult:
    """
    Compile *source* to PDF using *engine* (default: latexmk).

    Returns a BuildResult; never raises — errors go into BuildResult.error.
    """
    if engine not in _ALLOWED_ENGINES:
        raise ValueError(f"engine must be one of {_ALLOWED_ENGINES}")
    _require_command(engine)
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        engine,
        "-pdf",
        "-interaction=nonstopmode",
        f"-outdir={output_dir}",
        str(source),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True)
    except FileNotFoundError as exc:
        return BuildResult(
            source=source,
            pdf=None,
            svg=None,
            compiled=True,
            error=f"Executable not found: {exc}",
        )

    pdf_path = output_dir / source.with_suffix(".pdf").name
    if proc.returncode != 0 or not pdf_path.exists():
        stdout = proc.stdout.decode("utf-8", errors="replace")
        stderr = proc.stderr.decode("utf-8", errors="replace")
        return BuildResult(
            source=source,
            pdf=None,
            svg=None,
            compiled=True,
            error=f"{engine} failed (rc={proc.returncode}):\n{stdout}{stderr}",
        )

    return BuildResult(source=source, pdf=pdf_path, svg=None, compiled=True, error=None)


# =============================================================================
# Convert PDF → SVG
# =============================================================================


def convert_to_svg(pdf_path: Path, output_dir: Path) -> Path:
    """
    Convert *pdf_path* to SVG using pdf2svg (preferred) or dvisvgm.

    Returns the SVG Path on success; raises RuntimeError on failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path = output_dir / pdf_path.with_suffix(".svg").name

    if shutil.which("pdf2svg"):
        cmd = ["pdf2svg", str(pdf_path), str(svg_path)]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"pdf2svg failed (rc={proc.returncode}):\n{stderr}")
        return svg_path

    if shutil.which("dvisvgm"):
        cmd = ["dvisvgm", "--pdf", str(pdf_path), "-o", str(svg_path)]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"dvisvgm failed (rc={proc.returncode}):\n{stderr}")
        return svg_path

    raise RuntimeError(
        "Neither 'pdf2svg' nor 'dvisvgm' found on PATH. "
        "Install one of them to enable SVG conversion."
    )


# =============================================================================
# Incremental build — all sources
# =============================================================================


def build_all(
    assets_dir: Path,
    output_dir: Path,
    force: bool = False,
    svg: bool = True,
) -> list[BuildResult]:
    """
    Incrementally compile all TikZ sources under *assets_dir*.

    Uses a JSON state file at *output_dir*/.tikz-state.json to track hashes.
    Skips files whose hash has not changed (unless force=True).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    state = _load_state(output_dir)
    sources = find_tikz_sources(assets_dir)
    results: list[BuildResult] = []

    for source in sources:
        key = str(source)
        current_hash = compute_hash(source)
        cached_hash = state.get(key)

        if not force and cached_hash == current_hash:
            # Determine existing artefact paths without recompiling.
            pdf_path = output_dir / source.with_suffix(".pdf").name
            svg_path = output_dir / source.with_suffix(".svg").name
            results.append(
                BuildResult(
                    source=source,
                    pdf=pdf_path if pdf_path.exists() else None,
                    svg=svg_path if svg_path.exists() else None,
                    compiled=False,
                    error=None,
                )
            )
            continue

        # Compile to PDF.
        result = compile_tikz(source, output_dir)

        # Convert to SVG if requested and compilation succeeded.
        svg_path: Optional[Path] = None
        if svg and result.pdf is not None:
            try:
                svg_path = convert_to_svg(result.pdf, output_dir)
            except RuntimeError as exc:
                result = BuildResult(
                    source=result.source,
                    pdf=result.pdf,
                    svg=None,
                    compiled=result.compiled,
                    error=str(exc),
                )
        else:
            svg_path = result.svg  # None unless already set

        final = BuildResult(
            source=result.source,
            pdf=result.pdf,
            svg=svg_path,
            compiled=result.compiled,
            error=result.error,
        )
        results.append(final)

        # Only update state when compilation succeeded.
        if final.error is None:
            state[key] = current_hash

    _save_state(output_dir, state)
    return results
