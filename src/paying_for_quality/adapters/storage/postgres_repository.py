"""Postgres repository for Supabase (the system of record).

Connects with the server-side connection string, not the Supabase REST client, so SQL stays the
interface. All tables live in one schema (default "pfq") selected through search_path.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from ...core.errors import ConfigError, StorageError
from .db_errors import classify, connect_with_retry
from .sql_repository import SqlRepository, load_schema

_SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


class GuardedConnection:
    """Wraps a psycopg connection so driver errors during an operation become StorageError.

    Every repository call reaches the database through execute/commit/rollback, so this one choke
    point covers them all. The message is classified (db_errors) and never repeats the driver text;
    the original exception stays chained as __cause__ for PFQ_DEBUG.
    """

    def __init__(self, conn: Any, driver_error: type[BaseException]) -> None:
        self._conn = conn
        self._driver_error = driver_error

    def _guard(self, call: Callable[[], Any]) -> Any:
        try:
            return call()
        except self._driver_error as exc:
            raise StorageError(f"database operation failed: {classify(exc).message}") from exc

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        return self._guard(lambda: self._conn.execute(*args, **kwargs))

    def commit(self) -> None:
        self._guard(self._conn.commit)

    def rollback(self) -> None:
        # Rolling back a dead connection fails too; that second error would hide the first one,
        # and the server has already discarded the transaction, so it is ignored.
        try:
            self._conn.rollback()
        except self._driver_error:
            pass

    def close(self) -> None:
        try:
            self._conn.close()
        except self._driver_error:
            pass


class PostgresRepository(SqlRepository):
    dialect = "postgres"
    json_placeholder = "?::jsonb"

    def __init__(self, url: str, schema: str = "pfq", connect_attempts: int = 3) -> None:
        if not _SCHEMA_NAME.match(schema):
            raise ConfigError(f"invalid schema name {schema!r} (lowercase letters, digits, underscore)")
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - depends on install
            raise ConfigError('Postgres support is not installed: pip install -e ".[postgres]"') from exc
        # prepare_threshold=None: no server-side prepared statements, which Supabase's poolers may not keep.
        # Only transient failures (timeout, no free slots) are retried; see db_errors for why.
        # The classified message never echoes the driver text, which can include the host or user.
        conn = connect_with_retry(
            lambda: psycopg.connect(url, connect_timeout=15, prepare_threshold=None),
            psycopg.Error,
            attempts=connect_attempts,
        )
        self.schema = schema
        super().__init__(GuardedConnection(conn, psycopg.Error))
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
