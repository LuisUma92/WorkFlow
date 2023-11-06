import workflow.pyprisma as wfp
import click

@click.command()
@click.option("--verbose",default=1,help="Set verbose level")
def cli(verbose):
    wfp.init(verbose)
    more = True
    keywords = wfp.get_newtable("keyword",{"keyword":["keyword_list"]})
    option = 0
    while more:
        msn = 'Enter the number of keyword list to review\n'
        for i in range(len(keywords)):
            msn += f'\t{i} - {keywords[i][0]}\n'
        try:
            option = int(input(msn))
        except ValueError:
            print("invalid option")
        else:
            more = False
    # tables = wfp.structure.keys()
    main_table = "bib_entries"
    request = {main_table:["id","title","url"]}
    joins = [{
        "reviewed":"article_id",
        "bib_entries":"id"
    }]
    key_id = wfp.get_value("key_id","keyword",columns=["keyword_list"],values=[keywords[option][0]])
    conditions = [{
        "junction":"AND",
        "table":"reviewed",
        "column":"key_id",
        "value":key_id
    }]
    to_review = wfp.get_newtable(main_table,request,join_conditions=joins,conditions=conditions)
    print(to_review)
    while more:
        test = input("Press enter to exit...") or "exit"
        if test == "exit":
            more = False
        pass

