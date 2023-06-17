import os
from pathlib import Path
from appdirs import user_config_dir
import subprocess
import click

#loading User config folder
user_dir = Path(user_config_dir("cleta","LuisUmana"))
if not user_dir.is_dir():
    user_dir.mkdir()

#loading current root files
clean_list = user_dir / 'Clean_Extensions'
if not clean_list.is_file():
    clean_list.touch()
    clean_list.write_text('\n'.join(['*.aux','*.bbl','*.bcf','*.blg','*.fdb_latexmk','*.fls','*.log','*.out','*.run.xml','*.synctex.gz','*.xdv']))

def getExt():
    return [ext for ext in clean_list.read_text().split('\n') if ext != '']



@click.group()
def cli():
    pass

@cli.command(help = 'write file extension without dot')
@click.argument(
    'ext',
    type=str
)
def add(ext):
    ext = str('*.'+ext)
    file = getExt()
    if ext in file:
        return None
    file.append(ext)
    clean_list.write_text('\n'.join(file))

@cli.command()
@click.argument(
    'path',
    default=Path(os.getcwd()).absolute(),
    type=click.Path(exists=False,file_okay=False,dir_okay=True)
)
def clean(path):
    toClean = getExt()
    for term in toClean:
        # print(Path(path,term))
        subprocess.run('rm '+str(path / term),shell=True )

if __name__ == '__main__':
    cli()
