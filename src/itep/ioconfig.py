from dataclasses import is_dataclass
from pathlib import Path
from typing import Any, Dict
from itep.structure import ProjectStructure
from itep.utils import load_yaml, write_yaml
from datetime import date, datetime


def load_config(file: str):
    cfg_dict = load_yaml(file)
    return ProjectStructure(**cfg_dict)


def _to_dict(key: str, data: Any) -> Dict[str, str]:
    thisD = {}
    if isinstance(data, (int, str, Path)):
        thisD[key] = str(data)
    elif isinstance(data, (date, datetime)):
        thisD[key] = data.isoformat()
    elif isinstance(data, list):
        temp = []
        for ndata in data:
            if is_dataclass(ndata) or isinstance(ndata, dict):
                temp2 = []
                for nnkey, nndata in dict(ndata).items():
                    temp2.append(
                        (f"\t{k}: {v}\n\t" for k, v in _to_dict(nnkey, nndata).items())
                    )
                temp.append("\n\t- ".join(temp2))
            else:
                temp.append(str(ndata))
        thisD[key] = "\n\t- ".join(temp)
    elif is_dataclass(data):
        temp = {}
        if hasattr(data, "structure_repr"):
            temp = data.structure_repr()
        else:
            for nkey, ndata in dict(data).items():
                temp.update(_to_dict(nkey, ndata))
        thisD[key] = temp
    return thisD


def save_config(cfg: ProjectStructure, path: Path):
    data = {}
    for atrr, info in dict(cfg).items():
        data.update(_to_dict(atrr, info))
    write_yaml(path, data)
    pass
