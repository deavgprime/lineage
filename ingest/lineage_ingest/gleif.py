"""LEI records and parent links from the GLEIF API.

No key is needed. GLEIF allows 60 requests a minute, so the client spaces its calls. A parent is
either another LEI record or the reporting exception the entity filed instead, such as
NON_CONSOLIDATING or NATURAL_PERSONS, which tells the analyst why the chain stops.
"""

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lineage_ingest.companies_house import Transport, http

API = "https://api.gleif.org/api/v1"
MIN_INTERVAL = 1.0
RETRIES = 5


class GleifError(RuntimeError):
    pass


@dataclass(frozen=True)
class LeiRecord:
    lei: str
    legal_name: str
    registered_as: str | None
    jurisdiction: str | None
    status: str


@dataclass(frozen=True)
class Parent:
    """A parent record, or the reason the entity gave for not reporting one."""

    record: LeiRecord | None
    exception: str | None


def to_record(data: dict[str, Any]) -> LeiRecord:
    entity = data["attributes"]["entity"]
    return LeiRecord(
        lei=data["id"],
        legal_name=entity["legalName"]["name"],
        registered_as=entity.get("registeredAs"),
        jurisdiction=entity.get("jurisdiction"),
        status=entity.get("status", ""),
    )


class Gleif:
    def __init__(
        self,
        transport: Transport = http,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._transport = transport
        self._clock = clock
        self._sleep = sleep
        self._last = -MIN_INTERVAL

    def _get(self, path: str) -> dict[str, Any] | None:
        # API is a fixed https base, so no other scheme can be opened.
        headers = {"Accept": "application/vnd.api+json"}
        request = urllib.request.Request(API + path, headers=headers)  # noqa: S310
        for attempt in range(RETRIES):
            gap = self._clock() - self._last
            if gap < MIN_INTERVAL:
                self._sleep(MIN_INTERVAL - gap)
            self._last = self._clock()
            status, body = self._transport(request)
            if status == 200:
                data: dict[str, Any] = json.loads(body)
                return data
            if status == 404:
                return None
            if status == 429 or status >= 500:
                self._sleep(min(60.0, 5.0 * 2**attempt))
                continue
            raise GleifError(f"{path} returned {status}")
        raise GleifError(f"{path} failed after {RETRIES} attempts")

    def record(self, lei: str) -> LeiRecord | None:
        found = self._get(f"/lei-records/{lei}")
        return to_record(found["data"]) if found else None

    def by_registration(self, number: str, jurisdiction: str = "GB") -> list[LeiRecord]:
        query = urllib.parse.urlencode(
            {"filter[entity.registeredAs]": number, "filter[entity.jurisdiction]": jurisdiction}
        )
        found = self._get(f"/lei-records?{query}")
        return [to_record(d) for d in (found or {}).get("data", [])]

    def parent(self, lei: str, level: str = "direct") -> Parent:
        """Return the direct or ultimate parent of an entity."""
        if level not in ("direct", "ultimate"):
            raise ValueError(level)
        found = self._get(f"/lei-records/{lei}/{level}-parent")
        if found:
            return Parent(record=to_record(found["data"]), exception=None)
        exception = self._get(f"/lei-records/{lei}/{level}-parent-reporting-exception")
        reason = exception["data"]["attributes"]["reason"] if exception else None
        return Parent(record=None, exception=reason)
