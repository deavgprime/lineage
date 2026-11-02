"""Score the Presidio pass on passages with planted personal data, and on passages with none.

    python -m lineage_evals.run_redaction

A planted value counts as caught when a finding covers it. On passages with nothing planted, any
finding is a false positive. The known-entity pass alone catches none of these values, because no
tool reported them, so recall without the Presidio pass is zero by construction and is shown for
comparison. Results are written to `baselines/redaction.json`, or to the path given with --out.
It needs no model, so CI runs it on every pull request.
"""

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from lineage_agent.pii import PresidioScanner

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "datasets" / "redaction.jsonl"
BASELINE = ROOT / "baselines" / "redaction.json"
# Every identifier type must be caught every time; names may slip occasionally.
GATES = {"identifier": 1.0, "person": 0.8}


def load(path: Path = DATASET) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run() -> dict[str, object]:
    scanner = PresidioScanner()
    planted: Counter[str] = Counter()
    caught: Counter[str] = Counter()
    misses: list[str] = []
    false_positives: list[str] = []
    clean = 0
    for case in load():
        findings = scanner.scan(str(case["text"]))
        values = case["planted"]
        if not values:
            clean += 1
            false_positives += [f"{case['id']}: {f.entity} {f.text!r}" for f in findings]
        for item in values:
            planted[item["type"]] += 1
            if any(item["value"] in f.text or f.text in item["value"] for f in findings):
                caught[item["type"]] += 1
            else:
                misses.append(f"{case['id']} {case['language']}: {item['type']} {item['value']!r}")
    by_type = {t: round(caught[t] / n, 3) for t, n in sorted(planted.items())}
    identifiers = [t for t in planted if t != "PERSON"]
    id_recall = sum(caught[t] for t in identifiers) / sum(planted[t] for t in identifiers)
    person_recall = caught["PERSON"] / planted["PERSON"] if planted["PERSON"] else 1.0
    return {
        "planted": sum(planted.values()),
        "recall_by_type": by_type,
        "identifier_recall": round(id_recall, 3),
        "person_recall": round(person_recall, 3),
        "recall_without_presidio": 0.0,
        "clean_passages": clean,
        "false_positives": len(false_positives),
        "passed": id_recall >= GATES["identifier"] and person_recall >= GATES["person"],
        "misses": misses,
        "false_positive_findings": false_positives,
    }


def main() -> None:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else BASELINE
    result = run()
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
