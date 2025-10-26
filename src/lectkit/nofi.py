from pathlib import Path
from typing import List
import click


def save_to_file(
    currentDir: Path,
    newfilename: str,
    subcontent: List[str],
    save_type: str = "w",
):
    # Need to check if al the path to newfilename exists and if it doesn't
    # then create it
    IGNORE_FLAG = "END"
    if IGNORE_FLAG != newfilename.split()[-1]:
        parent = (currentDir / newfilename).parent

        if not parent.exists():
            print("Creating {}".format(parent))
            parent.mkdir(parents=True, exist_ok=True)

        # Create the newfilename with the subcontent
        try:
            with open(currentDir / newfilename, save_type) as file:
                for line in subcontent:
                    file.write(line)
        except IOError:
            print("An error occurred while trying to write")
            print(f"to the file {newfilename}.")
            return 2


@click.command()
@click.option(
    "-fi",
    "--filename",
    default="./NewNote.tex",
    help="Name of file with notes",
)
@click.option(
    "-mf",
    "--mainfile",
    default="NotesToImput.tex",
    help="Name of the main file where to import notes",
)
@click.option(
    "-cd",
    "--currentdir",
    default="",
    help="Path to working directory",
)
def cli(filename, mainfile, currentdir):
    currentdir = Path(currentdir).expanduser() if currentdir else Path().cwd()
    FLAG = "%>"
    READING_FLAG = False
    subcontent = []
    newfilename = ""
    toImport = []
    # opens file
    try:
        with open(currentdir / filename, "r") as file:
            content = [line for line in file]
        print(f"From {filename} where readded {len(content)} lines")
    except FileNotFoundError:
        print(f"The file {filename} does not exist.")
        return 1
    except IOError:
        print(f"An error occurred while trying to read the file {filename}.")
        return 1

    # Search for flag and append lines
    for line in content:
        if FLAG in line:
            if READING_FLAG:
                save_to_file(currentdir, newfilename, subcontent)
                subcontent = []
            else:
                READING_FLAG = True

            newfilename = line[2:-1]
            if "END" not in newfilename:
                toImport.append("".join(["  \\input{./", newfilename, "}\n"]))
        else:
            if READING_FLAG:
                subcontent.append(line)

    save_to_file(currentdir, newfilename, subcontent)
    save_to_file(currentdir, mainfile, toImport, save_type="a")


if __name__ == "__main__":
    cli()
