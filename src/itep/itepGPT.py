#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI para inicializar cursos en 'lect' y recrear enlaces desde config.yaml.
Requisitos: click (pip install click). No usa PyYAML; escribe/lee YAML simple.
"""

# import os
# import sys
import click
from pathlib import Path
from datetime import datetime

# --- Constantes por defecto ---
DEF_ABS_PARENT_DIR = "/home/luis/Documents/01-U/00-Fisica"
DEF_ABS_SRC_DIR = "/home/luis/.config/mytex"

CONFIG_FILES_ORDER = [
    ("press/config/0_packages.sty", "{ABS_SRC_DIR}/sty/SetFormatP.sty"),
    ("press/config/1_loyaut.sty", "{ABS_SRC_DIR}/sty/SetLoyaut.sty"),
    ("press/config/2_commands.sty", "{ABS_SRC_DIR}/sty/SetCommands.sty"),
    ("press/config/3_units.sty", "{ABS_SRC_DIR}/sty/SetUnits.sty"),
    ("press/config/5_profiles.sty", "{ABS_SRC_DIR}/sty/SetProfiles.sty"),
    ("press/config/6_headers.sty", "{ABS_SRC_DIR}/sty/SetHeaders.sty"),
    ("press/config/title.tex", "{ABS_SRC_DIR}/templates/title.tex"),
]

TEMPLATE_TNN = "{ABS_SRC_DIR}/templates/TNN.tex"


# -------------------- Utilidades --------------------
def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str, overwrite: bool = True):
    if path.exists() and not overwrite:
        return False
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
    return True


def safe_symlink(target: Path, link_path: Path):
    ensure_dir(link_path.parent)
    if link_path.is_symlink() or link_path.exists():
        if link_path.is_symlink():
            try:
                current = link_path.readlink()
            except OSError:
                current = None
            if current == target:
                return False
            try:
                link_path.unlink()
            except OSError:
                pass
        else:
            return False
    link_path.symlink_to(target)
    return True


def to_yaml_scalar(s: str) -> str:
    s = str(s)
    if any(c in s for c in '":#{}[]&*,!|>?@`') or s.strip() != s or " " in s:
        return '"' + s.replace('"', '\\"') + '"'
    return s


def dump_yaml(data: dict) -> str:
    lines = []

    def emit_kv(key, value, indent=0):
        pad = "  " * indent
        if isinstance(value, list):
            lines.append(f"{pad}{key}:")
            for item in value:
                lines.append(f"{pad}  - {to_yaml_scalar(item)}")
        elif isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            for k2, v2 in value.items():
                emit_kv(k2, v2, indent + 1)
        else:
            lines.append(f"{pad}{key}: {to_yaml_scalar(value)}")

    for k, v in data.items():
        emit_kv(k, v, 0)
    return "\n".join(lines) + "\n"


def load_yaml_simple(path: Path) -> dict:
    if not path.exists():
        return {}
    data = {}
    stack = [data]
    key_stack = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            level = indent // 2
            txt = line.strip()
            if txt.startswith("- "):
                val = txt[2:].strip()
                val = val.strip('"').replace('\\"', '"')
                if key_stack:
                    container = stack[-1]
                    if isinstance(container, list):
                        container.append(val)
                    else:
                        lst = container.setdefault(key_stack[-1], [])
                        lst.append(val)
                continue
            if ":" in txt:
                k, v = txt.split(":", 1)
                k = k.strip()
                v = v.strip()
                while len(stack) > level + 1:
                    stack.pop()
                    if key_stack:
                        key_stack.pop()
                cur = stack[-1]
                if not v:
                    new_map = {}
                    cur[k] = new_map
                    stack.append(new_map)
                    key_stack.append(k)
                else:
                    val = v.strip().strip('"').replace('\\"', '"')
                    cur[k] = val
    return data


def list_roots(abs_parent: Path):
    return sorted([p.name for p in abs_parent.iterdir() if p.is_dir()])


def ask_yes_no(prompt: str, default: bool) -> bool:
    suf = "[Y/n]" if default else "[y/N]"
    ans = click.prompt(
        f"{prompt} {suf}", default=("y" if default else "n"), show_default=False
    )
    return str(ans).strip().lower() in ("y", "yes", "s")


def create_press_config(target_dir: Path, abs_src_dir: Path):
    for rel, tmpl in CONFIG_FILES_ORDER:
        link = target_dir / rel
        target = Path(tmpl.format(ABS_SRC_DIR=str(abs_src_dir)))
        safe_symlink(target, link)
    biber = target_dir / "press/config/4_biber.sty"
    write_text(biber, "# \\addbibresources{bib/}\n", overwrite=True)


def create_topics(target_dir: Path, abs_src_dir: Path, n_topics: int):
    topics = []
    src = Path(TEMPLATE_TNN.format(ABS_SRC_DIR=str(abs_src_dir)))
    for i in range(1, n_topics + 1):
        tnum = f"T{i:02d}"
        dest = target_dir / f"press/{tnum}.tex"
        if src.exists():
            content = src.read_text(encoding="utf-8")
            write_text(dest, content, overwrite=False)
        else:
            write_text(dest, "", overwrite=False)
        topics.append(tnum)
    return topics


def add_general_links(target_dir: Path, abs_parent_dir: Path, roots: list):
    for root in roots:
        bib_link = target_dir / f"press/bib/{root}"
        img_link = target_dir / f"press/img/{root}"
        bib_target = abs_parent_dir / root / "bib"
        img_target = abs_parent_dir / root / "img"
        safe_symlink(bib_target, bib_link)
        safe_symlink(img_target, img_link)


def build_config_yaml_dict(
    target_dir: Path,
    abs_parent_dir: Path,
    abs_src_dir: Path,
    topics: list,
    bib_roots: list,
    img_roots: list,
    template_src: Path,
):
    return {
        "lecture_code": target_dir.name,
        "abs_project_dir": str(target_dir),
        "abs_parent_dir": str(abs_parent_dir),
        "abs_src_dir": str(abs_src_dir),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "version": "1.1",
        "template_source": str(template_src),
        "press": {
            "config_files": [
                "0_packages.sty",
                "1_loyaut.sty",
                "2_commands.sty",
                "3_units.sty",
                "4_biber.sty",
                "5_profiles.sty",
                "6_headers.sty",
                "title.tex",
            ]
        },
        "bib_roots": bib_roots,
        "img_roots": img_roots,
        "topics": topics,
    }


def write_config_yaml(target_dir: Path, data: dict):
    yaml_text = dump_yaml(data)
    write_text(target_dir / "config.yaml", yaml_text, overwrite=True)


# -------------------- CLI --------------------
@click.group(
    help="Herramienta para inicializar cursos (lect) y recrear enlaces desde config.yaml."
)
def cli():
    pass


@cli.command("init", help="Inicializa estructura de curso y genera config.yaml")
@click.argument("path_or_flag", required=False)
@click.option(
    "--parent", "abs_parent_dir", default=DEF_ABS_PARENT_DIR, show_default=True
)
@click.option("--src", "abs_src_dir", default=DEF_ABS_SRC_DIR, show_default=True)
@click.option("--topics", "n_topics", default=0, type=int, show_default=True)
@click.option(
    "--general",
    is_flag=True,
    help="Usa ABS_PARENT_DIR/00AA-Lectures y pide LECTURE_CODE.",
)
def init_cmd(path_or_flag, abs_parent_dir, abs_src_dir, n_topics, general):
    abs_parent = Path(abs_parent_dir).resolve()
    abs_src = Path(abs_src_dir).resolve()

    if general or (path_or_flag == "--general"):
        abs_project_dir = abs_parent / "00AA-Lectures"
        click.echo(f"Directorio de cursos generales: {abs_project_dir}")
        lec = click.prompt("Ingrese el LECTURE_CODE", type=str)
        target_dir = abs_project_dir / lec
    elif path_or_flag:
        p = Path(path_or_flag).expanduser().resolve()
        if not p.is_dir():
            raise click.ClickException(f"La ruta no existe: {p}")
        target_dir = p
    else:
        target_dir = Path.cwd()

    for sub in ("admin", "eval", "press/config", "press/bib", "press/img"):
        ensure_dir(target_dir / sub)

    create_press_config(target_dir, abs_src)
    topics = create_topics(target_dir, abs_src, n_topics) if n_topics > 0 else []

    bib_roots, img_roots = [], []
    if ask_yes_no("¿Desea agregar enlaces a temas generales?", default=True):
        if ask_yes_no(
            "¿Desea considerar el directorio actual como general?", default=False
        ):
            root_self = target_dir.name
            add_general_links(target_dir, abs_parent, [root_self])
            bib_roots.append(root_self)
            img_roots.append(root_self)
        dirs = list_roots(abs_parent)
        while True:
            click.echo(f"--- Temas en {abs_parent} ---")
            for i, name in enumerate(dirs, start=1):
                click.echo(f"{i:3d}) {name}")
            choice = click.prompt("Número del ROOT (o 'a' para abortar)", default="a")
            if str(choice).lower() == "a":
                break
            if not str(choice).isdigit():
                continue
            idx = int(choice) - 1
            if idx < 0 or idx >= len(dirs):
                continue
            root_chosen = dirs[idx]
            add_general_links(target_dir, abs_parent, [root_chosen])
            bib_roots.append(root_chosen)
            img_roots.append(root_chosen)
            if not ask_yes_no("¿Otro tema general?", default=True):
                break

    cfg = build_config_yaml_dict(
        target_dir,
        abs_parent,
        abs_src,
        topics,
        bib_roots,
        img_roots,
        Path(TEMPLATE_TNN.format(ABS_SRC_DIR=str(abs_src))),
    )
    write_config_yaml(target_dir, cfg)
    click.echo(f"Creado: {target_dir / 'config.yaml'}")


@cli.command("relink", help="Recrea symlinks usando config.yaml")
@click.argument("project_dir", required=False)
@click.option(
    "--parent", "abs_parent_dir", default=DEF_ABS_PARENT_DIR, show_default=True
)
@click.option("--src", "abs_src_dir", default=DEF_ABS_SRC_DIR, show_default=True)
def relink_cmd(project_dir, abs_parent_dir, abs_src_dir):
    target_dir = Path(project_dir).resolve() if project_dir else Path.cwd()
    cfg = load_yaml_simple(target_dir / "config.yaml")
    if not cfg:
        raise click.ClickException("No se pudo leer config.yaml")
    abs_parent = Path(cfg.get("abs_parent_dir", abs_parent_dir)).resolve()
    abs_src = Path(cfg.get("abs_src_dir", abs_src_dir)).resolve()

    create_press_config(target_dir, abs_src)
    roots = list(
        dict.fromkeys((cfg.get("bib_roots") or []) + (cfg.get("img_roots") or []))
    )
    add_general_links(target_dir, abs_parent, roots)
    click.echo("Symlinks recreados según config.yaml.")


if __name__ == "__main__":
    cli()
