"""Write the README's results table from the committed baselines.

    python -m lineage_evals.readme          # rewrite the table in README.md
    python -m lineage_evals.readme --check  # fail if README.md is out of date

The table sits between two markers in README.md. A unit test runs the check, so the README can never
show numbers the baselines do not.
"""

import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BASELINES = ROOT / "packages" / "evals" / "baselines"
README = ROOT / "README.md"
START = "<!-- results:start -->"
END = "<!-- results:end -->"


def _load(name: str) -> Any:
    return json.loads((BASELINES / f"{name}.json").read_text(encoding="utf-8"))


def _pct(value: float) -> str:
    """A percentage to one decimal, rounded down so the README never overstates a result."""
    text = f"{math.floor(value * 1000 + 1e-9) / 10:.1f}".removesuffix(".0")
    return f"{text}%"


def table() -> str:
    screening = {r["pack"]: r for r in _load("screening")}
    ownership = _load("ownership")
    citations = _load("citations")["summary"]
    safety = _load("safety")["summary"]
    redaction = _load("redaction")
    policy = _load("policy")
    answers = policy["answers"]
    uk, uae = screening["uk"], screening["uae"]
    lowest = min(citations["faithful_by_company"].values())
    every_pr, committed = "Every pull request", "Committed with the change"
    if redaction["false_positives"] == 0:
        ids = f"no false positives on {redaction['clean_passages']} clean passages"
    else:
        ids = f"{redaction['false_positives']} false positives"
    rows = [
        (
            "Sanctions and PEP recall, listed names",
            f"UK {uk['found']} of {uk['positives']}, UAE {uae['found']} of {uae['positives']}",
            "At least 98% per pack",
            every_pr,
        ),
        (
            "Recall, spellings on no list",
            f"UK {uk['unlisted_found']} of {uk['unlisted']}, "
            f"UAE {uae['unlisted_found']} of {uae['unlisted']}",
            "Reported",
            every_pr,
        ),
        (
            "Screening false positives",
            f"UK {uk['false_positives']}, UAE {uae['false_positives']} "
            f"of {uk['negatives']} negatives",
            "Reported",
            every_pr,
        ),
        (
            "Ownership chains, live register",
            f"{ownership['exact']} of {ownership['cases']}",
            "At least 90%",
            every_pr,
        ),
        (
            "Claims citing a source",
            f"{_pct(citations['cited'])} of {citations['claims']} claims "
            f"in {citations['files']} files",
            "100%",
            committed,
        ),
        (
            "Claims judged faithful",
            f"{_pct(citations['faithful'])}, lowest company {_pct(lowest)}",
            "At least 95% per company",
            committed,
        ),
        ("Safety runs failed", f"{safety['failed_runs']} of {safety['runs']}", "0", committed),
        (
            "Identifiers redacted",
            f"{_pct(redaction['identifier_recall'])}, {ids}",
            "100%",
            every_pr,
        ),
        ("Names redacted (English)", _pct(redaction["person_recall"]), "At least 80%", every_pr),
        (
            "Policy retrieval recall at 5",
            _pct(policy["retrieval"]["recall_at_5"]),
            "Reported",
            committed,
        ),
        (
            "Policy answers cited and faithful",
            f"{_pct(answers['cited'])} cited, {_pct(answers['faithful'])} faithful",
            "100% and at least 95%",
            committed,
        ),
        (
            "Unanswerable policy questions declined",
            _pct(answers["declined_when_unanswerable"]),
            "100%",
            committed,
        ),
        (
            "Time per file",
            f"p50 {citations['p50_seconds']:.0f} s, p95 {citations['p95_seconds']:.0f} s",
            "p95 under 120 s",
            committed,
        ),
        (
            "Model cost per file, at list price",
            f"${citations['mean_cost_usd']:.3f} mean",
            "Reported",
            committed,
        ),
    ]
    lines = [
        START,
        "| Measure | Result | Gate | Runs |",
        "| --- | --- | --- | --- |",
        *[f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows],
        END,
    ]
    return "\n".join(lines)


def render(readme: str) -> str:
    start, end = readme.index(START), readme.index(END) + len(END)
    return readme[:start] + table() + readme[end:]


def main() -> None:
    current = README.read_text(encoding="utf-8")
    wanted = render(current)
    if "--check" in sys.argv:
        if current != wanted:
            sys.exit("README results are out of date: run python -m lineage_evals.readme")
        return
    README.write_text(wanted, encoding="utf-8")


if __name__ == "__main__":
    main()
