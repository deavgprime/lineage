from dataclasses import replace
from pathlib import Path

import pytest
from lineage_evals import ownership

DATASET = (
    Path(__file__).resolve().parents[2] / "packages" / "evals" / "datasets" / "ownership.jsonl"
)


@pytest.fixture(scope="module")
def cases() -> list[ownership.OwnershipCase]:
    return ownership.load(DATASET)


@pytest.mark.unit
def test_dataset_is_valid(cases: list[ownership.OwnershipCase]) -> None:
    assert ownership.problems(cases) == []


@pytest.mark.unit
def test_at_least_five_chains_pass_through_two_or_more_companies(
    cases: list[ownership.OwnershipCase],
) -> None:
    assert sum(c.depth >= 2 for c in cases) >= 5


@pytest.mark.unit
def test_validation_catches_a_named_individual(cases: list[ownership.OwnershipCase]) -> None:
    case = next(c for c in cases if c.category == "individual_direct")
    named = replace(case, ultimate_controllers=({"type": "individual", "name": "A Person"},))
    broken = [named if c is case else c for c in cases]
    assert any("by name" in p for p in ownership.problems(broken))


@pytest.mark.unit
def test_validation_catches_a_wrong_depth(cases: list[ownership.OwnershipCase]) -> None:
    case = next(c for c in cases if c.category == "two_layers")
    broken = [replace(c, depth=1) if c is case else c for c in cases]
    assert any("does not fit" in p for p in ownership.problems(broken))
