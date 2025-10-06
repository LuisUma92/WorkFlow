import structure
from dataclasses import dataclass, field, asdict, fields
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union


class Lecture(structure.ProjectStructure):
    # Específicos de Lecture
    admin: Dict[str, Any] = field(default_factory=dict)
    press_config_files: Dict[str, str] = field(default_factory=dict)
    eval_config_files: Dict[str, str] = field(default_f actory=dict)
