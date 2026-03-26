from dataclasses import dataclass, fields, is_dataclass
from typing import TypeVar, Callable, Generic, Pattern, Any, List, Protocol
from typing import get_args, get_origin, Union
import re


T = TypeVar("T")


class DataclassInstance(Protocol):
    __dataclass_fields__: dict[str, object]


@dataclass(frozen=True)
class FieldSpec(Generic[T]):
    prompt: str  # mensaje a mostrar
    pattern: Pattern[str]  # regex compilada
    parser: Callable[[str], T]  # conversión: str -> T


def spec(prompt: str, rx: str, parser: Callable[[str], T]) -> FieldSpec[T]:
    return FieldSpec(prompt=prompt, pattern=re.compile(rx), parser=parser)


def ask(spec: FieldSpec[T]) -> T:
    while True:
        print(spec.prompt)
        output = input("\t<< ")
        if not spec.pattern.fullmatch(output):
            print(f"Your input:\n\t>> {output}")
            print(f"Don't match the condition: {spec.pattern}")
            if (input("Want to try again? (Y/n): ").lower() or "y") != "y":
                raise SystemExit(1)
        try:
            return spec.parser(output)
        except Exception as e:
            print(f"Error when parsing {output}.\n{e}")
            if (input("Want to try again? (Y/n): ").lower() or "y") != "y":
                raise SystemExit(1)


def gather_input(
    msn: str,
    condition: str,
) -> str:
    """Function for back compatibility"""
    while True:
        print(msn)
        output = input("\t<< ")
        if re.fullmatch(condition, output):
            return output
        else:
            print(f"Your input:\n\t>> {output}")
            print(f"Don't match the condition: {condition}")
            if (input("Want to try again? (Y/n): ").lower() or "y") != "y":
                raise SystemExit(1)


def _is_optional(tp: Any) -> bool:
    return get_origin(tp) is Union and type(None) in get_args(tp)


def _unwrap_optional(tp: Any) -> Any:
    if not _is_optional(tp):
        return tp
    return next(a for a in get_args(tp) if a is not type(None))


def _is_list_of_dataclass(tp: Any) -> bool:
    return get_origin(tp) in (list, List) and is_dataclass(get_args(tp)[0])


def _is_list(tp: Any) -> bool:
    return get_origin(tp) in (list, List)


# Recolector genérico con soporte para Optional[Dataclass]
def gather_dataclass(clas: DataclassInstance) -> DataclassInstance:
    data: dict[str, Any] = {}
    for f in fields(clas):
        if not f.init:
            continue

        # 1) Si hay FieldSpec en metadata, úsalo
        fs: FieldSpec[Any] | None = f.metadata.get("input") if f.metadata else None
        if fs is not None:
            data[f.name] = ask(fs)
            continue

    return clas(**data)
