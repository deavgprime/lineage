from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from lineage_evals import safety

DATASET = Path(__file__).resolve().parents[2] / "packages" / "evals" / "datasets" / "safety.jsonl"


@pytest.fixture(scope="module")
def cases() -> list[safety.SafetyCase]:
    return safety.load(DATASET)


@pytest.mark.unit
def test_dataset_is_valid(cases: list[safety.SafetyCase]) -> None:
    assert safety.problems(cases) == []


@pytest.mark.unit
def test_both_jurisdictions_and_languages_are_covered(cases: list[safety.SafetyCase]) -> None:
    seen = Counter((c.jurisdiction, c.language) for c in cases)
    assert seen[("uk", "en")] and seen[("uae", "en")] and seen[("uae", "ar")]


@pytest.mark.unit
def test_every_injection_keeps_the_genuine_news(cases: list[safety.SafetyCase]) -> None:
    injections = [c for c in cases if c.attack == "prompt_injection"]
    assert all("record_adverse_media" in c.must for c in injections)


@pytest.mark.unit
def test_validation_catches_an_unplanted_secret(cases: list[safety.SafetyCase]) -> None:
    case = cases[0]
    broken = [replace(case, must_not_contain=("not anywhere",)), *cases[1:]]
    assert any("neither in the text" in p for p in safety.problems(broken))


@pytest.mark.unit
def test_validation_catches_a_sign_off_case_that_allows_finalising(
    cases: list[safety.SafetyCase],
) -> None:
    case = next(c for c in cases if c.attack == "skip_signoff")
    broken = [replace(c, must=("refuse_request",)) if c is case else c for c in cases]
    assert any("keep the file open" in p for p in safety.problems(broken))
