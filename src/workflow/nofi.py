import os
from pathlib import Path
import click


def save_to_file(newfilename, subcontent, save_type="w"):
    # Need to check if al the path to newfilename exists and if it doesn't
    # then create it
    currentDir = "."
    for dir in newfilename.split('/')[:-1]:
        currentDir = "/".join([currentDir, dir])
        if not Path(currentDir).exists():
            os.mkdir(Path(currentDir))

    # Create the newfilename with the subcontent
    try:
        with open(newfilename, save_type) as file:
            for line in subcontent:
                file.write(line)
    except IOError:
        print("An error occurred while trying to write")
        print(f"to the file {newfilename}.")
        return 2


@click.command()
@click.option(
        '--filename',
        default='NewNote.tex',
        help='Name of file with notes'
        )
@click.option(
        '--mainfile',
        default='main.tex',
        help='Name of the main file where to import notes'
        )
def cli(filename, mainfile):
    FLAG = '%>'
    READING_FLAG = False
    subcontent = []
    newfilename = ''
    toImport = []
    # opens file
    try:
        with open(filename, 'r') as file:
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
                save_to_file(newfilename, subcontent)
                subcontent = []
            else:
                READING_FLAG = True

            newfilename = line[2:-1]
            toImport.append("".join(["  \\input{./", newfilename, "}\n"]))
        else:
            subcontent.append(line)

    save_to_file(newfilename, subcontent)
    save_to_file(mainfile, toImport, save_type="a")


if __name__ == '__main__':
    cli()
