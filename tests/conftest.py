"""Shared fixtures. The `repo` fixture runs every repository test against SQLite, and also against
Supabase Postgres when run with `pytest -m supabase` and PFQ_TEST_DATABASE_URL is set."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from paying_for_quality.adapters.storage.raw_store import FileRawStore
from paying_for_quality.adapters.storage.sqlite_repository import SqliteRepository


def _env_value(key: str) -> str | None:
    """Read a key from the environment or the main checkout's .env, without printing it."""
    if os.environ.get(key):
        return os.environ[key]
    for candidate in (Path.cwd() / ".env", *(p / ".env" for p in Path.cwd().parents)):
        if candidate.is_file():
            for line in candidate.read_text().splitlines():
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


@pytest.fixture(params=["sqlite", pytest.param("postgres", marks=pytest.mark.supabase)])
def repo(request, tmp_path):
    if request.param == "sqlite":
        repository = SqliteRepository(tmp_path / "test.db")
        repository.apply_schema()
        yield repository
        repository.close()
        return
    url = _env_value("PFQ_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PFQ_TEST_DATABASE_URL is not set")
    from paying_for_quality.adapters.storage.postgres_repository import PostgresRepository

    repository = PostgresRepository(url, schema=f"pfq_test_{uuid.uuid4().hex[:8]}")
    repository.apply_schema()
    try:
        yield repository
    finally:
        repository.drop_schema()
        repository.close()


@pytest.fixture
def raw_store(tmp_path):
    return FileRawStore(tmp_path / "raw")


class StepClock:
    """Deterministic clock: each call is one minute after the previous one."""

    def __init__(self) -> None:
        self.now = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        self.now += timedelta(minutes=1)
        return self.now


@pytest.fixture
def clock():
    return StepClock()
