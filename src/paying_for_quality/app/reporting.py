"""Named, committed SQL analyses. Each query reads only Core-accepted rows."""

from __future__ import annotations

from importlib import resources

from ..core.errors import PfqError
from ..core.ports import QueryResult, Repository

_QUERIES = resources.files("paying_for_quality.queries")


def available_queries() -> list[str]:
    return sorted(p.name.removesuffix(".sql") for p in _QUERIES.iterdir() if p.name.endswith(".sql"))


def run_query(repo: Repository, name: str) -> QueryResult:
    names = available_queries()
    if name not in names:
        raise PfqError(f"unknown query '{name}'. Available: {', '.join(names)}")
    return repo.query(_QUERIES.joinpath(f"{name}.sql").read_text())
