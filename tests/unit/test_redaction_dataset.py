import json
from collections import Counter
from pathlib import Path

import pytest
from lineage_agent.names import script_of
from lineage_agent.pii import ENTITIES

ROWS = [
    json.loads(line)
    for line in (
        Path(__file__).resolve().parents[2] / "packages" / "evals" / "datasets" / "redaction.jsonl"
    )
    .read_text(encoding="utf-8")
    .splitlines()
]


@pytest.mark.unit
def test_ids_are_unique_and_values_are_in_their_text() -> None:
    assert len({r["id"] for r in ROWS}) == len(ROWS)
    for r in ROWS:
        for item in r["planted"]:
            assert item["value"] in r["text"], r["id"]
            assert item["type"] in ENTITIES, r["id"]


@pytest.mark.unit
def test_text_matches_its_language() -> None:
    for r in ROWS:
        assert script_of(r["text"]) == {"en": "latin", "ar": "arabic"}[r["language"]], r["id"]


@pytest.mark.unit
def test_every_type_is_covered_and_clean_passages_exist() -> None:
    types = Counter(item["type"] for r in ROWS for item in r["planted"])
    assert set(types) == set(ENTITIES) - {"CREDIT_CARD"}
    assert sum(not r["planted"] for r in ROWS) >= 10
    assert {r["language"] for r in ROWS if not r["planted"]} == {"en", "ar"}
