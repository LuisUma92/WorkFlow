import json
import subprocess
import sys
from pathlib import Path

# Ruta al archivo
FILE_PATH = "course-schema.json"


def copy_to_clipboard(text: str):
    """
    Soporte multiplataforma básico:
    - Linux (xclip / xsel)
    - macOS (pbcopy)
    - Windows (clip)
    """
    try:
        if sys.platform.startswith("linux"):
            p = subprocess.Popen(
                ["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE
            )
            p.communicate(input=text.encode())
        elif sys.platform == "darwin":
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode())
        elif sys.platform.startswith("win"):
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode())
        else:
            raise RuntimeError(
                "Sistema operativo no soportado para portapapeles automático."
            )
    except FileNotFoundError:
        print("No se encontró herramienta de clipboard (xclip/xsel/pbcopy/clip).")
        print("Contenido generado:\n")
        print(text)


def main():
    data = json.loads(Path(FILE_PATH).read_text(encoding="utf-8"))

    units = data["course"]["units"]

    lines = []
    for u in units:
        uid = u.get("id", "").strip()
        name = u.get("name", "").strip()
        lines.append(f"# {uid} - {name}")

    output = "\n".join(lines)

    copy_to_clipboard(output)

    print("Contenido copiado al portapapeles:")
    print(output)


if __name__ == "__main__":
    main()
