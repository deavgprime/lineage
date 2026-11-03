"""Usage limits on opening cases and asking policy questions."""

import os
import uuid
from typing import Any

import pytest
from apitest import app, headers
from lineage_api.limits import Limits
from lineage_api.runner import FixtureAsker, FixtureRunner
from lineage_db.migrate import migrate

URL = os.environ.get("DATABASE_URL", "")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="DATABASE_URL is not set"),
]


def fresh_analyst() -> dict[str, str]:
    # A user of their own, so earlier tests' cases do not count against them.
    return headers(f"limits-{uuid.uuid4().hex[:8]}", "analyst", ["uk"])


def open_case(client: Any, who: dict[str, str], n: int) -> Any:
    body = {"company_number": f"0077{n:04d}", "jurisdiction": "uk"}
    return client.post("/cases", json=body, headers=who)


def test_cases_per_hour_are_limited_per_user() -> None:
    migrate(URL)
    limits = Limits(cases_per_hour=3, drafting_per_user=100, drafting_total=100)
    one, other = fresh_analyst(), fresh_analyst()
    with app(FixtureRunner(), limits=limits) as client:
        assert [open_case(client, one, i).status_code for i in range(3)] == [202] * 3
        refused = open_case(client, one, 3)
        assert refused.status_code == 429
        assert refused.headers["retry-after"] == "3600"
        assert open_case(client, other, 4).status_code == 202


def test_drafting_at_once_is_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    import lineage_api.cases as cases

    migrate(URL)
    # Keep cases in "drafting" by not running the background task at all.
    monkeypatch.setattr(cases, "run_case", lambda *args, **kwargs: None)
    limits = Limits(cases_per_hour=100, drafting_per_user=2, drafting_total=100)
    who = fresh_analyst()
    with app(FixtureRunner(), limits=limits) as client:
        assert [open_case(client, who, 10 + i).status_code for i in range(2)] == [202, 202]
        refused = open_case(client, who, 12)
        assert refused.status_code == 429 and "drafting at once" in refused.json()["detail"]


def test_questions_per_hour_are_limited() -> None:
    migrate(URL)
    limits = Limits(questions_per_hour=2)
    who = fresh_analyst()
    with app(FixtureRunner(), FixtureAsker(), limits=limits) as client:
        ask = {"question": "How long are records kept?", "pack": "uk"}
        codes = [
            client.post("/policy/questions", json=ask, headers=who).status_code for _ in range(3)
        ]
        assert codes == [200, 200, 429]
