"""Draft a file for each company in the citation set eight times, then check and judge every draft.

    DATABASE_URL=... COMPANIES_HOUSE_API_KEY=... python -m lineage_evals.run_citations

Drafting and judging run on Claude Opus 5.5 at medium effort through Claude Code. The set is the
first company of each category in the ownership set, so it covers direct, layered, statement and
overseas chains. Results are written to `baselines/citations.json`.
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import psycopg
from lineage_agent.agent import Agent
from lineage_agent.model import EFFORT, MODEL, ClaudeCode
from lineage_agent.tools.screening import screen
from lineage_ingest.companies_house import CompaniesHouse
from lineage_ingest.gleif import Gleif

from lineage_evals.citations import CITED_GATE, FAITHFUL_GATE, RUNS, score
from lineage_evals.ownership import load

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "datasets" / "ownership.jsonl"
BASELINE = ROOT / "baselines" / "citations.json"
CACHE = Path.home() / ".cache" / "lineage" / "companies-house"
WORKERS = 4


def companies() -> list[tuple[str, str]]:
    seen: dict[str, tuple[str, str]] = {}
    for case in load(DATASET):
        seen.setdefault(case.category, (case.id, case.company_number))
    return list(seen.values())


def one(case_id: str, number: str, run: int) -> dict[str, Any]:
    model = ClaudeCode()
    started = time.monotonic()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        agent = Agent(
            register=CompaniesHouse(cache=CACHE),
            lei=Gleif(),
            screen=lambda name, pack: screen(conn, name, pack),
            model=model,
        )
        result = agent.run(number, "uk")
    seconds = time.monotonic() - started
    row: dict[str, Any] = {
        "case": case_id,
        "run": run,
        "seconds": round(seconds, 1),
        "attempts": result.attempts,
        "cited": not result.citation_failures,
        "rating": result.draft.risk_rating if result.draft else None,
    }
    judged = score(model, result.redacted_evidence, result.redacted_draft)
    row |= {
        "claims": judged.claims,
        "supported": judged.supported,
        "unsupported": judged.unsupported,
    }
    print(f"{case_id} run {run}: {judged.supported}/{judged.claims} supported, {seconds:.0f}s")
    return row


def main() -> None:
    jobs = [(cid, num, run) for cid, num in companies() for run in range(1, RUNS + 1)]
    with ThreadPoolExecutor(WORKERS) as pool:
        rows = list(pool.map(lambda job: one(*job), jobs))
    claims = sum(r["claims"] for r in rows)
    supported = sum(r["supported"] for r in rows)
    cited = sum(r["cited"] for r in rows) / len(rows)
    faithful = supported / claims
    times = sorted(r["seconds"] for r in rows)
    # The gate holds for each company over its eight runs, so a weak company cannot hide behind
    # the others. A single run has too few claims for one miss to be measured against 95%.
    per_company = {
        cid: round(
            sum(r["supported"] for r in rows if r["case"] == cid)
            / sum(r["claims"] for r in rows if r["case"] == cid),
            4,
        )
        for cid, _ in companies()
    }
    summary = {
        "model": MODEL,
        "effort": EFFORT,
        "files": len(rows),
        "runs_per_company": RUNS,
        "cited": cited,
        "claims": claims,
        "supported": supported,
        "faithful": round(faithful, 4),
        "faithful_by_company": per_company,
        "p95_seconds": times[int(0.95 * (len(times) - 1))],
        "passed": cited >= CITED_GATE and min(per_company.values()) >= FAITHFUL_GATE,
    }
    BASELINE.write_text(json.dumps({"summary": summary, "runs": rows}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if not summary["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
