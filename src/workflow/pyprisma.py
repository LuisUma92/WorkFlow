# workflow.pyprisma
# Manage coonection with a SQL database with
# specific structure

import mysql.connector as sql
# from mysql.connector import errorcode
# import mariadb as sql
import getpass

structure = {
    "bib_entries" : {
        # "id": "INT",
        "entry_type":"\tVARCHAR(100)",
        "bibkey":"\tCHAR(100)",
        "title":"\tVARCHAR(250)",
        "journaltitle":"\tVARCHAR(100),",
        "issue_volume":"\tINT",
        "issue_number":"\tINT",
        "year":"\tYEAR",
        "pages":"\tCHAR(21)",
        "database_name":"\tCHAR(20)\n\tSpecify the information sources (e.g. databases, registers) used to identify studies.",
        "accessed":"\tDATE\nSpecify the information used to identify the date when last searched.",
        "url":"\tTEXT(21844) CHARACTER SET utf8\n\tProvide especific URL to access.",
        "doi":"\tTEXT(21844) CHARACTER SET utf8\n\tProvide especific DOI to access.",
        "keyword":"\tCHAR(250)\n\tProvide papers's assigned kewords"
    },
    "author" : {
        # "id_author":"INT",
        "first_name":"\tCHAR(20)",
        "last_name":"\tVARCHAR(100)",
        "alias":"\tBOOLEAN DEFAULT 0",
        "affiliation":"\tCHAR(100)"
    },
    "bib_author" : {
        "id_author":"\tauthor.id_author",
        "id":"\tbib_entries.id",
        "first_author":"\tBOOLEAN",
    },
    "bib_references" : {
        "article":"\tbib_entrie.bib",
        "reference":"\tbib_entrie.bib",
    },
    "keyword" : {
        # "key_id":"INT",
        "keyword_list":"\tVARCHAR(500) CHARACTER SET utf8\nSearch keywords used"
    },
    "reviewed" : {
        "key_id":"\tINT UNSIGNED\nREFERENCES keyword (key_id)",
        "article_id":"\tINT UNSIGNED\nREFERENCES bib_entries (id)",
        "retrieved":"\t\tBOOLEAN\nFlag 0 if paper was retrieved",
        "included":"\t\tBOOLEAN\nFlag 1 if paper was included",
    },
    "abstract" : {
        # "id":"bib_entries.id",
        "objectives":"\tTEXT(21844) CHARACTER SET utf8,\n\tProvide an explicit statement of the main objective(s) or question(s) the review addresses.",
        "rationale":"\tTEXT(21844) CHARACTER SET utf8\n\tDescribe the rationale for the review in the context of existing knowledge.",
        "eligibility_criteria":"\tTEXT(21844) CHARACTER SET utf8\n\tSpecify the inclusion and exclusion criteria for the review.",
        "methods_synthesis":"\tTEXT(21844) CHARACTER SET utf8\n\tSpecify the methods used.",
        "results_synthesis":"\tTEXT(21844) CHARACTER SET utf8\n\tPresent results for main outcomes, preferably indicating the number of included studies and participants for each. If meta-analysis was done, report the summary estimate and confidence/credible interval. If comparing groups, indicate the direction of the effect (i.e. which group is favoured).",
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
__verbose = 0
def get_verbose():
    return __verbose
def ser_verbose(verbose):
    global __verbose
    __verbose = verbose


def init(verbose):
    if verbose > 0:
        global __verbose
        __verbose = verbose
    if not set_connection():
        exit()
    pass

def format_query(identity,table,columns=[],values=[]):
    '''Returns a formatted string to make a query'''
    msn= f"SELECT {identity} FROM {table} WHERE "
    for i in range(len(columns)):
        if i > 0: msn += " AND "
        column = columns[i]
        value = values[i]
        msn += f"{column} = '{value}'"
    msn += ";"
    return msn

def get_value(identity,table,columns=[],values=[]):
    '''Test the existence of any entry with same {value} at {table}.{column} as provided.
    If it exists it returns the integer that identify such entry.
    If it does not exists returns 0.
    If there are more columns or values returns -1.
    If it exits but the identifier is not a integer returns -2.'''
    if __verbose >= 1: print("-"*60+f"\n>> Getting {identity} FROM {table}")
    if len(columns) != len(values):
        print(f"ERROR:\n\nThere is a mismatch between columns and values\n\tColumns:{columns}\n\tValues:{values}")
        return -1
    msn = format_query(identity,table,columns,values)
    test = comunicate_db(msn,query=True)
    if len(test) > 0:
        print(f"\n\n{table}.{columns}='{values}' already exists\nWith {identity}: {test[0][0]}")
        return test[0][0]
    else:
        print(f"ERROR:\nThere is no entry at {table}.{columns},\nWith value '{values}' ")
        if __verbose >= 3: print(test)
        return 0

def get_row(table,columns=[],values=[]):
    '''Return a dictionary fora a row in a {table} that fulfill the {columns}={values} conditions'''
    msn = format_query('*',table,columns,values)
    output = comunicate_db(msn,query=True,dictionary=True)
    if type(output) == str:
        return {'error':0}
    elif type(output) == list:
        return dict(zip(structure[table],output))
    else:
        return output

def manually_add_register(this_items,table):
    '''Complete the dictionary passed as argument'''
    if __verbose >= 1: print("-"*60+f"\n>> Manually adding register")
    desc = ""
    output = {}
    for item in this_items.keys():
        if len(this_items[item]) > 0:
            desc = this_items[item]
        confirmed = False
        while(not confirmed):
            print("="*60+f"\n>>\t{item}\n")
            if desc == structure[table][item]:
                temp = input(f"\t\tDescription: \n{desc}\n\n Write information:\n")
            else:
                temp = input(f"\t\tDescription: \n{structure[table][item]}\n\n Write information (Press enter to add:)\n{desc}") or desc

            # TEST IF bib already exists
            if item == 'title':
                test = int(get_value("id","bib_entries",["title"],[temp]))
                if test > 0:
                    print(f'\n\nThis entry already exists with id: {test}')
                    return get_row('bib_entries',columns=["title"],values=[temp])
            if item == 'affiliation':
                test = int(get_value("id_author","author",columns=["first_name","last_name"],values=[output["first_name"],output["last_name"]]))
                if test > 0:
                    print(f'\n\nThis entry already exists with id: {test}')
                    return get_row('author',columns=["id_author"],values=[test])

            test = input("Continue with nest register? (y/n)\n") or 'y'
            if test == "y":
                output[item] = temp
                confirmed = True
    return output

def add_author(title,author_list=[]):
    '''This Function create register for all authors of an article. It makes the bib_author entry as well.'''
    if __verbose >= 1: print("-"*60+f"\n>> Adding authors for {title}")
    '''Get the entry ID on bib_entries'''
    entry_id = int(get_value("id","bib_entries",["title"],[title]))
    if entry_id > 0:
        if __verbose >= 2: print(f"\t\tThis entry have id: {entry_id}")
    else:
        print('Error cant find specific article id', entry_id)
        print(title)
        return 0
    author_id = 0
    '''If there is no first_author declared it set first author entry as first_author'''
    first_author = False
    test = int(get_value("id_author","bib_author",["id","first_author"],[entry_id,1]))
    if test == 0:
        first_author = True
    '''If author_list have length grater than 0 it is an automatic process'''
    manually = True
    if len(author_list) > 0:
        manually = False
    '''If automatic process it define a counter i'''
    i = 0
    '''Test for adding more author'''
    test = 'y'
    all_entered = False
    while not all_entered:
        if manually:
            if first_author:
                print('\n\tEnter information of lead author')
            else:
                print('\n\tEnter information of next author')
            this_author = manually_add_register(structure["author"],"author")
        else:
            this_author = author_list[i]
            if __verbose >= 4: print(this_author, author_list)
            i += 1
        identified = False
        while not identified:
            author_id = int(get_value("id_author","author",["first_name","last_name"],[this_author["first_name"],this_author["last_name"]]))
            if author_id > 0:
                identified = True
            else:
                if comunicate_db(f"INSERT INTO author (first_name,last_name) VALUES ('{this_author['first_name']}','{this_author['last_name']}');") == 'again':
                    this_author = manually_add_register(this_author,"author")
                    continue
        if first_author:
            comunicate_db(f"INSERT INTO bib_author (id_author,id,first_author) VALUES ({author_id},{entry_id},1)")
        else:
            comunicate_db(f"INSERT INTO bib_author (id_author,id) VALUES ({author_id},{entry_id})")
        if manually:
            test = input('Insert more authors (y/n)') or 'y'
        else:
            if __verbose >= 3: print("\nTesting if all entered")
            if i == len(author_list):
                test = 'n'
                if __verbose >= 3: print("All entered",i,len(author_list)-1)
        first_author = False
        print("next", i)
        if test != 'y':
            all_entered = True
    return 1

def add_abstract(title):
    '''For an specific title it manually add abstract items'''
    if __verbose >= 1: print("-"*60+f"\n>> Adding abstract for {title}")
    entry_id = int(get_value("id","bib_entries",["title"],[title]))
    if entry_id > 0:
        if __verbose >= 2: print(f"\t\tThis entry have id: {entry_id}")
    else:
        # print('Error cant find specific article id')
        # print(temp)
        return 0
    info = manually_add_register(structure["abstract"],"abstract")
    columns,values = order_information(info, 'id,', f" '{entry_id}',")
    msn = f'INSERT INTO abstract ({columns[:-1]}) VALUES ({values[:-1]});'
    comunicate_db(msn)
    return 1

def add_keywords(keywords):
    '''Insert a keyword combination if it does not exists.'''
    if __verbose >= 1: print("-"*60+f"\n>> Adding keywords: {keywords}")
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
    if __verbose >= 1: print("-"*60+f"\n>> Initialize review for: {title}\n   Using keyword: {keywords}")
    article_id = int(get_value("id","bib_entries",["title"],[title]))
    keyword_id = int(get_value("key_id","keyword",["keyword_list"],[keywords]))
    msn = f"""INSERT INTO reviewed (key_id,article_id)
    VALUES ({keyword_id},{article_id}) ;
    """
    comunicate_db(msn)

def order_authors(author_string):
    '''Create a list of dictionaries wit the structure
    {"first_name":name,"last_name":last_name}'''
    if __verbose >= 1: print("-"*60+f"\n>> Creating author_list")
    author_list = []
    temp_list = author_string.split(" and ")
    if __verbose >= 4: print(temp_list)
    for author in temp_list:
        if __verbose >= 3: print(author,type(author))
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
    '''Return a formatted string for the column list and associated values'''
    if __verbose >= 3: print("-"*60+"\n>> Creating formatted strings for query")
    for column, data in info.items():
        columns += f' {column},'
        values += f" '{data}',"
    return columns, values

def set_connection():
    '''This function initialize the variables needed for mysql.connector connection'''
    global __usr, __passwd, __this_host, __this_database
    __usr = input('User: ')
    __passwd = getpass.getpass()
    test = input(f'Current host: {__this_host}, \n\tDo you want to keep it (y/n)') or 'y'
    if test != 'y':
        __this_host = input('Host: ')
    test = input(f'Current database: {__this_database}, \n\tDo you want to keep it (y/n)') or 'y'
    if test != 'y':
        __this_database = input('Database: ')
    try:
        print(f">> {__usr}@{__this_host}:{__this_database}")
        dbcnx = sql.connect(user=__usr,
                            password=__passwd,
                            host=__this_host,
                            # port=3306,
                            database=__this_database)
        if dbcnx.is_connected():
            db_Info = dbcnx.get_server_info()
            print(f"Connected to MariaDB version {db_Info}")
            dbcnx.close()
            print("MariaDB connection is close")
    except sql.Error as e:
        print("Error while connecting to MariaDB", e)
        return 0
    return 1

def comunicate_db(msn,query=False,dictionary=False):
    '''Function that connect and execute the command.
    Returns an empty string if writing content that already exits (errno 1062) or query = False.
    Returns "again" if any other error occurs
    If query = True Returns a list of tuples, each row is a tuple.
    If dictionary = True Returns a dictionary wit each column name and first row of content.
    '''
    output = ''
    if dictionary:
        query = True
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
                if dictionary:
                    output = dict(zip(cursor.column_names,output[0]))
                if __verbose >= 3: print(output)
            else:
                dbcnx.commit()
            cursor.close()
            dbcnx.close()
            print("MariaDB connection is close")
    except sql.Error as e:
        if e.errno == 1062:
            print("Entry already exists")
            return ''
        print("Error while connecting to MariaDB", e)
        test = input("-"*60+"\nTry again? (y/n)") or 'y'
        if test == 'y':
            return 'again'
        else:
                exit()
    return output

def add_reference(info={},author_list = []):
    ''' Function to be call each time a new reference is made. It create a new entry en bib_entries table'''
    more = True
    manually = False
    test = ''
    first_time = True
    exists = 0
    columns = ''
    values = ''
    while more:
        msn = "INSERT INTO bib_entries ("
        if len(info) == 0:
            info = manually_add_register(structure["bib_entries"],"bib_entries")
            manually = True
        else:
            if __verbose >= 1: print("-"*60+"\n>> Adding a reference to bib_entries")
            if __verbose >= 3: print(info)
        if first_time:
            columns, values = order_information(info)
            exists = int(get_value("id","bib_entries",["title"],[info["title"]]))
        if exists == 0:
            if __verbose >= 2: print(">> Creating a new register")
            if first_time:
                msn += f'{columns[:-1]}) VALUES ({values[:-1]});'
                if comunicate_db(msn) == 'again':
                    info = manually_add_register(info,"bib_entries")
                    continue
            add_author(info['title'],author_list)
            if manually:
                test = input('Did you want to add abstract (y/n)')
                if test == 'y':
                    add_abstract(info['title'])
                test = input('Add a new reference (y/n)') or 'y'
            else:
                test = 'n'
            if test != 'y': more = False
        elif exists < 0:
            print("ERROR quitting")
            exit()
        else:
            if __verbose >= 2: print(">> Testing if all authors are on database")
            msn = f"""SELECT first_name,last_name FROM author
    INNER JOIN bib_author
    ON bib_author.id_author = author.id_author
    AND bib_author.id = {exists};
            """
            current_authors_list = comunicate_db(msn,query=True)
            if __verbose >= 3: print("Current author list:\n", current_authors_list)
            if __verbose >= 3: print("Actual author list:\n", author_list)
            if len(author_list) == 0:
                if len(current_authors_list) > 0:
                    for temp_author in current_authors_list:
                        if temp_author[0] == 'Editorial':
                            more = False
                            break
                        else:
                            author_list.append( get_row('author',columns=["first_name","last_name"],values=[temp_author[0],temp_author[1]]) )
                first_time = False
                exists = 0
                continue
            elif len(current_authors_list) == len(author_list):
                more = False
            else:
                add_these_authors = []
                add_it = False
                for author in author_list:
                    for i in range(len(current_authors_list)):
                        if author["first_name"] == current_authors_list[i][0] and author["last_name"] == current_authors_list[i][1]:
                            print(f"\t{author} already on database")
                            add_it = False
                            break
                        add_it = True
                    if add_it: add_these_authors.append(author)
                    add_it = False
                add_author(info['title'],add_these_authors)
                more = False
    if __verbose >= 3: input("="*60+"\nPress any key to continue...")
    return 1

# if __name__ == '__main__':
#     cli()
