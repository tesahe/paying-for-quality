"""`pfq` command-line interface: the composition root.

The CLI parses arguments, reads configuration, builds adapters, calls ONE use case and formats the
result. It never runs SQL itself, never calls an LLM and never does pay math.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from .adapters.llm.baseline import BaselineExtractor
from .adapters.llm.fake import FakeExtractor
from .adapters.rates.bls import BlsOewsRates
from .adapters.rates.cited import CitedRates
from .adapters.sources import registry
from .adapters.storage import open_repository
from .adapters.storage.raw_store import FileRawStore
from .app import market, rates, reporting
from .core.errors import ConfigError, PfqError, SourceNotAllowed
from .core.entities import RateSourceInfo
from .core.ports import QueryResult, RateSource

EXTRACTORS = {"baseline": BaselineExtractor, "fake": FakeExtractor}


# --- configuration -----------------------------------------------------------------------
def read_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser (no python-dotenv dependency). Comments and blanks are ignored."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def config(env_file: str) -> dict[str, str]:
    """Environment variables override the .env file."""
    merged = read_env_file(Path(env_file))
    merged.update({k: v for k, v in os.environ.items() if k.startswith(("DATABASE_URL", "PFQ_"))})
    return merged


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def open_repo(cfg: dict[str, str]):
    url = cfg.get("DATABASE_URL", "")
    if not url:
        raise ConfigError("DATABASE_URL is not set; copy .env.example to .env and fill it in")
    return open_repository(url, cfg.get("PFQ_DB_SCHEMA", "pfq"))


# --- output ------------------------------------------------------------------------------
def _plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def format_table(result: QueryResult) -> str:
    if not result.rows:
        return "(no rows)"
    cells = [list(result.columns)] + [["" if v is None else str(_plain(v)) for v in row] for row in result.rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(result.columns))]
    lines = ["  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip() for row in cells]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


# --- commands ----------------------------------------------------------------------------
def cmd_init_db(args, cfg) -> int:
    repo = open_repo(cfg)
    try:
        applied = repo.apply_schema()
        version = repo.schema_version()
    finally:
        repo.close()
    if applied:
        print(f"Applied migration(s) {', '.join(map(str, applied))}; schema is at version {version}.")
    else:
        print(f"Schema is up to date (version {version}).")
    return 0


def cmd_sources(args, cfg) -> int:
    print("Posting sources:")
    for info in registry.load_registry(args.registry).values():
        status = "ready" if info.terms_checked else "blocked (terms not checked or not allowed)"
        print(f"  {info.slug:<22} {info.kind:<11} {info.segment:<7} {status}")
    print("Rate sources:")
    for rate_info in registry.load_rate_registry(args.registry).values():
        status = "ready" if rate_info.terms_checked else "blocked (terms not checked or not allowed)"
        print(f"  {rate_info.slug:<22} {rate_info.kind:<11} {rate_info.provenance_kind:<14} {status}")
    return 0


def cmd_collect(args, cfg) -> int:
    sources = registry.load_registry(args.registry)
    if args.source not in sources:
        raise ConfigError(f"unknown source '{args.source}'. Known: {', '.join(sorted(sources))}")
    info = sources[args.source]
    if not info.terms_checked:  # before building an adapter: the terms check is the reason that matters
        raise SourceNotAllowed(f"source '{info.slug}' has not passed its robots.txt/terms check")
    repo = open_repo(cfg)
    try:
        result = market.collect(info, registry.build_source(info), repo, FileRawStore(cfg.get("PFQ_RAW_DIR", "data/raw")), utc_now)
    finally:
        repo.close()
    print(f"{result.source}: {result.total} postings: {result.n_new} new, {result.n_changed} changed, "
          f"{result.n_unchanged} unchanged")
    return 0


def cmd_extract(args, cfg) -> int:
    repo = open_repo(cfg)
    try:
        result = market.extract(
            EXTRACTORS[args.extractor](), repo, FileRawStore(cfg.get("PFQ_RAW_DIR", "data/raw")), utc_now,
            limit=args.limit,
        )
    finally:
        repo.close()
    print(f"Extracted {result.total} postings with {result.extractor}: {result.accepted} accepted, "
          f"{result.review} sent to review, {result.rejected} rejected" + (f", {result.failed} failed" if result.failed else ""))
    for code, count in result.issue_counts.most_common():
        print(f"  {code}: {count}")
    return 0


def build_rate_source(info: RateSourceInfo, repo, cfg) -> RateSource:
    """Composition root for rate sources: one adapter per registry `kind`."""
    if info.kind == "cited":
        return CitedRates(info.options.get("path", "data/rates.toml"))
    if info.kind == "bls_oews":
        return BlsOewsRates(info.options.get("occupations", []), retrieved_on=utc_now().date().isoformat())
    if info.kind == "job_boards":
        return rates.JobBoardRates(repo, FileRawStore(cfg.get("PFQ_RAW_DIR", "data/raw")))
    raise ConfigError(f"no adapter for rate source kind '{info.kind}'")


def cmd_rates_load(args, cfg) -> int:
    sources = registry.load_rate_registry(args.registry)
    if args.source not in sources:
        raise ConfigError(f"unknown rate source '{args.source}'. Known: {', '.join(sorted(sources))}")
    info = sources[args.source]
    if not info.terms_checked:  # before building an adapter or touching the network
        raise SourceNotAllowed(f"rate source '{info.slug}' has not passed its terms check")
    repo = open_repo(cfg)
    try:
        result = rates.load_rates(info, build_rate_source(info, repo, cfg), repo, utc_now)
    finally:
        repo.close()
    print(f"{result.source}: {result.total} rates: {result.new} new, {result.unchanged} unchanged, "
          f"{result.rejected} rejected")
    for code, count in result.issue_counts.most_common():
        print(f"  {code}: {count}")
    return 0


def cmd_query(args, cfg) -> int:
    repo = open_repo(cfg)
    try:
        result = reporting.run_query(repo, args.name)
    finally:
        repo.close()
    if args.json:
        print(json.dumps([dict(zip(result.columns, map(_plain, row))) for row in result.rows], indent=2))
    else:
        print(format_table(result))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pfq", description="Paying for Quality: price vs. value of expertise.")
    parser.add_argument("--env-file", default=".env", help="configuration file (default: .env)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="create or upgrade the database schema").set_defaults(func=cmd_init_db)

    p = sub.add_parser("sources", help="list registered sources and whether they may be collected")
    p.add_argument("--registry", default="data/sources.toml")
    p.set_defaults(func=cmd_sources)

    p = sub.add_parser("collect", help="collect postings from one registered source")
    p.add_argument("--source", required=True)
    p.add_argument("--registry", default="data/sources.toml")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("extract", help="extract and validate fields from collected postings")
    p.add_argument("--extractor", choices=sorted(EXTRACTORS), default="baseline")
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("rates", help="pay rates from any source (cited figures, BLS wages, job boards)")
    rates_sub = p.add_subparsers(dest="rates_command", required=True)
    p = rates_sub.add_parser("load", help="load, validate and store rates from one registered rate source")
    p.add_argument("--source", required=True)
    p.add_argument("--registry", default="data/sources.toml")
    p.set_defaults(func=cmd_rates_load)

    p = sub.add_parser("query", help=f"run a named analysis ({', '.join(reporting.available_queries())})")
    p.add_argument("name")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=cmd_query)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args, config(args.env_file))
    except PfqError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # unexpected: show the type only; messages may carry connection details
        if os.environ.get("PFQ_DEBUG"):
            raise
        print(f"error: unexpected {type(exc).__name__} (set PFQ_DEBUG=1 for details)", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
