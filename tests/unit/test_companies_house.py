import json
import urllib.request
from pathlib import Path

import pytest
from lineage_ingest.companies_house import LIMIT, CompaniesHouse, CompaniesHouseError

KEY = "test-key-not-real"


class Fake:
    def __init__(self, *responses: tuple[int, object]) -> None:
        self.responses = list(responses)
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request) -> tuple[int, bytes]:
        self.requests.append(request)
        status, body = self.responses.pop(0)
        return status, json.dumps(body).encode()


def client(fake: Fake, **kwargs: object) -> CompaniesHouse:
    return CompaniesHouse(KEY, transport=fake, sleep=lambda s: None, **kwargs)  # type: ignore[arg-type]


@pytest.mark.unit
def test_returns_json_and_sends_basic_auth() -> None:
    fake = Fake((200, {"company_name": "EXAMPLE LTD"}))
    assert client(fake).company("00000001") == {"company_name": "EXAMPLE LTD"}
    assert fake.requests[0].get_header("Authorization", "").startswith("Basic ")


@pytest.mark.unit
def test_missing_record_is_none() -> None:
    assert client(Fake((404, {}))).company("00000002") is None


@pytest.mark.unit
def test_retries_rate_limit_and_server_errors() -> None:
    fake = Fake((429, {}), (503, {}), (200, {"items": []}))
    assert client(fake).controllers("00000003") == {"items": []}
    assert len(fake.requests) == 3


@pytest.mark.unit
def test_gives_up_after_repeated_failures() -> None:
    with pytest.raises(CompaniesHouseError, match="after 5 attempts"):
        client(Fake(*[(500, {})] * 5)).company("00000004")


@pytest.mark.unit
def test_client_errors_are_not_retried() -> None:
    fake = Fake((401, {}))
    with pytest.raises(CompaniesHouseError, match="401"):
        client(fake).company("00000005")
    assert len(fake.requests) == 1


@pytest.mark.unit
def test_cache_avoids_a_second_request(tmp_path: Path) -> None:
    fake = Fake((200, {"company_name": "CACHED LTD"}))
    first = client(fake, cache=tmp_path)
    second = client(fake, cache=tmp_path)
    assert first.company("00000006") == second.company("00000006")
    assert len(fake.requests) == 1


@pytest.mark.unit
def test_waits_when_the_window_is_full() -> None:
    waits: list[float] = []
    fake = Fake(*[(200, {})] * (LIMIT + 1))
    ch = CompaniesHouse(KEY, transport=fake, clock=lambda: 0.0, sleep=waits.append)
    for i in range(LIMIT + 1):
        ch.company(f"{i:08d}")
    assert waits == [300.0]


@pytest.mark.unit
def test_key_never_appears_in_repr_or_errors() -> None:
    ch = client(Fake((403, {})))
    assert KEY not in repr(ch)
    with pytest.raises(CompaniesHouseError) as err:
        ch.company("00000007")
    assert KEY not in str(err.value)


@pytest.mark.unit
def test_missing_key_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMPANIES_HOUSE_API_KEY", raising=False)
    with pytest.raises(CompaniesHouseError, match="not set"):
        CompaniesHouse()
