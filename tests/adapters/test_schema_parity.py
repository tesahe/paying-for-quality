"""The SQLite and Postgres schemas (base + migrations) must declare the same tables and columns (DC-1)."""

import re

from paying_for_quality.adapters.storage.sql_repository import TABLES, full_schema, load_migrations
from paying_for_quality.core.vocab import DOMAINS, Engagement, ProvenanceKind, RaterKind

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
    sqlite, postgres = tables_and_columns(full_schema("sqlite")), tables_and_columns(full_schema("postgres"))
    assert sqlite == postgres


def test_schema_covers_every_repository_table():
    assert set(tables_and_columns(full_schema("sqlite"))) == set(TABLES)


def test_postgres_enables_rls_on_every_table():
    sql = full_schema("postgres")
    for table in TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in sql


def test_both_dialects_have_the_same_numbered_migrations():
    assert [v for v, _ in load_migrations("sqlite")] == [v for v, _ in load_migrations("postgres")]
    assert [v for v, _ in load_migrations("sqlite")][0] == 2  # version 1 is the base schema


def test_vocabulary_checks_match_core():
    """The CHECK constraints on rate_observation list exactly the Core vocabularies."""
    for dialect in ("sqlite", "postgres"):
        sql = full_schema(dialect)
        for column, values in (
            ("domain", DOMAINS),
            ("engagement", {e.value for e in Engagement}),
            ("rater_kind", {k.value for k in RaterKind}),
            ("provenance_kind", {p.value for p in ProvenanceKind}),
        ):
            checks = re.findall(rf"{column} TEXT NOT NULL CHECK \({column} IN \((.*?)\)\)", sql, re.S)
            assert checks, (dialect, column)
            for check in checks:
                assert set(re.findall(r"'(\w+)'", check)) == set(values), (dialect, column)
