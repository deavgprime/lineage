"""The case endpoints against Postgres, with signed test tokens and a stub agent."""

import os
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from apitest import ANALYST_1, ANALYST_2, AUDITOR, MLRO
from apitest import app as make_app
from fastapi.testclient import TestClient
from lineage_agent.agent import Result
from lineage_agent.claims import Claim, Draft
from lineage_db.migrate import migrate

URL = os.environ.get("DATABASE_URL", "")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="DATABASE_URL is not set"),
]

SOURCE = "companies-house:company:00000001"
RECORD = "Company EXAMPLE TRADING LTD, number 00000001."


def stub_runner(number: str, pack: str, audit: Any) -> Result:
    audit("plan", {"steps": ["registry_chain", "draft"]})
    audit("tool_call", {"tool": "registry"})
    claim = Claim(text="The company is registered.", source_id=SOURCE, quote=RECORD)
    draft = Draft(
        summary=[claim], ownership=[], screening=[], risk_rating="low", risk_reasons=[claim]
    )
    audit("draft", {"attempts": 1})
    return Result(
        company_number=number,
        pack=pack,
        plan=["registry_chain", "draft"],
        draft=draft,
        attempts=1,
        citation_failures=[],
        evidence=[{"source_id": SOURCE, "title": "Companies House record", "text": RECORD}],
        alerts=["opensanctions:sanctions:X for " + SOURCE],
    )


def failing_runner(number: str, pack: str, audit: Any) -> Result:
    audit("plan", {})
    raise RuntimeError("register unavailable")


def app(runner: Any = None) -> TestClient:
    return make_app(runner or stub_runner)


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    migrate(URL)
    with app() as c:
        yield c


@pytest.fixture(scope="module")
def case_id(client: TestClient) -> str:
    response = client.post(
        "/cases", json={"company_number": "00000001", "jurisdiction": "uk"}, headers=ANALYST_1
    )
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "drafting"
    return str(response.json()["id"])


def test_an_opened_case_is_drafted_with_its_evidence(client: TestClient, case_id: str) -> None:
    body = client.get(f"/cases/{case_id}", headers=ANALYST_1).json()
    assert body["status"] == "draft"
    assert body["subject"] == "EXAMPLE TRADING LTD"
    assert body["rating"] == "low"
    assert body["draft"]["summary"][0]["source_id"] == SOURCE
    assert body["evidence"][0]["text"] == RECORD
    assert body["alerts"] == ["opensanctions:sanctions:X for " + SOURCE]


def test_the_audit_trail_has_every_step_in_order(client: TestClient, case_id: str) -> None:
    rows = client.get(f"/cases/{case_id}/audit", headers=ANALYST_1).json()
    assert [r["action"] for r in rows] == ["case_opened", "plan", "tool_call", "draft"]
    assert [r["actor"] for r in rows][1:] == ["agent"] * 3
    assert all(len(r["row_hash"]) == 64 for r in rows)


def test_the_queue_shows_own_cases_only(client: TestClient, case_id: str) -> None:
    assert case_id in {c["id"] for c in client.get("/cases", headers=ANALYST_1).json()}
    assert case_id not in {c["id"] for c in client.get("/cases", headers=ANALYST_2).json()}
    assert case_id in {c["id"] for c in client.get("/cases", headers=MLRO).json()}
    drafted = client.get("/cases", params={"status": "draft"}, headers=ANALYST_1).json()
    assert all(c["status"] == "draft" for c in drafted)


def test_another_analyst_gets_not_found(client: TestClient, case_id: str) -> None:
    assert client.get(f"/cases/{case_id}", headers=ANALYST_2).status_code == 404
    assert client.get(f"/cases/{case_id}/audit", headers=ANALYST_2).status_code == 404
    assert client.get(f"/cases/{uuid.uuid4()}", headers=ANALYST_1).status_code == 404


def test_auditors_and_other_packs_cannot_open_cases(client: TestClient) -> None:
    body = {"company_number": "00000001", "jurisdiction": "uk"}
    assert client.post("/cases", json=body, headers=AUDITOR).status_code == 403
    uae = {"company_number": "00000001", "jurisdiction": "uae"}
    assert client.post("/cases", json=uae, headers=ANALYST_1).status_code == 403
    bad = {"company_number": "1; DROP", "jurisdiction": "uk"}
    assert client.post("/cases", json=bad, headers=ANALYST_1).status_code == 422
    assert client.post("/cases", json=body).status_code == 401


def test_a_failed_run_is_recorded() -> None:
    with app(failing_runner) as c:
        opened = c.post(
            "/cases", json={"company_number": "00000002", "jurisdiction": "uk"}, headers=ANALYST_1
        ).json()
        body = c.get(f"/cases/{opened['id']}", headers=ANALYST_1).json()
        rows = c.get(f"/cases/{opened['id']}/audit", headers=ANALYST_1).json()
    assert body["status"] == "failed"
    assert body["draft"] is None
    assert [r["action"] for r in rows] == ["case_opened", "plan", "failed"]


def test_every_audit_row_verifies(client: TestClient, case_id: str) -> None:
    rows = client.get(f"/cases/{case_id}/audit", headers=ANALYST_1).json()
    assert rows and all(r["verified"] for r in rows)


def test_an_edited_audit_row_fails_verification(client: TestClient, case_id: str) -> None:
    import psycopg

    # Edit one row behind the append-only trigger, check it, then roll the edit back.
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("ALTER TABLE audit_log DISABLE TRIGGER audit_log_append_only")
        conn.execute(
            "UPDATE audit_log SET payload = '{\"tampered\": true}' WHERE seq = "
            "(SELECT min(seq) FROM audit_log WHERE case_id = %s)",
            (uuid.UUID(case_id),),
        )
        results = conn.execute(
            "SELECT hash_ok, link_ok FROM audit_verify(%s)", (uuid.UUID(case_id),)
        ).fetchall()
        conn.rollback()
    assert results[0] == (False, True)
    assert all(r == (True, True) for r in results[1:])


def test_the_whole_chain_verifies() -> None:
    import psycopg
    from lineage_db.audit import verify

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        report = verify(conn)
    assert report.ok, report


def test_an_export_verifies_on_its_own(client: TestClient, case_id: str, tmp_path: Any) -> None:
    import json
    import subprocess
    import sys
    from pathlib import Path

    assert client.get(f"/cases/{case_id}/audit/export", headers=ANALYST_1).status_code == 403
    response = client.get(f"/cases/{case_id}/audit/export", headers=AUDITOR)
    assert response.status_code == 200, response.text
    export = response.json()
    assert export["exported_by"] == "auditor-1" and export["rows"]
    path = tmp_path / "export.json"
    path.write_text(json.dumps(export))
    script = Path(__file__).resolve().parents[2] / "scripts" / "verify_audit_export.py"
    ok = subprocess.run([sys.executable, str(script), str(path)], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout
    # Change one recorded action and the check fails.
    export["rows"][0]["hashed_text"] = export["rows"][0]["hashed_text"].replace("case_opened", "x")
    path.write_text(json.dumps(export))
    bad = subprocess.run([sys.executable, str(script), str(path)], capture_output=True, text=True)
    assert bad.returncode == 1
    # The export itself is recorded in the trail.
    actions = [r["action"] for r in client.get(f"/cases/{case_id}/audit", headers=AUDITOR).json()]
    assert actions[-1] == "audit_export"
