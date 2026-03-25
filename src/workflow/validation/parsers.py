from __future__ import annotations

from pathlib import Path

import yaml

_MAX_FILE_SIZE = 1_048_576  # 1 MB


def parse_md_frontmatter(filepath: Path) -> dict | None:
    """Extract YAML frontmatter from a Markdown file.

    Reads text between the first pair of '---' markers at the top of the file.
    Returns the parsed dict, or None if no frontmatter block is found.
    """
    if filepath.stat().st_size > _MAX_FILE_SIZE:
        return None
    try:
        text = filepath.read_text(encoding="utf-8")
    except OSError:
        return None

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    end_index = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = i
            break

    if end_index is None:
        return None

    yaml_block = "\n".join(lines[1:end_index])
    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None

    return parsed


def parse_tex_metadata(filepath: Path) -> dict | None:
    """Extract commented YAML metadata from a LaTeX file.

    Reads lines between '% ---' markers, strips leading '% ' prefix,
    then parses the result as YAML.
    Returns the parsed dict, or None if no metadata block is found.
    """
    if filepath.stat().st_size > _MAX_FILE_SIZE:
        return None
    try:
        text = filepath.read_text(encoding="utf-8")
    except OSError:
        return None

    lines = text.splitlines()
    start_index = None
    end_index = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "% ---":
            if start_index is None:
                start_index = i
            else:
                end_index = i
                break

    if start_index is None or end_index is None:
        return None

    yaml_lines = []
    for line in lines[start_index + 1 : end_index]:
        if line.startswith("% "):
            yaml_lines.append(line[2:])
        elif line.strip() == "%":
            yaml_lines.append("")
        else:
            yaml_lines.append(line)

    yaml_block = "\n".join(yaml_lines)
    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None

    return parsed
