"""Stable JSON forms of Core objects (for raw snapshots and the extraction audit trail)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any

from .entities import ExtractionCandidate, RawPostingDoc


def doc_to_json(doc: RawPostingDoc) -> bytes:
    """Canonical bytes: same document, same bytes, same hash."""
    payload = dataclasses.asdict(doc)
    payload["metadata"] = dict(doc.metadata)
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")


def doc_from_json(data: bytes) -> RawPostingDoc:
    return RawPostingDoc(**json.loads(data.decode("utf-8")))


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate_to_json(candidate: ExtractionCandidate) -> str:
    """The untrusted extractor output, kept verbatim for audit."""
    return json.dumps(dataclasses.asdict(candidate), sort_keys=True, default=str)


def issues_to_json(issues: Any) -> str:
    return json.dumps([issue.to_dict() for issue in issues])
