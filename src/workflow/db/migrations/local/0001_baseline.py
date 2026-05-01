"""0001_baseline — local DB (slipbox.db) baseline (ITEP-0010).

No-op upgrade. Stamps the current LocalBase schema as head so any future
LocalBase migration ships through the runner from a known starting point.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0001_baseline"
description: str = "Stamp current slipbox.db schema as baseline."


def upgrade(connection: Connection) -> None:
    """No-op: schema already matches model definitions at this revision."""
    return None
