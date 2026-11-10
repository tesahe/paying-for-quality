"""Fake extractor for tests and no-key demos: scripted answers, including deliberately bad ones."""

from __future__ import annotations

from typing import Mapping

from ...core.entities import ExtractionCandidate, RawPostingDoc


class FakeExtractor:
    name = "fake"
    prompt_version = "none"

    def __init__(self, scripted: Mapping[str, ExtractionCandidate | Exception] | None = None) -> None:
        self.scripted = dict(scripted or {})

    def extract(self, doc: RawPostingDoc) -> ExtractionCandidate:
        answer = self.scripted.get(doc.external_id)
        if isinstance(answer, Exception):
            raise answer
        if answer is not None:
            return answer
        return ExtractionCandidate(company=doc.company, title=doc.title, platform=doc.company)
