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

        # De quí en adelante no funciona
        # ftype = f.type
        #
        # if _is_optional(ftype):
        #     # 2) Optional[T] donde T es dataclass -> preguntar y construir
        #     inner = _unwrap_optional(ftype)
        #     if is_dataclass(inner):
        #         yn = (
        #             input(f"¿Desea capturar «{f.name}»? (y/N): ").strip().lower() or "n"
        #         )
        #         data[f.name] = gather_dataclass(inner) if yn == "y" else None
        #         continue
        #     else:
        #         # Optional de tipo simple sin spec -> dejar None por defecto
        #         data[f.name] = None
        #         continue
        # elif _is_list_of_dataclass(ftype):
        #     # 3) List[Dataclass] -> pedir cantidad e instanciar cada elemento
        #     elem_type = get_args(ftype)[0]
        #     n = ask(spec(f"¿Cuántos elementos para «{f.name}»?", r"[0-9]{1,3}", int))
        #     items = []
        #     for i in range(n):
        #         print(f"\n— {f.name}[{i}] —")
        #         gather_fn = getattr(elem_type, "gather_info", None)
        #         items.append(
        #             gather_fn() if callable(gather_fn) else gather_dataclass(elem_type)
        #         )
        #     data[f.name] = items
        #     continue
        # elif _is_list(ftype):
        #     # 4) List simple sin spec -> CSV rápido
        #     csv = ask(
        #         spec(f"Ingrese CSV para «{f.name}» (vacío = lista vacía)", r".*", str)
        #     )
        #     data[f.name] = [t.strip() for t in csv.split(",")] if csv.strip() else []
        #     continue
        #
        # # 5) Tipos simples sin spec -> omitir (usar default) o podrías añadir un fallback
        # # data[f.name] no se establece: dataclasses usará default/default_factory
        #
    return clas(**data)
