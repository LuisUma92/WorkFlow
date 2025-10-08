from re import M
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
template_dir = Path(user_config_dir("mytex/templates", "LuisUmana"))
if not user_dir.is_dir():
    user_dir.mkdir()
book_list = user_dir / "books.json"
HEADER = ""
BOTTOM = ""
MAIN_TEMPLATE = "00AA.tex"
EXERCISE_TEMPLATE = "TNNE000.tex"
VERBOSE = 1

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
    log(f"{contents['name']}: readed", 3)
    with open(book_list, "r") as file:
        old_contents = json.load(file)
    old_contents["library"].append(contents)
    log(f"{contents['name']}: added to book_lias", 3)
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


def chapter_path(name, code, edition, ch):
    return f"{code}_{name.capitalize()}_{edition}/C{ch:02d}"


def file_upto_section(name, chNum, secNum):
    return f"{name}-C{chNum:02d}S{secNum}"


def current_file(path, fout, idx):
    return f"{path}/{fout}P{idx:03d}.tex"


def add_inputs(
    name,
    code,
    edition,
    chNum,
    secNum,
    start,
    end,
    main_path="\\FisicaDir/",
):
    chapter_relative_path = chapter_path(name, code, edition, chNum)
    path = f"{main_path}/{chapter_relative_path}"
    fout = file_upto_section(name, chNum, secNum)
    text = ""
    for idx in range(start, end + 1):
        thisF = current_file(path, fout, idx)
        text += "\t\\input{" + f"{thisF}" + "}\n"
    return text


def exercises_file_content(
    ch,
    idx,
    book,
    template_file_name=EXERCISE_TEMPLATE,
):
    with open(template_dir / template_file_name, "r") as f:
        exe_file = f.readlines()
    reference_info = (
        f"  \\exe[{ch}]" + "{" + str(idx) + "} %\\cite{" + str(book) + "}\n"
    )
    exe_file[1] = reference_info
    msn = "".join(exe_file)
    return msn


def init_head_bottom(template_file_name=MAIN_TEMPLATE):
    with open(template_dir / template_file_name, "r") as f:
        template_file = f.readlines()
    reading_head = True
    for line in template_file:
        if reading_head:
            global HEADER
            HEADER += line
            if line == "> contents":
                reading_head = False
        else:
            global BOTTOM
            BOTTOM += line


def create_solution_file(start, end, ch, sec, name, code, edition, output):
    chapter_relative_dir = chapter_path(name, code, edition, ch)
    path = output / chapter_relative_dir
    if not path.exists():
        os.makedirs(path)
    fout = file_upto_section(name, ch, sec)
    text = ""
    for idx in range(start, end + 1):
        thisF = current_file(path, fout, idx)
        msn = exercises_file_content(ch, idx, name)
        include_path = current_file(chapter_relative_dir, fout, idx)
        text += "\t\\input{" + include_path + "}\n"
        with open(path / thisF, "w") as file:
            file.write(msn)
    return text


def create_book_solutions_files(book, output_dir):
    main_text = ""
    for sec in book["distro"]:
        main_text += create_solution_file(
            sec[2],
            sec[3],
            sec[0],
            sec[1],
            book["name"],
            book["code"],
            book["edition"],
            output_dir,
        )
    init_head_bottom()
    outputfile_name = f"ER-{book['code']}-{book['name']}-{book['edition']}.tex"
    with open(output_dir / outputfile_name, "w") as file:
        file.write(HEADER)
        file.write(main_text)
        file.write(BOTTOM)
    log(f"Main wrote to: {outputfile_name}", 3)


@cli.command()
@click.option("--file", default=book_list)
@click.option("--name", default="none")
@click.option("--output", default=".")
@click.option("--verbose", default=1)
def init(file, name, output, verbose):
    global VERBOSE
    VERBOSE = verbose
    book = get_book(name)
    if not book:
        log(f"Requested book: {name}\n  is not in bib", 0)
        book = add_book(file)
        name = book["name"]

    output_dir = Path(output).expanduser()
    output_dir = output_dir.absolute()
    msn = f"""Configurarion:
    Exercise template: {EXERCISE_TEMPLATE}
    Main template: {MAIN_TEMPLATE}
    Output directory: {output_dir}
    Book to process: {book["code"]}-{book["name"]}-{book["edition"]}
    """
    log(msn, 3)
    create_book_solutions_files(book, output_dir)
    log("----- Done ------", 0)


def log(mns, verbose=2):
    if verbose < VERBOSE:
        print(mns)


if __name__ == "__main__":
    cli()
