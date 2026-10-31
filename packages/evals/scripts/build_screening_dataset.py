"""Build datasets/screening.jsonl from the OpenSanctions bulk files.

    python build_screening_dataset.py --sanctions sanctions.csv --peps peps.csv --version <id>

The inputs are the targets.simple.csv files of the `sanctions` and `peps` datasets. The output is
fixed once reviewed, so a rebuild against newer data produces a different file on purpose.
"""

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from lineage_evals.names import normalise, script_of

SEED = 20261031
LATIN = re.compile(r"[A-Za-z][A-Za-z .,'\-]*[A-Za-z.]")
ARABIC = re.compile(r"[ء-ي ]+")
ORG_SCHEMAS = {"Company", "Organization"}
TITLED = re.compile(r"[A-Z][a-z]+(?: [A-Z][a-z]+)+")
LISTS_USED = {
    "US OFAC Specially Designated Nationals (SDN) List",
    "UN Security Council Consolidated Sanctions",
    "EU Financial Sanctions Files (FSF)",
    "UK FCDO Sanctions List",
    "United Arab Emirates Local Terrorist List",
    "Saudi Arabia National Terrorism List (UNSCR 1373)",
    "Qatar Unified Record of Persons and Entities on Sanction List",
}
COMPANY_WORDS = (
    [
        "Harbourline",
        "Northgate",
        "Silverbrook",
        "Larchfield",
        "Ironwood",
        "Kestrel Point",
        "Brightwater",
        "Oakridge",
        "Stonebridge",
        "Westmarch",
        "Fernhill",
        "Copperleaf",
        "Redcliffe",
        "Alderbank",
        "Maple Quay",
    ],
    [
        "Logistics",
        "Trading",
        "Holdings",
        "Engineering",
        "Marine Services",
        "Foods",
        "Capital Partners",
        "Industrial Supply",
        "Consulting",
        "Textiles",
        "Energy Services",
        "Property Group",
        "Packaging",
        "Shipping Agency",
        "Components",
    ],
)


def read(path: Path, keep: set[str]) -> list[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)
    with path.open(encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r["schema"] in keep]


def names_of(row: dict[str, str]) -> list[str]:
    return [row["name"], *[a for a in row["aliases"].split(";") if a]]


def build_index(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for name in names_of(row):
            index[normalise(name)].add(row["id"])
    return index


def case(
    n: int,
    query: str,
    etype: str,
    category: str,
    positive: bool,
    listed: str | None,
    ids: list[str],
) -> dict[str, object]:
    return {
        "id": f"scr-{n:03d}",
        "query": query,
        "script": script_of(query),
        "entity_type": etype,
        "category": category,
        "expected": "match" if positive else "no_match",
        "expected_list": listed if positive else None,
        "expected_entity_ids": sorted(ids) if positive else [],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sanctions", type=Path, required=True)
    ap.add_argument("--peps", type=Path, required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--out", type=Path, default=Path("packages/evals/datasets"))
    args = ap.parse_args()
    rng = random.Random(SEED)

    sanctions = [
        r
        for r in read(args.sanctions, {"Person", *ORG_SCHEMAS})
        if LISTS_USED & set(r["dataset"].split(";"))
    ]
    peps = read(args.peps, {"Person"})
    s_index, p_index = build_index(sanctions), build_index(peps)
    everything = set(s_index) | set(p_index)

    def etype(row: dict[str, str]) -> str:
        return "person" if row["schema"] == "Person" else "organization"

    def fits(name: str) -> bool:
        return bool(LATIN.fullmatch(name)) and 2 <= len(name.split()) <= 5 and len(name) <= 60

    rows: list[dict[str, object]] = []

    def add(
        query: str, kind: str, category: str, positive: bool, listed: str | None, ids: set[str]
    ) -> None:
        rows.append(case(len(rows) + 1, query, kind, category, positive, listed, sorted(ids)))

    used: set[str] = set()

    def fresh(query: str) -> bool:
        key = normalise(query)
        if key in used:
            return False
        used.add(key)
        return True

    # exact_name: 30 people, 30 organisations, primary name as listed
    for kind, want in (("person", 30), ("organization", 30)):
        pool = [r for r in sanctions if etype(r) == kind and fits(r["name"])]
        rng.shuffle(pool)
        done = 0
        for r in pool:
            if done < want and fresh(r["name"]):
                add(r["name"], kind, "exact_name", True, "sanctions", s_index[normalise(r["name"])])
                done += 1

    # latin_variant: another Latin spelling that the record itself lists
    pool = [
        r for r in sanctions if fits(r["name"]) and any(fits(a) for a in r["aliases"].split(";"))
    ]
    rng.shuffle(pool)
    done = 0
    for r in pool:
        alts = [
            a for a in r["aliases"].split(";") if fits(a) and normalise(a) != normalise(r["name"])
        ]
        if alts and done < 30:
            alias = rng.choice(alts)
            if fresh(alias):
                add(alias, etype(r), "latin_variant", True, "sanctions", s_index[normalise(alias)])
                done += 1

    # arabic_script: the Arabic spelling the record lists
    pool = [
        r
        for r in sanctions
        if any(ARABIC.fullmatch(a) and len(a.split()) >= 2 for a in r["aliases"].split(";"))
    ]
    rng.shuffle(pool)
    done = 0
    for r in pool:
        alts = [a for a in r["aliases"].split(";") if ARABIC.fullmatch(a) and len(a.split()) >= 2]
        alias = rng.choice(alts)
        if done < 30 and fresh(alias):
            add(alias, etype(r), "arabic_script", True, "sanctions", s_index[normalise(alias)])
            done += 1

    # pep: politically exposed people, kept out of the sanctions index
    pool = [r for r in peps if fits(r["name"]) and normalise(r["name"]) not in s_index]
    rng.shuffle(pool)
    done = 0
    for r in pool:
        if done < 20 and fresh(r["name"]):
            add(r["name"], "person", "pep", True, "pep", p_index[normalise(r["name"])])
            done += 1

    # token_collision: given name of one listed person, family name of another, same country
    by_country: dict[str, list[list[str]]] = defaultdict(list)
    for r in sanctions:
        if r["schema"] == "Person" and TITLED.fullmatch(r["name"]) and r["countries"]:
            by_country[r["countries"].split(";")[0]].append(r["name"].split())
    countries = sorted(c for c, v in by_country.items() if len(v) >= 40)
    done = 0
    while done < 30:
        people = by_country[rng.choice(countries)]
        a, b = rng.sample(people, 2)
        query = f"{a[0]} {b[-1]}"
        if len(a[0]) > 2 and normalise(query) not in everything and fresh(query):
            add(query, "person", "token_collision", False, None, set())
            done += 1

    # common_name: frequent given and family names from the PEP list, in a pairing not on any list
    first = Counter(normalise(r["name"]).split()[0] for r in peps if fits(r["name"]))
    last = Counter(normalise(r["name"]).split()[-1] for r in peps if fits(r["name"]))
    firsts = [t for t, n in first.most_common(300) if len(t) > 3]
    lasts = [t for t, n in last.most_common(300) if len(t) > 3]
    done = 0
    while done < 15:
        query = f"{rng.choice(firsts).title()} {rng.choice(lasts).title()}"
        if normalise(query) not in everything and fresh(query):
            add(query, "person", "common_name", False, None, set())
            done += 1

    # invented_company: made-up trading names that appear on no list
    combos = [f"{a} {b} Ltd" for a in COMPANY_WORDS[0] for b in COMPANY_WORDS[1]]
    rng.shuffle(combos)
    done = 0
    for query in combos:
        if done < 15 and normalise(query) not in everything and fresh(query):
            add(query, "organization", "invented_company", False, None, set())
            done += 1

    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "screening.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    meta = {
        "source": "OpenSanctions bulk data, datasets sanctions and peps",
        "version": args.version,
        "seed": SEED,
        "licence": "CC BY-NC 4.0, see README.md in this folder",
        "cases": len(rows),
        "categories": dict(Counter(str(r["category"]) for r in rows)),
    }
    (args.out / "screening.meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
