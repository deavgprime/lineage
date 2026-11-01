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
from collections.abc import Callable
from pathlib import Path

from lineage_agent.names import normalise, script_of
from lineage_evals.screening import PACK_CATEGORIES

SEED = 20261031
LATIN = re.compile(r"[A-Za-z][A-Za-z .,'\-]*[A-Za-z.]")
TITLED = re.compile(r"[A-Z][a-z]+(?: [A-Z][a-z]+)+")
NATIVE = {
    "uk": re.compile(f"[{chr(0x0400)}-{chr(0x04FF)} ]+"),
    "uae": re.compile(f"[{chr(0x0621)}-{chr(0x064A)} ]+"),
}
LISTS = {
    "uk": {"UK FCDO Sanctions List"},
    "uae": {
        "United Arab Emirates Local Terrorist List",
        "UN Security Council Consolidated Sanctions",
    },
}
PEP_COUNTRY = {"uk": "gb", "uae": "ae"}
ORG_SCHEMAS = {"Company", "Organization"}
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

Row = dict[str, str]


def read(path: Path, keep: set[str]) -> list[Row]:
    csv.field_size_limit(sys.maxsize)
    with path.open(encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r["schema"] in keep]


def aliases(row: Row) -> list[str]:
    return [a for a in row["aliases"].split(";") if a]


def build_index(rows: list[Row]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for name in [row["name"], *aliases(row)]:
            index[normalise(name)].add(row["id"])
    return index


def fits(name: str) -> bool:
    return bool(LATIN.fullmatch(name)) and 2 <= len(name.split()) <= 5 and len(name) <= 60


def kind(row: Row) -> str:
    return "person" if row["schema"] == "Person" else "organization"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sanctions", type=Path, required=True)
    ap.add_argument("--peps", type=Path, required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--out", type=Path, default=Path("packages/evals/datasets"))
    args = ap.parse_args()
    rng = random.Random(SEED)

    sanctions = read(args.sanctions, {"Person", *ORG_SCHEMAS})
    peps = read(args.peps, {"Person"})
    s_index, p_index = build_index(sanctions), build_index(peps)
    everything = set(s_index) | set(p_index)
    rows: list[dict[str, object]] = []
    used: set[str] = set()

    def add(
        query: str, etype: str, category: str, pack: str, listed: str | None, ids: set[str]
    ) -> None:
        used.add(normalise(query))
        rows.append(
            {
                "id": f"scr-{len(rows) + 1:03d}",
                "query": query,
                "script": script_of(query),
                "entity_type": etype,
                "jurisdiction": pack,
                "category": category,
                "expected": "match" if listed else "no_match",
                "expected_list": listed,
                "expected_entity_ids": sorted(ids),
            }
        )

    def take(
        pool: list[Row],
        want: int,
        pick: Callable[[Row], str | None],
        category: str,
        pack: str,
        listed: str,
        index: dict[str, set[str]],
    ) -> None:
        rng.shuffle(pool)
        done = 0
        for r in pool:
            if done == want:
                break
            query = pick(r)
            if query and normalise(query) not in used:
                add(query, kind(r), category, pack, listed, index[normalise(query)])
                done += 1
        assert done == want, f"{pack} {category}: only {done} of {want}"

    for pack in ("uk", "uae"):
        want = PACK_CATEGORIES
        listed = [r for r in sanctions if LISTS[pack] & set(r["dataset"].split(";"))]
        people = [r for r in listed if r["schema"] == "Person" and fits(r["name"])]
        orgs = [r for r in listed if r["schema"] in ORG_SCHEMAS and fits(r["name"])]
        half = want["exact_name"] // 2
        take(
            people,
            want["exact_name"] - half,
            lambda r: r["name"],
            "exact_name",
            pack,
            "sanctions",
            s_index,
        )
        take(orgs, half, lambda r: r["name"], "exact_name", pack, "sanctions", s_index)

        def variant(r: Row) -> str | None:
            alts = [a for a in aliases(r) if fits(a) and normalise(a) != normalise(r["name"])]
            return rng.choice(alts) if alts else None

        take(
            [r for r in listed if fits(r["name"])],
            want["latin_variant"],
            variant,
            "latin_variant",
            pack,
            "sanctions",
            s_index,
        )

        def native(r: Row, script: re.Pattern[str] = NATIVE[pack]) -> str | None:
            alts = [a for a in aliases(r) if script.fullmatch(a) and len(a.split()) >= 2]
            return rng.choice(alts) if alts else None

        take(
            list(listed), want["native_script"], native, "native_script", pack, "sanctions", s_index
        )
        local = [
            r
            for r in peps
            if PEP_COUNTRY[pack] in r["countries"].split(";")
            and fits(r["name"])
            and normalise(r["name"]) not in s_index
        ]
        take(local, want["pep"], lambda r: r["name"], "pep", pack, "pep", p_index)

    # Negatives apply to both packs.
    by_country: dict[str, list[list[str]]] = defaultdict(list)
    for r in sanctions:
        if r["schema"] == "Person" and TITLED.fullmatch(r["name"]) and r["countries"]:
            by_country[r["countries"].split(";")[0]].append(r["name"].split())
    countries = sorted(c for c, v in by_country.items() if len(v) >= 40)
    count = 0
    while count < 30:
        a, b = rng.sample(by_country[rng.choice(countries)], 2)
        query = f"{a[0]} {b[-1]}"
        key = normalise(query)
        if len(a[0]) > 2 and key not in everything and key not in used:
            add(query, "person", "token_collision", "both", None, set())
            count += 1

    first = Counter(normalise(r["name"]).split()[0] for r in peps if fits(r["name"]))
    last = Counter(normalise(r["name"]).split()[-1] for r in peps if fits(r["name"]))
    firsts = [t for t, _ in first.most_common(300) if len(t) > 3]
    lasts = [t for t, _ in last.most_common(300) if len(t) > 3]
    count = 0
    while count < 15:
        query = f"{rng.choice(firsts).title()} {rng.choice(lasts).title()}"
        key = normalise(query)
        if key not in everything and key not in used:
            add(query, "person", "common_name", "both", None, set())
            count += 1

    combos = [f"{a} {b} Ltd" for a in COMPANY_WORDS[0] for b in COMPANY_WORDS[1]]
    rng.shuffle(combos)
    count = 0
    for query in combos:
        key = normalise(query)
        if count < 15 and key not in everything and key not in used:
            add(query, "organization", "invented_company", "both", None, set())
            count += 1

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
        "jurisdictions": dict(Counter(str(r["jurisdiction"]) for r in rows)),
        "categories": dict(Counter(str(r["category"]) for r in rows)),
    }
    (args.out / "screening.meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
