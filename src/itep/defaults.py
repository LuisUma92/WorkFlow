from pathlib import Path

DEF_ABS_PARENT_DIR = Path("/home/luis/Documents/01-U/00-Fisica")
DEF_ABS_SRC_DIR = Path("/home/luis/.config/mytex")
DEF_TEX_CONFIG = {
    "0-packages.sty": "{src_dir}/sty/SetFormat.sty",
    "1-loyaut.sty": "{src_dir}/sty/SetLoyaut.sty",
    "2-commands.sty": "{src_dir}/sty/SetCommands.sty",
    "2-partial.sty": "{src_dir}/sty/PartialCommands.sty",
    "3-units.sty": "{src_dir}/sty/SetUnits.sty",
    "3-symbols.sty": "{src_dir}/sty/SetSymbols.sty",
    "5-profiles.sty": "{src_dir}/sty/SetProfiles.sty",
    "6-headers.sty": "{src_dir}/sty/SetHeaders.sty",
    "title.tex": "{src_dir}/template/title.tex",
    "instructions.tex": "{src_dir}/template/{institution}-PPI.tex",
}
