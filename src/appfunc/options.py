from typing import Iterable


def select_enum_type(name: str, enum_base: Iterable[str]) -> str:
    selected = None
    max_opt = len(enum_base)
    while not selected:
        print(f"Choose you {name}:")
        for idx, enum_item in enumerate(enum_base):
            print(f"\t{idx}: {enum_item}")
        try:
            print("Enter -1 to avoid selecting a topic.\n")
            choice = int(input(f"Enter the number for your {name}: "))
        except ValueError:
            print("You must write just the option number.\nTry again.")
            continue
        if choice < 0:
            raise StopIteration
        elif choice < max_opt:
            selected = list(enum_base)[choice]
        else:
            print(f"You must choose between [0, {max_opt - 1}].\nTry again.")
    return selected
