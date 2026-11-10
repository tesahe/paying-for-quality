"""Source census: which public job-board APIs list postings for AI human-data companies.

Prints counts only; stores nothing. One request per second, generic client name.
Usage: python scripts/source_census.py [kind:token ...]
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

USER_AGENT = "paying-for-quality-research/0.1"
URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{t}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{t}?includeCompensation=true",
}
PAY_WORDS = ("$", "per hour", "/hr", "hourly", "compensation", "salary")

DEFAULT_TARGETS = [
    f"{kind}:{token}"
    for token in (
        "scaleai", "surgeai", "invisibletech", "invisible", "turing", "labelbox", "snorkelai",
        "prolific", "handshake", "mercor", "micro1", "toloka", "outlier", "dataannotation", "alignerr",
    )
    for kind in ("greenhouse", "lever", "ashby")
]


def fetch(url: str) -> tuple[int, object | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return 0, None


HOURLY_WORDS = ("per hour", "/hr", "/hour", "hourly", "an hour")


def summarize(kind: str, data: object) -> tuple[int, int, int]:
    """(postings, postings mentioning a $ pay figure, postings mentioning hourly pay)."""
    if kind == "lever":
        jobs = data if isinstance(data, list) else []
        texts = [json.dumps(j.get("salaryRange")) + j.get("descriptionPlain", "") + j.get("additionalPlain", "") for j in jobs]
    elif kind == "ashby":
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        texts = [json.dumps(j.get("compensation")) + (j.get("descriptionPlain") or "") for j in jobs]
    else:
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        texts = [j.get("content") or "" for j in jobs]
    with_pay = sum(1 for t in texts if any(w in t.lower() for w in PAY_WORDS) and "$" in t)
    hourly = sum(1 for t in texts if "$" in t and any(w in t.lower() for w in HOURLY_WORDS))
    return len(jobs), with_pay, hourly


def sample_titles(kind: str, data: object, k: int = 3) -> str:
    jobs = data if isinstance(data, list) else data.get("jobs", [])  # type: ignore[union-attr]
    key = "text" if kind == "lever" else "title"
    return " | ".join(str(j.get(key, ""))[:40] for j in jobs[:k])


def main(targets: list[str]) -> None:
    for target in targets:
        kind, token = target.split(":", 1)
        status, data = fetch(URLS[kind].format(t=token))
        if status == 200 and data is not None:
            n, with_pay, hourly = summarize(kind, data)
            if n:
                print(f"{kind:<10} {token:<16} postings={n:<4} pay=${with_pay:<4} hourly={hourly:<4} e.g. {sample_titles(kind, data)}")
        time.sleep(1)


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT_TARGETS)
