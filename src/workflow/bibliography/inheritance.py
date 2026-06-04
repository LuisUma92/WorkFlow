"""Biblatex crossref/xdata field inheritance (Wave A — A4-5, ADR-0019).

Implements biblatex's default data-inheritance rules (the ``biblatex.def``
``\\DeclareDataInheritance`` setup, biblatex manual §4.5.3) used when an entry
is exported with ``--resolve-xref``. The model stores relations only
(``bib_relation``); inheritance is resolved at export time (decision D2).

Two mechanisms are supported:

- **crossref**: the parent's fields are inherited by the child with the
  biblatex field *remapping* rules (e.g. a ``@book`` parent's ``title`` becomes
  the child ``@inbook``'s ``booktitle``). Some fields are dropped (``noinherit``).
- **xdata**: the referenced entry's fields are copied verbatim (same field
  name, no remapping) — xdata is biblatex's plain field-sharing mechanism.

``xref`` and ``related`` do **not** trigger field inheritance in biblatex; they
are pointers only, so this module leaves them untouched.

Inheritance is one level deep here (child ← parent). Recursive grandparent
inheritance is intentionally out of scope.
"""

from __future__ import annotations

# Fields never inherited under any source/target pair (biblatex global default).
GLOBAL_NOINHERIT: frozenset[str] = frozenset({
    "ids",
    "crossref",
    "xref",
    "entryset",
    "execute",
    "label",
    "options",
    "presort",
    "related",
    "relatedoptions",
    "relatedstring",
    "relatedtype",
    "shorthand",
    "shorthandintro",
    "sortkey",
    "xdata",
})

# One \DeclareDataInheritance block: parent fields remapped to child fields when
# the (source_type, target_type) pair matches. A remap target of "" means the
# field is dropped (noinherit) for that pair. Rules are applied in order; a
# later matching rule overrides an earlier one for the same parent field — so
# the more specific mv* → in* mappings (which appear later) win.
_InheritanceRule = tuple[frozenset[str], frozenset[str], dict[str, str]]

_DROP = ""  # sentinel: field is not inherited for this pair

_RULES: tuple[_InheritanceRule, ...] = (
    # book/mvbook → inbook family: parent title becomes child booktitle.
    (
        frozenset({"mvbook", "book"}),
        frozenset({"inbook", "bookinbook", "suppbook"}),
        {
            "title": "booktitle",
            "subtitle": "booksubtitle",
            "titleaddon": "booktitleaddon",
            "shorttitle": _DROP,
            "sorttitle": _DROP,
            "indextitle": _DROP,
            "indexsorttitle": _DROP,
        },
    ),
    # mvbook → book/inbook family: parent title becomes child maintitle.
    (
        frozenset({"mvbook"}),
        frozenset({"book", "inbook", "bookinbook", "suppbook"}),
        {
            "title": "maintitle",
            "subtitle": "mainsubtitle",
            "titleaddon": "maintitleaddon",
            "shorttitle": _DROP,
            "sorttitle": _DROP,
            "indextitle": _DROP,
            "indexsorttitle": _DROP,
        },
    ),
    # mvcollection/mvreference → collection/reference family: title → maintitle.
    (
        frozenset({"mvcollection", "mvreference"}),
        frozenset({
            "collection", "reference",
            "incollection", "inreference", "suppcollection",
        }),
        {
            "title": "maintitle",
            "subtitle": "mainsubtitle",
            "titleaddon": "maintitleaddon",
            "shorttitle": _DROP,
            "sorttitle": _DROP,
            "indextitle": _DROP,
            "indexsorttitle": _DROP,
        },
    ),
    # collection/reference → incollection family: title → booktitle.
    (
        frozenset({"collection", "reference"}),
        frozenset({"incollection", "inreference", "suppcollection"}),
        {
            "title": "booktitle",
            "subtitle": "booksubtitle",
            "titleaddon": "booktitleaddon",
            "shorttitle": _DROP,
            "sorttitle": _DROP,
            "indextitle": _DROP,
            "indexsorttitle": _DROP,
        },
    ),
    # mvproceedings → proceedings/inproceedings: title → maintitle.
    (
        frozenset({"mvproceedings"}),
        frozenset({"proceedings", "inproceedings"}),
        {
            "title": "maintitle",
            "subtitle": "mainsubtitle",
            "titleaddon": "maintitleaddon",
            "shorttitle": _DROP,
            "sorttitle": _DROP,
        },
    ),
    # proceedings → inproceedings: title → booktitle.
    (
        frozenset({"proceedings"}),
        frozenset({"inproceedings"}),
        {
            "title": "booktitle",
            "subtitle": "booksubtitle",
            "titleaddon": "booktitleaddon",
            "shorttitle": _DROP,
            "sorttitle": _DROP,
        },
    ),
    # periodical → article/suppperiodical: title → journaltitle.
    (
        frozenset({"periodical"}),
        frozenset({"article", "suppperiodical"}),
        {
            "title": "journaltitle",
            "subtitle": "journalsubtitle",
            "shorttitle": _DROP,
            "sorttitle": _DROP,
            "indextitle": _DROP,
            "indexsorttitle": _DROP,
        },
    ),
)


def _remap_for(parent_type: str, child_type: str) -> dict[str, str]:
    """Merge all matching \\DeclareDataInheritance remaps (later rule wins)."""
    merged: dict[str, str] = {}
    p = (parent_type or "").lower()
    c = (child_type or "").lower()
    for sources, targets, remap in _RULES:
        if p in sources and c in targets:
            merged.update(remap)
    return merged


def inherit_crossref(
    parent_type: str,
    child_type: str,
    parent_fields: dict[str, str],
) -> dict[str, str]:
    """Return the fields a crossref child inherits from its parent.

    Applies the biblatex field remapping for the (parent_type, child_type)
    pair plus the global same-name default for every other field. Fields in
    :data:`GLOBAL_NOINHERIT` and fields the rules mark ``_DROP`` are excluded.
    The caller is responsible for child-wins precedence (only fill fields the
    child lacks).
    """
    remap = _remap_for(parent_type, child_type)
    out: dict[str, str] = {}
    for field, value in parent_fields.items():
        if field in GLOBAL_NOINHERIT:
            continue
        if field in remap:
            target = remap[field]
            if target == _DROP:
                continue
            out[target] = value
        else:
            out[field] = value  # same-name inheritance (global default)
    return out


def inherit_xdata(parent_fields: dict[str, str]) -> dict[str, str]:
    """Return the fields an xdata reference contributes (verbatim, same name).

    xdata is biblatex's plain field-sharing mechanism: no remapping, only the
    global noinherit set is excluded. Caller applies child-wins precedence.
    """
    return {
        field: value
        for field, value in parent_fields.items()
        if field not in GLOBAL_NOINHERIT
    }
