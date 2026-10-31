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
    assert meta["jurisdictions"] == {"uk": 70, "uae": 70, "both": 60}
    assert meta["version"]
    assert sum(meta["categories"].values()) == len(cases)


@pytest.mark.unit
@pytest.mark.parametrize("pack", screening.JURISDICTIONS)
def test_each_pack_has_70_positive_cases(cases: list[screening.ScreeningCase], pack: str) -> None:
    assert sum(c.expected == "match" and c.jurisdiction == pack for c in cases) == 70


@pytest.mark.unit
@pytest.mark.parametrize(("pack", "script"), screening.NATIVE_SCRIPT.items())
def test_native_script_cases_use_the_pack_script(
    cases: list[screening.ScreeningCase], pack: str, script: str
) -> None:
    native = [c for c in cases if c.category == "native_script" and c.jurisdiction == pack]
    assert native
    assert all(script_of(c.query) == script for c in native)


@pytest.mark.unit
def test_validation_catches_a_wrong_native_script(cases: list[screening.ScreeningCase]) -> None:
    case = next(c for c in cases if c.category == "native_script" and c.jurisdiction == "uk")
    broken = [replace(c, jurisdiction="uae") if c is case else c for c in cases]
    assert any("native script" in p for p in screening.problems(broken))


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
