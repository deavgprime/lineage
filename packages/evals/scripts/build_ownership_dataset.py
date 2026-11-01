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

from lineage_agent.tools.registry import Json, depth, resolve, ultimate
from lineage_ingest.companies_house import CompaniesHouse

SEED = 20261031
TARGET = {
    "individual_direct": 10,
    "two_layers": 8,
    "three_or_more_layers": 6,
    "ends_in_statement": 3,
    "ends_overseas": 3,
}
SEEDS = ["00519500", "03261722"]


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
    # Seeded so the dataset rebuilds the same way. Not used for anything secret.
    rng = random.Random(SEED)  # noqa: S311
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
