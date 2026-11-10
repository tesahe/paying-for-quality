"""Cited rates: a small, hand-made, committed file of public pay figures (data/rates.toml).

Every entry must name its public source; Core rejects an entry without one (CITATION_MISSING). Entries
come from papers, official statistics or published guidance, never from a company's own job site or
the owner's contract work (AGENTS.md section 4).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Iterator

from ...core.entities import RateCandidate
from ...core.errors import ConfigError


def parse_rates(text: str) -> list[RateCandidate]:
    try:
        entries = tomllib.loads(text).get("rate", [])
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid rates file: {exc}") from None
    candidates = []
    for entry in entries:
        amount = entry.get("amount")
        candidates.append(
            RateCandidate(
                external_key=str(entry.get("id", "")),
                amount_min=entry.get("amount_min", amount),
                amount_max=entry.get("amount_max", amount),
                unit=entry.get("unit"),
                currency=entry.get("currency", "USD"),
                engagement=entry.get("engagement", "unknown"),
                rater_kind=entry.get("rater_kind", ""),
                domain=entry.get("domain", "none"),
                provenance_kind=entry.get("provenance_kind", ""),
                occupation=entry.get("occupation"),
                region=entry.get("region"),
                as_of=entry.get("as_of"),
                citation_url=entry.get("citation_url"),
                citation_note=entry.get("citation_note", ""),
            )
        )
    return candidates


class CitedRates:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def list_rates(self) -> Iterator[RateCandidate]:
        if not self.path.is_file():
            raise ConfigError(f"rates file not found: {self.path}")
        yield from parse_rates(self.path.read_text())
