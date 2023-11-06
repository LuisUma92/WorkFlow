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
        if "file" in entry:
            current_entry["file_path"] = entry["file"]
        for key in wfp.structure["bib_entries"].keys():
            if key == "url":
                if "url" in entry:
                    current_entry["url"] = entry["url"]
                else:
                    current_entry["url"] = "https://duckduckgo.com/?q="+entry["title"].replace(" ","+")
            elif key == "isn":
                for isn_type in wfp.structure["isn_list"]["id_isn"]:
                    if isn_type in entry:
                        current_entry["isn"] = entry[isn_type]
                        current_entry["isn_type"] = isn_type
            elif key in entry:
                current_entry[key] = entry[key]
        current_entry["database_name"] = filename.split("_")[0]
        current_entry["accessed"] = datetime.today().strftime("%Y-%m-%d")

        author_list = {}
        for person_roll in wfp.structure["author_type"]["id_author_type"]:
            if person_roll in entry:
                author_list[person_roll] = wfp.order_authors(entry[person_roll])
        if len(author_list) == 0:
            if "journaltitle" in current_entry:
                author_list["author"] = [{"first_name":"Editorial","last_name":current_entry["journaltitle"],"affiliation":filename.split("_")[0]}]
            elif "publisher" in current_entry:
                author_list["author"] = [{"first_name":"Editorial","last_name":current_entry["publisher"],"affiliation":filename.split("_")[0]}]
            elif "institution" in current_entry:
                author_list["author"] = [{"first_name":"Editorial","last_name":current_entry["institution"],"affiliation":filename.split("_")[0]}]
            elif "organization" in current_entry:
                author_list["author"] = [{"first_name":"Editorial","last_name":current_entry["organization"],"affiliation":filename.split("_")[0]}]
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
