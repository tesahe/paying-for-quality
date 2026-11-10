"""Schema migrations (AC-S3.5): an existing version-1 database is upgraded in place, without data loss."""

import sqlite3

from paying_for_quality.adapters.storage.sql_repository import load_schema
from paying_for_quality.adapters.storage.sqlite_repository import SqliteRepository


def columns(path):
    conn = sqlite3.connect(path)
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        return {t: [(c[1], c[2], c[3]) for c in conn.execute(f"PRAGMA table_info({t})")] for t in tables}
    finally:
        conn.close()


def make_v1_database(path):
    """A database as Sprint 2 left it: base schema only, with a collected posting."""
    conn = sqlite3.connect(path)
    conn.executescript(load_schema("sqlite"))
    conn.execute(
        "INSERT INTO source (slug, kind, board, company, segment, terms_checked) "
        "VALUES ('ashby-acme', 'ashby', 'acme', 'Acme', 'staff', 1)"
    )
    conn.execute(
        "INSERT INTO raw_posting (source_id, external_id, content_hash, raw_path, first_seen_at, last_seen_at) "
        "VALUES (1, 'job-1', 'h1', 'ashby-acme/h1.json', '2026-11-01', '2026-11-01')"
    )
    conn.commit()
    conn.close()


def test_version_1_database_is_migrated_without_data_loss(tmp_path):
    old, fresh = tmp_path / "old.db", tmp_path / "fresh.db"
    make_v1_database(old)

    repo = SqliteRepository(old)
    assert repo.schema_version() == 1
    assert repo.apply_schema() == [2]
    assert repo.schema_version() == 2
    assert repo.count_rows("raw_posting") == 1
    assert repo.count_rows("rate_observation") == 0
    repo.close()

    new = SqliteRepository(fresh)
    new.apply_schema()
    new.close()
    assert columns(old) == columns(fresh)  # an upgraded database matches a freshly created one


def test_second_run_is_a_no_op(tmp_path):
    repo = SqliteRepository(tmp_path / "db.sqlite")
    assert repo.apply_schema() == [2]  # fresh: base schema, then every migration
    assert repo.apply_schema() == []
    assert repo.schema_version() == 2
    assert repo.count_rows("schema_version") == 1
    repo.close()


def test_failed_migration_leaves_the_previous_version(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    make_v1_database(path)
    from paying_for_quality.adapters.storage import sql_repository

    monkeypatch.setattr(
        sql_repository, "load_migrations",
        lambda dialect: [(2, "CREATE TABLE half_done (id INTEGER);\nTHIS IS NOT SQL;")],
    )
    repo = SqliteRepository(path)
    try:
        repo.apply_schema()
    except sqlite3.Error:
        pass
    else:  # pragma: no cover
        raise AssertionError("the broken migration should fail")
    assert repo.schema_version() == 1
    assert "half_done" not in columns(path)
    repo.close()
