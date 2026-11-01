"""Run the registry tool over the ownership set and report exact chain matches.

    COMPANIES_HOUSE_API_KEY=... python -m lineage_evals.run_ownership

The register changes over time, so a chain that differs from the labelled one is reported with its
company number for a person to check: either the tool is wrong or the register has moved on.
"""

import argparse
import json
import sys
from pathlib import Path

from lineage_agent.tools.registry import resolve
from lineage_ingest.companies_house import CompaniesHouse

from lineage_evals.ownership import load

DATASET = Path(__file__).resolve().parent.parent / "datasets" / "ownership.jsonl"
CACHE = Path.home() / ".cache" / "lineage" / "companies-house"
GATE = 0.90


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, help="also write the result to this JSON file")
    args = ap.parse_args()
    client = CompaniesHouse(cache=CACHE)
    cases = load(DATASET)
    differ = [c for c in cases if resolve(client, c.company_number) != c.chain]
    rate = 1 - len(differ) / len(cases)
    body = json.dumps({"cases": len(cases), "exact": len(cases) - len(differ), "rate": rate})
    print(body)
    if args.out:
        args.out.write_text(body + "\n")
    for c in differ:
        print(f"differs: {c.id} {c.company_number} {c.company_name}")
    if rate < GATE:
        sys.exit(1)


if __name__ == "__main__":
    main()
