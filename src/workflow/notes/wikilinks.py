"""Wikilink regex patterns owned by workflow.notes.

These were lifted from latexzettel.infra.regexes to remove the dependency on
the deprecated latexzettel shim layer (LZK-0004 / ADR-0014).
"""
from __future__ import annotations

import re
from typing import Pattern

# [[Note Name]] — plain reference
WIKILINK_NOTE_RE: Pattern[str] = re.compile(r"\[\[([^{#\]\|}]+)\]\]")

# [[Note Name#anchor]] or [[Note Name#^block]]
WIKILINK_NOTE_LABEL_RE: Pattern[str] = re.compile(
    r"\[\[([^{#\]\|}]+)\#\^?([^]]+)\]\]"
)

# [[Note Name|Display Text]]
WIKILINK_NOTE_TEXT_RE: Pattern[str] = re.compile(
    r"\[\[([^{#\]\|}]+)\|([^]]+)\]\]"
)

# [[Note Name#anchor|Display Text]] or [[Note Name#^block|Display Text]]
WIKILINK_NOTE_LABEL_TEXT_RE: Pattern[str] = re.compile(
    r"\[\[([^{#\]\|}]+)\#\^?([^|]+)\|([^]]+)\]\]"
)
