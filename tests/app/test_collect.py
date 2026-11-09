"""FR-1: collection stores each posting version once; re-runs are idempotent."""

import pytest

from paying_for_quality.app.market import collect
from paying_for_quality.core.errors import SourceFetchError, SourceNotAllowed
from tests.fakes import FakeSource, doc, source_info


def test_second_run_with_unchanged_content_adds_nothing(repo, raw_store, clock):  # AC-1.1
    source = FakeSource([doc("a"), doc("b"), doc("c")])
    first = collect(source_info(), source, repo, raw_store, clock)
    second = collect(source_info(), source, repo, raw_store, clock)
    assert (first.n_new, first.n_unchanged) == (3, 0)
    assert (second.n_new, second.n_changed, second.n_unchanged) == (0, 0, 3)
    assert repo.count_rows("raw_posting") == 3
    assert repo.count_rows("collection_run") == 2


def test_unchanged_posting_only_updates_last_seen(repo, raw_store, clock):
    source = FakeSource([doc("a")])
    collect(source_info(), source, repo, raw_store, clock)
    collect(source_info(), source, repo, raw_store, clock)
    ((first_seen, last_seen),) = repo.query("SELECT first_seen_at, last_seen_at FROM raw_posting").rows
    assert last_seen > first_seen


def test_changed_text_adds_a_new_version_and_keeps_the_old(repo, raw_store, clock):  # AC-1.2
    collect(source_info(), FakeSource([doc("a"), doc("b")]), repo, raw_store, clock)
    result = collect(source_info(), FakeSource([doc("a", text="Pay: $120,000 per year"), doc("b")]),
                     repo, raw_store, clock)
    assert (result.n_new, result.n_changed, result.n_unchanged) == (0, 1, 1)
    assert repo.query("SELECT COUNT(*) FROM raw_posting WHERE external_id = 'a'").rows[0][0] == 2


def test_raw_snapshot_is_written_to_the_raw_store(repo, raw_store, clock):
    collect(source_info(), FakeSource([doc("a")]), repo, raw_store, clock)
    ((path,),) = repo.query("SELECT raw_path FROM raw_posting").rows
    assert b"$100,000 per year" in raw_store.get(path)


def test_source_without_terms_check_is_refused_before_fetching(repo, raw_store, clock):  # AC-1.3
    source = FakeSource([doc("a")])
    with pytest.raises(SourceNotAllowed):
        collect(source_info(terms_checked=False), source, repo, raw_store, clock)
    assert source.calls == 0
    assert repo.count_rows("raw_posting") == 0


def test_fetch_failure_is_recorded_on_the_run(repo, raw_store, clock):
    source = FakeSource(error=SourceFetchError("api.example returned HTTP 503"))
    with pytest.raises(SourceFetchError):
        collect(source_info(), source, repo, raw_store, clock)
    assert repo.query("SELECT status, error FROM collection_run").rows == (("error", "api.example returned HTTP 503"),)
