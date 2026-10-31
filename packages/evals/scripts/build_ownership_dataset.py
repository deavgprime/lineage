"""Build datasets/ownership.jsonl from the Companies House register.

    COMPANIES_HOUSE_API_KEY=... python build_ownership_dataset.py --cache <dir>

Each case is a UK company and its ownership chain as the register of people with significant
control showed it on the retrieval date. The chain is followed through UK corporate controllers
until it reaches individuals, a company outside the UK, or a statement that no registrable person
exists.
"""

import argparse
import datetime as dt
import json
import random
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any

from lineage_ingest.companies_house import CompaniesHouse

# Companies House responses are untyped JSON.
Json = dict[str, Any]

SEED = 20261031
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
TARGET = {
    "individual_direct": 10,
    "two_layers": 8,
    "three_or_more_layers": 6,
    "ends_in_statement": 3,
    "ends_overseas": 3,
}
SEEDS = ["00519500", "03261722"]


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


def classify(node: Json) -> str | None:
    ends = ultimate(node)
    types = {e["type"] for e in ends}
    d = depth(node)
    if not ends:
        return "ends_in_statement" if node.get("stop") == "statement" else None
    if "unidentified_uk_company" in types or "legal_person" in types:
        return None
    if "protected" in types or "uk_company_without_controllers" in types:
        if d >= 2 and all(e["type"] == "uk_company_without_controllers" for e in ends):
            return "ends_in_statement"
        return None
    if types == {"overseas_company"}:
        return "ends_overseas"
    if types == {"individual"}:
        return {1: "individual_direct", 2: "two_layers"}.get(d, "three_or_more_layers")
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("packages/evals/datasets"))
    args = ap.parse_args()
    client = CompaniesHouse(cache=args.cache)
    rng = random.Random(SEED)
    chosen: dict[str, list[Json]] = {k: [] for k in TARGET}
    seen: set[str] = set()

    def consider(number: str) -> None:
        if number in seen:
            return
        seen.add(number)
        tree = resolve(client, number)
        label = classify(tree)
        if label and len(chosen[label]) < TARGET[label]:
            chosen[label].append(tree)

    for number in SEEDS:
        consider(number)
    day = dt.date(2012, 1, 1)
    while any(len(chosen[k]) < n for k, n in TARGET.items()):
        start = day + dt.timedelta(days=rng.randrange(0, 4500))
        query = urllib.parse.urlencode(
            {
                "company_status": "active",
                "company_type": "ltd",
                "size": 50,
                "incorporated_from": start.isoformat(),
                "incorporated_to": start.isoformat(),
            }
        )
        page = client.get(f"/advanced-search/companies?{query}") or {}
        for item in page.get("items", []):
            consider(item["company_number"])
            # Walk down from corporate controllers too, to find deeper chains faster.
        if len(seen) > 6000:
            break

    rows: list[Json] = []
    for label, trees in chosen.items():
        for tree in trees:
            rows.append(
                {
                    "id": f"own-{len(rows) + 1:03d}",
                    "company_number": tree["company_number"],
                    "company_name": tree["company_name"],
                    "category": label,
                    "depth": depth(tree),
                    "ultimate_controllers": ultimate(tree),
                    "chain": tree,
                }
            )
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "ownership.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    meta = {
        "source": "Companies House public data API",
        "retrieved": dt.date.today().isoformat(),
        "seed": SEED,
        "companies_examined": len(seen),
        "cases": len(rows),
        "categories": dict(Counter(r["category"] for r in rows)),
    }
    (args.out / "ownership.meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
