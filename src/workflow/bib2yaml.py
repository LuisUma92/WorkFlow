import click
import os
from pathlib import Path

workPath = Path(os.getcwd())

@click.command()
@click.option("--bib", default="this", help=".bib file name")
def cli(bib):
    if bib[-4:] == ".bib":
        myBibFile = workPath / bib
    else:
        myBibFile = workPath / f"{bib}.bib"
    if not myBibFile.is_file():
        print(f"Can't find file: {myBibFile}")
        return 0
    entries = clean_bib(myBibFile.read_text()).split("@")

    for entry in entries[1:]:
        print(read_bib(entry))

def read_bib(bibEntry):
    if len(bibEntry.split("{")) < 2:
        print("Invalid entry")
        return None
    tags = {}
    start_position = bibEntry.find("{")
    stop_position = bibEntry.rfind("}")
    if "\t" in bibEntry:
        tag_list = bibEntry[start_position+1:stop_position].split(",\t")
    else:
        tag_list = bibEntry[start_position+1:stop_position].split(",  ")
    for tag in tag_list[1:]:
        key = tag.split("=")
        tags[key[0]] = key[1]
    citation_key = tag_list[0]
    entry_type = bibEntry[:start_position]
    return tags, citation_key, entry_type

def clean_bib(bibText):
    lines = [line for line in bibText.split("\n") if line != '']
    lines = [line for line in lines if line[0] != "%"]
    return ''.join(lines)

if __name__ == "__main__":
    cli()
