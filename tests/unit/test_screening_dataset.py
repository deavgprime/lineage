import json
from dataclasses import replace
from pathlib import Path

import pytest
from lineage_evals import screening
from lineage_evals.names import normalise, script_of

DATASETS = Path(__file__).resolve().parents[2] / "packages" / "evals" / "datasets"


@pytest.fixture(scope="module")
def cases() -> list[screening.ScreeningCase]:
    return screening.load(DATASETS / "screening.jsonl")


@pytest.mark.unit
def test_dataset_is_valid(cases: list[screening.ScreeningCase]) -> None:
    assert screening.problems(cases) == []


@pytest.mark.unit
def test_meta_describes_the_dataset(cases: list[screening.ScreeningCase]) -> None:
    meta = json.loads((DATASETS / "screening.meta.json").read_text("utf-8"))
    assert meta["cases"] == len(cases)
    assert meta["version"]
    assert sum(meta["categories"].values()) == len(cases)


@pytest.mark.unit
def test_recall_set_is_140_cases(cases: list[screening.ScreeningCase]) -> None:
    assert sum(c.expected == "match" for c in cases) == 140


@pytest.mark.unit
def test_arabic_cases_are_written_in_arabic(cases: list[screening.ScreeningCase]) -> None:
    arabic = [c for c in cases if c.category == "arabic_script"]
    assert arabic
    assert all(script_of(c.query) == "arabic" for c in arabic)


@pytest.mark.unit
def test_negative_queries_do_not_repeat_a_positive_name(
    cases: list[screening.ScreeningCase],
) -> None:
    positive = {normalise(c.query) for c in cases if c.expected == "match"}
    assert not [c.id for c in cases if c.expected == "no_match" and normalise(c.query) in positive]


@pytest.mark.unit
def test_validation_catches_a_positive_without_ids(cases: list[screening.ScreeningCase]) -> None:
    broken = [replace(cases[0], expected_entity_ids=()), *cases[1:]]
    assert any("entity ids" in p for p in screening.problems(broken))


@pytest.mark.unit
def test_validation_catches_a_duplicate_query(cases: list[screening.ScreeningCase]) -> None:
    broken = [cases[0], replace(cases[1], query=cases[0].query), *cases[2:]]
    assert any("duplicate query" in p for p in screening.problems(broken))


@pytest.mark.unit
def test_validation_catches_a_short_dataset(cases: list[screening.ScreeningCase]) -> None:
    assert any("expected 200" in p for p in screening.problems(cases[:-1]))


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "folded"),
    [
        ("MORINA, Xhavit", "morina xhavit"),
        ("José  Núñez", "jose nunez"),
        ("Al-Rashid & Sons", "al rashid sons"),
        ("مُحَمَّد", "محمد"),
        ("أحمد", "احمد"),
    ],
)
def test_normalise(raw: str, folded: str) -> None:
    assert normalise(raw) == folded
