"""Ports: what the use cases need from the outside world. Adapters implement these."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Protocol, Sequence

from .entities import ExtractionCandidate, RawPostingDoc, SourceInfo, ValidationResult


class PostingSource(Protocol):
    def list_postings(self) -> Iterable[RawPostingDoc]: ...


class Extractor(Protocol):
    name: str
    prompt_version: str

    def extract(self, doc: RawPostingDoc) -> ExtractionCandidate: ...


class RawStore(Protocol):
    def put(self, source_slug: str, digest: str, content: bytes) -> str:
        """Store content; return the path to record in raw_posting.raw_path."""
        ...

    def get(self, path: str) -> bytes: ...


@dataclass(frozen=True)
class PendingRaw:
    raw_posting_id: int
    source_slug: str
    raw_path: str


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]


class Repository(Protocol):
    def apply_schema(self) -> None: ...

    def upsert_source(self, source: SourceInfo) -> int: ...

    def start_collection_run(self, source_id: int, started_at: datetime) -> int: ...

    def finish_collection_run(
        self, run_id: int, finished_at: datetime, status: str, n_new: int, n_changed: int, n_unchanged: int,
        error: str | None = None,
    ) -> None: ...

    def find_raw_posting(self, source_id: int, external_id: str, digest: str) -> int | None: ...

    def has_listing(self, source_id: int, external_id: str) -> bool: ...

    def insert_raw_posting(
        self, source_id: int, doc: RawPostingDoc, digest: str, raw_path: str, seen_at: datetime
    ) -> int: ...

    def touch_raw_posting(self, raw_posting_id: int, seen_at: datetime) -> None: ...

    def pending_extraction(self, limit: int | None = None) -> Sequence[PendingRaw]: ...

    def record_extraction(
        self, raw_posting_id: int, extractor: str, prompt_version: str, created_at: datetime,
        candidate_json: str, result: ValidationResult,
    ) -> int: ...

    def query(self, sql: str, params: Sequence[Any] = ()) -> QueryResult: ...

    def count_rows(self, table: str) -> int: ...

    def close(self) -> None: ...
