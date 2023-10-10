from re import split
import mysql.connector as sql
# import mariadb as sql
from cryptography.fernet import Fernet
import click

itemList = {
    "Title":"",
    "Objectives":"",
    "Eligibility criteria":"",
    "Information sources":"",
    "Risk of bias":"",
    "Synthesis of results":"",
    "Included studies":"",
    "Synthesis of results":"",
    "Limitations of evidence":"",
    "Interpretation":"",
    "Funding":"",
    "Registration":"",
    "Rationale":"",
    "Objectives":"",
    "Eligibility criteria":"",
    "Information sources":"",
    "Search strategy":"",
    "Selection process":"",
    "Data collection process":"",
    "Data items":"",
    "Study risk of bias assessment":"",
    "Effect measures":"",
    "Synthesis methods":"",
    "Reporting bias assessment":"",
    "Certainty assessment":"",
    "Study selection":"",
    "Study characteristics":"",
    "Risk of bias in studies":"",
    "Results of individual studies":"",
    "Results of syntheses":"",
    "Reporting biases":"",
    "Certainty of evidence":"",
    "Discussion":"",
    "Registration and protocol":"",
    "Support":"",
    "Competing interests":"",
    "Availability of data, code and other materials":"",
}

itemDescription = [
    "1	Identify the report as a systematic review.",
    "A2	Provide an explicit statement of the main objective(s) or question(s) the review addresses.",
    "A3	Specify the inclusion and exclusion criteria for the review.",
    "A4	Specify the information sources (e.g. databases, registers) used to identify studies and the date when each was last searched.",
    "A5	Specify the methods used to assess risk of bias in the included studies.",
    "A6	Specify the methods used to present and synthesise results.",
    "A7	Give the total number of included studies and participants and summarise relevant characteristics of studies.",
    "A8	Present results for main outcomes, preferably indicating the number of included studies and participants for each. If meta-analysis was done, report the summary estimate and confidence/credible interval. If comparing groups, indicate the direction of the effect (i.e. which group is favoured).",
    "A9	Provide a brief summary of the limitations of the evidence included in the review (e.g. study risk of bias, inconsistency and imprecision).",
    "A10	Provide a general interpretation of the results and important implications.",
    "A11	Specify the primary source of funding for the review.",
    "A12	Provide the register name and registration number.",
    "3	Describe the rationale for the review in the context of existing knowledge.",
    "4	Provide an explicit statement of the objective(s) or question(s) the review addresses.",
    "5	Specify the inclusion and exclusion criteria for the review and how studies were grouped for the syntheses.",
    "6	Specify all databases, registers, websites, organisations, reference lists and other sources searched or consulted to identify studies. Specify the date when each source was last searched or consulted.",
    "7	Present the full search strategies for all databases, registers and websites, including any filters and limits used.",
    "8	Specify the methods used to decide whether a study met the inclusion criteria of the review, including how many reviewers screened each record and each report retrieved, whether they worked independently, and if applicable, details of automation tools used in the process.",
    "9	Specify the methods used to collect data from reports, including how many reviewers collected data from each report, whether they worked independently, any processes for obtaining or confirming data from study investigators, and if applicable, details of automation tools used in the process.",
    "10a	List and define all outcomes for which data were sought. Specify whether all results that were compatible with each outcome domain in each study were sought (e.g. for all measures, time points, analyses), and if not, the methods used to decide which results to collect.\n10b	List and define all other variables for which data were sought (e.g. participant and intervention characteristics, funding sources). Describe any assumptions made about any missing or unclear information.",
    "11	Specify the methods used to assess risk of bias in the included studies, including details of the tool(s) used, how many reviewers assessed each study and whether they worked independently, and if applicable, details of automation tools used in the process.",
    "12	Specify for each outcome the effect measure(s) (e.g. risk ratio, mean difference) used in the synthesis or presentation of results.",
    "13a	Describe the processes used to decide which studies were eligible for each synthesis (e.g. tabulating the study intervention characteristics and comparing against the planned groups for each synthesis (item #5)).\n13b	Describe any methods required to prepare the data for presentation or synthesis, such as handling of missing summary statistics, or data conversions.\n13c	Describe any methods used to tabulate or visually display results of individual studies and syntheses.\n13d	Describe any methods used to synthesize results and provide a rationale for the choice(s). If meta-analysis was performed, describe the model(s), method(s) to identify the presence and extent of statistical heterogeneity, and software package(s) used.\n13e	Describe any methods used to explore possible causes of heterogeneity among study results (e.g. subgroup analysis, meta-regression).\n13f	Describe any sensitivity analyses conducted to assess robustness of the synthesized results.",
    "14	Describe any methods used to assess risk of bias due to missing results in a synthesis (arising from reporting biases).",
    "15	Describe any methods used to assess certainty (or confidence) in the body of evidence for an outcome.",
    "16a	Describe the results of the search and selection process, from the number of records identified in the search to the number of studies included in the review, ideally using a flow diagram.\n16b	Cite studies that might appear to meet the inclusion criteria, but which were excluded, and explain why they were excluded.",
    "17	Cite each included study and present its characteristics.",
    "18	Present assessments of risk of bias for each included study.",
    "19	For all outcomes, present, for each study: (a) summary statistics for each group (where appropriate) and (b) an effect estimate and its precision (e.g. confidence/credible interval), ideally using structured tables or plots.",
    "20a	For each synthesis, briefly summarise the characteristics and risk of bias among contributing studies.\n20b	Present results of all statistical syntheses conducted. If meta-analysis was done, present for each the summary estimate and its precision (e.g. confidence/credible interval) and measures of statistical heterogeneity. If comparing groups, describe the direction of the effect.\n20c	Present results of all investigations of possible causes of heterogeneity among study results.\n20d	Present results of all sensitivity analyses conducted to assess the robustness of the synthesized results.",
    "21	Present assessments of risk of bias due to missing results (arising from reporting biases) for each synthesis assessed.",
    "22	Present assessments of certainty (or confidence) in the body of evidence for each outcome assessed.",
    "23a	Provide a general interpretation of the results in the context of other evidence.\n23b	Discuss any limitations of the evidence included in the review.\n23c	Discuss any limitations of the review processes used.\n23d	Discuss implications of the results for practice, policy, and future research.",
    "24a	Provide registration information for the review, including register name and registration number, or state that the review was not registered.\n24b	Indicate where the review protocol can be accessed, or state that a protocol was not prepared.\n24c	Describe and explain any amendments to information provided at registration or in the protocol.",
    "25	Describe sources of financial or non-financial support for the review, and the role of the funders or sponsors in the review.",
    "26	Declare any competing interests of review authors.",
    "27	Report which of the following are publicly available and where they can be found: template data collection forms; data extracted from included studies; data used for all analyses; analytic code; any other materials used in the review.",
]

@click.group()
def cli():
    pass

@cli.command()
def add_complete_register():
    i = 0
    for item in itemList.keys():
        desc = itemDescription[i]
        confirmed = False
        while(not confirmed):
            print("="*60+f"\n>>\t{item}\n")
            temp = input(f"\t\tDescrición: \n{desc}\n\n Ingrese información\n")
            test = input("Continuar con el siguiente registro y/n\n")
            if test == "y":
                itemList[item] = temp
                confirmed = True
        i += 1
    print(itemList)

def clean_list():
    for item in itemList.keys():
        itemList[item] = ""

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
@click.argument('key_file')
def create_table(log_file,key_file,this_host,this_database):
    usr , passwd = read_log_info(log_file,key_file)

    try:
        dbcnx = sql.connect(user=usr,
                            password=passwd,
                            host=this_host,
                            port=3306,
                            database=this_database)
        if dbcnx.is_connected():
            db_Info = dbcnx.get_server_info()
            print(f"Connected to MariaDB version {db_Info}")
            # cmd = "CREATE TABLE entries(id INT, name TEXT);"
            # # for item in itemList.keys():
            #     cmd += f"'{item}' TEXT,"
            # cmd = cmd[:-1]+");"
            # cursor = dbcnx.cursor()
            # cursor.execute(cmd)
            # dbcnx.commit()
    except sql.Error as e:
        print("Error while connecting to MariaDB", e)
    else:
        # if dbcnx.is_connected():
        # cursor.close()
        dbcnx.close()
        print("MariaDB connection is close")

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
