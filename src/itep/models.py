from itep.structure import (
    ProjectModel,
    GeneralDirectory,
)
from itep.defaults import (
    DEF_ABS_PARENT_DIR,
    DEF_TEX_CONFIG,
)


class GeneralProject(ProjectModel):
    name = "general"
    parent = DEF_ABS_PARENT_DIR
    root = "{code}-{name}"
    patterns = {
        "numbering": "^[0-9]{2}",
        "initials": "^[A-Z]{2}",
    }
    main_topics = DEF_ABS_PARENT_DIR / GeneralDirectory.BIB
    tree = [
        "bib",
        "config",
        "img",
        "projects",
        "tex",
        "tex/000-0-Glossaries",
        "tex/000-1-Summaries",
        "tex/000-2-Notes",
        "tex/{t_idx:03}-{t_name}",  #  for T in topics
    ]
    links = {
        "config": DEF_TEX_CONFIG,
        "bib/": {
            "{main_t}": "{parent_dir}/{bib}/{main_t}",
            "{t_idx:03d}-{t_name}": "{parent_dir}/{bib}/{main_t}/{t_name}",
        },  # BIB for T in topics
        "img/": {
            "{b_dir}": "{parent_dir}/{img}/{b_dir}",
            "{root}": "{parent_dir}/{img}/{root}",
        },  # IMG for B in books
        "tex/{t_idx}-{t_name}": {
            "{b_dir}-{ch:02d}": "{parent_dir}/{exe}/{b_dir}/C{ch:02d}",
        },  # EXE for B in books
    }


class LectureProject(ProjectModel):
    name = "lecture"
    parent = DEF_ABS_PARENT_DIR / GeneralDirectory.LEC
    root = "{institution}-{code}"
    patterns = {
        "numbering": "^[0-9]{4}",
        "initials": "^[A-Z]{2}",
    }
    main_topics = DEF_ABS_PARENT_DIR
    tree = [
        "admin",
        "eval",
        "eval/config",
        "eval/img",
        "eval/tex",
        "eval/tex/{t_idx:03d}-{t_name}",  # ->mainT for T in topics
        "lect",
        "lect/bib",
        "lect/config",
        "lect/img",
        "lect/svg",
        "lect/tex",
        "lect/tex/{t_idx_03d}-{t_name}",  # ->mainT for T in topics
    ]
    links = {
        "eval/config": DEF_TEX_CONFIG,
        "eval/img/": {
            "{b_dir}": "{def_parent_dir}/{img}/{b_dir}",
            "{main_t}": "{def_parent_dir}/{img}/{main_t}",
        },  # IMG for B in books
        "eval/tex/{t_idx:03d}-{t_name}": {
            "{b_dir}-{ch:02d}": "{def_parent_dir}/{exe}/{b_dir}/{ch:02d}",
        },  # EXE for B in books
        "lect/config": DEF_TEX_CONFIG,
        "lect/bib/": {
            "{main_bib}": "{def_parent_dir}/{bib}/{main_bib}",
            "{t_idx:03d}-{t_name}": "{def_parent_dir}/{bib}/{main_bib}/{t_name}",
        },  # BIB for T in topics
        "lect/img/": {
            "{b_dir}": "{def_parent_dir}/{img}/{b_dir}",
            "{main_t}": "{def_parent_dir}/{img}/{main_t}",
        },  # IMG for B in books
        "lect/tex/{t_idx:03d}-{t_name}": {
            "{b_dir}-{ch:02d}": "{def_parent_dir}/{exe}/{b_dir}/{ch:02d}",
            "notes": "{def_parent_dir}/{main_t}/tex/{t_idx:03d}-{t_name}",
        },  # EXE for B in books
    }
