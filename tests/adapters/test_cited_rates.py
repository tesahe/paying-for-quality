"""The committed data/rates.toml parses, and every entry passes Core validation with a citation."""

from pathlib import Path

import pytest

from paying_for_quality.adapters.rates.cited import CitedRates, parse_rates
from paying_for_quality.core.errors import ConfigError, IssueCode
from paying_for_quality.core.rates import validate_rate

RATES_FILE = Path(__file__).resolve().parents[2] / "data" / "rates.toml"


def test_committed_rates_file_is_fully_valid():
    candidates = list(CitedRates(RATES_FILE).list_rates())
    assert len(candidates) >= 5
    keys = [c.external_key for c in candidates]
    assert len(keys) == len(set(keys)), "ids must be unique"
    for candidate in candidates:
        result = validate_rate(candidate)
        assert result.accepted, (candidate.external_key, result.issues)
        assert "Retrieved" in candidate.citation_note, candidate.external_key


def test_entry_without_citation_is_rejected_by_core():
    (candidate,) = parse_rates('[[rate]]\nid = "x"\namount = 20\nunit = "hour"\nrater_kind = "crowd"\n'
                               'provenance_kind = "literature"\n')
    assert IssueCode.CITATION_MISSING in {i.code for i in validate_rate(candidate).issues}


def test_range_entries_and_bad_files():
    (candidate,) = parse_rates('[[rate]]\nid = "r"\namount_min = 10\namount_max = 20\nunit = "hour"\n')
    assert (candidate.amount_min, candidate.amount_max) == (10, 20)
    with pytest.raises(ConfigError):
        parse_rates("[[rate]\n")
    with pytest.raises(ConfigError):
        list(CitedRates("does/not/exist.toml").list_rates())
