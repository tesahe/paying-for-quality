"""Test doubles shared across test modules."""

from __future__ import annotations

from paying_for_quality.core.entities import RawPostingDoc, SourceInfo


class FakeSource:
    def __init__(self, docs=(), error: Exception | None = None) -> None:
        self.docs = list(docs)
        self.error = error
        self.calls = 0

    def list_postings(self):
        self.calls += 1
        if self.error:
            raise self.error
        return iter(self.docs)


def source_info(slug="fake-board", terms_checked=True, segment="staff"):
    return SourceInfo(slug, "fake", "board", "Acme", segment, terms_checked, "2026-11-09", "test")


def doc(external_id, text="Pay: $100,000 per year", title="Data Lead", company="Acme", **metadata):
    return RawPostingDoc(external_id, f"https://example.test/{external_id}", title, company, text, None, metadata)
