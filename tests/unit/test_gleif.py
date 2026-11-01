import json
import urllib.request

import pytest
from lineage_ingest.gleif import Gleif, GleifError


def lei_record(lei: str, name: str, number: str | None = None) -> dict[str, object]:
    return {
        "id": lei,
        "attributes": {
            "entity": {
                "legalName": {"name": name},
                "registeredAs": number,
                "jurisdiction": "GB",
                "status": "ACTIVE",
            }
        },
    }


class Fake:
    def __init__(self, routes: dict[str, tuple[int, object]]) -> None:
        self.routes = routes
        self.paths: list[str] = []

    def __call__(self, request: urllib.request.Request) -> tuple[int, bytes]:
        path = request.full_url.split("/api/v1", 1)[1]
        self.paths.append(path)
        status, body = self.routes.get(path, (404, {"errors": []}))
        return status, json.dumps(body).encode()


def client(routes: dict[str, tuple[int, object]]) -> tuple[Gleif, Fake]:
    fake = Fake(routes)
    return Gleif(transport=fake, sleep=lambda s: None), fake


CHILD = "AAAAAAAAAAAAAAAAAA01"
PARENT = "AAAAAAAAAAAAAAAAAA02"


@pytest.mark.unit
def test_reads_a_record() -> None:
    gleif, _ = client({f"/lei-records/{CHILD}": (200, {"data": lei_record(CHILD, "CHILD LTD")})})
    record = gleif.record(CHILD)
    assert record is not None
    assert record.legal_name == "CHILD LTD"


@pytest.mark.unit
def test_finds_records_by_registration_number() -> None:
    path = (
        "/lei-records?filter%5Bentity.registeredAs%5D=00000001&filter%5Bentity.jurisdiction%5D=GB"
    )
    gleif, _ = client({path: (200, {"data": [lei_record(CHILD, "CHILD LTD", "00000001")]})})
    assert [r.lei for r in gleif.by_registration("00000001")] == [CHILD]


@pytest.mark.unit
def test_returns_the_parent_record() -> None:
    gleif, _ = client(
        {f"/lei-records/{CHILD}/direct-parent": (200, {"data": lei_record(PARENT, "PARENT PLC")})}
    )
    parent = gleif.parent(CHILD)
    assert parent.record is not None and parent.record.lei == PARENT
    assert parent.exception is None


@pytest.mark.unit
def test_falls_back_to_the_reporting_exception() -> None:
    exception = {"data": {"attributes": {"reason": "NON_CONSOLIDATING"}}}
    gleif, fake = client(
        {f"/lei-records/{CHILD}/ultimate-parent-reporting-exception": (200, exception)}
    )
    parent = gleif.parent(CHILD, "ultimate")
    assert parent.record is None
    assert parent.exception == "NON_CONSOLIDATING"
    assert fake.paths[0].endswith("/ultimate-parent")


@pytest.mark.unit
def test_rejects_an_unknown_level() -> None:
    gleif, _ = client({})
    with pytest.raises(ValueError):
        gleif.parent(CHILD, "grandparent")


@pytest.mark.unit
def test_client_errors_raise() -> None:
    gleif, _ = client({f"/lei-records/{CHILD}": (400, {})})
    with pytest.raises(GleifError, match="400"):
        gleif.record(CHILD)


@pytest.mark.unit
def test_spaces_requests_to_stay_under_the_limit() -> None:
    waits: list[float] = []
    fake = Fake({})
    gleif = Gleif(transport=fake, clock=lambda: 100.0, sleep=waits.append)
    gleif.record(CHILD)
    gleif.record(PARENT)
    assert waits == [1.0]
