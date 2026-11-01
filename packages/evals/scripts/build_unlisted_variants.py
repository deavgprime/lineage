"""Add screening cases whose spelling appears on no list.

    DATABASE_URL=... python build_unlisted_variants.py

Each case takes a person already in the screening set and changes the spelling the way people and
systems do: a dropped middle name, a common transliteration, a missing letter, or two letters
swapped. A variant is kept only if no record in the loaded index carries that spelling, so a match
has to come from the screening tool's tolerance and not from the list.
"""

import json
import os
import random
from collections import Counter
from pathlib import Path

import psycopg
from lineage_agent.names import normalise
from lineage_evals.screening import JURISDICTIONS, UNLISTED_PER_PACK, load

DATASETS = Path(__file__).resolve().parents[1] / "datasets"
SEED = 20261101
SWAPS = [
    ("ou", "u"),
    ("kh", "h"),
    ("y", "i"),
    ("ei", "ey"),
    ("ph", "f"),
    ("ck", "k"),
    ("oo", "u"),
    ("ee", "i"),
    ("sh", "sch"),
    ("ov", "ow"),
    ("ch", "tch"),
    ("ia", "iya"),
]


def drop_middle(tokens: list[str], rng: random.Random) -> list[str] | None:
    return [tokens[0], *tokens[2:]] if len(tokens) >= 3 else None


def transliterate(tokens: list[str], rng: random.Random) -> list[str] | None:
    for i in rng.sample(range(len(tokens)), len(tokens)):
        for old, new in SWAPS:
            if old in tokens[i].lower():
                word = tokens[i].lower().replace(old, new, 1)
                return [
                    *tokens[:i],
                    word.title() if tokens[i].istitle() else word.upper(),
                    *tokens[i + 1 :],
                ]
    return None


def drop_letter(tokens: list[str], rng: random.Random) -> list[str] | None:
    i = max(range(len(tokens)), key=lambda k: len(tokens[k]))
    word = tokens[i]
    if len(word) < 5:
        return None
    k = rng.randrange(1, len(word) - 1)
    return [*tokens[:i], word[:k] + word[k + 1 :], *tokens[i + 1 :]]


def swap_letters(tokens: list[str], rng: random.Random) -> list[str] | None:
    i = max(range(len(tokens)), key=lambda k: len(tokens[k]))
    word = tokens[i]
    if len(word) < 5:
        return None
    k = rng.randrange(1, len(word) - 2)
    if word[k] == word[k + 1]:
        return None
    return [*tokens[:i], word[:k] + word[k + 1] + word[k] + word[k + 2 :], *tokens[i + 1 :]]


CHANGES = [drop_middle, transliterate, drop_letter, swap_letters]


def main() -> None:
    # Seeded so the dataset rebuilds the same way. Not used for anything secret.
    rng = random.Random(SEED)  # noqa: S311
    path = DATASETS / "screening.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    rows = [r for r in rows if r["category"] != "unlisted_variant"]
    cases = [c for c in load(path) if c.category != "unlisted_variant"]
    used = {normalise(c.query) for c in cases}
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        listed = {r[0] for r in conn.execute("SELECT DISTINCT name_norm FROM screening_names")}
        version = conn.execute(
            "SELECT dataset_version FROM source_records WHERE source = 'opensanctions' "
            "GROUP BY dataset_version ORDER BY count(*) DESC LIMIT 1"
        ).fetchone()
    added: list[dict[str, object]] = []
    for pack in JURISDICTIONS:
        pool = [
            c
            for c in cases
            if c.jurisdiction == pack
            and c.entity_type == "person"
            and c.category in ("exact_name", "latin_variant")
            and c.script == "latin"
        ]
        rng.shuffle(pool)
        done = 0
        for n, case in enumerate(pool):
            if done == UNLISTED_PER_PACK:
                break
            change = CHANGES[n % len(CHANGES)]
            tokens = case.query.replace(",", "").split()
            new = change(tokens, rng)
            if not new:
                continue
            query = " ".join(new)
            key = normalise(query)
            if key in listed or key in used:
                continue
            used.add(key)
            added.append(
                {
                    "id": f"scr-{len(rows) + len(added) + 1:03d}",
                    "query": query,
                    "script": "latin",
                    "entity_type": "person",
                    "jurisdiction": pack,
                    "category": "unlisted_variant",
                    "expected": "match",
                    "expected_list": "sanctions",
                    "expected_entity_ids": list(case.expected_entity_ids),
                    "variant_of": case.id,
                    "change": change.__name__,
                }
            )
            done += 1
        if done != UNLISTED_PER_PACK:
            raise SystemExit(f"{pack}: only {done} variants")
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows + added), encoding="utf-8"
    )
    meta_path = DATASETS / "screening.meta.json"
    meta = json.loads(meta_path.read_text())
    meta["cases"] = len(rows) + len(added)
    everything = rows + added
    meta["categories"] = dict(Counter(str(r["category"]) for r in everything))
    meta["jurisdictions"] = dict(Counter(str(r["jurisdiction"]) for r in everything))
    meta["unlisted_checked_against"] = version[0] if version else None
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"added {len(added)} cases")


if __name__ == "__main__":
    main()
