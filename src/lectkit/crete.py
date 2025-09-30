import click
import subprocess
from pathlib import Path
from appdirs import user_config_dir
import os
import json


@click.group()
def cli():
    pass


# loading User config folder
user_dir = Path(user_config_dir("crete", "LuisUmana"))
if not user_dir.is_dir():
    user_dir.mkdir()
book_list = user_dir / "books.json"


# loading current root files
@cli.command()
def init_books():
    if not book_list.is_file():
        book_list.touch()
        book_list.write_text(json.dumps({"library": []}))


@cli.command()
@click.argument("bookinfo")
def add_book(bookinfo):
    with open(bookinfo, "r") as file:
        contents = json.load(file)
    with open(book_list, "r") as file:
        old_contents = json.load(file)
    old_contents["library"].append(contents)
    with open(book_list, "w") as file:
        json.dump(old_contents, file)
    return contents


def get_book(book):
    with open(book_list, "r") as file:
        library = json.load(file)
    for item in library["library"]:
        if item["name"] == book:
            return item
    return {}


def chapter_path(name, code, ch):
    return f"er-{code}-{name}/530-{name.capitalize()}-C{ch:02d}"


def file_upto_section(name, chNum, secNum):
    return f"{name}-C{chNum:02d}S{secNum}"


def current_file(path, fout, idx):
    thisF = path / "".join([fout, "P{:03d}.tex".format(idx)])
    return thisF


HEADER = """\\documentclass[12pt,
  notitlepage,
  % openany,
  twoside,
  % twocolumn,
  ]{article}
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%==<Definición de comandos propios>==================
\\newcommand{\\AAfolder}{/home/luis/.config/mytex}
\\usepackage{\\AAfolder/sty/SetFormat}
\\newcommand{\\AMfolder}{/home/luis/Documents/01-U/00-00AA-Apuntes}
\\usepackage{\\AAfolder/sty/ColorsLight}
\\usepackage{\\AAfolder/sty/SetSymbols}
\\addbibresource{\\AAfolder/bib/Biblioteca.bib}
\\usepackage{\\AAfolder/sty/HW-header}
\\setbool{solutions}{true}
\\newboolean{MC}
\\setbool{MC}{true}
\\graphicspath{{\\AMfolder/img/530_S439fi14-Sears}}
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%==<Inicia documento>================================
\\begin{document}
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% \\maketitle
% \\tableofcontents
% \\listoffigures
% \\listoftables
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
"""

BOTTOM = """
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%==<Bibliografía>====================================
%		Para la bibliografía se usa el gestor de
%	referencias bibtex. Toda la información de las
%	referencias se pone en un archivo aparte con la
%	terminación .bib y se agrega aquí
%
% \\printbibliography
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%==<Apéndice>========================================
%		Se puede crear apéndices que luego se pueden
%	referenciar con la etiqueta
% \\appendix
% \\section{Figuras \\label{app:fig}}
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%==<Index>===========================================
% \\printindex
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%==<Fin del documento>===============================
\\end{document}
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%"""


def add_inputs(name, code, chNum, secNum, start, end, main_path="\\AMfolder/"):
    CHPATH = chapter_path(name, code, chNum)
    path = Path(main_path + CHPATH)
    fout = file_upto_section(name, chNum, secNum)
    text = ""
    for idx in range(start, end + 1):
        thisF = path / "".join([fout, "P{:03d}.tex".format(idx)])
        text += "\t\\input{" + f"{thisF}" + "}\n"
    return text


def exercises_file_content(ch, idx, book):
    msn = "\\ifthenelse{\\boolean{MC}}{\n\\exa["
    msn += str(ch) + "]{" + str(idx) + "} %\\cite{" + str(book)
    msn += "}\n}{\\exa{}}\n.\n\n\\begin{enumerate}[a)]\n\\item ."
    msn += "\n\\end{enumerate}\n\n\\ifthenelse{\\boolean{solutions}}{"
    msn += "\n  \\paragraph{Solución:}\n  \\begin{enumerate}[a)]"
    msn += "\n    \\item .\n  Datos:\n  \\[\\begin{array}{l}"
    msn += "\n  \\end{array}\\] \n  \\end{enumerate} \n}{}"
    return msn


# @cli.command()
# @click.argument(
#     'start',
#     default=1,
#     type=int
# )
# @click.argument(
#     'end',
#     default=1,
#     type=int
# )
# @click.argument(
#     'ch',
#     default=1,
#     type=int
# )
# @click.argument(
#     'sec',
#     default='01',
#     type=str
# )
# @click.argument(
#     'name',
#     type=str
# )
# @click.argument(
#     'code',
#     type=str
# )
def create_solution_file(start, end, ch, sec, name, code):
    CHPATH = chapter_path(name, code, ch)
    path = Path(f"./{CHPATH}").absolute()
    # log(f'''
    # Se está trabajando en:
    # {path}''', verbose)
    if not path.exists():
        os.makedirs(path)
    fout = file_upto_section(name, ch, sec)
    for idx in range(start, end + 1):
        thisF = current_file(path, fout, idx)
        subprocess.run(["touch", thisF])
        msn = exercises_file_content(ch, idx, name)
        lines = msn.split("\n")
        for line in lines:
            os.system('echo "' + line + '" >> ' + str(thisF))
    pass


def create_book_solutions_files(book):
    main_text = ""
    for sec in book["distro"]:
        create_solution_file(sec[2], sec[3], sec[0], sec[1], book["name"], book["code"])
        main_text += add_inputs(
            book["name"], book["code"], sec[0], sec[1], sec[2], sec[3]
        )
    soluPath = chapter_path(book["name"], book["code"], "00")
    soluPath = soluPath
    with open(f"ER-{book['code']}.tex", "w") as file:
        file.write(HEADER)
        file.write(main_text)
        file.write(BOTTOM)


@cli.command()
@click.option("--file", default=book_list)
@click.option("--name", default="none")
def init(file, name):
    book = get_book(name)
    if not book:
        print("Requested book is not in bib")
        book = add_book(file)
        name = book["name"]
    create_book_solutions_files(book)


def log(mns, verbose=2):
    if verbose > 1:
        print(mns)


if __name__ == "__main__":
    cli()
