"""SummEval reader and the quality report (FR-11). The fixture is hand-made in SummEval's record shape;
it holds no real SummEval data."""

from pathlib import Path

import pytest

from paying_for_quality import cli
from paying_for_quality.adapters.datasets.summeval import load_summeval, parse_lines
from paying_for_quality.app.quality import agreement_report
from paying_for_quality.core.agreement import krippendorff_alpha
from paying_for_quality.core.errors import ConfigError

SAMPLE = Path(__file__).parent.parent / "fixtures" / "summeval_sample.jsonl"


def test_reader_builds_one_row_per_summary_and_one_slot_per_rater():
    data = load_summeval(SAMPLE)
    assert data.units == 4 and data.dataset == "SummEval"
    assert len(data.tables[("coherence", "expert")]) == 4
    assert [len(row) for row in data.tables[("coherence", "crowd")]] == [5, 5, 5, 5]
    assert data.tables[("coherence", "expert")][0] == [2.0, 2.0, 3.0]


def test_invalid_scores_become_missing_and_are_counted():  # AC-11.3
    data = load_summeval(SAMPLE)
    assert data.rejected_scores == 2  # "five" and 9
    assert data.tables[("fluency", "expert")][3] == [4.0, None, 4.0]
    assert data.tables[("consistency", "crowd")][3][2] is None


def test_report_has_one_row_per_dimension_with_alpha_from_core():  # AC-11.4
    data = load_summeval(SAMPLE)
    report = agreement_report(data)
    assert [row[0] for row in report.rows] == ["coherence", "consistency", "fluency", "relevance"]
    coherence = dict(zip(report.columns, report.rows[0]))
    assert coherence["expert_alpha"] == round(krippendorff_alpha(data.tables[("coherence", "expert")]), 3)
    assert coherence["units"] == 4
    assert coherence["expert_crowd_r"] > 0.8  # the hand-made groups rank the summaries the same way


@pytest.mark.parametrize("text, message", [
    ("{not json", "not valid JSON"),
    ("[1, 2]", "not a JSON object"),
    ('{"expert_annotations": []}', "turker_annotations"),
])
def test_malformed_files_are_reported_with_the_line(text, message):
    with pytest.raises(ConfigError, match=message):
        parse_lines([text])


def test_missing_file_explains_where_to_get_it(tmp_path, capsys):
    code = cli.main(["quality", "summeval", "--file", str(tmp_path / "absent.jsonl")])
    err = capsys.readouterr().err
    assert code == 1 and "Yale-LILY/SummEval" in err and "data/raw/summeval" in err


def test_cli_prints_the_report_without_a_database(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)  # no .env, no DATABASE_URL
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert cli.main(["quality", "summeval", "--file", str(SAMPLE)]) == 0
    out = capsys.readouterr().out
    assert "SummEval: 4 summaries" in out and "2 score(s) outside 1-5" in out
    assert "expert_alpha" in out and "relevance" in out
