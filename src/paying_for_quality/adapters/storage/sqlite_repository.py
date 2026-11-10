"""SQLite repository: local runs, offline demos and automated tests. Standard library only."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .sql_repository import SqlRepository, load_schema


class SqliteRepository(SqlRepository):
    dialect = "sqlite"

    def __init__(self, path: str | Path) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA foreign_keys = ON")
        super().__init__(conn)

    def _ts(self, value: datetime) -> Any:
        return value.isoformat()

    def _num(self, value: Decimal | None) -> Any:
        return None if value is None else float(value)

    def apply_schema(self) -> None:
        self._conn.executescript(load_schema("sqlite"))
        self._conn.commit()
