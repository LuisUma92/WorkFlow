"""Zettel ID generation — stdlib-only NanoID equivalent.

Generates random zettel IDs using secrets.choice over the NanoID URL-safe
alphabet (A-Za-z0-9_-). No external dependency required.

Public API
----------
generate_zettel_id(length: int = 12) -> str
"""

from __future__ import annotations

import secrets

__all__ = ["generate_zettel_id", "ZETTEL_ID_ALPHABET", "DEFAULT_LENGTH", "MIN_LENGTH", "MAX_LENGTH"]

ZETTEL_ID_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    "_-"
)
DEFAULT_LENGTH = 12
MIN_LENGTH = 8
MAX_LENGTH = 21


def generate_zettel_id(length: int = DEFAULT_LENGTH) -> str:
    """Generate a random zettel_id matching ``^[A-Za-z0-9_-]{8,21}$``.

    Args:
        length: Number of characters. Must be between 8 and 21 (inclusive).

    Returns:
        A cryptographically random string of *length* characters drawn from
        the NanoID URL-safe alphabet.

    Raises:
        ValueError: If *length* is outside the valid range [8, 21].
    """
    if not (MIN_LENGTH <= length <= MAX_LENGTH):
        raise ValueError(
            f"length must be between {MIN_LENGTH} and {MAX_LENGTH}, got {length}"
        )
    return "".join(secrets.choice(ZETTEL_ID_ALPHABET) for _ in range(length))
