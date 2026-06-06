import os
from pathlib import Path

import platformdirs

from workflow import config as _workflow_config
from workflow import paths

_DEFAULT_PHYSICS_DIR = Path.home() / "Documents" / "01-U" / "00-Fisica"
DEF_ABS_PARENT_DIR = Path(
    os.environ.get("WORKFLOW_PHYSICS_DIR", str(_DEFAULT_PHYSICS_DIR))
)
DEF_ABS_SRC_DIR = paths.data_dir()

# Default institution short name.  Reads config.yaml when present;
# falls back to "UCR" when no config is set.
DEFAULT_INSTITUTION: str = _workflow_config.get_default_institution("UCR")
# itep namespace kept behaviour-identical (P3 will collapse); just off appdirs.
DB_PATH = Path(platformdirs.user_data_dir("itep")) / "itep.db"

# XDG canonical pool for shared LaTeX assets (single source of truth).
# Populated from `shared/latex/sty/` + legacy `~/.config/mytex/sty/`.
_XDG_STY = paths.data_dir() / "sty"

# Templates still live in repo until migrated.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SHARED_LATEX = _REPO_ROOT / "shared" / "latex"
_TEMPLATES = _SHARED_LATEX / "templates"


# Default link layout (legacy hyphen scheme). Used when an institution has
# no specific dict in INSTITUTION_TEX_CONFIG.
DEF_TEX_CONFIG = {
    "0-packages.sty": str(_XDG_STY / "SetFormat.sty"),
    "1-loyaut.sty": str(_XDG_STY / "SetLoyaut.sty"),
    "2-commands.sty": str(_XDG_STY / "SetCommands.sty"),
    "2-partial.sty": str(_XDG_STY / "PartialCommands.sty"),
    "3-units.sty": str(_XDG_STY / "SetUnits.sty"),
    "3-symbols.sty": str(_XDG_STY / "SetSymbols.sty"),
    "5-profiles.sty": str(_XDG_STY / "SetProfiles.sty"),
    "6-headers.sty": str(_XDG_STY / "SetHeaders.sty"),
    "7-colors.sty": str(_XDG_STY / "colors-{institution}.sty"),
    "7-colors-light.sty": str(_XDG_STY / "ColorsLight.sty"),
    "8-zettelkasten.sty": str(_XDG_STY / "SetZettelkasten.sty"),
    "8-exercises.sty": str(_XDG_STY / "SetExercises.sty"),
    "8-constants.sty": str(_XDG_STY / "SetConstant.sty"),
    "8-vectors.sty": str(_XDG_STY / "VectorPGF.sty"),
    "title.tex": str(_TEMPLATES / "title.tex"),
    "instructions.tex": str(_TEMPLATES / "{institution}-PPI.tex"),
}


# Per-institution link layouts. Falls back to DEF_TEX_CONFIG if institution
# not listed. NOTE: beamer themes, biber bib, and tareas templates not yet
# in XDG — add entries here once moved.
INSTITUTION_TEX_CONFIG: dict[str, dict[str, str]] = {
    "UCIMED": {
        "0_packages.sty": str(_XDG_STY / "SetFormat.sty"),
        "1_loyaut.sty": str(_XDG_STY / "SetLoyaut.sty"),
        "1_loyaut_standalone.sty": str(_XDG_STY / "SetLoyaut-StandAlone.sty"),
        "2_commands.sty": str(_XDG_STY / "SetCommands.sty"),
        "2_partial.sty": str(_XDG_STY / "PartialCommands.sty"),
        "3_units.sty": str(_XDG_STY / "SetUnits.sty"),
        "4_constants.sty": str(_XDG_STY / "SetConstant.sty"),
        "4_symbols.sty": str(_XDG_STY / "SetSymbols.sty"),
        "5_colors.sty": str(_XDG_STY / "colors-UCIMED.sty"),
        "5_PGF_vector.sty": str(_XDG_STY / "VectorPGF.sty"),
        "5_profiles.sty": str(_XDG_STY / "SetProfiles.sty"),
        "6_headers.sty": str(_XDG_STY / "SetHeaders.sty"),
        "title.tex": str(_TEMPLATES / "title.tex"),
        "beamercolorthemeUCIMED.sty": str(_XDG_STY / "beamercolorthemeUCIMED.sty"),
        "beamerfontthemeUCIMED.sty": str(_XDG_STY / "beamerfontthemeUCIMED.sty"),
        "beamerinnerthemeUCIMED.sty": str(_XDG_STY / "beamerinnerthemeUCIMED.sty"),
        "beamerouterthemeUCIMED.sty": str(_XDG_STY / "beamerouterthemeUCIMED.sty"),
        "beamerthemeUCIMED.sty": str(_XDG_STY / "beamerthemeUCIMED.sty"),
    },
    "UCR": {
        "0_packages.sty": str(_XDG_STY / "SetFormat.sty"),
        "1_loyaut.sty": str(_XDG_STY / "SetLoyaut.sty"),
        "1_loyaut_standalone.sty": str(_XDG_STY / "SetLoyaut-StandAlone.sty"),
        "2_commands.sty": str(_XDG_STY / "SetCommands.sty"),
        "2_partial.sty": str(_XDG_STY / "PartialCommands.sty"),
        "3_units.sty": str(_XDG_STY / "SetUnits.sty"),
        "4_constants.sty": str(_XDG_STY / "SetConstant.sty"),
        "4_symbols.sty": str(_XDG_STY / "SetSymbols.sty"),
        "5_colors.sty": str(_XDG_STY / "colors-UCR.sty"),
        "5_PGF_vector.sty": str(_XDG_STY / "VectorPGF.sty"),
        "5_profiles.sty": str(_XDG_STY / "SetProfiles.sty"),
        "6_headers.sty": str(_XDG_STY / "SetHeaders.sty"),
        "title.tex": str(_TEMPLATES / "title.tex"),
        "beamercolorthemeUCR.sty": str(_XDG_STY / "beamercolorthemeUCR.sty"),
        "beamerfontthemeUCR.sty": str(_XDG_STY / "beamerfontthemeUCR.sty"),
        "beamerinnerthemeUCR.sty": str(_XDG_STY / "beamerinnerthemeUCR.sty"),
        "beamerouterthemeUCR.sty": str(_XDG_STY / "beamerouterthemeUCR.sty"),
        "beamerthemeUCR.sty": str(_XDG_STY / "beamerthemeUCR.sty"),
    },
}


def get_tex_config(institution: str | None) -> dict[str, str]:
    """Return link layout for an institution, or default if unknown."""
    if institution and institution in INSTITUTION_TEX_CONFIG:
        return INSTITUTION_TEX_CONFIG[institution]
    return DEF_TEX_CONFIG
