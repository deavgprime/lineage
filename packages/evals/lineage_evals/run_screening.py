"""Run the screening tool over the labelled set and report recall and precision per pack.

    DATABASE_URL=... python -m lineage_evals.run_screening

A positive case passes when any of its expected records is among the candidates. A negative case is
a false positive when any candidate is returned at all.
"""

import json
import os
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import psycopg
from lineage_agent.tools.screening import screen

from lineage_evals.screening import JURISDICTIONS, load

DATASET = Path(__file__).resolve().parent.parent / "datasets" / "screening.jsonl"
RECALL_GATE = 0.98


@dataclass(frozen=True)
class Result:
    pack: str
    positives: int
    found: int
    recall: float
    negatives: int
    false_positives: int
    precision: float


def run(url: str) -> tuple[list[Result], list[str]]:
    cases = load(DATASET)
    misses: list[str] = []
    found: Counter[str] = Counter()
    false_positives: Counter[str] = Counter()
    with psycopg.connect(url) as conn:
        for case in cases:
            packs = JURISDICTIONS if case.jurisdiction == "both" else (case.jurisdiction,)
            for pack in packs:
                ids = {c.record_id.rsplit(":", 1)[-1] for c in screen(conn, case.query, pack)}
                if case.expected == "match":
                    if ids & set(case.expected_entity_ids):
                        found[pack] += 1
                    else:
                        misses.append(f"{pack} {case.id} {case.category}: {case.query}")
                elif ids:
                    false_positives[pack] += 1
                    misses.append(f"{pack} {case.id} false positive: {case.query}")
    results = []
    for pack in JURISDICTIONS:
        positives = sum(c.expected == "match" and c.jurisdiction == pack for c in cases)
        negatives = sum(c.expected == "no_match" for c in cases)
        flagged = found[pack] + false_positives[pack]
        results.append(
            Result(
                pack=pack,
                positives=positives,
                found=found[pack],
                recall=found[pack] / positives,
                negatives=negatives,
                false_positives=false_positives[pack],
                precision=found[pack] / flagged if flagged else 1.0,
            )
        )
    return results, misses


def main() -> None:
    results, misses = run(os.environ["DATABASE_URL"])
    print(json.dumps([asdict(r) for r in results], indent=2))
    for miss in misses:
        print(miss)
    if any(r.recall < RECALL_GATE for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
