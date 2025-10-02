# packages/lectkit/structures.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union
import yaml  # type: ignore


def load_yaml(path: Union[str, Path]) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("El YAML raíz debe ser un mapeo (dict).")
    return data


"""
This is a general structure that every project file should implement this
to its specific needs
"""


@dataclass
class ProjectStructureOLD:
    code: str = ""
    name: str = ""
    topics: list[str] = field(default_factory=list)
    books: list[str] = field(default_factory=list)
    descriptions: dict[str, str] = field(default_factory=dict)

    def get_description(self, var_name: str) -> str:
        msn = f"ERROR: {var_name} not in structure"
        return self.descriptions.get(var_name, msn)


def make_structureOLD(struct_type="general") -> ProjectStructureOLD:
    base_desc = {
        "code": "Alfanumeric code",
        "name": "Name of the project",
        "topics": "List of topics",
        "books": "List of books",
    }
    overrides = {
        "general": {
            "topics": "General theme areas shared across courses",
            "books": "Reference books used broadly",
        },
        "course": {
            "topics": "Course topics (mapped to T## files)",
            "books": "Course-specific textbooks",
        },
    }
    desc = {**base_desc, **overrides.get(struct_type, {})}
    return ProjectStructureOLD(descriptions=desc)


# ==================== Normalización de placeholders ====================
def _norm_sec(sec: Union[str, int]) -> str:
    """sec: int 1..99 → '01'..'99'; especiales 'A0'/'D0' se respetan."""
    if isinstance(sec, int):
        if sec < 0 or sec > 99:
            raise ValueError("sec fuera de rango (esperado 1..99)")
        return f"{sec:02d}"
    s = str(sec).upper()
    if s in {"A0", "D0"}:
        return s
    if s.isdigit():
        return f"{int(s):02d}"
    return s[:2]


def _safe_format(template: str, context: Mapping[str, Any]) -> str:
    """Render 'template' con placeholders tipo f-string usando format_map."""

    class _Dict(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    return template.format_map(_Dict(**context))


# ==================== Patrón híbrido: base + overrides ====================
BASE_DESCRIPTIONS: Dict[str, str] = {
    "code": "Alfanumeric code",
    "name": "Name of the project",
    "topics": "Topics mapping (T## → metadata) o lista según configuración",
    "books": "List of book codes related to the project (si aplica)",
}

OVERRIDES: Dict[str, Dict[str, str]] = {
    "general": {
        "topics": "General theme areas (compartidos entre cursos)",
        "books": "Reference books usados de forma transversal",
    },
    "course": {
        "topics": "Course topics (sílabos; T## con metadatos como chapters/weeks)",
        "books": "Course-specific textbooks/references (si aplica)",
    },
}

# ==================== Dataclass base ====================


@dataclass
class ProjectStructure:
    # Tipo (para overrides de descripción)
    type: str = "general"  # "general" | "course"
    # Campos comunes
    code: str = ""  # p.ej. 'C01' o main code
    name: str = ""  # nombre humano
    root: str = ""
    # Para Main topic: topics puede ser dict T## → {...}
    # Para Lecture: topics T## → {name, chapters, weeks}
    topics: Any = field(default_factory=dict)
    books: Any = field(default_factory=dict)

    # Específicos de Main topic
    main_topic_root: Optional[str] = None
    config_files: Dict[str, str] = field(
        default_factory=dict
    )  # mapeo nombre→archivo (config/)
    # Específicos de Lecture
    lecture_code: Optional[str] = None
    admin: Dict[str, Any] = field(default_factory=dict)
    press_config_files: Dict[str, str] = field(default_factory=dict)
    eval_config_files: Dict[str, str] = field(default_factory=dict)

    # Rutas “fuente de verdad”
    abs_project_dir: Optional[str] = None
    abs_parent_dir: Optional[str] = None
    abs_src_dir: Optional[str] = None
    # permite 00II-ImagesFigures
    figures_base_dir: Optional[str] = None
    # permite base configurable para 00EE-ExamplesExercises
    exercises_base_dir: Optional[str] = None

    # Metadatos y patrones
    descriptions: Dict[str, str] = field(default_factory=dict)
    created_at: Optional[str] = None
    version: Optional[str] = None
    # Patrones genéricos (opcional, por si decidís listarlos en YAML)
    patterns: List[str] = field(default_factory=list)
    named_patterns: Dict[str, str] = field(default_factory=dict)

    # Cache de nombres desde Library (topic01/sub-topic01)
    _library: Dict[str, Any] = field(default_factory=dict, repr=False)

    # ---- API amigable ----
    def get_description(self, var_name: str) -> str:
        return self.descriptions.get(
            var_name, f"ERROR: {var_name} is not in {self.__class__.__name__}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    # Render múltiple a partir de patterns[]
    def render_all(
        self,
        ch: int,
        TN: int,
        par: int,
        sec: Union[int, str],
        topic01: Optional[str] = None,
        sub_topic01: Optional[str] = None,
        content_name: Optional[str] = None,
        BOOK_REFERENCE: Optional[str] = None,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> List[str]:
        ctx: Dict[str, Any] = {
            "ch": ch,
            "TN": TN,
            "par": par,
            "sec": _norm_sec(sec),
            "topic01": topic01 or self._library.get("topic01", ""),
            "sub_topic01": sub_topic01 or self._library.get("sub-topic01", ""),
            "content_name": content_name or "",
            "BOOK_REFERENCE": BOOK_REFERENCE or "",
            "ROOT": self.main_topic_root or "",
            "LECTURE_CODE": self.lecture_code or "",
        }
        if extra:
            ctx.update(extra)
        return [_safe_format(p, ctx) for p in self.patterns]

    # Render de un patrón “nombrado”
    def render_named(
        self,
        name: str,
        ch: int,
        TN: int,
        par: int,
        sec: Union[int, str],
        **kwargs: Any,
    ) -> str:
        if name not in self.named_patterns:
            raise KeyError(f"No existe el patrón '{name}'")
        pattern = self.named_patterns[name]
        return (
            self.render_all(ch, TN, par, sec, **kwargs)[0]
            if pattern in self.patterns
            else _safe_format(
                pattern,
                {
                    "ch": ch,
                    "TN": TN,
                    "par": par,
                    "sec": _norm_sec(sec),
                    "topic01": kwargs.get("topic01", self._library.get("topic01", "")),
                    "sub_topic01": kwargs.get(
                        "sub_topic01", self._library.get("sub-topic01", "")
                    ),
                    "content_name": kwargs.get("content_name", ""),
                    "BOOK_REFERENCE": kwargs.get("BOOK_REFERENCE", ""),
                    "ROOT": self.main_topic_root or "",
                    "LECTURE_CODE": self.lecture_code or "",
                    **kwargs.get("extra", {}),
                },
            )
        )


# ==================== Factory (híbrido) ====================


def make_structure(
    struct_type: str = "general", override_descriptions: Optional[Dict[str, str]] = None
) -> ProjectStructure:
    desc = {**BASE_DESCRIPTIONS, **OVERRIDES.get(struct_type, {})}
    if override_descriptions:
        desc.update(override_descriptions)
    return ProjectStructure(type=struct_type, descriptions=desc)


# ==================== Cargadores desde YAML (2 esquemas) ====================


def load_main_topic_yaml(path: Union[str, Path]) -> ProjectStructure:
    """
    Carga el config.yaml del **Main topic** (estructura y claves según ADR).
    Espera, entre otras claves:
      - main_topic_root, abs_project_dir, abs_parent_dir, abs_src_dir, version, created_at
      - topics (mapa T## → {name, book_list?})
      - config_files (mapa nombre→archivo bajo config/)
      - Library (para topic01/sub-topic01)
      - (opcionales) figures_base_dir, exercises_base_dir, patterns, named_patterns
    """
    y = load_yaml(path)
    ps = make_structure("general", y.get("descriptions"))

    ps.main_topic_root = y.get("main_topic_root") or y.get("ROOT")
    ps.abs_project_dir = y.get("abs_project_dir")
    ps.abs_parent_dir = y.get("abs_parent_dir")
    ps.abs_src_dir = y.get("abs_src_dir")
    ps.created_at = y.get("created_at")
    ps.version = y.get("version")

    # Mapa de topics T##:
    ps.topics = y.get("topics", {}) or {}
    if not isinstance(ps.topics, dict):
        # Por si viniera como lista en alguna variante
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
