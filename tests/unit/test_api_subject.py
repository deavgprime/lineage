import pytest
from lineage_agent.agent import Result
from lineage_api.cases import subject_of


def result(*records: tuple[str, str]) -> Result:
    return Result(
        company_number="00519500",
        pack="uk",
        plan=[],
        draft=None,
        attempts=0,
        citation_failures=[],
        evidence=[{"source_id": s, "title": "", "text": t} for s, t in records],
    )


@pytest.mark.unit
def test_the_subject_is_the_company_itself_not_its_parent() -> None:
    r = result(
        ("companies-house:company:00445790", "Company TESCO PLC, number 00445790."),
        ("companies-house:company:00519500", "Company TESCO STORES LIMITED, number 00519500."),
    )
    assert subject_of(r, "00519500") == "TESCO STORES LIMITED"


@pytest.mark.unit
def test_falls_back_to_the_lei_name_then_the_number() -> None:
    lei = (
        "gleif:LEI1",
        "LEI LEI1. Legal name: EXAMPLE FZE. Registered as X in AE. Status: ACTIVE.",
    )
    assert subject_of(result(lei), "00000001") == "EXAMPLE FZE"
    assert subject_of(result(), "00000001") == "00000001"
