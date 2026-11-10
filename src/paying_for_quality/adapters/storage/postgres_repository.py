"""Postgres repository for Supabase (the system of record).

Connects with the server-side connection string, not the Supabase REST client, so SQL stays the
interface. All tables live in one schema (default "pfq") selected through search_path.
"""

from __future__ import annotations

import re

from ...core.errors import ConfigError, StorageError
from .sql_repository import SqlRepository, load_schema

_SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


class PostgresRepository(SqlRepository):
    dialect = "postgres"
    json_placeholder = "?::jsonb"

    def __init__(self, url: str, schema: str = "pfq") -> None:
        if not _SCHEMA_NAME.match(schema):
            raise ConfigError(f"invalid schema name {schema!r} (lowercase letters, digits, underscore)")
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - depends on install
            raise ConfigError('Postgres support is not installed: pip install -e ".[postgres]"') from exc
        try:
            # prepare_threshold=None: no server-side prepared statements, which Supabase's poolers may not keep.
            conn = psycopg.connect(url, connect_timeout=15, prepare_threshold=None)
        except psycopg.Error:
            # Never echo the driver message: it can include the host or user from DATABASE_URL.
            raise StorageError("could not connect to the database; check DATABASE_URL in .env") from None
        self.schema = schema
        super().__init__(conn)
        self._conn.execute(f'SET search_path TO "{schema}"')
        self._conn.commit()

    def _sql(self, sql: str) -> str:
        return super()._sql(sql).replace("?", "%s")

    def _apply_base_schema(self) -> None:
        with self._transaction():
            self._conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"')
            self._conn.execute(f'SET search_path TO "{self.schema}"')
            self._conn.execute(load_schema("postgres"))

    def _apply_migration(self, version: int, sql: str) -> None:
        with self._transaction():
            self._conn.execute(sql)
            self._conn.execute("UPDATE schema_version SET version = %s", (version,))

    def drop_schema(self) -> None:
        """Tests only: remove a throwaway schema."""
        with self._transaction():
            self._conn.execute(f'DROP SCHEMA IF EXISTS "{self.schema}" CASCADE')
