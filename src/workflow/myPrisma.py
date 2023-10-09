
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

@click.group()
def cli():
    pass

@cli.command()
def add_register():
    for item in itemList.keys():
        confirmed = False
        while(not confirmed):
            temp = input(f"Ingrese {item}\n")
            test = input("Continuar con el siguiente registro y/n\n")
            if test == "y":
                itemList[item] = temp
                confirmed = True

    print(itemList)

def clean_list():
    for item in itemList.keys():
        itemList[item] = ""

if __name__ == '__main__':
    cli()
