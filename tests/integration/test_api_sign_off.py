"""Sign-off rules through the API, and the database refusing every other way to finish a file."""

import os
import uuid
from collections.abc import Iterator
from typing import Any, Literal

import psycopg
import pytest
from apitest import ANALYST_1, ANALYST_2, AUDITOR, MLRO, MLRO_2, RUN, app
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
ALERT = "opensanctions:sanctions:Q1 for " + SOURCE


def runner(number: str, pack: str, audit: Any) -> Result:
    """Rates high for company numbers starting with H, low otherwise, with one weak alert."""
    rating: Literal["low", "high"] = "high" if number.startswith("H") else "low"
    record = f"Company EXAMPLE {number} LTD, number {number}."
    claim = Claim(text="Registered.", source_id=SOURCE, quote=record)
    draft = Draft(
        summary=[claim], ownership=[], screening=[], risk_rating=rating, risk_reasons=[claim]
    )
    return Result(
        company_number=number,
        pack=pack,
        plan=[],
        draft=draft,
        attempts=1,
        citation_failures=[],
        evidence=[{"source_id": SOURCE, "title": "record", "text": record}],
        alerts=[ALERT],
    )


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    migrate(URL)
    with app(runner) as c:
        yield c


def open_case(client: TestClient, number: str) -> str:
    body = {"company_number": number, "jurisdiction": "uk"}
    response = client.post("/cases", json=body, headers=ANALYST_1)
    assert response.status_code == 202, response.text
    return str(response.json()["id"])


def sign(client: TestClient, case: str, who: dict[str, str], **body: Any) -> Any:
    body.setdefault("alert_notes", {ALERT: "Different entity: name only, no shared details."})
    return client.post(f"/cases/{case}/sign-off", json=body, headers=who)


def test_a_low_file_is_final_after_one_sign_off(client: TestClient) -> None:
    case = open_case(client, "00000011")
    response = sign(client, case, ANALYST_1, rating="low")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["rating"]) == ("final", "low")
    assert body["sign_offs"][0]["stage"] == "first"
    assert body["sign_offs"][0]["signer_name"] == "analyst-uk-1"
    actions = [r["action"] for r in client.get(f"/cases/{case}/audit", headers=ANALYST_1).json()]
    assert actions[-1] == "sign_off"
    assert sign(client, case, ANALYST_1, rating="low").status_code == 409


def test_every_alert_needs_a_note(client: TestClient) -> None:
    case = open_case(client, "00000012")
    response = sign(client, case, ANALYST_1, rating="low", alert_notes={ALERT: "  "})
    assert response.status_code == 409
    assert "clear every alert" in response.json()["detail"]


def test_an_override_needs_a_reason(client: TestClient) -> None:
    case = open_case(client, "00000013")
    assert sign(client, case, ANALYST_1, rating="medium").status_code == 422
    response = sign(client, case, ANALYST_1, rating="medium", reason="Cash-intensive sector.")
    assert response.json()["sign_offs"][0]["reason"] == "Cash-intensive sector."


def test_only_the_assigned_analyst_and_no_auditor_can_sign(client: TestClient) -> None:
    case = open_case(client, "00000014")
    assert sign(client, case, ANALYST_2, rating="low").status_code == 404
    assert sign(client, case, AUDITOR, rating="low").status_code == 403


def test_a_high_file_waits_for_a_different_mlro(client: TestClient) -> None:
    case = open_case(client, "H0000015")
    first = sign(client, case, ANALYST_1, rating="high").json()
    assert first["status"] == "awaiting_mlro"
    assert sign(client, case, ANALYST_1, rating="high").status_code == 403
    done = sign(client, case, MLRO, rating="high")
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "final"
    assert [s["stage"] for s in done.json()["sign_offs"]] == ["first", "second"]


def test_an_mlro_cannot_give_both_sign_offs(client: TestClient) -> None:
    opened = client.post(
        "/cases", json={"company_number": "H0000016", "jurisdiction": "uk"}, headers=MLRO
    ).json()
    assert sign(client, opened["id"], MLRO, rating="high").json()["status"] == "awaiting_mlro"
    again = sign(client, opened["id"], MLRO, rating="high")
    assert again.status_code == 409
    assert sign(client, opened["id"], MLRO_2, rating="high").json()["status"] == "final"


def owner_update(case: str, sql: str) -> None:
    with psycopg.connect(URL) as conn:
        conn.execute(sql, (uuid.UUID(case),))


def test_the_database_refuses_to_finish_a_file_without_a_sign_off(client: TestClient) -> None:
    case = open_case(client, "00000017")
    with pytest.raises(psycopg.errors.RaiseException, match="only be signed off"):
        owner_update(case, "UPDATE cases SET status = 'final', rating = 'low' WHERE id = %s")


def test_the_database_refuses_a_high_file_with_one_signer(client: TestClient) -> None:
    case = open_case(client, "H0000018")
    with psycopg.connect(URL) as conn:
        draft_id = conn.execute(
            "SELECT id FROM drafts WHERE case_id = %s", (uuid.UUID(case),)
        ).fetchone()
        assert draft_id is not None
        conn.execute(
            "INSERT INTO sign_offs (case_id, draft_id, signer, signer_role, stage, "
            "drafted_rating, rating) VALUES (%s, %s, %s, 'analyst', 'first', 'high', 'high')",
            (uuid.UUID(case), draft_id[0], f"a1-{RUN}"),
        )
        with pytest.raises(psycopg.errors.RaiseException, match="different MLRO"):
            conn.execute(
                "UPDATE cases SET status = 'final', rating = 'high' WHERE id = %s",
                (uuid.UUID(case),),
            )


def test_a_final_file_never_changes(client: TestClient) -> None:
    case = open_case(client, "00000019")
    sign(client, case, ANALYST_1, rating="low")
    with pytest.raises(psycopg.errors.RaiseException, match="is final"):
        owner_update(case, "UPDATE cases SET subject = 'changed' WHERE id = %s")


def test_lowering_a_high_file_still_needs_a_different_mlro(client: TestClient) -> None:
    case = open_case(client, "H0000020")
    lowered = sign(client, case, ANALYST_1, rating="low", reason="Analyst disagrees.")
    assert lowered.status_code == 200, lowered.text
    assert lowered.json()["status"] == "awaiting_mlro"
    done = sign(client, case, MLRO, rating="low", reason="Agreed after review.")
    assert done.json()["status"] == "final"


def test_the_database_refuses_a_lowered_high_file_with_one_signer(client: TestClient) -> None:
    case = open_case(client, "H0000021")
    with psycopg.connect(URL) as conn:
        draft_id = conn.execute(
            "SELECT id FROM drafts WHERE case_id = %s", (uuid.UUID(case),)
        ).fetchone()
        assert draft_id is not None
        conn.execute(
            "INSERT INTO sign_offs (case_id, draft_id, signer, signer_role, stage, "
            "drafted_rating, rating, reason) "
            "VALUES (%s, %s, %s, 'analyst', 'first', 'high', 'low', 'lowered')",
            (uuid.UUID(case), draft_id[0], f"a1-{RUN}"),
        )
        with pytest.raises(psycopg.errors.RaiseException, match="different MLRO"):
            conn.execute(
                "UPDATE cases SET status = 'final', rating = 'low' WHERE id = %s",
                (uuid.UUID(case),),
            )
