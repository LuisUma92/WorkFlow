from re import M
from . import pyprisma as wfp

# import pandas as pd
# import numpy as np

# import subprocess


def to_retrieved():
    """
    Inspect each element from bib_entries and opens its url link to inspect if
    it is worthy to retrieve.

    If it's not worthy, it calls set_rationale, and set retrived as -1

    If article is retrived, it ask for tags calling set_article_tags

    Requires:
      - [prismadb_tags.tag]

    Requires:
      - prismadb_bib_entries.id
      - prismadb_keywords.id
    """
    pass


def save_current_values(cmd):
    """
    Use a INSET INTO cmd, if all goes well returns true
    """
    NoMore = False
    if wfp.get_verbose() > 2:
        print(cmd)
    ans = wfp.communicate_db(cmd)
    if wfp.get_verbose() > 2:
        print(ans)
    if ans.equals(wfp.AGAIN):
        print("Your are trying again")
    else:
        NoMore = True
    return NoMore


def create_unique_text_entry(
        tag=False,
        rationale=False
        ):
    """
    Create a new entry on prismadb_rationale_list
    or prismadb_tags
    """
    db = ""
    field = ""
    msn = "Write your new "
    MaxLength = 0
    if tag and rationale:
        raise Exception("There is no reason for set multiple entries at once")
    elif tag:
        db = "prismadb_tags"
        field = "tag"
        MaxLength = 200
        msn += "tag\n"
        if wfp.get_verbose() > 2:
            print(db)
    elif rationale:
        db = "prismadb_rationale_list"
        field = "rationale_argument"
        MaxLength = 500
        msn += "rational\n"
        if wfp.get_verbose() > 2:
            print(db)
    else:
        raise Exception("No table selected")
    More = True
    while More:
        new_text = input(msn)
        if len(new_text) > MaxLength:
            print("your text is too long, please try again")
            continue
        else:
            cmd = f"INSERT INTO {db} ({field}) VALUES ('{new_text}');"
            More = not save_current_values(cmd)


def get_and_update_list(db):
    """
    Ask to the database for all entries on db and display them.
    Then, proced to ask to the user if want to update the current list.

    Return a dataframe with all entries
    """
    all_enlisted = False
    new_item = True

    while not all_enlisted:
        cmd = f"SELECT * FROM {db};"

        item_list = wfp.communicate_db(cmd, True)

        if item_list.empty:
            new_item = True
        else:
            print(item_list)
            test = input("Want to add new item? (y/n)") or 'y'
            if test == "y":
                new_item = True
            else:
                all_enlisted = True
                continue

        if new_item:
            if db == "prismadb_rationale_list":
                create_unique_text_entry(rationale=True)
            elif db == "prismadb_tags":
                create_unique_text_entry(tag=True)
            else:
                print(f"There is not implementation for {db}")
            new_item = False
    return item_list


def set_rationale(keywords_id, article_id):
    """
    Present rationale_argument list and set prismadb_review_rationale.

    Calls create_unique_text_entry if the correct argument doesn't exists

    Requires:
      - prismadb_keywords.id
      - prismadb_bib_entries.id
    Searches for:
      - prismadb_rationale_list.id
      - [prismadb_rationale_list.rationale_argument]
    """
    tabledb = "prismadb_rationale_list"
    db = "prismadb_review_rationale"

    rationale_list = get_and_update_list(tabledb)

    all_enlisted = False
    while not all_enlisted:
        print(rationale_list)
        rationale_id = input("\n\tWrite the rationale id number\n")

        try:
            rationale_id = int(rationale_id)
        except ValueError:
            print("Your options is not an integer\nTry again")
            continue
        selected_rationale = rationale_list.at[
                rationale_id-1,
                "rationale_argument"
                ]
        print("You have selected", selected_rationale)
        test = input("Please confirm selection (y/n)") or "y"
        if test != "y":
            continue
        else:
            cmd = f"INSERT INTO {db}"
            cmd += " (id_article_id, id_key_id,id_rationale_id) VALUES "
            cmd += f"('{article_id}','{keywords_id}','{rationale_id}');"
            all_enlisted = save_current_values(cmd)


def set_article_tags(article_id):
    """
    Present tag list and set prismadb_article_tags.

    Calls create_unique_text_entry if desire tag doesn't exist.

    Requires:
      - prismadb_bib_entries.id
    Searches for:
      - prismadb_tags.id
      - [prismadb_tags.tag]
    """
    db = "prismadb_article_tags"
    tabledb = "prismadb_tags"
    tag_list = get_and_update_list(tabledb)

    all_enlisted = False
    while not all_enlisted:
        print(tag_list)
        tag_id = input("\n\tWrite the rationale id number\n")

        try:
            tag_id = int(tag_id)
        except ValueError:
            print("Your options is not an integer\nTry again")
            continue
        selected_tag = tag_list.at[
                tag_id-1,
                "tag"
                ]
        print("You have selected", selected_tag)
        test = input("Please confirm selection (y/n)") or "y"
        if test != "y":
            continue
        else:
            cmd = f"INSERT INTO {db}"
            cmd += " (id_article_id, id_tag_id) VALUES "
            cmd += f"('{article_id}','{tag_id}');"
            save_current_values(cmd)
        test = input("Do you want to add more tags (y/n)") or "y"
        if test != "y":
            continue
        else:
            all_enlisted = True
