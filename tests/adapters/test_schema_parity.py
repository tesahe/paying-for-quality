"""The SQLite and Postgres schemas must declare the same tables and columns (DC-1)."""

import re

from paying_for_quality.adapters.storage.sql_repository import TABLES, load_schema

CONSTRAINT_WORDS = {"UNIQUE", "PRIMARY", "FOREIGN", "CHECK", "CONSTRAINT"}


def tables_and_columns(sql: str) -> dict[str, list[str]]:
    tables = {}
    for name, body in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", sql, re.S):
        columns = []
        for line in body.strip().splitlines():
            first = line.strip().split()[0]
            if first.upper() not in CONSTRAINT_WORDS:
                columns.append(first)
        tables[name] = columns
    return tables


def test_both_schemas_declare_the_same_tables_and_columns():
    sqlite, postgres = tables_and_columns(load_schema("sqlite")), tables_and_columns(load_schema("postgres"))
    assert sqlite == postgres


def test_schema_covers_every_repository_table():
    assert set(tables_and_columns(load_schema("sqlite"))) == set(TABLES)


def test_postgres_enables_rls_on_every_table():
    sql = load_schema("postgres")
    for table in TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in sql
