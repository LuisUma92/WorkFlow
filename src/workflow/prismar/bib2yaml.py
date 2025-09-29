import click
import os
import bibtexparser
from pathlib import Path
from .summary import Summary

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
    library = bibtexparser.parse_string(myBibFile.read_text())

    for entry in library.entries:
        summaryName = entry.key +  "-"
        for field in entry.fields:
            if field.key == "title":
                summaryName += field.value
        summaryFile = Summary(name = summaryName, path = str(workPath / "res"))
        summaryFile.bib = entry.key
        for field in entry.fields:
            if field.key == "title":
                summaryFile.title = field.value
            if field.key == "author":
                authors = field.value.split(" and ")
                for author in authors:
                    if len(author.split(", ")) > 1:
                        summaryFile.author.append(author.split(", "))
                    else:
                        summaryFile.author.append([author," "])

        summaryFile.save()

def clean_bib(bibText):
    lines = [line for line in bibText.split("\n") if line != '']
    lines = [line for line in lines if line[0] != "%"]
    return ''.join(lines)

if __name__ == "__main__":
    cli()
