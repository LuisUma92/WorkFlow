from re import T
from click.decorators import R
import workflow.pyprisma as wfp
# import pandas as pd
import numpy as np
import click
# import os
import subprocess


def get_text(info = "this information"):
    msn = ""
    right_size = False
    while not right_size:
        msn = input("="*60+f"\nPlease write {info}. (Press enter to continue ...)\n\tCurrent information: {msn}\n")
        if len(msn.encode("utf-8")) < wfp.TEXT_MAX_BYTE_SIZE:
            right_size = True
        else:
            print("ERROR! Information length exceeds maximum length")
    return msn


@click.command()
@click.option("--verbose",default=1,help="Set verbose level")
def cli(verbose):
    wfp.init(verbose)
    more = True
    columnsNames = "keyword_list"
    keywords = wfp.get_newtable("keyword",{"keyword":[columnsNames]})
    option = 0
    while more:
        msn = 'Enter the number of keyword list to review\n'
        '''conditions display for option input'''
        for i in (range(len(keywords.index))):
            thisKWL = keywords.iloc[i,0]
            msn += f'\t{i} - {thisKWL}\n'
        try:
            option = int(input(msn))
        except ValueError:
            print("invalid option")
        else:
            more = False
    # tables = wfp.structure.keys()
    main_table = "bib_entries"
    requested_columns = ["id","title","url"]
    request = {main_table:requested_columns}
    joins = [{
        "reviewed":"article_id",
        "bib_entries":"id"
    }]
    key_id = wfp.get_value("key_id","keyword",columns=["keyword_list"],values=[keywords.iloc[option,0]])
    conditions = [
        {
            "junction":"AND",
            "table":"reviewed",
            "column":"key_id",
            "value":key_id
        },
        {
            "junction":"AND",
            "table":"reviewed",
            "column":"included",
            "value":0
        }
        ]
    to_review = wfp.get_newtable(
        main_table,request,
        join_conditions=joins,
        conditions=conditions
        )
    if verbose >= 4: print(to_review)
    more = True
    reviewed_columns = list(wfp.structure["reviewed"].keys())
    print(reviewed_columns)
    ucrproxy = "proxyucr.elogim.com/auth-meta/login.php?url="
    while more:
        for idx, row in to_review.iterrows():
            update_mns = f"UPDATE reviewed SET "
            update_condition = f"WHERE {reviewed_columns[1]} = {row[requested_columns[0]]} "
            msn = '-'*60+f'\n\t\tYou are reviewing:\n{row[requested_columns[1]]}'
            print(msn)
            subprocess.run(["firefox",row[requested_columns[2]]])

            # Inquire for adding current article
            test = input("Exclude this article? (n/y)") or "n"
            if test == "y":
                rationale = get_text("the rationale for exclude this article")
                update_mns += f"{reviewed_columns[4]} = "
                update_mns += '\"'+rationale+'\"'
                update_mns += f", {reviewed_columns[3]} = -1 "+update_condition
                wfp.comunicate_db(update_mns)
                continue

            # Included article and adding abstract
            update_mns += f"{reviewed_columns[3]} =  1"
            print("Use this proxy",ucrproxy)
            wfp.add_abstract(row[requested_columns[1]])

            # Inquire for retrieving current article
            while more:
                more = False
                test = input("Retrieve this article? (y/n)") or "y"
                if test == "y":
                    print("Use this proxy",ucrproxy)
                    input("Press enter to continue ...")
                    update_mns += f"{reviewed_columns[2]} = 0 "+update_condition
                elif test == "n":
                    update_mns += f"{reviewed_columns[2]} = -1 "+update_condition
                else:
                    print("Invalid option")
                    more = True
                if not more:
                    wfp.comunicate_db(update_mns)
            more = True


            test = input("\n\nContinue to next article (y/n)") or "y"
            if test != "y":
                break
        test = input("Press enter to exit...") or "exit"
        if test == "exit":
            more = False
        pass

