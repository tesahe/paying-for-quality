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

from ...core.entities import Outcome, RateObservation, RateSourceInfo, RawPostingDoc, SourceInfo, ValidationResult
from ...core.ports import PendingRaw, PostedPay, QueryResult
from ...core.serialization import issues_to_json

TABLES = (
    "schema_version", "source", "collection_run", "raw_posting",
    "extraction_run", "posting", "pay_quote", "review_item",
    "rate_source", "rate_observation",
)


def load_schema(dialect: str) -> str:
    """The base schema (version 1). Later versions are added by the numbered migrations."""
    return resources.files("paying_for_quality.schema").joinpath(f"{dialect}.sql").read_text()


def load_migrations(dialect: str) -> list[tuple[int, str]]:
    """Numbered migrations (`NNN_name.sql`) for one dialect, in version order."""
    folder = resources.files("paying_for_quality.schema").joinpath("migrations", dialect)
    found = []
    for item in folder.iterdir():
        if item.name.endswith(".sql") and item.name[:3].isdigit():
            found.append((int(item.name[:3]), item.read_text()))
    return sorted(found)


def full_schema(dialect: str) -> str:
    """The schema a fresh database ends up with: the base schema plus every migration."""
    return "\n".join([load_schema(dialect), *(sql for _, sql in load_migrations(dialect))])


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

    # --- schema and migrations -----------------------------------------------------------
    def _apply_base_schema(self) -> None:
        raise NotImplementedError

    def _apply_migration(self, version: int, sql: str) -> None:
        raise NotImplementedError

    def schema_version(self) -> int:
        row = self._execute("SELECT MAX(version) FROM schema_version").fetchone()
        self._conn.commit()
        return int(row[0] or 0)

    def apply_schema(self) -> list[int]:
        """Create the base schema if missing, then apply every migration newer than the stored version.

        Each migration runs in one transaction together with its version bump, so a failure leaves the
        database at the previous version. Returns the versions applied (empty when already up to date).
        """
        self._apply_base_schema()
        current = self.schema_version()
        applied = []
        for version, sql in load_migrations(self.dialect):
            if version > current:
                self._apply_migration(version, sql)
                applied.append(version)
        return applied

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

    # --- rates -------------------------------------------------------------------------------
    def upsert_rate_source(self, info: RateSourceInfo) -> int:
        with self._transaction():
            row = self._execute("SELECT id FROM rate_source WHERE slug = ?", (info.slug,)).fetchone()
            values = (info.kind, info.provenance_kind, info.terms_checked, info.checked_at, info.terms_note)
            if row:
                self._execute(
                    "UPDATE rate_source SET kind = ?, provenance_kind = ?, terms_checked = ?, checked_at = ?,"
                    " terms_note = ? WHERE id = ?",
                    (*values, row[0]),
                )
                return int(row[0])
            return self._insert(
                "INSERT INTO rate_source (slug, kind, provenance_kind, terms_checked, checked_at, terms_note)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (info.slug, *values),
            )

    def insert_rate(self, rate_source_id: int, observation: RateObservation, loaded_at: datetime) -> bool:
        """Idempotent on (rate_source_id, external_key): a stored rate is never overwritten."""
        o = observation
        with self._transaction():
            exists = self._execute(
                "SELECT 1 FROM rate_observation WHERE rate_source_id = ? AND external_key = ?",
                (rate_source_id, o.external_key),
            ).fetchone()
            if exists:
                return False
            self._insert(
                "INSERT INTO rate_observation (rate_source_id, external_key, amount_min, amount_max, currency, unit,"
                " hourly_min_usd, hourly_max_usd, engagement, rater_kind, domain, provenance_kind, occupation,"
                " region, as_of, citation_url, citation_note, raw_posting_id, loaded_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rate_source_id, o.external_key, self._num(o.amount_min), self._num(o.amount_max), o.currency,
                 o.unit.value, self._num(o.hourly_min_usd), self._num(o.hourly_max_usd), o.engagement, o.rater_kind,
                 o.domain, o.provenance_kind, o.occupation, o.region, o.as_of, o.citation_url, o.citation_note,
                 o.raw_posting_id, self._ts(loaded_at)),
            )
            return True

    def current_posted_pay(self) -> list[PostedPay]:
        """Hourly-normalizable USD pay quotes of current, Core-accepted postings (same "current" rule as
        queries/pay_by_domain.sql: latest snapshot of each listing, latest accepted extraction of it)."""
        rows = self._execute(
            "SELECT rp.id, rp.raw_path, p.title, q.id, q.amount_min, q.amount_max, q.currency, q.unit"
            " FROM posting p"
            " JOIN raw_posting rp ON rp.id = p.raw_posting_id"
            " JOIN pay_quote q ON q.posting_id = p.id"
            " WHERE q.hourly_min_usd IS NOT NULL"
            " AND rp.id = (SELECT MAX(r2.id) FROM raw_posting r2"
            "              WHERE r2.source_id = rp.source_id AND r2.external_id = rp.external_id)"
            " AND p.extraction_run_id = (SELECT MAX(p2.extraction_run_id) FROM posting p2"
            "                            WHERE p2.raw_posting_id = p.raw_posting_id)"
            " ORDER BY rp.id, q.id"
        ).fetchall()
        self._conn.commit()
        result, index, last = [], 0, None
        for raw_id, raw_path, title, _quote_id, amount_min, amount_max, currency, unit in rows:
            index = index + 1 if raw_id == last else 0
            last = raw_id
            result.append(PostedPay(int(raw_id), raw_path, title, index, amount_min, amount_max, currency, unit))
        return result

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
