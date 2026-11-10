"""Repository logic shared by the SQLite and Postgres adapters.

SQL is written once, with `?` placeholders and `{J}` for JSON parameters. Each dialect subclass
supplies the differences (placeholder style, timestamps, numbers, JSON) through small hooks.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from importlib import resources
from typing import Any, Iterator, Sequence

from ...core.entities import Outcome, RawPostingDoc, SourceInfo, ValidationResult
from ...core.ports import PendingRaw, QueryResult
from ...core.serialization import issues_to_json

TABLES = (
    "schema_version", "source", "collection_run", "raw_posting",
    "extraction_run", "posting", "pay_quote", "review_item",
)


def load_schema(dialect: str) -> str:
    return resources.files("paying_for_quality.schema").joinpath(f"{dialect}.sql").read_text()


class SqlRepository:
    dialect = ""
    json_placeholder = "?"

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    # --- dialect hooks -------------------------------------------------------------------
    def _sql(self, sql: str) -> str:
        return sql.replace("{J}", self.json_placeholder)

    def _ts(self, value: datetime) -> Any:
        return value

    def _num(self, value: Decimal | None) -> Any:
        return value

    # --- plumbing ------------------------------------------------------------------------
    def _execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        return self._conn.execute(self._sql(sql), tuple(params))

    def _insert(self, sql: str, params: Sequence[Any]) -> int:
        return int(self._execute(sql + " RETURNING id", params).fetchone()[0])

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        try:
            yield
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise

    def close(self) -> None:
        self._conn.close()

    # --- sources and collection ----------------------------------------------------------
    def upsert_source(self, source: SourceInfo) -> int:
        with self._transaction():
            row = self._execute("SELECT id FROM source WHERE slug = ?", (source.slug,)).fetchone()
            values = (
                source.kind, source.board, source.company, source.segment,
                source.terms_checked, source.robots_checked_at, source.terms_note,
            )
            if row:
                self._execute(
                    "UPDATE source SET kind = ?, board = ?, company = ?, segment = ?, terms_checked = ?,"
                    " robots_checked_at = ?, terms_note = ? WHERE id = ?",
                    (*values, row[0]),
                )
                return int(row[0])
            return self._insert(
                "INSERT INTO source (slug, kind, board, company, segment, terms_checked, robots_checked_at,"
                " terms_note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (source.slug, *values),
            )

    def start_collection_run(self, source_id: int, started_at: datetime) -> int:
        with self._transaction():
            return self._insert(
                "INSERT INTO collection_run (source_id, started_at, status) VALUES (?, ?, 'running')",
                (source_id, self._ts(started_at)),
            )

    def finish_collection_run(
        self, run_id: int, finished_at: datetime, status: str, n_new: int, n_changed: int, n_unchanged: int,
        error: str | None = None,
    ) -> None:
        with self._transaction():
            self._execute(
                "UPDATE collection_run SET finished_at = ?, status = ?, n_new = ?, n_changed = ?,"
                " n_unchanged = ?, error = ? WHERE id = ?",
                (self._ts(finished_at), status, n_new, n_changed, n_unchanged, error, run_id),
            )

    def find_raw_posting(self, source_id: int, external_id: str, digest: str) -> int | None:
        row = self._execute(
            "SELECT id FROM raw_posting WHERE source_id = ? AND external_id = ? AND content_hash = ?",
            (source_id, external_id, digest),
        ).fetchone()
        return int(row[0]) if row else None

    def has_listing(self, source_id: int, external_id: str) -> bool:
        row = self._execute(
            "SELECT 1 FROM raw_posting WHERE source_id = ? AND external_id = ? LIMIT 1", (source_id, external_id)
        ).fetchone()
        return row is not None

    def insert_raw_posting(
        self, source_id: int, doc: RawPostingDoc, digest: str, raw_path: str, seen_at: datetime
    ) -> int:
        with self._transaction():
            return self._insert(
                "INSERT INTO raw_posting (source_id, external_id, content_hash, raw_path, url, title,"
                " first_seen_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (source_id, doc.external_id, digest, raw_path, doc.url, doc.title, self._ts(seen_at), self._ts(seen_at)),
            )

    def touch_raw_posting(self, raw_posting_id: int, seen_at: datetime) -> None:
        with self._transaction():
            self._execute("UPDATE raw_posting SET last_seen_at = ? WHERE id = ?", (self._ts(seen_at), raw_posting_id))

    # --- extraction ----------------------------------------------------------------------
    def pending_extraction(self, limit: int | None = None) -> list[PendingRaw]:
        """Latest version of each listing that has no extraction run yet."""
        sql = (
            "SELECT rp.id, s.slug, rp.raw_path FROM raw_posting rp JOIN source s ON s.id = rp.source_id"
            " WHERE NOT EXISTS (SELECT 1 FROM extraction_run e WHERE e.raw_posting_id = rp.id)"
            " AND rp.id = (SELECT MAX(r2.id) FROM raw_posting r2"
            "              WHERE r2.source_id = rp.source_id AND r2.external_id = rp.external_id)"
            " ORDER BY rp.id"
        )
        params: tuple[Any, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        return [PendingRaw(int(r[0]), r[1], r[2]) for r in self._execute(sql, params).fetchall()]

    def record_extraction(
        self, raw_posting_id: int, extractor: str, prompt_version: str, created_at: datetime,
        candidate_json: str, result: ValidationResult,
    ) -> int:
        """One transaction: the audit row, then the posting (accepted) or review item (review)."""
        with self._transaction():
            run_id = self._insert(
                "INSERT INTO extraction_run (raw_posting_id, extractor, prompt_version, created_at, candidate_json,"
                " outcome, issues_json) VALUES (?, ?, ?, ?, {J}, ?, {J})",
                (raw_posting_id, extractor, prompt_version, self._ts(created_at), candidate_json,
                 result.outcome.value, issues_to_json(result.issues)),
            )
            if result.outcome is Outcome.ACCEPTED and result.posting is not None:
                p = result.posting
                posting_id = self._insert(
                    "INSERT INTO posting (raw_posting_id, extraction_run_id, company, platform, title, domain,"
                    " seniority, credentials_json, posted_at) VALUES (?, ?, ?, ?, ?, ?, ?, {J}, ?)",
                    (raw_posting_id, run_id, p.company, p.platform, p.title, p.domain, p.seniority,
                     json.dumps(list(p.credentials)), p.posted_at),
                )
                for q in p.pay_quotes:
                    self._insert(
                        "INSERT INTO pay_quote (posting_id, amount_min, amount_max, currency, unit, hourly_min_usd,"
                        " hourly_max_usd, evidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (posting_id, self._num(q.amount_min), self._num(q.amount_max), q.currency, q.unit.value,
                         self._num(q.hourly_min_usd), self._num(q.hourly_max_usd), q.evidence),
                    )
            elif result.outcome is Outcome.REVIEW:
                self._insert("INSERT INTO review_item (extraction_run_id, status) VALUES (?, 'open')", (run_id,))
            return run_id

    # --- reads ---------------------------------------------------------------------------
    def query(self, sql: str, params: Sequence[Any] = ()) -> QueryResult:
        cursor = self._execute(sql, params)
        columns = tuple(d[0] for d in cursor.description)
        rows = tuple(tuple(r) for r in cursor.fetchall())
        self._conn.commit()  # end the read transaction (Postgres) so the session does not idle in one
        return QueryResult(columns, rows)

    def count_rows(self, table: str) -> int:
        if table not in TABLES:
            raise ValueError(f"unknown table {table!r}")
        return int(self._execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
