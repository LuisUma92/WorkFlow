"""0004_item_item_type — add Item.item_type nullable column.

Pre-existing global DBs lack ``item.item_type`` (model declares
``Mapped[str | None]`` with default None). ``workflow evaluations list``
joins through Item and crashes with
``no such column: item.item_type`` until this column is in place.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

revision: str = "0004_item_item_type"
description: str = "Add nullable item.item_type column."
base: str = "global"


def upgrade(connection: Connection) -> None:
    rows = connection.exec_driver_sql("PRAGMA table_info(item)").fetchall()
    cols = {r[1] for r in rows}
    if "item_type" not in cols:
        connection.exec_driver_sql(
            "ALTER TABLE item ADD COLUMN item_type VARCHAR(20)"
        )
