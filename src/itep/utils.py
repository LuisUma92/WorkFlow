# src/itep/utils.py
from pathlib import Path
from typing import Any, Dict, Union
from enum import EnumType
import yaml
import re


def load_yaml(path: Union[str, Path]) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("The YAML file must be mapped yo a dict.")
    return data


def gather_input(
    msn: str,
    condition: str,
) -> str:
    output: str | None = None
    while not output:
        output = input(msn)
        if re.fullmatch(condition, output):
            return output
        else:
            print(f"Your input:\n\t>> {output}")
            print(f"Don't match the condition: {condition}")
            output = None
            ans = input("Do you want to try again? (Y/n): ").lower() or "y"
            if ans == "y":
                continue
            else:
                quit()


def select_enum_type(enum_base: EnumType) -> EnumType:
    selected: EnumType | None = None
    max_opt = len(enum_base)
    while not selected:
        print("Choose you project type:")
        for idx, enum_item in enumerate(enum_base):
            print(f"\t{idx}: {enum_item}")
        try:
            choice = int(input("Enter the number for your project type: "))
        except ValueError:
            print("You must write just the option number.\nTry again.")
            continue
        if choice < max_opt:
            selected = list(enum_base)[choice]
        else:
            print(f"You must choose between [0, {max_opt - 1}].\nTry again.")
    return selected


def code_format(
    ind: str,
    sec: Union[str, int],
    max: int = 2,
) -> str:
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


def ensure_dir(path: Path, name: str = "path") -> None:
    if not path.exists():
        print(f"Your {name} path:\n\t{path}\ndon't exists.")
        ans = input("Do you want to create it? (Y,n): ").lower() or "y"
        if ans == "y":
            path.mkdir(parents=True, exist_ok=True)
        else:
            print("We can't procced with out this directory.")
            ans = input("Do you want to abort (Y,n) ") or "y"
            if ans == "y":
                quit()
