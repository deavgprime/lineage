"""A client for the Companies House public data API.

The API key is read once and never logged or shown in reprs. Requests stay under the published limit
of 600 per five minutes, retry on rate limiting and server errors, and can be cached on disk so a
rebuild does not repeat calls.
"""

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

API = "https://api.company-information.service.gov.uk"
LIMIT = 600
WINDOW = 300.0
RETRIES = 5

Json = dict[str, Any]
# Takes a request, returns (status, body). Tests swap in a fake.
Transport = Callable[[urllib.request.Request], tuple[int, bytes]]


def http(request: urllib.request.Request) -> tuple[int, bytes]:
    try:
        # Requests only ever go to the fixed https API base.
        with urllib.request.urlopen(request, timeout=30) as resp:  # noqa: S310
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class CompaniesHouseError(RuntimeError):
    pass


class CompaniesHouse:
    def __init__(
        self,
        key: str | None = None,
        cache: Path | None = None,
        transport: Transport = http,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = key or os.environ.get("COMPANIES_HOUSE_API_KEY", "")
        if not key:
            raise CompaniesHouseError("COMPANIES_HOUSE_API_KEY is not set")
        self._auth = "Basic " + base64.b64encode(f"{key}:".encode()).decode()
        self._cache = cache
        self._transport = transport
        self._clock = clock
        self._sleep = sleep
        self._sent: deque[float] = deque()
        if cache:
            cache.mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        return f"CompaniesHouse(cache={self._cache})"

    def get(self, path: str) -> Json | None:
        """Return the JSON at path, or None if Companies House has no such record."""
        cached = (
            self._cache / (hashlib.sha256(path.encode()).hexdigest() + ".json")
            if self._cache
            else None
        )
        if cached and cached.exists():
            data: Json | None = json.loads(cached.read_text())
            return data
        # API is a fixed https base, so no other scheme can be opened.
        request = urllib.request.Request(API + path, headers={"Authorization": self._auth})  # noqa: S310
        for attempt in range(RETRIES):
            self._wait_for_slot()
            status, body = self._transport(request)
            if status == 200:
                data = json.loads(body)
                break
            if status == 404:
                data = None
                break
            if status == 429 or status >= 500:
                self._sleep(min(60.0, 5.0 * 2**attempt))
                continue
            raise CompaniesHouseError(f"{path} returned {status}")
        else:
            raise CompaniesHouseError(f"{path} failed after {RETRIES} attempts")
        if cached:
            cached.write_text(json.dumps(data))
        return data

    def _wait_for_slot(self) -> None:
        now = self._clock()
        while self._sent and now - self._sent[0] >= WINDOW:
            self._sent.popleft()
        if len(self._sent) >= LIMIT:
            self._sleep(WINDOW - (now - self._sent[0]))
            self._sent.popleft()
        self._sent.append(self._clock())

    def company(self, number: str) -> Json | None:
        return self.get(f"/company/{number}")

    def controllers(self, number: str) -> Json | None:
        return self.get(f"/company/{number}/persons-with-significant-control?items_per_page=100")

    def controller_statements(self, number: str) -> Json | None:
        return self.get(f"/company/{number}/persons-with-significant-control-statements")

    def search(self, **params: str | int) -> Json | None:
        return self.get(f"/advanced-search/companies?{urllib.parse.urlencode(params)}")
