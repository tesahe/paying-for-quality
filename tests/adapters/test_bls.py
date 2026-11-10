"""BLS OEWS adapter against responses in the shape the live API returned on 2026-11-09 (no network)."""

from decimal import Decimal

import pytest

from paying_for_quality.adapters.rates.bls import BlsOewsRates, latest_point, series_id
from paying_for_quality.core.errors import IssueCode, SourceFetchError
from paying_for_quality.core.rates import validate_rate


def response(value="65.38", year="2025", footnotes=({},), results_as_list=False):
    series = [{"seriesID": "X", "data": [
        {"year": year, "period": "A01", "periodName": "Annual", "latest": "true", "value": value,
         "footnotes": list(footnotes)},
    ]}]
    results = [{"series": series}] if results_as_list else {"series": series}
    return {"status": "REQUEST_SUCCEEDED", "message": ["No Data Available for Series X Year: 2024"],
            "Results": results}


def test_series_id_format():
    assert series_id("15-1252") == "OEUN000000000000015125208"
    assert len(series_id("29-1210")) == 25
    with pytest.raises(ValueError):
        series_id("15-12")


def test_hourly_median_becomes_a_cited_outside_option_rate():
    fetched = []

    def fetch(url):
        fetched.append(url)
        return response()

    source = BlsOewsRates([{"soc": "15-1252", "domain": "coding", "title": "Software Developers"}],
                          retrieved_on="2026-11-09", fetch=fetch)
    (candidate,) = list(source.list_rates())
    assert fetched == ["https://api.bls.gov/publicAPI/v1/timeseries/data/OEUN000000000000015125208"]
    assert candidate.external_key == "OEUN000000000000015125208:2025"
    assert "retrieved 2026-11-09" in candidate.citation_note
    assert "BLS.gov cannot vouch" in candidate.citation_note  # required by the BLS API terms
    obs = validate_rate(candidate).observation
    assert obs.hourly_min_usd == Decimal("65.38")
    assert (obs.rater_kind, obs.domain, obs.provenance_kind, obs.as_of) == ("outside_option", "coding",
                                                                          "gov_statistic", "2025-05")


@pytest.mark.parametrize("value, footnotes", [("-", ({},)), ("115.00", ({"code": "5", "text": "top-coded"},))])
def test_suppressed_or_top_coded_values_are_rejected_by_core(value, footnotes):
    source = BlsOewsRates([{"soc": "29-1210", "domain": "medicine"}], "2026-11-09",
                          fetch=lambda url: response(value=value, footnotes=footnotes))
    (candidate,) = list(source.list_rates())
    issues = {i.code for i in validate_rate(candidate).issues}
    assert issues & {IssueCode.MISSING_FIELD, IssueCode.AMOUNT_INVALID}


def test_results_may_be_a_list_and_failures_raise():
    assert latest_point(response(results_as_list=True), "X")["value"] == "65.38"
    with pytest.raises(SourceFetchError):
        latest_point({"status": "REQUEST_NOT_PROCESSED"}, "X")
    with pytest.raises(SourceFetchError):
        latest_point({"status": "REQUEST_SUCCEEDED", "Results": {"series": [{"data": []}]}}, "X")
