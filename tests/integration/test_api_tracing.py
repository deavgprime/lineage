"""Opening a case produces one trace: the request, then the background drafting run."""

import os
import uuid

import pytest
from apitest import ANALYST_1, app
from lineage_api import telemetry
from lineage_api.runner import FixtureRunner
from lineage_db.migrate import migrate
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

URL = os.environ.get("DATABASE_URL", "")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="DATABASE_URL is not set"),
]


def test_a_case_is_traced_from_request_to_draft() -> None:
    migrate(URL)
    exporter = InMemorySpanExporter()
    client = app(FixtureRunner())
    assert telemetry.configure(client.app, exporter)  # type: ignore[arg-type]
    with client:
        opened = client.post(
            "/cases?note=private",
            json={"company_number": "00000041", "jurisdiction": "uk"},
            headers=ANALYST_1,
        )
        assert opened.status_code == 202
        client.get("/health/live")
    telemetry.flush()
    spans = exporter.get_finished_spans()
    draft = next(s for s in spans if s.name == "case.draft")
    request = next(s for s in spans if s.name == "POST /cases")
    assert draft.context.trace_id == request.context.trace_id
    assert draft.attributes is not None
    assert uuid.UUID(str(draft.attributes["lineage.case_id"])) == uuid.UUID(opened.json()["id"])
    assert not [s for s in spans if "health" in s.name]
    values = [str(v) for s in spans for v in (s.attributes or {}).values()]
    assert not [v for v in values if "private" in v or "Bearer" in v]
    assert request.attributes is not None and request.attributes.get("net.peer.ip") == ""
