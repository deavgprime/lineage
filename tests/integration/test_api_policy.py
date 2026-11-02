"""Policy questions through the API, with the fixture asker and a small test corpus."""

import os
import uuid
from collections.abc import Iterator, Sequence
from typing import Any

import psycopg
import pytest
from apitest import ANALYST_1, ANALYST_2, AUDITOR, MLRO, app, headers
from fastapi.testclient import TestClient
from lineage_api.runner import FixtureAsker, FixtureRunner
from lineage_db.audit import verify
from lineage_db.migrate import migrate
from lineage_ingest.policy import DIMENSIONS, Document, Section, load

URL = os.environ.get("DATABASE_URL", "")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="DATABASE_URL is not set"),
]
RUN = uuid.uuid4().hex[:8]
UAE_ANALYST = headers("analyst-uae-1", "analyst", ["uae"])


class Flat:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (DIMENSIONS - 1) for _ in texts]


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    migrate(URL)
    corpus = Document(
        id=f"test-policy-{RUN}",
        pack="uk",
        title="Test policy",
        source="test",
        version="1",
        licence="test",
        url=None,
        sections=(
            Section(f"Test {RUN} 10.1", "Record keeping", "Records are kept for five years. More."),
        ),
    )
    with psycopg.connect(URL, autocommit=True) as conn:
        load(conn, corpus, Flat())
    with app(FixtureRunner(), FixtureAsker()) as c:
        yield c
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("DELETE FROM policy_documents WHERE id = %s", (corpus.id,))


def ask(client: TestClient, who: dict[str, str], question: str, pack: str = "uk") -> Any:
    return client.post("/policy/questions", json={"question": question, "pack": pack}, headers=who)


def test_a_question_is_answered_from_the_corpus_with_a_citation(client: TestClient) -> None:
    response = ask(client, ANALYST_1, f"How long are records kept {RUN}?")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answered"] and body["asked_by_name"] == "analyst-uk-1"
    (statement,) = body["statements"]
    assert statement["quote"] == "Records are kept for five years"
    assert statement["source_id"] in {p["id"] for p in body["passages"]}


def test_history_is_private_except_to_mlros_and_auditors(client: TestClient) -> None:
    asked = ask(client, ANALYST_1, f"Record keeping {RUN}?").json()
    for who, sees in [(ANALYST_1, True), (ANALYST_2, False), (MLRO, True), (AUDITOR, True)]:
        ids = {q["id"] for q in client.get("/policy/questions", headers=who).json()}
        assert (asked["id"] in ids) is sees
    assert client.get(f"/policy/questions/{asked['id']}", headers=ANALYST_2).status_code == 404


def test_a_user_can_only_ask_in_their_own_pack(client: TestClient) -> None:
    assert ask(client, UAE_ANALYST, "Records?", "uk").status_code == 403
    assert ask(client, ANALYST_1, "x", "uk").status_code == 422


def test_questions_are_in_the_audit_chain() -> None:
    with psycopg.connect(URL) as conn:
        actions = {
            r[0]
            for r in conn.execute(
                "SELECT action FROM audit_log WHERE case_id IS NULL AND action LIKE 'policy%'"
            )
        }
        assert {"policy_question", "policy_search", "policy_answer"} <= actions
        assert verify(conn).ok
