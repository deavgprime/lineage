"""Compare eval results with the baselines on the base branch and write a Markdown table.

    python -m lineage_evals.report --current <dir> --baseline <dir>

Both directories hold the files in `baselines/`: screening.json and ownership.json, which CI
produces on every run, and citations.json and safety.json, which are produced where model access
exists and committed with the change. A missing file shows as a dash.
"""

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

MARKER = "<!-- lineage-evals -->"

Read = Callable[[dict[str, Any]], float | None]


def _pack(pack: str, key: str) -> Callable[[Any], float | None]:
    def read(results: Any) -> float | None:
        return next((r[key] for r in results if r["pack"] == pack), None)

    return read


def _summary(key: str) -> Callable[[Any], float | None]:
    def read(body: Any) -> float | None:
        value = body["summary"]
        for part in key.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        return value  # type: ignore[no-any-return]

    return read


def _lowest(body: Any) -> float | None:
    by_company = body["summary"].get("faithful_by_company")
    return min(by_company.values()) if by_company else None


# (eval file, measure, how to read it, format, gate as text)
ROWS: list[tuple[str, str, Callable[[Any], float | None], str, str]] = [
    ("screening", "UK recall", _pack("uk", "recall"), "pct", "at least 98%"),
    ("screening", "UAE recall", _pack("uae", "recall"), "pct", "at least 98%"),
    ("screening", "UK false positives", _pack("uk", "false_positives"), "int", ""),
    ("screening", "UAE false positives", _pack("uae", "false_positives"), "int", ""),
    ("screening", "UK unlisted spellings", _pack("uk", "unlisted_recall"), "pct", ""),
    ("screening", "UAE unlisted spellings", _pack("uae", "unlisted_recall"), "pct", ""),
    ("ownership", "Exact chains", lambda b: b["rate"], "pct", "at least 90%"),
    ("citations", "Cited claims", _summary("cited"), "pct", "100%"),
    ("citations", "Faithful claims", _summary("faithful"), "pct", ""),
    ("citations", "Lowest company, faithful", _lowest, "pct", "at least 95%"),
    ("citations", "p95 seconds per file", _summary("p95_seconds"), "num", "under 120"),
    ("citations", "Mean cost per file (USD)", _summary("mean_cost_usd"), "usd", ""),
    ("safety", "Failed runs", _summary("failed_runs"), "int", "0"),
    ("policy", "Retrieval recall at 5", lambda b: b["retrieval"]["recall_at_5"], "pct", ""),
    ("policy", "Answers cited", lambda b: b.get("answers", {}).get("cited"), "pct", "100%"),
    (
        "policy",
        "Answers faithful",
        lambda b: b.get("answers", {}).get("faithful"),
        "pct",
        "at least 95%",
    ),
    (
        "policy",
        "Declined when not in the corpus",
        lambda b: b.get("answers", {}).get("declined_when_unanswerable"),
        "pct",
        "100%",
    ),
    ("redaction", "Identifiers caught", lambda b: b["identifier_recall"], "pct", "100%"),
    ("redaction", "Names caught", lambda b: b["person_recall"], "pct", "at least 80%"),
    ("redaction", "False positives", lambda b: b["false_positives"], "int", ""),
]


def _load(directory: Path, name: str) -> Any:
    path = directory / f"{name}.json"
    return json.loads(path.read_text("utf-8")) if path.exists() else None


def _fmt(value: float | None, kind: str) -> str:
    if value is None:
        return "-"
    if kind == "pct":
        return f"{value:.1%}"
    if kind == "usd":
        return f"${value:.3f}"
    if kind == "num":
        return f"{value:.1f}"
    return str(int(value))


def report(current: Path, baseline: Path) -> str:
    lines = [
        MARKER,
        "### Eval results",
        "",
        "| Eval | Measure | This pull request | Base branch | Gate |",
        "| --- | --- | --- | --- | --- |",
    ]
    model_evals = []
    for name, measure, read, kind, gate in ROWS:
        now, before = _load(current, name), _load(baseline, name)
        a = _fmt(read(now) if now is not None else None, kind)
        b = _fmt(read(before) if before is not None else None, kind)
        lines.append(f"| {name} | {measure} | {a} | {b} | {gate} |")
        if name in {"citations", "safety", "policy"} and now != before and name not in model_evals:
            model_evals.append(name)
    lines.append("")
    if model_evals:
        lines.append(f"New model eval results in this pull request: {', '.join(model_evals)}.")
    else:
        lines.append(
            "Model evals (citations, safety) are unchanged from the base branch. They run where "
            "model access exists and are committed with the change."
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    args = ap.parse_args()
    print(report(args.current, args.baseline), end="")


if __name__ == "__main__":
    main()
