# from re import split
from pickle import TRUE
from re import split
from threading import current_thread
from inkscapefigures.main import re
import mysql.connector as sql
# import mariadb as sql
from cryptography.fernet import Fernet
import click
import getpass
import bibtexparser
from datetime import datetime

structure = {
    "bib_entries" : {
        # "id": "INT",
        "entrie_type":"VARCHAR(100)",
        "bibkey":"CHAR(100)",
        "title":"VARCHAR(250)",
        "journaltitle":"VARCHAR(100),",
        "issue_volume":"INT",
        "issue_number":"INT",
        "year":"YEAR",
        "pages":"CHAR(10)",
        "database_name":"\tCHAR(20)\nSpecify the information sources (e.g. databases, registers) used to identify studies.",
        "accessed":"\tDATE\nSpecify the information used to identify the date when last searched.",
        "url":"\tVARCHAR(21844) CHARACTER SET utf8\nProvide especific URL to access.",
        "doi":"\tVARCHAR(21844) CHARACTER SET utf8\nProvide especific DOI to access.",
        "keyword":"\tCHAR(40)\nProvide papers's assigned kewords"
    },
    "author" : {
        # "id_author":"INT",
        "first_name":"CHAR(20)",
        "last_name":"CHAR(20)",
        "affiliation":"CHAR(100)"
    },
    "bib_author" : {
        "id_author":"author.id_author",
        "id":"bib_entries.id",
        "first_author":"BOOLEAN",
    },
    "bib_references" : {
        "article":"bib_entrie.bib",
        "reference":"bib_entrie.bib",
    },
    "keyword" : {
        # "key_id":"INT",
        "keyword_list":"VARCHAR(500) CHARACTER SET utf8\nSearch keywords used"
    },
    "reviewed" : {
        "key_id":"INT UNSIGNED\nREFERENCES keyword (key_id)",
        "article_id":"INT UNSIGNED\nREFERENCES bib_entries (id)",
        "retrived":"\tBOOLEAN\nFlag 1 if paper was retrived",
        "included":"\tBOOLEAN\nFlag 1 if paper was included",
    },
    "abstract" : {
        # "id":"bib_entries.id",
        "objectives":"\tVARCHAR(21844) CHARACTER SET utf8,\nProvide an explicit statement of the main objective(s) or question(s) the review addresses.",
        "rationale":"\tVARCHAR(21844) CHARACTER SET utf8\nDescribe the rationale for the review in the context of existing knowledge.",
        "eligibility_criteria":"\tVARCHAR(21844) CHARACTER SET utf8\nSpecify the inclusion and exclusion criteria for the review.",
        "methods_synthesis":"\tVARCHAR(21844) CHARACTER SET utf8\nSpecify the methods used.",
        "results_synthesis":"\tVARCHAR(21844) CHARACTER SET utf8\nPresent results for main outcomes, preferably indicating the number of included studies and participants for each. If meta-analysis was done, report the summary estimate and confidence/credible interval. If comparing groups, indicate the direction of the effect (i.e. which group is favoured).",
    },
        # "abs_id":"INT UNSIGNED AUTO_INCREMENT",
}
'''Structure of data base'''
#:
#:

__usr = ''
__passwd = ''
__this_host = 'localhost'
__this_database = 'prisma7be'
__verbose = 3

@click.group()
@click.option('--verbose',default=9)
def cli(verbose):
    if verbose < 9:
        global __verbose
        __verbose = verbose
    set_connection()
    pass

# @cli.command()
# def add_complete_register():
#     i = 0
#     for item in itemList.keys():
#         desc = itemDescription[i]
#         confirmed = False
#         while(not confirmed):
#             print("="*60+f"\n>>\t{item}\n")
#             temp = input(f"\t\tDescrición: \n{desc}\n\n Ingrese información\n")
#             test = input("Continuar con el siguiente registro y/n\n")
#             if test == "y":
#                 itemList[item] = temp
#                 confirmed = True
#         i += 1
#     print(itemList)

def get_id(identity,table,columns=[],values=[]):
    '''Test the existence of any entry with same {value} at {table}.{column} as provided. If it exists it returns -1'''
    if __verbose > 1: print("-"*60+f"\n>> Getting id {identity} FROM {table}")
    if len(columns) != len(values):
        print(f"ERROR:\n\nThere is a mismatch between columns and values\n\tColumns:{columns}\n\tValues:{values}")
        return -1
    msn= f"SELECT {identity} FROM {table} WHERE "
    for i in range(len(columns)):
        if i > 0: msn += " AND "
        column = columns[i]
        value = values[i]
        msn += f"{column} = '{value}'"
    msn += ";"
    test = comunicate_db(msn,query=True)
    if len(test) > 0:
        print(f"\n\n{table}.{columns}='{values}' already exists\nWith {identity}: {test[0][0]}")
        try:
            output = int(test[0][0])
        except ValueError:
            print(f"\nIsn't a integer")
            return -2
        else:
            return output
    else:
        print(f"ERROR:\n\nThere is no entry at {table}.{columns},\nWith value '{values}' ")
        return 0

def manually_add_register(this_items):
    if __verbose > 1: print("-"*60+f"\n>> Manually adding register")
    desc = ""
    output = {}
    for item in this_items.keys():
        if len(this_items[item]) > 0:
            desc = this_items[item]
        confirmed = False
        while(not confirmed):
            print("="*60+f"\n>>\t{item}\n")
            temp = input(f"\t\tDescripción: \n{desc}\n\n Ingrese información\n")

            # TEST IF bib already exists
            if item == 'title':
                test = get_id("id","bib_entries",["title"],[temp])
                if test >= 0:
                    print(f'\n\nThis entry already exists with id: {test}')
                    return {'error':0}

            test = input("Continuar con el siguiente registro y/n\n") or 'y'
            if test == "y":
                output[item] = temp
                confirmed = True
    return output

def add_author(title,author_list=[]):
    '''This Function create register for all authors of an article. It makes the bib_author entry as well.'''
    if __verbose > 1: print("-"*60+f"\n>> Adding authors for {title}")
    '''Get the entry ID on bib_entries'''
    entrie_id = get_id("id","bib_entries",["title"],[title])
    if entrie_id > 0:
        if __verbose >= 2: print(f"\t\tThis entry have id: {entrie_id}")
    else:
        print('Error cant find specific article id', entrie_id)
        print(title)
        return 0
    author_id = 0
    '''If there is no first_author declared it set fist author entry as first_author'''
    first_author = False
    test = get_id("id_author","bib_author",["id","first_author"],[entrie_id,1])
    if test == 0:
        first_author = True
    '''If author_list have length grater than 0 it is an automatic process'''
    manually = True
    if len(author_list) > 0:
        manually = False
    '''If automatic process it define a counter i'''
    i = 0
    '''Test for add more author'''
    test = 'y'
    all_entered = False
    while not all_entered:
        if manually:
            if first_author:
                print('\n\tEnter information of lead author')
            else:
                print('\n\tEnter information of next author')
            this_author = manually_add_register(structure["author"])
        else:
            this_author = author_list[i]
            print(this_author, author_list)
            i += 1
        identified = False
        while not identified:
            author_id = get_id("id_author","author",["first_name","last_name"],[this_author["first_name"],this_author["last_name"]])
            if author_id > 0:
                identified = True
            else:
                comunicate_db(f"INSERT INTO author (first_name,last_name) VALUES ('{this_author['first_name']}','{this_author['last_name']}');")
        if first_author:
            comunicate_db(f"INSERT INTO bib_author (id_author,id,first_author) VALUES ({author_id},{entrie_id},1)")
        else:
            comunicate_db(f"INSERT INTO bib_author (id_author,id) VALUES ({author_id},{entrie_id})")
        if manually:
            test = input('Insert more authors (y/n)') or 'y'
        else:
            if __verbose > 3: print("\nTesting if all entered")
            if i == len(author_list):
                test = 'n'
                if __verbose >3: print("All entered",i,len(author_list)-1)
        first_author = False
        print("next", i)
        if test != 'y':
            all_entered = True
    return 1

def add_abstract(title):
    '''For an specific title it manually add abstract items'''
    if __verbose > 1: print("-"*60+f"\n>> Adding abstract for {title}")
    entrie_id = get_id("id","bib_entries",["title"],[title])
    if entrie_id > 0:
        if __verbose >= 2: print(f"\t\tThis entry have id: {entrie_id}")
    else:
        # print('Error cant find specific article id')
        # print(temp)
        return 0
    info = manually_add_register(structure["abstract"])
    columns,values = order_information(info, 'id,', f" '{entrie_id}',")
    msn = f'INSERT INTO abstract ({columns[:-1]}) VALUES ({values[:-1]});'
    comunicate_db(msn)
    return 1

def add_keywords(keywords):
    '''Insert a keyword combination if it does not exists.'''
    if __verbose > 1: print("-"*60+f"\n>> Adding keywords: {keywords}")
    msn = f"""INSERT INTO keyword (keyword_list)
    SELECT '{keywords}'
    FROM dual
    WHERE NOT EXISTS (
        SELECT 1
        FROM keyword
        WHERE keyword_list = '{keywords}');"""
    comunicate_db(msn)

def init_review_table(title,keywords):
    '''Insert a entry on review table for a specific title with a specific keyword combination'''
    article_id = get_id("id","bib_entries",["title"],[title])
    keyword_id = get_id("key_id","keyword",["keyword_list"],[keywords])
    msn = f"""INSERT INTO reviewed (key_id,article_id)
    VALUES ({keyword_id},{article_id}) ;
    """
    comunicate_db(msn)

@cli.command()
@click.option("--filename")
def import_bib(filename):
    '''Parse and add all entries on .bib file.\nFile Name: database_keywords.bib'''
    with open(filename) as file:
        library = bibtexparser.load(file)
    for entry in library.entries:
        current_entry = {}
        author_list = []
        if "ENTRYTYPE" in entry:
            current_entry["entrie_type"] = entry["ENTRYTYPE"]
        if "ID" in entry:
            current_entry["bibkey"] = entry["ID"]
        if "title" in entry:
            current_entry["title"] = entry["title"]
        if "journal" in entry:
            current_entry["journaltitle"] = entry["journal"]
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
            author_list = order_authors(entry["author"])


        if __verbose > 2: print(current_entry,author_list)
        if __verbose > 3: input("-----------")
        add_reference(current_entry,author_list)
        add_keywords(filename.split("_")[1][:-4])
        init_review_table(current_entry["title"],filename.split("_")[1][:-4])

def order_authors(author_string):
    author_list = []
    temp_list = author_string.split(" and ")
    if __verbose > 2: print(temp_list)
    for author in temp_list:
        if __verbose > 2:
            print(author,type(author))
        if "{" in author:
            author = author.replace("{","")
            author = author.replace("}","")
        if "'" in author:
            author = author.replace("'","")
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

def order_information(info, columns = '', values = ''):
        for column, data in info.items():
             columns += f' {column},'
             values += f" '{data}',"
        return columns, values

def set_connection():
    '''This function initialize the variables needed for mysql.connector connection'''
    global __usr, __passwd, __this_host, __this_database
    __usr = input('User: ')
    __passwd = getpass.getpass()
    test = input(f'Current host: {__this_host}, \n\tDo you want to change it (y/n)')
    if test == 'y':
        __this_host = input('Host: ')
    test = input(f'Current database: {__this_database}, \n\tDo you want to change it (y/n)')
    if test == 'y':
        __this_database = input('Database: ')
    try:
        print(f">>{__usr}@{__this_host}:{__this_database}")
        dbcnx = sql.connect(user=__usr,
                            password=__passwd,
                            host=__this_host,
                            # port=3306,
                            database=__this_database)
        if dbcnx.is_connected():
            db_Info = dbcnx.get_server_info()
            print(f"Connected to MariaDB version {db_Info}")
    except sql.Error as e:
        print("Error while connecting to MariaDB", e)
        if __verbose > 3: input("-"*60)
    finally:
        if dbcnx.is_connected():
            dbcnx.close()
            print("MariaDB connection is close")

def comunicate_db(msn,query=False):
    '''Function that connect and execute the command'''
    output = ''
    try:
        print("-"*60+f"\n>>{__usr}@{__this_host}:{__this_database}")
        dbcnx = sql.connect(user=__usr,
                            password=__passwd,
                            host=__this_host,
                            # port=3306,
                            database=__this_database)
        if dbcnx.is_connected():
            db_Info = dbcnx.get_server_info()
            print(f"Connected to MariaDB version {db_Info}")
            cursor = dbcnx.cursor()
            if __verbose >= 2: print(msn)
            cursor.execute(msn)
            if query:
                output = cursor.fetchall()
                if __verbose > 3: print(output)
            else:
                dbcnx.commit()
    except sql.Error as e:
        print("Error while connecting to MariaDB", e)
        if __verbose > 3: input("-"*60)
    # finally:
        # if dbcnx.is_connected():
    cursor.close()
    dbcnx.close()
    print("MariaDB connection is close")
    return output

# @cli.command()
def add_reference(info={},author_list = []):
    ''' Function to be call each time a new reference is made. It create a new entry en bib_entries table'''
    no_more = False
    manually = False
    test = ''
    while not no_more:
        msn = "INSERT INTO bib_entries ("
        if len(info) == 0:
            info = manually_add_register(structure["bib_entries"])
            manually = True
        if 'error' in info: return 0
        columns, values = order_information(info)
        exists = get_id("id","bib_entries",["title"],[info["title"]])
        if exists < 0:
            msn += f'{columns[:-1]}) VALUES ({values[:-1]});'
            comunicate_db(msn)
            add_author(info['title'],author_list)
            if manually:
                test = input('Did you want to add abstract (y/n)')
                if test == 'y':
                    add_abstract(info['title'])
                test = input('Add a new reference (y/n)') or 'y'
            else:
                test = 'y'
            if test != 'y': no_more = True
        else:
            msn = f"""SELECT first_name,last_name FROM author
    INNER JOIN bib_author
    ON bib_author.id_author = author.id_author
    AND bib_author.id = {exists};
            """
            current_authors_list = comunicate_db(msn,query=True)
            if __verbose > 2: print(current_authors_list)
            if __verbose > 3: print(author_list)
            if len(current_authors_list) == len(author_list):
                no_more = True
            else:
                add_these_authors = []
                add_it = False
                for author in author_list:
                    for i in range(len(current_authors_list)):
                        if author["first_name"] == current_authors_list[i][0] and author["last_name"] == current_authors_list[i][1]:
                            print(f"{author} already on database")
                            add_it = False
                            break
                        add_it = True
                    if add_it: add_these_authors.append(author)
                add_author(info['title'],add_these_authors)
                no_more =True
    if __verbose > 3: click.pause()
    return 1

@cli.command()
@click.option(
    '--this_host',
    default='192.168.68.18',
    type=str
)
@click.option(
    '--this_database',
    default='prisma7be',
    type=str
)
@click.argument('log_file')
@click.option('--key_file',prompt='write key file path')
def remote(log_file,key_file,this_host,this_database):
    usr , passwd = read_log_info(log_file,key_file)

def read_log_info(log_file,key_file):
    with open(key_file,'rb') as f:
        key = f.read()
    fernet = Fernet(key)
    with open(log_file,'rb') as f:
        content = fernet.decrypt(f.read()).decode('ascii')
    data = content.split(',')
    return data[0],data[1]

@cli.command()
@click.argument('usr')
@click.argument('pwd')
@click.argument('key_file')
def create_log_data(usr,pwd,key_file):
    with open(key_file,'rb') as f:
        key = f.read()
    fernet = Fernet(key)
    content = usr +','+pwd
    with open('log.data','wb') as f:
        f.write(fernet.encrypt(content.encode('ascii')))

if __name__ == '__main__':
    cli()
