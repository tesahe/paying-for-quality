"""Market-side use cases: collect postings, extract and validate them."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from ..core.entities import Outcome, SourceInfo
from ..core.errors import PfqError, SourceFetchError, SourceNotAllowed
from ..core.ports import Extractor, PostingSource, RawStore, Repository
from ..core.serialization import candidate_to_json, content_hash, doc_from_json, doc_to_json
from ..core.validation import DEFAULT_POLICY, ValidationPolicy, validate_extraction

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class CollectResult:
    source: str
    n_new: int
    n_changed: int
    n_unchanged: int

    @property
    def total(self) -> int:
        return self.n_new + self.n_changed + self.n_unchanged


@dataclass
class ExtractResult:
    extractor: str
    accepted: int = 0
    review: int = 0
    rejected: int = 0
    failed: int = 0
    issue_counts: Counter = field(default_factory=Counter)

    @property
    def total(self) -> int:
        return self.accepted + self.review + self.rejected + self.failed


def collect(info: SourceInfo, source: PostingSource, repo: Repository, raw_store: RawStore, now: Clock) -> CollectResult:
    """Store each posting once per version. Unchanged content only updates last_seen_at."""
    if not info.terms_checked:
        raise SourceNotAllowed(
            f"source '{info.slug}' has not passed its robots.txt/terms check (terms_checked = false in the registry)"
        )
    source_id = repo.upsert_source(info)
    run_id = repo.start_collection_run(source_id, now())
    n_new = n_changed = n_unchanged = 0
    try:
        for doc in source.list_postings():
            content = doc_to_json(doc)
            digest = content_hash(content)
            seen_at = now()
            existing = repo.find_raw_posting(source_id, doc.external_id, digest)
            if existing is not None:
                repo.touch_raw_posting(existing, seen_at)
                n_unchanged += 1
                continue
            is_changed = repo.has_listing(source_id, doc.external_id)
            path = raw_store.put(info.slug, digest, content)
            repo.insert_raw_posting(source_id, doc, digest, path, seen_at)
            if is_changed:
                n_changed += 1
            else:
                n_new += 1
    except Exception as exc:
        message = str(exc) if isinstance(exc, PfqError) else type(exc).__name__
        repo.finish_collection_run(run_id, now(), "error", n_new, n_changed, n_unchanged, message)
        if isinstance(exc, PfqError):
            raise
        raise SourceFetchError(f"collection from '{info.slug}' failed: {message}") from exc
    repo.finish_collection_run(run_id, now(), "ok", n_new, n_changed, n_unchanged)
    return CollectResult(info.slug, n_new, n_changed, n_unchanged)


def extract(
    extractor: Extractor,
    repo: Repository,
    raw_store: RawStore,
    now: Clock,
    policy: ValidationPolicy = DEFAULT_POLICY,
    limit: int | None = None,
) -> ExtractResult:
    """Run the extractor on unprocessed snapshots. Core validation decides what is stored.

    An extractor failure (e.g. an API error) is counted and not recorded, so the posting is retried
    on the next run.
    """
    result = ExtractResult(extractor.name)
    for pending in repo.pending_extraction(limit):
        doc = doc_from_json(raw_store.get(pending.raw_path))
        try:
            candidate = extractor.extract(doc)
        except Exception:
            result.failed += 1
            continue
        verdict = validate_extraction(candidate, doc.text, policy)
        repo.record_extraction(
            pending.raw_posting_id, extractor.name, extractor.prompt_version, now(),
            candidate_to_json(candidate), verdict,
        )
        result.issue_counts.update(issue.code.value for issue in verdict.issues)
        if verdict.outcome is Outcome.ACCEPTED:
            result.accepted += 1
        elif verdict.outcome is Outcome.REVIEW:
            result.review += 1
        else:
            result.rejected += 1
    return result
