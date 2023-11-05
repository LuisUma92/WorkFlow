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
        if "institution" in entry:
            current_entry["institution"] = entry["institution"]
        if "organization" in entry:
            current_entry["organization"] = entry["institution"]
        if "publisher" in entry:
            current_entry["publisher"] = entry["publisher"]
        if "title" in entry:
            current_entry["title"] = entry["title"]
        if "journal" in entry:
            current_entry["journaltitle"] = entry["journal"]
        if "journaltitle" in entry:
            current_entry["journaltitle"] = entry[""]
        if "indextitle" in entry:
           current_entry["indextitle"] = entry["indextitle"]
        if "booktitle" in entry:
           current_entry["booktitle"] = entry["booktitle"]
        if "maintitle" in entry:
           current_entry["maintitle"] = entry["maintitle"]
        if "issuetitle" in entry:
           current_entry["issuetitle"] = entry["issuetitle"]
        if "eventtitle" in entry:
           current_entry["eventtitle"] = entry["eventtitle"]
        if "reprinttitle" in entry:
           current_entry["reprinttitle"] = entry["reprinttitle"]
        if "series" in entry:
           current_entry["series"] = entry["series"]
        if "part" in entry:
           current_entry["part"] = entry["part"]
        if "issue" in entry:
           current_entry["issue"] = entry["issue"]
        if "volumes" in entry:
           current_entry["volumes"] = entry["volumes"]
        if "edition" in entry:
           current_entry["edition"] = entry["edition"]
        if "version" in entry:
           current_entry["version"] = entry["version"]
        if "pubstate" in entry:
           current_entry["pubstate"] = entry["pubstate"]
        if "pages" in entry:
           current_entry["pages"] = entry["pages"]
        if "pagetotal" in entry:
           current_entry["pagetotal"] = entry["pagetotal"]
        if "pagination" in entry:
           current_entry["pagination"] = entry["pagination"]
        if "date" in entry:
           current_entry["publication_date"] = entry["date"]
        if "eventdate" in entry:
           current_entry["eventdate"] = entry["eventdate"]
        if "urldate" in entry:
           current_entry["urldate"] = entry["urldate"]
        if "location" in entry:
           current_entry["location"] = entry["location"]
        if "venue" in entry:
           current_entry["venue"] = entry["venue"]
        if "eid" in entry:
           current_entry["eid"] = entry["eid"]
        if "eprint" in entry:
           current_entry["eprint"] = entry["eprint"]
        if "eprinttype" in entry:
           current_entry["eprinttype"] = entry["eprinttype"]
        if "addendum" in entry:
           current_entry["addendum"] = entry["addendum"]
        if "howpublished" in entry:
           current_entry["howpublished"] = entry["howpublished"]
        if "language" in entry:
           current_entry["language"] = entry["language"]
        if "" in entry:
           current_entry["isn"] = entry[""]
        if "" in entry:
           current_entry["isn_type"] = entry[""]
        if "" in entry:
           current_entry["addendum"] = entry[""]
        if "note" in entry:
           current_entry["notes"] = entry["note"]
        if "" in entry:
           current_entry["howpublished"] = entry[""]
        if "" in entry:
           current_entry["language"] = entry[""]
        if "" in entry:
           current_entry["isn"] = entry[""]
        if "" in entry:
           current_entry["isn_type"] = entry[""]
        if "volume" in entry:
            current_entry["issue_volume"] = entry["volume"]
        if "number" in entry:
            current_entry["issue_number"] = entry["number"]
        if "year" in entry:
            current_entry["year"] = entry["year"]
        if "pages" in entry:
            current_entry["pages"] = entry["pages"]
        current_entry["database_name"] = filename.split("_")[0]
        current_entry["accessed"] = datetime.today().strftime("%Y-%m-%d")
        if "url" in entry:
            current_entry["url"] = entry["url"]
        else:
            current_entry["url"] = "https://duckduckgo.com/?q="+entry["title"].replace(" ","+")
        if "doi" in entry:
            current_entry["doi"] = entry["doi"]
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
