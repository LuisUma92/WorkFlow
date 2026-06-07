import shutil
import subprocess


def copy_to_clipboard(text: str) -> None:
    if shutil.which("wl-copy") is None:
        return

    subprocess.run(
        ["wl-copy"],
        input=text,
        text=True,
        check=False,
    )
