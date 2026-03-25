from datetime import datetime
from decimal import Decimal
from django.db import IntegrityError
import bibtexparser
from prismadb.models import Author, Bib_entries, Bib_author, Isn_list
from prismadb.models import Author_type
from django.db.models import IntegerField, fields


def order_authors(author_string):
    '''Create a list of dictionaries wit the structure
    {"first_name":name,"last_name":last_name}'''
    # if __verbose >= 1: print("-"*60+f"\n>> Creating author_list")
    author_list = []
    temp_list = author_string.split(" and ")
    # if __verbose >= 4: print(temp_list)
    for author in temp_list:
        # if __verbose >= 3: print(author,type(author))
        if "{" in author:
            author = author.replace("{","")
            author = author.replace("}","")
        # if "'" in author:
        #     author = author.replace("'","\\'")
        if ", " in author:
            info = author.split(", ")
            author_list.append({"first_name":info[1],"last_name":info[0]})
        else:
            if "." in author:
                end_first_name = author.rfind('.')
                author_list.append({
                                    "first_name":author[:end_first_name+1],
                                    "last_name":author[end_first_name+2:]
                })
            else:
                info = author.split(" ",1)
                author_list.append({"first_name":info[0],"last_name":info[1]})
    return author_list


def safe_type(mod, key, data):
    mod_filds = mod._meta.fields
    for mod_entry in mod_filds:
        if mod_entry.name == key:
            if isinstance(mod_entry, IntegerField):
                if data == "":
                    data = 0
                obj = int(data)
            elif isinstance(mod_entry, Decimal):
                if data == "":
                    data = 0.
                obj = float(data)
            elif isinstance(mod_entry, fields.DateTimeField):
                if data == "":
                    data = datetime(1000, 1, 1)
                obj = datetime.strptime(str(data), "%Y-%m-%d")
            else:
                obj = data
    return obj


def bib2db(entry, filename):
    bib_keys = [field.name for field in Bib_entries._meta.fields]
    bib_keys.remove("id")
    bib_keys.remove("database_name")
    bib_keys.remove("accessed")
    isn_elements = [isn.id_isn for isn in Isn_list.objects.all()]
    current_entry = {}
    if "ENTRYTYPE" in entry:
        this_key = "entry_type"
        current_entry[this_key] = entry["ENTRYTYPE"]
        bib_keys.remove(this_key)
    if "ID" in entry:
        this_key = "bibkey"
        current_entry[this_key] = entry["ID"]
        bib_keys.remove(this_key)
    if "journal" in entry:
        this_key = "journaltitle"
        current_entry[this_key] = entry["journal"]
        bib_keys.remove(this_key)
    if "date" in entry:
        this_key = "publication_date"
        current_entry[this_key] = entry["date"]
        bib_keys.remove(this_key)
    if "note" in entry:
        this_key = "notes"
        current_entry[this_key] = entry["note"]
        bib_keys.remove(this_key)
    if "volume" in entry:
        this_key = "issue_volume"
        current_entry[this_key] = entry["volume"]
        bib_keys.remove(this_key)
    if "number" in entry:
        this_key = "issue_number"
        current_entry[this_key] = entry["number"]
        bib_keys.remove(this_key)
    if "file" in entry:
        this_key = "file_path"
        current_entry[this_key] = entry["file"]
        bib_keys.remove(this_key)
    if "abstract" in entry:
        this_key = "abstract_text"
        current_entry[this_key] = entry["abstract"]
        bib_keys.remove(this_key)
    for key in bib_keys:
        if key == "url":
            if "url" in entry:
                current_entry["url"] = entry["url"]
            else:
                current_entry["url"] = "https://duckduckgo.com/?q="+entry["title"].replace(" ","+")
        elif key == "isn_type" or key == "isn":
            for isn_type in isn_elements:
                if isn_type in entry:
                    current_entry["isn"] = entry[isn_type]
                    current_entry["isn_type"] = Isn_list.objects.get(id_isn = isn_type)
        elif key in entry:
            current_entry[key] = safe_type(Bib_entries, key, entry[key])
        # else:
        #     current_entry[key] = safe_type(Bib_entries, key, "")
    current_entry["database_name"] = filename.split("_")[0]
    current_entry["accessed"] = datetime.today().strftime("%Y-%m-%d")
    return current_entry


def load_bib_file(filename):
    with open(filename,'r') as file:
        library = bibtexparser.load(file)
    author_type_elements = [author_type.type_of_author for author_type in Author_type.objects.all()]
    all_bib_entries = []
    for entry in library.entries:
        current_entry = bib2db(entry,filename)
        print(current_entry)
        try:
            Bib_entries.objects.create(**current_entry)
        except IntegrityError as e:
            print(f'Duplicate at article: {e}')
        author_list = {}
        for person_roll in author_type_elements:
            if person_roll in entry:
                author_list[person_roll] = order_authors(entry[person_roll])
        if len(author_list) == 0:
            if "journaltitle" in current_entry:
                author_list["author"] = [{"first_name":"Editorial","last_name":current_entry["journaltitle"],"affiliation":filename.split("_")[0]}]
            elif "publisher" in current_entry:
                author_list["author"] = [{"first_name":"Editorial","last_name":current_entry["publisher"],"affiliation":filename.split("_")[0]}]
            elif "institution" in current_entry:
                author_list["author"] = [{"first_name":"Editorial","last_name":current_entry["institution"],"affiliation":filename.split("_")[0]}]
            elif "organization" in current_entry:
                author_list["author"] = [{"first_name":"Editorial","last_name":current_entry["organization"],"affiliation":filename.split("_")[0]}]

        for roll,in_roll_list in author_list.items():
            first = True
            for this_author in in_roll_list:
                this_author_information = {}
                try:
                    Author.objects.create(**this_author)
                except IntegrityError as e:
                    print(f'Duplicate author: {e}')

                if first:
                    this_author_information['first_author'] = True
                    first = False
                this_author_information['id_article'] = Bib_entries.objects.get(bibkey=entry["ID"])
                this_author_information['id_author']= Author.objects.get(first_name=this_author['first_name'],last_name=this_author['last_name'])
                this_author_information['category'] = Author_type.objects.get(type_of_author=roll)
                try:
                    Bib_author.objects.create(**this_author_information)
                except IntegrityError as e:
                    print(f'Duplicate bib-author: {e}')


        all_bib_entries.append({**current_entry,**author_list})
    return all_bib_entries
