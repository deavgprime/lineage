from typing import Any

import pytest
from lineage_agent.tools.registry import depth, resolve, uk_number, ultimate


class FakeRegister:
    """Answers registry paths from a dict, as Companies House would."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def get(self, path: str) -> Any:
        return self.data.get(path.split("?")[0])


def psc(kind: str, **fields: Any) -> dict[str, Any]:
    return {"kind": kind, **fields}


def individual(company: str, ident: str) -> dict[str, Any]:
    link = f"/company/{company}/persons-with-significant-control/individual/{ident}"
    return psc(
        "individual-person-with-significant-control", name="Mr A Person", links={"self": link}
    )


UK_PARENT = {"country_registered": "England And Wales", "registration_number": "2"}

REGISTER = FakeRegister(
    {
        "/company/00000001": {"company_name": "CHILD LTD"},
        "/company/00000001/persons-with-significant-control": {
            "items": [
                psc(
                    "corporate-entity-person-with-significant-control",
                    name="PARENT LTD",
                    identification=UK_PARENT,
                ),
                psc(
                    "corporate-entity-person-with-significant-control",
                    name="FOREIGN INC",
                    identification={"legal_authority": "Delaware Law", "country_registered": "USA"},
                ),
                psc(
                    "individual-person-with-significant-control",
                    ceased_on="2020-01-01",
                    links={"self": "/old"},
                ),
            ]
        },
        "/company/00000002": {"company_name": "PARENT LTD"},
        "/company/00000002/persons-with-significant-control": {
            "items": [individual("00000002", "abc123")]
        },
        "/company/00000009": {"company_name": "WIDELY HELD PLC"},
        "/company/00000009/persons-with-significant-control": {"items": []},
        "/company/00000009/persons-with-significant-control-statements": {
            "items": [{"statement": "no-individual-or-entity-with-signficant-control"}]
        },
    }
)


@pytest.mark.unit
def test_follows_uk_parents_and_stops_at_overseas_ones() -> None:
    tree = resolve(REGISTER, "00000001")  # type: ignore[arg-type]
    types = [c["type"] for c in tree["controllers"]]
    assert types == ["uk_company", "overseas_company"]
    assert depth(tree) == 2


@pytest.mark.unit
def test_individuals_are_register_links_not_names() -> None:
    tree = resolve(REGISTER, "00000001")  # type: ignore[arg-type]
    people = [u for u in ultimate(tree) if u["type"] == "individual"]
    assert people == [
        {
            "type": "individual",
            "psc": "/company/00000002/persons-with-significant-control/individual/abc123",
        }
    ]
    assert "Mr A Person" not in str(tree)


@pytest.mark.unit
def test_ceased_controllers_are_ignored() -> None:
    tree = resolve(REGISTER, "00000001")  # type: ignore[arg-type]
    assert "/old" not in str(tree)


@pytest.mark.unit
def test_a_statement_ends_the_chain() -> None:
    tree = resolve(REGISTER, "00000009")  # type: ignore[arg-type]
    assert tree["stop"] == "statement"
    assert tree["controllers"] == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("ident", "number"),
    [
        ({"country_registered": "England And Wales", "registration_number": "123"}, "00000123"),
        ({"country_registered": "Scotland", "registration_number": "SC613281"}, "SC613281"),
        ({"country_registered": "Jersey", "registration_number": "12345"}, None),
        ({"legal_authority": "Companies Act 2006"}, None),
    ],
)
def test_uk_number(ident: dict[str, str], number: str | None) -> None:
    assert uk_number(ident) == number
