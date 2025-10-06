from dataclasses import dataclass, field
from typing import Dict, Any, Self
import structure


@dataclass
class GeneralTopic:
    name: str = ""
    chapters: List[str] = field(default_factory=list)


class General(structure.ProjectStructure):
    base: Dict[str, Any] = {
        "config_files": structure.TexConfig,
    }
    Self.topics: Dict[str, GeneralTopic] = field(default_factory=dict)
