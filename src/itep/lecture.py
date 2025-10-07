from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from itep import structure
from typing import Any, Dict, List


class institution(Enum):
    UCR = "UCR"
    FIDE = "UFide"
    UCIMED = "UCIMED"


@dataclass
class Lecture(structure.ProjectStructure):
    # Específicos de Lecture
    admin: Dict[str, Any] = {
        "institution": institution,
        "total_week_count": int,
        "lectures_per_week": int,
        "year": int,
        "cycle": int,
        "first_monday": datetime,
        "week_day": List[str],
    }
    press: Dict[str, Any] = {
        "config_files": structure.TexConfig,
    }
    eval: Dict[str, Any] = {
        "config_files": structure.TexConfig,
        "instruments": {
            "partial": {
                "amount": int,
                "duedate": List[str],
            },
            "quiz": {
                "amount": int,
                "duedate": List[str],
            },
            "homework": {
                "amount": int,
                "duedate": List[str],
            },
            "project": {
                "amount": int,
                "duedate": List[str],
            },
        },
    }
    topics: Dict[str, structure.Topic] = field(default_factory=dict)
