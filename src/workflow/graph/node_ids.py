"""Helpers for the graph node-id convention (``note:<int>``)."""

NOTE_PREFIX = "note:"


def is_note(node_id: str) -> bool:
    """True if *node_id* follows the ``note:<int>`` convention (prefix check only)."""
    return node_id.startswith(NOTE_PREFIX)


def parse_note_id(node_id: str) -> int | None:
    """Return the integer note id, or *None* if *node_id* is not a valid ``note:<int>``.

    Returns None for:
    - ids that do not start with ``note:``
    - ids whose suffix is empty or non-numeric (e.g. ``note:abc``, ``note:``)

    Negative integers (``note:-5``) parse and are returned as-is; a DB lookup for
    a negative id simply returns no rows, so callers need no extra guard.
    """
    if not node_id.startswith(NOTE_PREFIX):
        return None
    suffix = node_id[len(NOTE_PREFIX):]
    try:
        return int(suffix)
    except ValueError:
        return None
