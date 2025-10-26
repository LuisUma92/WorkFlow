import re


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
