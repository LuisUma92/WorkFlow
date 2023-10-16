# from re import split
import mysql.connector as sql
# import mariadb as sql
from cryptography.fernet import Fernet
import click
import getpass

structure = {
    "bib_entries":{
        # "id": "INT",
        "bibkey":"CHAR(10)",
        "title":"VARCHAR(250)",
        "journaltitle":"VARCHAR(100),",
        "issue_volume":"INT",
        "issue_number":"INT",
        "year":"YEAR",
        "pages":"CHAR(10)"
    },
    "author":{
        # "id_author":"INT",
        "first_name":"CHAR(20)",
        "last_name":"CHAR(20)",
    },
    "bib_author":{
        "id_author":"author.id_author",
        "id":"bib_entries.id",
        "first_author":"BOOLEAN",
    },
    "bib_references":{
        "article":"bib_entrie.bib",
        "reference":"bib_entrie.bib",
    },
    "abstract":{
        "id":"bib_entries.id",
        "objectives":"\tVARCHAR(21844) CHARACTER SET utf8,\nProvide an explicit statement of the main objective(s) or question(s) the review addresses.",
        "rationale":"\tVARCHAR(21844) CHARACTER SET utf8\nDescribe the rationale for the review in the context of existing knowledge.",
        "database_name":"\tCHAR(20)\nSpecify the information sources (e.g. databases, registers) used to identify studies.",
        "accessed":"\tDATE\nSpecify the information used to identify the date when last searched.",
        "doi_url":"\tVARCHAR(21844) CHARACTER SET utf8\nProvide especific DOI or as second option URL to access.",
        "keyword":"\tCHAR(40)\nProvide papers's assigned kewords",
        "eligibility_criteria":"\tVARCHAR(21844) CHARACTER SET utf8\nSpecify the inclusion and exclusion criteria for the review.",
        "retrived":"\tBOOLEAN\nFlag 1 if paper was retrived",
        "included":"\tBOOLEAN\nFlag 1 if paper was included",
        "methods_synthesis":"\tVARCHAR(21844) CHARACTER SET utf8\nSpecify the methods used.",
        "results_synthesis":"\tVARCHAR(21844) CHARACTER SET utf8\nPresent results for main outcomes, preferably indicating the number of included studies and participants for each. If meta-analysis was done, report the summary estimate and confidence/credible interval. If comparing groups, indicate the direction of the effect (i.e. which group is favoured).",
    },
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

def add_register(this_items):
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
                '''Test the existence of any bib_entry with same title as provided. If it exists it returns {'error':0}'''
                test = comunicate_db(f"SELECT id FROM bib_entries WHERE title = '{temp}';",query=True)
                if len(test) > 0:
                    print(f'\n\nThis entry already exists with id: {temp[0][0]}')
                    return {'error':0}

            test = input("Continuar con el siguiente registro y/n\n") or 'y'
            if test == "y":
                output[item] = temp
                confirmed = True
    return output

@cli.command()
@click.argument('title')
def add_author(title):
    '''This Function create register for all authors of an article. It makes the bib_author entry as well.'''
    entrie_id = 0
    temp = comunicate_db(f"SELECT id FROM bib_entries WHERE title = '{title}';",query=True)
    if len(temp) > 0:
        if __verbose >= 2: print(f"\t\tThis entry have id: {temp}")
        entrie_id = temp[0][0]
    else:
        print(temp)
    author_id = 0
    all_entered = False
    first_author = True
    while not all_entered:
        if first_author:
            print('\n\tEnter information of lead author')
        else:
            print('\n\tEnter information of next author')
        this_author = add_register(structure["author"])
        identified = False
        while not identified:
            temp = comunicate_db(f"SELECT id_author FROM author WHERE first_name='{this_author['first_name']}' AND last_name='{this_author['last_name']}';",query=True)
            if len(temp) == 1:
                author_id = temp[0][0]
                identified = True
            else:
                comunicate_db(f"INSERT INTO author (first_name,last_name) VALUES ('{this_author['first_name']}','{this_author['last_name']}');")
        if first_author:
            comunicate_db(f"INSERT INTO bib_author (id_author,id,first_author) VALUES ({author_id},{entrie_id},1)")
        else:
            comunicate_db(f"INSERT INTO bib_author (id_author,id) VALUES ({author_id},{entrie_id})")
        test = input('Insert more authors (y/n)') or 'y'
        first_author = False
        if test != 'y':
            all_entered = True

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

def comunicate_db(msn,query=False):
    '''Function that connect and execute the command'''
    output = ''
    try:
        print(__usr,__passwd,__this_host,__this_database)
        dbcnx = sql.connect(user=__usr,
                            password=__passwd,
                            host=__this_host,
                            # port=3306,
                            database=__this_database)
        if dbcnx.is_connected():
            db_Info = dbcnx.get_server_info()
            print(f"Connected to MariaDB version {db_Info}")
            # cmd = "CREATE TABLE entries(id INT, name TEXT},"
            # # for item in itemList.keys():
            #     cmd += f"'{item}' TEXT,"
            # cmd = cmd[:-1]+"},"
            cursor = dbcnx.cursor()
            if __verbose >= 2: print(msn)
            cursor.execute(msn)
            if query:
                output = cursor.fetchall()
            else:
                dbcnx.commit()
    except sql.Error as e:
        print("Error while connecting to MariaDB", e)
    else:
        # if dbcnx.is_connected():
        # cursor.close()
        dbcnx.close()
        print("MariaDB connection is close")
    return output

@cli.command()
def add_reference():
    ''' Function to be call each time a new reference is made.
   It create a new entry en bib_entries table'''
    msn = "INSERT INTO bib_entries ("
    info = add_register(structure["bib_entries"])
    if 'error' in info: return 0
    columns = ''
    values = ''
    for column, data in info.items():
         columns += f' {column},'
         values += f" '{data}',"
    msn += f'{columns[:-1]}) VALUES ({values[:-1]});'
    comunicate_db(msn)
    add_author(info['title'])
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
