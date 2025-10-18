# src/itep/utils.py
from pathlib import Path
from typing import Any, Dict, Union
import yaml


def load_yaml(path: Union[str, Path]) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("El YAML raíz debe ser un mapeo (dict).")
    return data


def code_format(ind: str, sec: Union[str, int], max: int = 2) -> str:
    """sec: int 1..99 → '01'..'99'; especiales 'A0'/'D0' se respetan."""
    ind = ind.upper()
    if isinstance(sec, int):
        if sec < 0 or sec > 10**max - 1:
            raise ValueError(f"sec fuera de rango (esperado 1..{10**max - 1})")
        return f"{ind}{sec:0{max}d}"
    sec = str(sec).upper()
    if len(sec) == max:
        return f"{ind}{sec}"
    elif len(sec) < max:
        return f"{ind}{0:0{max - len(sec)}}{sec}"
    else:
        raise ValueError(f"{sec}({len(sec)}) fuera del rango esperado: {max}")


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
