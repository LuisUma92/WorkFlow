# src/itep/utils.py
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
import yaml
from itep.structure import ProjectStructure, make_structure


def load_yaml(path: Union[str, Path]) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("El YAML raíz debe ser un mapeo (dict).")
    return data


# ==================== Cargadores desde YAML (2 esquemas) ====================


def load_main_topic_yaml(path: Union[str, Path]) -> ProjectStructure:
    """
    Carga el config.yaml del **Main topic** (estructura y claves según ADR).
    Espera, entre otras claves:
      - main_topic_root, abs_project_dir, abs_parent_dir, abs_src_dir, version,
        created_at
      - topics (mapa T## → {name, book_list?})
      - config_files (mapa nombre→archivo bajo config/)
      - Library (para topic01/sub-topic01)
      - (opcionales) figures_base_dir, exercises_base_dir, patterns,
        named_patterns
    """
    y = load_yaml(path)
    ps = make_structure("general", y.get("descriptions"))

    ps.data.main_topic_root = y.get("ROOT")
    ps.data.abs_project_dir = y.get("abs_project_dir")
    ps.data.abs_parent_dir = y.get("abs_parent_dir")
    ps.data.abs_src_dir = y.get("abs_src_dir")
    ps.data.created_at = y.get("created_at")
    ps.data.version = y.get("version")

    # Mapa de topics T##:
    ps.topics = y.get("topics", {}) or {}
    if not isinstance(ps.topics, dict):
        ps.topics = {f"T{i + 1:02d}": {"name": t} for i, t in enumerate(ps.topics)}

    # Config files (diccionario nombre→archivo)
    cfg = y.get("config_files", {}) or {}
    if isinstance(cfg, dict):
        ps.config_files = {str(k): str(v) for k, v in cfg.items()}

    # Rutas base opcionales (para resolver dualidad 00BB/00II y ejercicios)
    ps.figures_base_dir = y.get("figures_base_dir")  # opcional
    ps.exercises_base_dir = y.get("exercises_base_dir")  # opcional

    # Patrones opcionales
    if "patterns" in y and isinstance(y["patterns"], list):
        ps.patterns = [str(p) for p in y["patterns"]]
    if "named_patterns" in y and isinstance(y["named_patterns"], dict):
        ps.named_patterns = {str(k): str(v) for k, v in y["named_patterns"].items()}

    # Library
    lib = y.get("Library") or y.get("library") or {}
    if isinstance(lib, dict):
        ps._library = lib
    return ps


def load_lecture_yaml(path: Union[str, Path]) -> ProjectStructure:
    """
    Carga el config.yaml de **Lecture** (estructura y claves según ADR).
    Espera:
      - lecture_code, abs_project_dir, abs_parent_dir, abs_src_dir, version, created_at
      - admin: {total_week_count, lectures_per_week, year, cicle, first_monday, week_day: [...]}
      - main_topic_root: [ROOT, ...]  (lista de raíces principales relacionadas)
      - topics: mapa T## → {name, chapters: [C##], weeks: [W##L##]}
      - press.config_files (mapa)
      - eval.config_files  (mapa)
      - opcionales: figures_base_dir, exercises_base_dir, patterns, named_patterns, Library
    """
    y = load_yaml(path)
    ps = make_structure("course", y.get("descriptions"))

    ps.lecture_code = y.get("lecture_code")
    ps.abs_project_dir = y.get("abs_project_dir")
    ps.abs_parent_dir = y.get("abs_parent_dir")
    ps.abs_src_dir = y.get("abs_src_dir")
    ps.created_at = y.get("created_at")
    ps.version = y.get("version")

    # admin
    adm = y.get("admin") or {}
    if isinstance(adm, dict):
        ps.admin = adm

    # main_topic_root como lista (según ADR)
    ps.main_topic_root = None  # no único; guardamos en _library por conveniencia
    if isinstance(y.get("main_topic_root"), list):
        ps._library["main_topic_root_list"] = list(y["main_topic_root"])

    # topics (dict T## → {...})
    ps.topics = y.get("topics", {}) or {}
    if not isinstance(ps.topics, dict):
        ps.topics = {}

    # press/eval config_files (mapas)
    press = y.get("press") or {}
    if isinstance(press, dict) and isinstance(press.get("config_files"), dict):
        ps.press_config_files = {
            str(k): str(v) for k, v in press["config_files"].items()
        }

    eval_ = y.get("eval") or {}
    if isinstance(eval_, dict) and isinstance(eval_.get("config_files"), dict):
        ps.eval_config_files = {
            str(k): str(v) for k, v in eval_["config_files"].items()
        }

    # Rutas base opcionales
    ps.figures_base_dir = y.get("figures_base_dir")
    ps.exercises_base_dir = y.get("exercises_base_dir")

    # Patrones opcionales
    if "patterns" in y and isinstance(y["patterns"], list):
        ps.patterns = [str(p) for p in y["patterns"]]
    if "named_patterns" in y and isinstance(y["named_patterns"], dict):
        ps.named_patterns = {str(k): str(v) for k, v in y["named_patterns"].items()}

    # Library (por si querés topic01/sub-topic01 en curso también)
    lib = y.get("Library") or y.get("library") or {}
    if isinstance(lib, dict):
        ps._library = {**ps._library, **lib}
    return ps


# ==================== Ayudas ====================


def get_topic_names(ps: ProjectStructure) -> Tuple[Optional[str], Optional[str]]:
    """Extrae topic01 y sub-topic01 si están en la sección Library del YAML."""
    lib = getattr(ps, "_library", {})
    t1 = lib.get("topic01") if isinstance(lib, dict) else None
    st1 = lib.get("sub-topic01") if isinstance(lib, dict) else None
    return t1, st1
