"""Trace who controls a UK company through the Companies House register.

The chain follows people with significant control through UK companies until it reaches individuals,
a company outside the UK, or a company that states it has no registrable person. Individuals are
returned as links to their register records, never by name, as decision 0001 requires for anything
that may later reach a model.
"""

from typing import Any

from lineage_ingest.companies_house import CompaniesHouse

# Companies House responses are untyped JSON.
Json = dict[str, Any]

UK_COUNTRIES = {
    "england",
    "wales",
    "scotland",
    "northern ireland",
    "united kingdom",
    "england and wales",
    "england & wales",
    "uk",
    "great britain",
}
MAX_DEPTH = 8


def is_uk(ident: dict[str, str]) -> bool:
    place = " ".join(
        ident.get(k) or "" for k in ("country_registered", "place_registered", "legal_authority")
    ).lower()
    return "companies act" in place or any(c in place for c in UK_COUNTRIES)


def uk_number(ident: dict[str, str]) -> str | None:
    country = (ident.get("country_registered") or ident.get("place_registered") or "").lower()
    number = (ident.get("registration_number") or "").strip().upper().replace(" ", "")
    if not number or not any(c in country for c in UK_COUNTRIES):
        return None
    if number.isdigit():
        number = number.zfill(8)
    return number if len(number) == 8 else None


def resolve(client: CompaniesHouse, number: str, seen: frozenset[str] = frozenset()) -> Json:
    """Return the chain above one company as a nested tree."""
    profile = client.get(f"/company/{number}") or {}
    node: Json = {
        "company_number": number,
        "company_name": profile.get("company_name"),
        "controllers": [],
    }
    if number in seen or len(seen) >= MAX_DEPTH:
        node["stop"] = "loop_or_depth"
        return node
    pscs = client.get(f"/company/{number}/persons-with-significant-control?items_per_page=100")
    controllers: list[Json] = []
    for item in (pscs or {}).get("items", []):
        if item.get("ceased_on"):
            continue
        kind = item.get("kind", "")
        if kind.startswith("individual"):
            # Private individuals are kept as their register record, never by name.
            controllers.append({"type": "individual", "psc": item["links"]["self"]})
        elif kind.startswith("corporate-entity"):
            ident = item.get("identification") or {}
            child = uk_number(ident)
            if child:
                controllers.append(
                    {"type": "uk_company", **resolve(client, child, seen | {number})}
                )
            elif is_uk(ident):
                # A UK company filed without a usable registration number.
                controllers.append({"type": "unidentified_uk_company", "name": item.get("name")})
            else:
                controllers.append({"type": "overseas_company", "name": item.get("name")})
        elif kind.startswith("legal-person"):
            controllers.append({"type": "legal_person", "name": item.get("name")})
        elif kind.startswith("super-secure"):
            controllers.append({"type": "protected"})
    if not controllers:
        statements = (
            client.get(f"/company/{number}/persons-with-significant-control-statements") or {}
        )
        active = [s for s in statements.get("items", []) if not s.get("ceased_on")]
        node["stop"] = "statement" if active else "none_filed"
    node["controllers"] = controllers
    return node


def depth(node: Json) -> int:
    kids = [c for c in node["controllers"] if c["type"] == "uk_company"]
    return 1 + max((depth(k) for k in kids), default=0)


def ultimate(node: Json) -> list[Json]:
    found: list[Json] = []
    for c in node["controllers"]:
        if c["type"] == "uk_company":
            found += ultimate(c) or [
                {"type": "uk_company_without_controllers", "company_number": c["company_number"]}
            ]
        else:
            found.append({k: v for k, v in c.items() if k in ("type", "name", "psc")})
    unique: list[Json] = []
    for f in found:
        if f not in unique:
            unique.append(f)
    return unique
