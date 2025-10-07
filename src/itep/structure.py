# src/itep/structures.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Union


class ConfigType(Enum):
    BASE = "base"
    EVAL = "eval"
    PRESS = "press"


# ==================== Patrón híbrido: base + overrides ====================
BASE_DESCRIPTIONS: Dict[str, str] = {
    "code": "Alfanumeric code",
    "name": "Name of the project",
    "root": "{code}-{name}",
    "data": "Dictionary with metadata",
    "main_topic_root": "List of topics",
    "books": "List of book codes related to the project (si aplica)",
    "topics": "Topics mapping (T## → metadata) o lista según configuración",
}

OVERRIDES: Dict[str, Dict[str, str]] = {
    "general": {
        "main_topic_list": "List of directories names on 00BB-Library",
        "topics": "General theme areas",
        "books": "Reference books usados de forma transversal",
    },
    "course": {
        "main_topic_list": "List of directories names on abs_parent_dir",
        "topics": "Course topics (sílabos; with metadata: chapters/weeks)",
        "books": "Course-specific textbooks/references",
    },
}

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


# ==================== Dataclass base ====================


class TexConfig:
    packages: Dict = {
        "type": "sty",
        "src": "SetFormat",
        "termination": "sty",
        "number": 0,
    }
    loyaut: Dict = {
        "type": "sty",
        "src": "SetLoyaut",
        "termination": "sty",
        "number": 1,
    }
    commands: Dict = {
        "type": "sty",
        "src": "SetCommands",
        "termination": "sty",
        "number": 2,
    }
    partial: Dict = {
        "type": "sty",
        "src": "PartialCommands",
        "termination": "sty",
        "number": 2,
    }
    units: Dict = {
        "type": "sty",
        "src": "SetUnits",
        "termination": "sty",
        "number": 3,
    }
    profiles: Dict = {
        "type": "sty",
        "src": "SetProfiles",
        "termination": "sty",
        "number": 5,
    }
    headers: Dict = {
        "type": "sty",
        "src": "SetHeaders",
        "termination": "sty",
        "number": 6,
    }
    title: Dict = {
        "type": "template",
        "src": "title",
        "termination": "tex",
        "number": None,
    }


@dataclass
class MetaData:
    # absolute routes
    abs_project_dir: Optional[str] = None
    abs_parent_dir: Optional[str] = None
    abs_src_dir: Optional[str] = None
    # 00II-ImagesFigures
    figures_base_dir: List[str] = field(default_factory=list)
    # 00EE-ExamplesExercises
    exercises_base_dir: List[str] = field(default_factory=list)
    # Metadata and patterns
    descriptions: Dict[str, str] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    version: Optional[str] = None
    # Generic patterns (optional)
    patterns: List[str] = field(default_factory=list)
    named_patterns: Dict[str, str] = field(default_factory=dict)

    # -------------------- Custom constructor --------------------
    def __init__(self, data: Optional[Dict[str, Any]] = None):
        """
        Allows you to initialize the object with a dictionary.
        Assigns only recognized keys; ignores others.
        Converts 'created_at' to a datetime if it comes as a string.
        """
        # Inicializa valores por defecto
        for f in fields(self):
            setattr(
                self,
                f.name,
                f.default_factory() if callable(f.default_factory) else f.default,
            )

        if not data:
            return

        for key, value in data.items():
            if not hasattr(self, key):
                continue  # ignores unknown fields

            # Conversión automática para created_at
            if key == "created_at" and isinstance(value, str):
                try:
                    value = datetime.fromisoformat(value)
                except Exception:
                    # Si falla el parseo, lo deja como string
                    pass

            # Si el campo debe ser lista y recibimos un string, convertimos
            if key in {"figures_base_dir", "exercises_base_dir"} and isinstance(
                value, str
            ):
                value = [value]

            setattr(self, key, value)

    # -------------------- Métodos utilitarios --------------------
    def to_dict(self) -> Dict[str, Any]:
        """Devuelve un diccionario serializable (convierte datetime a ISO)."""
        result = {}
        for f in fields(self):
            val = getattr(self, f.name)
            if isinstance(val, datetime):
                val = val.isoformat()
            result[f.name] = val
        return result

    def __repr__(self) -> str:
        return f"MetaData(version={self.version}, created_at={self.created_at}, abs_project_dir={self.abs_project_dir})"

    def get(self, key, default):
        if not hasattr(self, key):
            return default
        else:
            return getattr(self, key)


@dataclass
class Topic:
    name: str = ""
    chapters: List[str] = field(default_factory=list)
    weeks: Optional[List[str]] = None

    def __init__(self, data: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Inicializa desde dict o kwargs.
        - 'chapters' siempre se almacena como lista.
        - 'weeks' puede ser None (se preserva), o lista; si viene como str -> [str].
        - Campos desconocidos se ignoran.
        """
        # Inicializar con defaults de la dataclass (incluye default_factory)
        for f in fields(self):
            setattr(
                self,
                f.name,
                f.default_factory()
                if callable(getattr(f, "default_factory", None))
                else f.default,
            )

        # Combinar data y kwargs
        if data:
            kwargs.update(data)

        for key, value in kwargs.items():
            if not hasattr(self, key):
                continue

            if key == "chapters":
                if value is None:
                    value = []
                elif isinstance(value, str):
                    value = [value]
                elif not isinstance(value, list):
                    raise TypeError(
                        f"'chapters' debe ser lista[str] o str, no {type(value)}"
                    )

            elif key == "weeks":
                # Permitir None explícito
                if value is None:
                    # se mantiene None
                    pass
                elif isinstance(value, str):
                    value = [value]
                elif not isinstance(value, list):
                    raise TypeError(
                        f"'weeks' debe ser Optional[list[str]] o str, no {type(value)}"
                    )

            setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        """Devuelve diccionario serializable (weeks puede ser None o lista)."""
        return {
            "name": self.name,
            "chapters": list(self.chapters),
            "weeks": (None if self.weeks is None else list(self.weeks)),
        }

    def __repr__(self) -> str:
        n_weeks = "None" if self.weeks is None else len(self.weeks)
        return (
            f"Topic(name={self.name!r}, chapters={len(self.chapters)}, weeks={n_weeks})"
        )


@dataclass
class ProjectStructure:
    """
    This is a general structure that every project file should implement this
    to its specific needs
    """

    # Tipo (para overrides de descripción)
    type: str = "general"  # "general" | "course"
    # Campos comunes
    code: str = ""  # p.ej. 'C01' o main code
    name: str = ""  # nombre humano
    root: str = ""
    data: MetaData = field(default_factory=MetaData)
    # Específicos de Main topic
    main_topic_root: List[str] = field(default_factory=list)
    books: Any = field(default_factory=dict)
    # Para Main topic: topics puede ser dict T## → {...}
    # Para Lecture: topics T## → {name, chapters, weeks}
    topics: Any = field(default_factory=dict)

    # ---- API amigable ----
    def get_description(self, var_name: str) -> str:
        return self.data.descriptions.get(
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
        content_name: Optional[str] = None,
        BOOK_REFERENCE: Optional[str] = None,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> List[str]:
        ctx: Dict[str, Any] = {
            "ch": ch,
            "TN": TN,
            "par": par,
            "sec": _norm_sec(sec),
            "content_name": content_name or "",
            "BOOK_REFERENCE": BOOK_REFERENCE or "",
            "ROOT": self.main_topic_root or "",
        }
        if extra:
            ctx.update(extra)
        return [_safe_format(p, ctx) for p in self.data.patterns]

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
        if name not in self.data.named_patterns:
            raise KeyError(f"No existe el patrón '{name}'")
        pattern = self.data.named_patterns[name]
        return (
            self.render_all(ch, TN, par, sec, **kwargs)[0]
            if pattern in self.data.patterns
            else _safe_format(
                pattern,
                {
                    "ch": ch,
                    "TN": TN,
                    "par": par,
                    "sec": _norm_sec(sec),
                    "content_name": kwargs.get("content_name", ""),
                    "BOOK_REFERENCE": kwargs.get("BOOK_REFERENCE", ""),
                    "ROOT": self.main_topic_root or "",
                    **kwargs.get("extra", {}),
                },
            )
        )


# ==================== Factory (híbrido) ====================


def make_structure(
    struct_type: str = "general",
    override_descriptions: Optional[Dict[str, str]] = None,
) -> ProjectStructure:
    desc = {**BASE_DESCRIPTIONS, **OVERRIDES.get(struct_type, {})}
    if override_descriptions:
        desc.update(override_descriptions)
    thisStructure = ProjectStructure(type=struct_type)
    thisStructure.data.descriptions = desc
    return thisStructure
