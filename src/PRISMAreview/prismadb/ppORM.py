# Manage coonection with a SQL database with
# specific STRUCTURE

import mysql.connector as sql
# from mysql.connector import errorcode
# import mariadb as sql
# import sqlalchemy as sql
import getpass
import pandas as pd
from django.apps import apps
from django.db.models import ForeignKey
from .models import Author_type, Isn_list  # , Keyword
from datetime import datetime  # , date


# >> global constants <<=======================================================
TRANSLATED_BIB_KEYS = {
    "entry_type": "ENTRYTYPE",
    "bibkey": "ID",
    "journaltitle": "journal",
    "publication_date": "date",
    "notes": "note",
    "issue_volume": "volume",
    "issue_number": "number",
    "file_path": "file"
    }

STRUCTURE = {}

CONDITIONS_STRUCTURE = {
    "junction": "",
    "table": "",
    "column": "",
    "value": ""
    }

AGAIN = pd.DataFrame(data=("again",), columns=["id"])

TEXT_MAX_BYTE_SIZE = 65534

# >> Private variables - To improve modularity and security <<=================
__usr = ''
__passwd = ''
__this_host = 'localhost'
# __this_database = 'prisma7be'
__this_database = 'prisma'


# >> Logging functionality <<==================================================
__verbose = 0
__log_file_name = "log-ppORM"
END_FUNCTION = "%"*25+" END LINE "+"%"*25


def get_verbose():
    return __verbose


def set_verbose(verbose):
    global __verbose
    __verbose = verbose
    if __verbose >= 3:
        global __log_file_name
        __log_file_name = f"log-ppORM-{datetime.now()}"


def log(msn, verbose):
    if __verbose >= verbose and verbose >= 0:
        print(msn)
    if __verbose >= 3:
        with open(__log_file_name, "a") as log_file:
            log_this = f"{datetime.time(datetime.now())}"
            log_this += " >>"
            log_this += str(msn)
            log_this += "\n"
            log_file.write(log_this)


# >> Initialization <<=========================================================
def set_connection():
    '''
    This function initialize the variables needed for mysql.connector
    connection
    '''
    global __usr, __passwd, __this_host, __this_database
    if __usr == '':
        __usr = input('User: ')
    if __passwd == '':
        __passwd = getpass.getpass()
    input_msn = f'Current host: {__this_host},\n\tDo you want to keep it (y/n)'
    test = input(input_msn) or 'y'
    if test != 'y':
        __this_host = input('Host: ')
    input_msn = f'Current database: {__this_database},'
    input_msn += '\n\tDo you want to keep it (y/n)'
    test = input(input_msn) or 'y'
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


def init_structure():
    models = apps.get_models()
    isn = 'id_isn'
    toa = 'type_of_author'

    for model in models:
        table_name = model._meta.db_table
        if table_name.split('_')[0] == 'prismadb':
            column_names = {}
            for field in model._meta.fields:
                comment = field.db_comment
                if field.name == isn:
                    column_names[isn] = list(
                            Isn_list.objects.values_list(isn, flat=True)
                            )
                elif field.name == toa:
                    column_names[toa] = list(
                            Author_type.objects.values_list(toa, flat=True)
                            )
                elif isinstance(field, ForeignKey):
                    this_field_name = field.name+'_id'
                    column_names[this_field_name] = comment
                else:
                    column_names[field.name] = comment

            STRUCTURE[table_name] = column_names


def init(verbose):
    if verbose > 0:
        global __verbose
        __verbose = verbose
    if not set_connection():
        exit()
    init_structure()


# >> Comunicating <<===========================================================
def communicate_db(
        msn,
        query=False
        ):
    '''
    Function that connect and execute the command.

    Returns an empty DataFrame if writing content that already exits
    (errno 1062) or query = False.

    Returns AGAIN if any other error occurs

    If query = True Returns a DataFrame.
    '''
    output = pd.DataFrame()
    try:
        log("-"*60+f"\n>>{__usr}@{__this_host}:{__this_database}", 1)
        dbcnx = sql.connect(user=__usr,
                            password=__passwd,
                            host=__this_host,
                            # port=3306,
                            database=__this_database)
        if dbcnx.is_connected():
            db_Info = dbcnx.get_server_info()
            log(f"Connected to MariaDB version {db_Info}", 0)
            cursor = dbcnx.cursor()
            log(msn, 2)
            cursor.execute(msn)
            if query:
                output = cursor.fetchall()
                output = pd.DataFrame(output, columns=cursor.column_names)
                log(output, 3)
            else:
                dbcnx.commit()
            cursor.close()
            dbcnx.close()
            log("MariaDB connection is close", 0)
    except sql.Error as e:
        if e.errno == 1062:
            log("Entry already exists", 1)
            return pd.DataFrame()
        log(f"Error while connecting to MariaDB {e}", 1)
        test = input("."*60+"\nTry again? (y/n)") or 'y'
        if test == 'y':
            log(END_FUNCTION, 1)
            return AGAIN
        else:
            exit()
    log(END_FUNCTION, 1)
    return output


def manually_add_register(this_items, table):
    '''Complete the dictionary passed as argument'''
    log("-"*60+"\n>> Manually adding register", 1)
    desc = ""
    output = {}

    for item in this_items.keys():
        if this_items[item] is None:
            desc = ""
        elif len(this_items[item]) > 0:
            desc = this_items[item]
        confirmed = False
        while not confirmed:
            log("="*60+f"\n>>\t{item}\n", 0)
            if desc == STRUCTURE[table][item]:
                input_msn = f"\t\tDescription:\n{desc}\n\nWrite information:\n"
                temp = input(input_msn)
            else:
                input_msn = f"\t\tDescription: \n{STRUCTURE[table][item]}\n\n"
                input_msn += f"Current information:\n{desc}\n"
                input_msn += "Press enter to add it or write the new entry:\n"
                temp = input(input_msn) or desc
            log(input_msn, -1)
            log(f"Value to save:\t{temp}", -1)

            test = input("Continue with next register? (y/n)\n") or 'y'
            if test == "y":
                output[item] = temp
                confirmed = True
    log(END_FUNCTION, 1)
    return output


# >> Formatting information <<=================================================
def secure_string(data):
    if type(data) is dict:
        for key, value in data.items():
            temp = secure_apostrophes(value)
            if temp != value:
                data[key] = temp
    return data


def secure_apostrophes(mystring):
    if type(mystring) is str:
        if "'" in mystring and "\\\'" not in mystring:
            output = mystring.replace("'", "\\\'")
        else:
            return mystring
    else:
        return mystring
    return output


def format_authors(author_string):
    '''
    Formally known as order_authors
    Create a list of dictionaries wit the STRUCTURE
    {"first_name":name,"last_name":last_name}
    '''
    log("-"*60+"\n>> Creating author_list", 1)
    author_list = []
    name_key = "first_name"
    surname_key = "last_name"
    temp_list = author_string.split(" and ")
    log(temp_list, 2)
    for author in temp_list:
        log(f"{author}, {type(author)}", 3)
        if "{" in author:
            author = author.replace("{", "")
            author = author.replace("}", "")
        if len(author.split(",")) > 2:
            # There is a different author_list format from the .bib file
            list_to_clean = temp_list[0].split(",")
            for new_author in list_to_clean:
                words = new_author.split(" ")
                if len(words) == 2:
                    author_list.append({
                        name_key: words[0],
                        surname_key: words[1]
                        })
                elif len(words) == 3:
                    author_list.append({
                        name_key: " ".join(words[0:-1]),
                        surname_key: words[-1]
                        })
                elif len(words) > 3:
                    author_list.append({
                        name_key: " ".join(words[0:1]),
                        surname_key: " ".join(words[2:])
                        })
        elif ", " in author:
            info = author.split(", ")
            author_list.append({
                name_key: info[1],
                surname_key: info[0]
                })
        else:
            if "." in author:
                end_first_name = author.rfind('.')
                author_list.append({
                                    name_key: author[:end_first_name+1],
                                    surname_key: author[end_first_name+2:]
                })
            else:
                info = author.split(" ", 1)
                if len(info) == 2:
                    author_list.append({
                        name_key: info[0],
                        surname_key: info[1]
                        })
                elif len(info) == 1:
                    author_list.append({
                        name_key: info[0],
                        surname_key: ""
                        })
                else:
                    print(f"Me cago en {author}")
    log(END_FUNCTION, 1)
    return author_list


def parse_entry(entry):
    log(entry, 2)
    url_info = {}
    if "url" in entry:
        url_info["url_string"] = entry["url"]
    else:
        url_string = "https://duckduckgo.com/?q="
        url_string += entry["title"].replace(" ", "+")
        url_info["url_string"] = url_string

    current_entry = {}
    for key in STRUCTURE["prismadb_bib_entries"].keys():
        if key in TRANSLATED_BIB_KEYS:
            if TRANSLATED_BIB_KEYS[key] in entry:
                current_entry[key] = entry[TRANSLATED_BIB_KEYS[key]]
        elif key == "isn":
            isn_type, content = parse_isn(entry)
            if isn_type != 0:
                current_entry["isn"] = content
                current_entry["isn_type_id"] = isn_type
        elif key == "isn_type_id":
            pass
        elif key in entry:
            current_entry[key] = entry[key]
        elif key == "accessed":
            current_entry[key] = datetime.today().strftime("%Y-%m-%d")

    author_list = {}
    for person_roll in STRUCTURE["prismadb_author_type"]["type_of_author"]:
        if person_roll in entry:
            author_list[person_roll] = format_authors(entry[person_roll])
    log(current_entry, 3)
    log(author_list, 3)
    log(url_info, 3)
    return current_entry, author_list, url_info


def parse_isn(entry):
    content = None
    isn_type = 0
    for isn_name in STRUCTURE["prismadb_isn_list"]["id_isn"]:
        if isn_name in entry:
            content = entry[isn_name]
            isn_type = Isn_list.objects.get(id_isn=isn_name).id
    return isn_type, content


# >> ORM functionality that can be dropped ====================================
def format_select(
        identity,
        table,
        info
        ):
    '''Returns a formatted string to make a query'''
    msn = f"SELECT {identity} FROM {table} WHERE "
    msn += order_equalising(info)
    msn += ";"
    return msn


def format_insert(
        table,
        info
        ):
    msn = f"INSERT INTO {table} SET "
    msn += order_equalising(info)
    msn += ";"
    return msn


def order_columns_values(info, columns='', values=''):
    '''
    From a dictionary rearrange the information.
    Return a formatted string for the column list and associated values
    ready for a INSERT query.
    '''
    for column, data in info.items():
        columns += f' {column},'
        values += f' "{data}",'
    return columns, values


def order_equalising(info, connector=" AND "):
    """
    From a dictionary rearrange the information equalising each key to the
    value
    """
    msn = ""
    i = 0
    for column, value in info.items():
        if i > 0:
            msn += connector
        msn += f"{column} = '{value}'"
        i += 1
    return msn


# >> Getting information <<====================================================
def get_id(
        identity,
        table,
        columns=[],
        values=[]
        ):
    '''
    Test the existence of any entry with same {value} at {table}.{column}
    as provided.
    If it exists it returns the integer that identify such entry.
    If it does not exists returns 0.
    If there are not a matching number of columns and values returns -1.
    '''
    log("-"*60+f"\n>> Getting {identity} FROM {table}", 1)
    if len(columns) != len(values):
        msn = "ERROR:\n\nThere is a mismatch between columns and values"
        msn += f"\n\tColumns:{columns}\n\tValues:{values}"
        log(msn, 1)
        log(END_FUNCTION, 1)
        return -1
    more = True
    test = pd.DataFrame()
    while more:
        msn = format_select(identity, table, columns, values)
        log(msn, 3)

        test = communicate_db(msn, query=True)
        more = False
        if test.equals(AGAIN):
            more = True
            log("."*60, 0)
            log("You selected the option to manually get a value", 0)
            log("Current values:", 0)
            for i in range(len(columns)):
                log(f"\t{columns[i]}:\t{values[i]}", 0)
                input_msn = "Write new value or press enter to keep it\n"
                values[i] = input(input_msn) or values[i]
                log("Value to save:\t{values[i]}",-1)
            log("."*60, 0)

        if test.shape == (1, 1):
            log(f"\n\n{table}.{columns}='{values}' already exists", 0)
            log(f"With {identity}: {test.iat[0, 0]}", 0)
            try:
                my_id = int(test.iat[0, 0])
                log(END_FUNCTION, 1)
                return my_id
            except ValueError:
                log("For some reason {test.iat[0, 0]} isn't an int", 0)
                if test.iat[0, 0] is None:
                    log(END_FUNCTION, 1)
                    return 0
                else:
                    break
        elif test.empty:
            log(f"There are no instances for\n{table}.{columns}='{values}'", 2)
            log(END_FUNCTION, 1)
            return 0
        else:
            log(f"ERROR:\nThere are multiply entries at {table}.{columns},")
            log(f"\nWith value '{values}' ", 0)
            log(test, 3)
            if __verbose == 4:
                msn = "Do you want to select one of the retrieved values?(y/n)"
                opt = input(msn) or 'y'
                if opt == 'y':
                    msn = f"Write the number of the {identity} you want:\n"
                    opt = input(msn)
                    try:
                        opt = int(opt)
                        log(END_FUNCTION, 1)
                        return opt
                    except ValueError:
                        print("Invalid option\nTry again")
            else:
                more = False
    log(END_FUNCTION, 1)
    return -1


def get_newtable(
        main_table,
        request_columns,
        join_conditions=[],
        conditions=[]
        ):
    '''Query an join table
    request_columns = {"table_name":["columns",],}
    join_conditions = [{
        "join_table_name":"column",
        "main_table_name":"column"
    },]
    conditions = [CONDITIONS_STRUCTURE,]
    CONDITIONS_STRUCTURE = {
        "junction":"",
        "table":"",
        "column":"",
        "value":""
    }
    '''
    msn = "-"*60+"\n>> Creating a new view >> returns DataFrame"
    log(msn, 2)
    columns = ""
    for table_name, column_names in request_columns.items():
        for column in column_names:
            columns += f" {table_name}.{column},"
    columns = columns[:-1]

    inner_joins = ''
    if len(join_conditions) > 0:
        for join in join_conditions:
            start = ''
            end = ''
            for table_name, column in join.items():
                if table_name == main_table:
                    end = f" = {table_name}.{column}\n"
                else:
                    start = f"INNER JOIN {table_name} ON {table_name}.{column}"
            inner_joins += start+end

    conditions_list = ''
    if len(conditions) > 0:
        for condition in conditions:
            conditions_list += f'{condition["junction"]} {condition["table"]}.'
            conditions_list += f"{condition['column']}='{condition['value']}'"
            conditions_list += "\n"
    msn = f'''SELECT {columns} FROM {main_table}
    {inner_joins}   {conditions_list}   ;'''
    log(msn, 3)
    log(END_FUNCTION, 2)
    return communicate_db(msn)
