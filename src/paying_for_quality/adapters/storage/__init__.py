"""Storage adapters. `open_repository` picks one from the DATABASE_URL scheme."""

from __future__ import annotations

from ...core.errors import ConfigError
from .sql_repository import SqlRepository


def open_repository(url: str, schema: str = "pfq") -> SqlRepository:
    if url.startswith(("postgresql://", "postgres://")):
        from .postgres_repository import PostgresRepository

        return PostgresRepository(url, schema)
    if url.startswith("sqlite:///"):
        from .sqlite_repository import SqliteRepository

        return SqliteRepository(url.removeprefix("sqlite:///"))
    raise ConfigError("DATABASE_URL must start with postgresql:// or sqlite:///")
