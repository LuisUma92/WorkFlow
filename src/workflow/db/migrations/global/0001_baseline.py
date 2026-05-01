"""0001_baseline — global DB baseline (ITEP-0010).

No-op upgrade. Stamps the current ITEP-0008-clean schema as head, so any
future migration ships through the runner from a known starting point.
Pre-Phase-0 DBs are out of scope; the only known live install was walked
through ITEP-0008 manually on 2026-04-29 before this baseline.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0001_baseline"
description: str = "Stamp ITEP-0008-clean global schema as baseline."


def upgrade(connection: Connection) -> None:
    """No-op: schema already matches model definitions at this revision."""
    return None
