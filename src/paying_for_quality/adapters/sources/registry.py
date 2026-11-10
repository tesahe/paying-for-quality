"""Source registry (data/sources.toml) and the factory that builds a PostingSource for an entry."""

from __future__ import annotations

import tomllib
from pathlib import Path

from ...core.entities import SourceInfo
from ...core.errors import ConfigError
from ...core.ports import PostingSource


def load_registry(path: str | Path) -> dict[str, SourceInfo]:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"source registry not found: {path}")
    try:
        entries = tomllib.loads(path.read_text()).get("source", [])
        sources = [
            SourceInfo(
                slug=e["slug"], kind=e["kind"], board=e["board"], company=e["company"], segment=e["segment"],
                terms_checked=bool(e["terms_checked"]), robots_checked_at=e.get("robots_checked_at"),
                terms_note=e.get("terms_note", ""),
            )
            for e in entries
        ]
    except (tomllib.TOMLDecodeError, KeyError) as exc:
        raise ConfigError(f"invalid source registry {path}: {exc}") from None
    return {s.slug: s for s in sources}


def build_source(info: SourceInfo) -> PostingSource:
    if info.kind == "ashby":
        from .ashby import AshbySource

        return AshbySource(info.board, info.company)
    raise ConfigError(f"no collector for source kind '{info.kind}' yet")
