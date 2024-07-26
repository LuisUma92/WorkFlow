import os
from pathlib import Path
from appdirs import user_config_dir

import logging
import click

import inkscapefigures as inkfig
from inkscapefigures.picker import pick
from ruamel.yaml import YAML

# Loading logger
logging.basicConfig(level='INFO')
log = logging.getLogger('nori')

# loading User config folder
user_dir = Path(user_config_dir("nori","LuisUmana"))
if not user_dir.is_dir():
    user_dir.mkdir()

# loading current root files
root_file = user_dir / 'root'
if not root_file.is_file():
    root_file.touch()

def getRoot():
    return [root for root in root_file.read_text().split('\n') if root != '']

def add_root(path):
    path = str(path)
    roots = getRoot()
    if path in roots:
        return None
    roots.append(path)
    root_file.write_text('\n'.join(roots))

# # definition of config
# config = user_dir / 'config.py'

# LaTeX citation format
def latex_citation(citeKey,note,verbatim=False):
    if verbatim:
        note = '``'+note+"''"
    note = note+rf"\cite{{{citeKey}}}"
    return note

# YAML loader
def open(name):
    if not name.exists():
        log.error("selected file: {} - don't exist".format(name))
        return {-1:0}

    yaml = YAML(typ='safe')
    data = yaml.load(name)
    # log.info('{} loaded'.format(name))
    log.debug(data)

    return data

# main definition
@click.group()
def cli():
    pass

@cli.command()
@click.argument(
    'root',
    default=os.getcwd(),
    type=click.Path(exists=False,file_okay=False,dir_okay=True)
)
def insert(root):
    '''
        Search and insert notes
    '''
    summDir =  Path(root).absolute()
    if not summDir.exists():
        summDir.mkdir()
    add_root(summDir)

    summaries = summDir.glob('*.yaml')
    summaries = sorted(summaries, key=lambda f: f.stat().st_mtime, reverse=True)

    files = [inkfig.main.beautify(f.stem) for f in summaries]
    _, summIdx, _ = pick(files)
    fileName = summaries[summIdx]
    yamlINFO = open(fileName)
    isOutPut = False
    recurrentDictionary = False
    currentDic = yamlINFO
    printThis = ''

    while not isOutPut:
        if recurrentDictionary:
            currentKeys = [*currentDic]
        else:
            currentKeys = [*yamlINFO]
        currentKeys.append('None')
        _,keyIdx,txt = pick(currentKeys)

        if recurrentDictionary:
            if type(currentDic[currentKeys[keyIdx]]) is str:
                printThis = latex_citation(yamlINFO['Bib'],currentDic[currentKeys[keyIdx]])
                isOutPut = True

        if currentKeys[keyIdx] == 'None':
            isOutPut = True
        elif currentKeys[keyIdx] == 'Authors':
            txt = ''
            for author in yamlINFO[currentKeys[keyIdx]]:
                txt += author[1]+' '+author[0]+', '
            printThis = latex_citation(yamlINFO['Bib'],txt)
            isOutPut = True
        elif type(currentDic[currentKeys[keyIdx]]) is dict:
            if not recurrentDictionary:
                currentDic = yamlINFO[currentKeys[keyIdx]]
                recurrentDictionary = True
            else:
                currentDic = currentDic[currentKeys[keyIdx]]
        elif type(currentDic[currentKeys[keyIdx]]) is list:
            _,_,txt = pick(currentDic[currentKeys[keyIdx]])
            printThis = latex_citation(yamlINFO['Bib'],txt)
            isOutPut = True
        elif currentKeys[keyIdx] == 'Conclusions':
            printThis = latex_citation(yamlINFO['Bib'],txt)
            isOutPut = True

    print(printThis)
    # return printThis

if __name__ == "__main__":
    cli()
