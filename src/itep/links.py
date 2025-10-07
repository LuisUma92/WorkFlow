from itep.structure import MetaData, ConfigType
from itep.utils import load_yaml
import click
from pathlib import Path
from datetime import datetime

# --- Constantes por defecto ---
DEF_ABS_PARENT_DIR = "/home/luis/Documents/01-U/00-Fisica"
DEF_ABS_SRC_DIR = "/home/luis/.config/mytex"

# -------------------- Utilidades --------------------


def safe_symlink(target: Path, link_path: Path):
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


def create_config_links(
    target_dir: Path,
    abs_src_dir: Path,
    links_relations: dict,
    config_type: ConfigType = ConfigType.BASE,
):
    if config_type != ConfigType.BASE:
        target_dir = target_dir / config_type.value
    for rel, src_file in links_relations:
        link = target_dir / "config" / rel
        target = abs_src_dir / src_file
        safe_symlink(target, link)


# -------------------- CLI --------------------
@click.group(help="Herramienta para recrear enlaces desde config.yaml.")
def cli():
    pass


@cli.command("relink", help="Recrea symlinks usando config.yaml")
@click.argument("project_dir", required=False)
@click.option(
    "--parent",
    "abs_parent_dir",
    default=DEF_ABS_PARENT_DIR,
    show_default=True,
)
@click.option(
    "--src",
    "abs_src_dir",
    default=DEF_ABS_SRC_DIR,
    show_default=True,
)
def relink_cmd(project_dir, abs_parent_dir, abs_src_dir):
    target_dir = Path(project_dir).resolve() if project_dir else Path.cwd()
    cfg = load_yaml(target_dir / "config.yaml")
    if not cfg:
        raise click.ClickException("No se pudo leer config.yaml")
    data = MetaData(cfg.get("data"))
    abs_project = Path(data.get("abs_project_dir", abs_parent_dir)).resolve()
    abs_src = Path(data.get("abs_src_dir", abs_src_dir)).resolve()

    for config_type in ConfigType:
        if config_type.value in cfg.keys():
            relations = cfg[config_type.value]["config_files"]
            create_config_links(
                abs_project,
                abs_src,
                relations,
                config_type,
            )
    click.echo("Symlinks recreados según config.yaml.")


if __name__ == "__main__":
    cli()
