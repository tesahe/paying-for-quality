"""BLS Occupational Employment and Wage Statistics (OEWS): national hourly median wages.

These are the experts' outside option: what an hour of their expertise earns outside AI data work.

- API: BLS Public Data API v1, GET https://api.bls.gov/publicAPI/v1/timeseries/data/<series_id>
  (no key; 25 queries/day, so one run of ~9 occupations is well inside the limit).
- Series ID: "OE" + "U" (not seasonally adjusted) + "N" (national) + "0000000" (area) + "000000"
  (all industries) + 6-digit SOC code + datatype "08" (hourly median wage).
- The API returns only the latest OEWS estimates (no history).
- Terms (bls.gov/developers/termsOfService.htm): cite the retrieval date and state that "BLS.gov cannot
  vouch for the data or analyses derived from these data after the data have been retrieved from
  BLS.gov." Both go into every observation's citation note.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Iterator, Mapping

from ...core.entities import RateCandidate
from ...core.errors import SourceFetchError
from ..sources.http import get_json

URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/{series_id}"
HOURLY_MEDIAN = "08"
TOP_CODED = "5"  # OEWS footnote 5: the wage is at or above the published cap, so not an exact figure
DISCLAIMER = (
    "BLS.gov cannot vouch for the data or analyses derived from these data after the data have been "
    "retrieved from BLS.gov."
)


def series_id(soc: str, datatype: str = HOURLY_MEDIAN) -> str:
    digits = soc.replace("-", "")
    if len(digits) != 6 or not digits.isdigit():
        raise ValueError(f"invalid SOC code {soc!r}")
    return f"OEUN0000000000000{digits}{datatype}"


def latest_point(response: Any, sid: str) -> dict[str, Any]:
    """The most recent annual data point of one series, or a SourceFetchError."""
    if not isinstance(response, dict) or response.get("status") != "REQUEST_SUCCEEDED":
        raise SourceFetchError(f"BLS API did not succeed for {sid}")
    results = response.get("Results")
    series = results.get("series") if isinstance(results, dict) else (results or [{}])[0].get("series")
    data = (series or [{}])[0].get("data") or []
    if not data:
        raise SourceFetchError(f"BLS API returned no data for {sid}")
    latest = [d for d in data if str(d.get("latest")).lower() == "true"]
    return latest[0] if latest else max(data, key=lambda d: str(d.get("year")))


def _amount(point: Mapping[str, Any]) -> str | None:
    """The value, or None when it is top-coded or not a number (Core then rejects the rate)."""
    codes = {str(f.get("code")) for f in point.get("footnotes") or [] if isinstance(f, dict) and f.get("code")}
    value = str(point.get("value", "")).replace(",", "").strip()
    if TOP_CODED in codes:
        return None
    try:
        float(value)
    except ValueError:
        return None
    return value


class BlsOewsRates:
    def __init__(
        self,
        occupations: Iterable[Mapping[str, str]],
        retrieved_on: str,
        fetch: Callable[[str], Any] = get_json,
    ) -> None:
        self.occupations = list(occupations)
        self.retrieved_on = retrieved_on
        self._fetch = fetch

    def list_rates(self) -> Iterator[RateCandidate]:
        for occupation in self.occupations:
            soc, title = occupation["soc"], occupation.get("title", occupation["soc"])
            sid = series_id(soc)
            point = latest_point(self._fetch(URL.format(series_id=sid)), sid)
            year = str(point.get("year", ""))
            amount = _amount(point)
            yield RateCandidate(
                external_key=f"{sid}:{year}",
                amount_min=amount,
                amount_max=amount,
                unit="hour",
                engagement="employee",  # OEWS covers wage and salary workers, not the self-employed
                rater_kind="outside_option",
                domain=occupation["domain"],
                provenance_kind="gov_statistic",
                occupation=soc,
                region="US",
                as_of=f"{year}-05" if year else None,  # OEWS estimates refer to May of the survey year
                citation_url=URL.format(series_id=sid),
                citation_note=(
                    f"BLS OEWS national hourly median wage, {title} (SOC {soc}), May {year} estimate; "
                    f"retrieved {self.retrieved_on} via the BLS Public Data API. {DISCLAIMER}"
                ),
            )
