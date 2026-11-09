"""Deterministic baseline extractor (no LLM, no cost).

1. Structured compensation from the source (Ashby `summaryComponents` of type Salary), with the
   posting's compensation summary as evidence.
2. Otherwise, a regex for pay phrases in the text ("$90 – $120 per hour", "$150k/yr").

Domain is the source's department, seniority a title keyword. It is the comparison point a real
LLM extractor must beat in Sprint 3, and its output still goes through Core validation.
"""

from __future__ import annotations

import re
from typing import Any

from ...core.entities import ExtractionCandidate, PayQuoteCandidate, RawPostingDoc

INTERVAL_UNITS = {"1 HOUR": "hour", "1 DAY": "day", "1 WEEK": "week", "1 MONTH": "month", "1 YEAR": "year"}

_AMOUNT = r"(\d[\d,]*(?:\.\d+)?\s?[kKmM]?)(?![a-zA-Z])"
PAY_PATTERN = re.compile(
    r"\$\s?" + _AMOUNT
    + r"(?:\s*(?:-|–|—|to)\s*\$?\s?" + _AMOUNT + r")?"
    + r"\s*(?:/|per\s|an\s|a\s)\s*(hour|hr|year|yr|annum|week|day|month)\b",
    re.IGNORECASE,
)

SENIORITY_WORDS = (
    "intern", "junior", "senior", "staff", "principal", "lead", "head", "director", "vp", "manager",
)


def guess_seniority(title: str) -> str | None:
    words = re.findall(r"[a-z]+", title.lower())
    for keyword in SENIORITY_WORDS:
        if keyword in words:
            return keyword
    return None


def structured_quotes(doc: RawPostingDoc) -> list[PayQuoteCandidate]:
    comp: Any = doc.metadata.get("compensation") or {}
    evidence = comp.get("compensationTierSummary") or comp.get("scrapeableCompensationSalarySummary") or ""
    quotes = []
    for part in comp.get("summaryComponents") or []:
        if part.get("compensationType") != "Salary":
            continue
        if part.get("minValue") is None and part.get("maxValue") is None:
            continue
        quotes.append(
            PayQuoteCandidate(
                amount_min=part.get("minValue"),
                amount_max=part.get("maxValue"),
                unit=INTERVAL_UNITS.get(part.get("interval") or "", part.get("interval")),
                currency=part.get("currencyCode") or "USD",
                evidence=evidence,
            )
        )
    return quotes


def text_quotes(text: str) -> list[PayQuoteCandidate]:
    match = PAY_PATTERN.search(text)
    if not match:
        return []
    low, high, unit = match.group(1), match.group(2), match.group(3)
    return [PayQuoteCandidate(amount_min=low.replace(" ", ""), amount_max=(high or low).replace(" ", ""),
                              unit=unit, evidence=match.group(0))]


class BaselineExtractor:
    name = "baseline-regex"
    prompt_version = "v1"

    def extract(self, doc: RawPostingDoc) -> ExtractionCandidate:
        department = doc.metadata.get("department")
        return ExtractionCandidate(
            company=doc.company,
            title=doc.title,
            platform=doc.company,
            domain=department.strip().lower() if isinstance(department, str) and department.strip() else None,
            seniority=guess_seniority(doc.title),
            posted_at=doc.posted_at,
            pay_quotes=tuple(structured_quotes(doc) or text_quotes(doc.text)),
            confidence=None,
        )
