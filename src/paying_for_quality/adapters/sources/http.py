"""Gentle HTTP GET for public job-board APIs: generic client name, timeout, 1 request/second."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ...core.errors import SourceFetchError

USER_AGENT = "paying-for-quality-research/0.1"
MIN_INTERVAL_SECONDS = 1.0
_last_request = 0.0


def get_json(url: str, timeout: float = 20) -> Any:
    global _last_request
    wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    host = urllib.parse.urlsplit(url).netloc
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise SourceFetchError(f"{host} returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SourceFetchError(f"could not reach {host} ({type(exc).__name__})") from None
    except json.JSONDecodeError:
        raise SourceFetchError(f"{host} did not return JSON") from None
    finally:
        _last_request = time.monotonic()
