"""Rate loading (FR-9): any RateSource, one Core validation path, idempotent storage, aggregate query."""

from dataclasses import replace
from decimal import Decimal

import pytest

from paying_for_quality.adapters.llm.fake import FakeExtractor
from paying_for_quality.app.market import collect, extract
from paying_for_quality.app.rates import JobBoardRates, load_rates
from paying_for_quality.app.reporting import run_query
from paying_for_quality.core.entities import (
    ExtractionCandidate, PayQuoteCandidate, RateCandidate, RateSourceInfo,
)
from paying_for_quality.core.errors import SourceNotAllowed
from tests.fakes import FakeSource, doc, source_info

CITED = RateSourceInfo("cited-test", "cited", "literature", True, "2026-11-09", "test")
JOBS = RateSourceInfo("job-boards", "job_boards", "job_board", True, "2026-11-09", "test")


class FakeRates:
    def __init__(self, rates=()):
        self.rates = list(rates)
        self.calls = 0

    def list_rates(self):
        self.calls += 1
        return iter(self.rates)


def rate(key, hourly, domain="medicine", rater_kind="expert", provenance="dataset_paper", url="https://example.test"):
    return RateCandidate(
        external_key=key, amount_min=hourly, amount_max=hourly, unit="hour", engagement="contractor",
        rater_kind=rater_kind, domain=domain, provenance_kind=provenance, citation_url=url,
    )


def test_load_is_idempotent_and_rejects_uncited(repo, clock):  # AC-9.1
    source = FakeRates([rate("a", 40), rate("b", 60), rate("uncited", 50, url=None)])
    first = load_rates(CITED, source, repo, clock)
    assert (first.new, first.unchanged, first.rejected) == (2, 0, 1)
    assert first.issue_counts == {"CITATION_MISSING": 1}
    second = load_rates(CITED, source, repo, clock)
    assert (second.new, second.unchanged, second.rejected) == (0, 2, 1)
    assert repo.count_rows("rate_observation") == 2


def test_unchecked_rate_source_is_refused_before_any_fetch(repo, clock):  # AC-9.6
    source = FakeRates([rate("a", 40)])
    with pytest.raises(SourceNotAllowed):
        load_rates(replace(CITED, terms_checked=False), source, repo, clock)
    assert source.calls == 0
    assert repo.count_rows("rate_observation") == 0


def collect_contract_posting(repo, raw_store, clock):
    evidence = "$65 - $158 per hour"
    docs = [
        doc("red-1", text=f"Pay: {evidence}", title="AI Red Teamer, CBRNE (Remote)", employmentType="Contract"),
        doc("ops-1", text="Pay: $100,000 per year", title="Operations Lead", employmentType="FullTime"),
    ]
    collect(source_info(), FakeSource(docs), repo, raw_store, clock)
    scripted = {
        "red-1": ExtractionCandidate(company="Acme", title=docs[0].title,
                                     pay_quotes=(PayQuoteCandidate(65, 158, "hour", evidence),)),
        "ops-1": ExtractionCandidate(company="Acme", title=docs[1].title,
                                     pay_quotes=(PayQuoteCandidate(100000, 100000, "year", "$100,000 per year"),)),
    }
    extract(FakeExtractor(scripted), repo, raw_store, clock)


def test_job_board_postings_become_rates_with_engagement(repo, raw_store, clock):  # AC-9.3
    collect_contract_posting(repo, raw_store, clock)
    result = load_rates(JOBS, JobBoardRates(repo, raw_store), repo, clock)
    assert (result.new, result.rejected) == (2, 0)
    rows = repo.query(
        "SELECT engagement, rater_kind, domain, hourly_min_usd, hourly_max_usd, raw_posting_id, citation_url"
        " FROM rate_observation ORDER BY hourly_max_usd DESC"
    ).rows
    contract, staff = rows
    assert contract[:3] == ("contractor", "expert", "stem_science")
    assert (Decimal(str(contract[3])), Decimal(str(contract[4]))) == (Decimal(65), Decimal(158))
    assert contract[5] is not None and contract[6] is None  # linked to its posting, no URL needed
    assert staff[:3] == ("employee", "staff", "none")

    again = load_rates(JOBS, JobBoardRates(repo, raw_store), repo, clock)
    assert (again.new, again.unchanged) == (0, 2)


def test_rates_by_domain_aggregates_across_provenance_kinds(repo, clock):  # AC-9.4
    source = FakeRates([
        rate("paper", 40, provenance="dataset_paper"),
        rate("gov", 60, rater_kind="expert", provenance="gov_statistic"),
        rate("lit", 80, provenance="literature"),
        rate("crowd", 12, domain="none", rater_kind="crowd", provenance="literature"),
    ])
    load_rates(CITED, source, repo, clock)
    result = run_query(repo, "rates_by_domain")
    assert result.columns == ("domain", "rater_kind", "n", "n_provenance", "median_hourly_usd")
    rows = {(r[0], r[1]): (r[2], r[3], Decimal(str(r[4]))) for r in result.rows}
    assert rows[("medicine", "expert")] == (3, 3, Decimal(60))
    assert rows[("none", "crowd")] == (1, 1, Decimal(12))
    assert not any("company" in column for column in result.columns)
