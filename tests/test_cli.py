"""CLI smoke tests: the full collect -> extract -> query path through `main(argv)` on a temp SQLite DB."""

import json

import pytest

from paying_for_quality import cli
from paying_for_quality.adapters.sources import registry
from tests.adapters.test_ashby import RESPONSE
from paying_for_quality.adapters.sources.ashby import AshbySource

REGISTRY = """
[[source]]
slug = "ashby-acme"
kind = "ashby"
board = "acme"
company = "Acme"
segment = "staff"
terms_checked = true

[[source]]
slug = "blocked"
kind = "ashby"
board = "nope"
company = "Nope"
segment = "expert"
terms_checked = false
"""


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sources.toml").write_text(REGISTRY)
    (tmp_path / ".env").write_text(f"DATABASE_URL=sqlite:///{tmp_path / 'pfq.db'}\nPFQ_RAW_DIR={tmp_path / 'raw'}\n")
    for key in ("DATABASE_URL", "PFQ_DB_SCHEMA", "PFQ_RAW_DIR", "PFQ_DEBUG"):
        monkeypatch.delenv(key, raising=False)
    fetched = []

    def fake_build(info):
        def fetch(url):
            fetched.append(url)
            return RESPONSE

        return AshbySource(info.board, info.company, fetch=fetch)

    monkeypatch.setattr(registry, "build_source", fake_build)
    return fetched


def run(capsys, *argv):
    code = cli.main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_full_pipeline(env, capsys):
    assert run(capsys, "init-db")[0] == 0

    code, out, _ = run(capsys, "collect", "--source", "ashby-acme", "--registry", "sources.toml")
    assert code == 0 and "2 postings: 2 new, 0 changed, 0 unchanged" in out

    _, out, _ = run(capsys, "collect", "--source", "ashby-acme", "--registry", "sources.toml")
    assert "0 new, 0 changed, 2 unchanged" in out

    code, out, _ = run(capsys, "extract")
    assert code == 0 and "Extracted 2 postings with baseline-regex: 2 accepted" in out

    code, out, _ = run(capsys, "query", "pay_by_domain", "--json")
    assert code == 0
    assert json.loads(out) == [{"segment": "staff", "domain": "operations", "n": 1, "median_hourly_usd": 84.14}]

    code, out, _ = run(capsys, "query", "pay_transparency")
    assert code == 0 and "ashby-acme" in out and "50.0" in out


def test_blocked_source_is_refused_without_fetching(env, capsys):
    run(capsys, "init-db")
    code, _, err = run(capsys, "collect", "--source", "blocked", "--registry", "sources.toml")
    assert code == 1 and "terms" in err
    assert env == []  # no request was made


def test_blocked_source_without_adapter_reports_terms_not_missing_adapter(env, tmp_path, capsys, monkeypatch):
    # Regression: found in the real Supabase run, where a blocked 'website' source said "no collector".
    monkeypatch.undo()  # use the real build_source
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'pfq.db'}")
    (tmp_path / "web.toml").write_text(
        '[[source]]\nslug = "site"\nkind = "website"\nboard = "x"\ncompany = "X"\nsegment = "expert"\n'
        "terms_checked = false\n"
    )
    code, _, err = run(capsys, "collect", "--source", "site", "--registry", "web.toml")
    assert code == 1 and "terms check" in err and "no collector" not in err


def test_unknown_source_and_query(env, capsys):
    run(capsys, "init-db")
    code, _, err = run(capsys, "collect", "--source", "nope", "--registry", "sources.toml")
    assert code == 1 and "unknown source" in err
    code, _, err = run(capsys, "query", "nope")
    assert code == 1 and "Available: pay_by_domain, pay_transparency" in err


def test_missing_database_url_explains_what_to_do(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    code, _, err = run(capsys, "init-db")
    assert code == 1 and "copy .env.example to .env" in err


def test_connection_error_never_shows_the_password(tmp_path, monkeypatch, capsys):  # AC-DC-4
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "postgresql://pfq_user:S3cretPassw0rd@127.0.0.1:1/postgres")
    code, out, err = run(capsys, "init-db")
    assert code == 1
    assert "S3cretPassw0rd" not in out + err and "pfq_user" not in out + err
    assert "check DATABASE_URL" in err


def test_usage_error_exit_code(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["collect"])  # --source is required
    assert exc.value.code == 2
