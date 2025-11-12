# src/itep/utils.py
from pathlib import Path
from typing import Any, Dict, Protocol, Self, Union, List, Tuple
import yaml

from appfunc.iofunc import gather_input
from appfunc.options import select_enum_type


def ensure_dir(
    path: Path,
    name: str = "directory",
    forced: bool = False,
) -> None:
    if not path.exists() and not forced:
        print(f"Your {name} path:\n\t{path}\ndon't exists.")
        ans = input("Do you want to create it? (Y,n): ").lower() or "y"
        if ans == "y":
            path.mkdir(parents=True, exist_ok=True)
        else:
            print("We can't procced with out this directory.")
            ans = input("Do you want to abort (Y,n) ") or "y"
            if ans == "y":
                quit()
    elif not path.exists() and forced:
        path.mkdir(parents=True, exist_ok=True)


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


class DefinedByFiles(Protocol):
    @classmethod
    def from_directory(cls, path: Path) -> Self:
        return cls()


def add_to_reference_dict(
    object: DefinedByFiles,
    path: Path,
    mark: str,
    max: int = 2,
    object_dict: Dict[str, DefinedByFiles] = {},
) -> Dict[str, DefinedByFiles]:
    enough = False
    while not enough:
        idx = len(object_dict) + 1
        ref = code_format(mark, idx, max)
        object_dict[ref] = object.from_directory(path)
        if None in object_dict.values():
            return {}
        print(f"Current list:\n\t>> {object_dict}")
        ans = input("Want to add more? (y/N): ").lower() or "n"
        if ans == "n":
            enough = True
    return object_dict


def set_directory_list(msn: str, path: Path) -> List[str]:
    dir_list = [d.name for d in path.iterdir() if d.is_dir()]
    enough = False
    selected_list = []
    while not enough:
        selection = select_enum_type(msn, dir_list)
        if selection not in selected_list:
            selected_list.append(selection)
        print(f"Current selected directories:\n\t>> {selected_list}")
        ans = input("Do you want to add more? (y/N): ").lower() or "n"
        if ans == "n":
            enough = True
    return selected_list


def load_yaml(path: Union[str, Path]) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("The YAML file must be mapped to a dict.")
    return data


def write_yaml(path: Path, data: Dict) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def enter_hours(name: str) -> Tuple:
    msn = f"Enter the scheldule time for {name}\n"
    msn += "hour,timezone (ej: 13,-6)\n"
    msn += "\t<< "
    hours = gather_input(msn, "^([0-9]|[12][0-9]),([+-])([0-9]|[12][0-9])")
    hour, tmz = hours.split(",")
    return int(hour), int(tmz)
