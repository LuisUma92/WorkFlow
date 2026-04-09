import os
from pathlib import Path
from appdirs import user_data_dir

_DEFAULT_PHYSICS_DIR = Path.home() / "Documents" / "01-U" / "00-Fisica"
DEF_ABS_PARENT_DIR = Path(os.environ.get("WORKFLOW_PHYSICS_DIR", str(_DEFAULT_PHYSICS_DIR)))
DEF_ABS_SRC_DIR = Path(user_data_dir("workflow", "LuisUmana"))
DB_PATH = Path(user_data_dir("itep")) / "itep.db"

# Resolve shared LaTeX assets from the repo (shared/latex/)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SHARED_LATEX = _REPO_ROOT / "shared" / "latex"

DEF_TEX_CONFIG = {
    "0-packages.sty": str(_SHARED_LATEX / "sty" / "SetFormat.sty"),
    "1-loyaut.sty": str(_SHARED_LATEX / "sty" / "SetLoyaut.sty"),
    "2-commands.sty": str(_SHARED_LATEX / "sty" / "SetCommands.sty"),
    "2-partial.sty": str(_SHARED_LATEX / "sty" / "PartialCommands.sty"),
    "3-units.sty": str(_SHARED_LATEX / "sty" / "SetUnits.sty"),
    "3-symbols.sty": str(_SHARED_LATEX / "sty" / "SetSymbols.sty"),
    "5-profiles.sty": str(_SHARED_LATEX / "sty" / "SetProfiles.sty"),
    "6-headers.sty": str(_SHARED_LATEX / "sty" / "SetHeaders.sty"),
    "7-colors.sty": str(_SHARED_LATEX / "sty" / "colors-{institution}.sty"),
    "7-colors-light.sty": str(_SHARED_LATEX / "sty" / "ColorsLight.sty"),
    "8-zettelkasten.sty": str(_SHARED_LATEX / "sty" / "SetZettelkasten.sty"),
    "8-exercises.sty": str(_SHARED_LATEX / "sty" / "SetExercises.sty"),
    "8-constants.sty": str(_SHARED_LATEX / "sty" / "SetConstant.sty"),
    "8-vectors.sty": str(_SHARED_LATEX / "sty" / "VectorPGF.sty"),
    "title.tex": str(_SHARED_LATEX / "templates" / "title.tex"),
    "instructions.tex": str(_SHARED_LATEX / "templates" / "{institution}-PPI.tex"),
}
