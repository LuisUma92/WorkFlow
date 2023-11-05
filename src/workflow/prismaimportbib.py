from datetime import datetime
import bibtexparser
import click
import workflow.pyprisma as wfp

@click.command()
@click.option("--filename",help="File Name: database_keywords.bib")
@click.option("--verbose",default=1,help="Set verbose level")
def cli(filename,verbose):
    '''Parse and add all entries on .bib file.\nFile Name: database_keywords.bib'''

    '''Initialize connection'''
    wfp.init(verbose)

    if wfp.get_verbose() >= 1: print("-"*60+f"\n>> Import bib file:\n{filename}")
    with open(filename) as file:
        library = bibtexparser.load(file)
    for entry in library.entries:
        current_entry = {}
        author_list = []
        if "ENTRYTYPE" in entry:
            current_entry["entry_type"] = entry["ENTRYTYPE"]
        if "ID" in entry:
            current_entry["bibkey"] = entry["ID"]
        if "journal" in entry:
            current_entry["journaltitle"] = entry["journal"]
        if "date" in entry:
           current_entry["publication_date"] = entry["date"]
        if "note" in entry:
           current_entry["notes"] = entry["note"]
        if "volume" in entry:
            current_entry["issue_volume"] = entry["volume"]
        if "number" in entry:
            current_entry["issue_number"] = entry["number"]
        for key in wfp.structure["bib_entries"].keys():
            if key == "url":
                if "url" in entry:
                    current_entry["url"] = entry["url"]
                else:
                    current_entry["url"] = "https://duckduckgo.com/?q="+entry["title"].replace(" ","+")
            elif key in entry:
                current_entry[key] = entry[key]
        current_entry["database_name"] = filename.split("_")[0]
        current_entry["accessed"] = datetime.today().strftime("%Y-%m-%d")
        if "author" in entry:
            author_list = wfp.order_authors(entry["author"])

        if wfp.get_verbose() >= 2: print(current_entry,author_list)
        if wfp.get_verbose() >= 3: input("-"*60+"\n"+"-"*60)
        wfp.add_reference(current_entry,author_list)
        wfp.add_keywords(filename.split("_")[1][:-4])
        wfp.init_review_table(current_entry["title"],filename.split("_")[1][:-4])
        if wfp.get_verbose() >= 1: print("DONE !\n"+'='*60)

def read_article():
    pass

def read_incollection():
    pass

if __name__ == "__main__":
    cli()
