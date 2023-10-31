import bibtexparser
import click

@click.group()
def cli():
    pass

@cli.command()
@click.option("--base_name")
@click.option("--amount", default=1)
def merge(base_name, amount):
    temp_buffer = ""
    for i in range(amount):
        with open(base_name+f"({i+1}).bib","r") as file:
            temp_buffer += file.read()
            temp_buffer += "\n"

    with open(base_name+".bib","w") as file:
        file.write(temp_buffer)

if __name__ == "__main__":
    cli()
