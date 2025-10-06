# src/itep/structures.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Union


# ==================== Patrón híbrido: base + overrides ====================
BASE_DESCRIPTIONS: Dict[str, str] = {
    "code": "Alfanumeric code",
    "name": "Name of the project",
    "root": "{code}-{name}",
    "data": "Dictionary with metadata",
    "main_topic_root": "List of topics"
    "books": "List of book codes related to the project (si aplica)",
    "topics": "Topics mapping (T## → metadata) o lista según configuración",
}

OVERRIDES: Dict[str, Dict[str, str]] = {
    "general": {
        "main_topic_list": "List of directories names on 00BB-Library"
        "topics": "General theme areas",
        "books": "Reference books usados de forma transversal",
    },
    "course": {
        "main_topic_list": "List of directories names on abs_parent_dir"
        "topics": "Course topics (sílabos; with metadata: chapters/weeks)",
        "books": "Course-specific textbooks/references",
    },
}

# ==================== Dataclass base ====================


@dataclass
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
    # Patrones genéricos (opcional, por si decidís listarlos en YAML)
    patterns: List[str] = field(default_factory=list)
    named_patterns: Dict[str, str] = field(default_factory=dict)


"""
This is a general structure that every project file should implement this
to its specific needs
"""


@dataclass
class ProjectStructure:
    # Tipo (para overrides de descripción)
    type: str = "general"  # "general" | "course"
    # Campos comunes
    code: str = ""  # p.ej. 'C01' o main code
    name: str = ""  # nombre humano
    root: str = ""
    data: MetaData = MetaData()
    # Específicos de Main topic
    main_topic_root: List[str] = field(default_factory=list)
    books: Any = field(default_factory=dict)
    # Para Main topic: topics puede ser dict T## → {...}
    # Para Lecture: topics T## → {name, chapters, weeks}
    topics: Any = field(default_factory=dict)

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
            "content_name": content_name or "",
            "BOOK_REFERENCE": BOOK_REFERENCE or "",
            "ROOT": self.main_topic_root or "",
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
