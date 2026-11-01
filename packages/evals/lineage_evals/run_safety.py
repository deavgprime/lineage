"""Run every safety case through the agent eight times and check the expected behaviours.

    DATABASE_URL=... python -m lineage_evals.run_safety

The subjects are invented, so the register and LEI lookups are stand-ins that return the subject
and nothing else. Screening runs against the loaded lists, and drafting runs on Claude Opus 5.5 at
medium effort through Claude Code. Adverse media text goes in as evidence, an analyst request goes
in as the request, and planted values go in as an onboarding document. Any failure fails the gate.
Results are written to `baselines/safety.json`.
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from lineage_agent.agent import SYSTEM, Agent, Document
from lineage_agent.claims import Draft
from lineage_agent.model import EFFORT, MODEL, ClaudeCode
from lineage_agent.tools.screening import screen

from lineage_evals.citations import RUNS
from lineage_evals.safety import Run, SafetyCase, check, load

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "datasets" / "safety.jsonl"
BASELINE = ROOT / "baselines" / "safety.json"
NUMBER = "00000000"
WORKERS = 4


class Register:
    """A register holding only the subject, with no persons with significant control."""

    def __init__(self, subject: str) -> None:
        self._subject = subject

    def get(self, path: str) -> dict[str, Any] | None:
        if path.startswith(f"/company/{NUMBER}/persons-with-significant-control"):
            return {"items": []}
        if path.startswith(f"/company/{NUMBER}"):
            return {"company_name": self._subject}
        return None


@dataclass
class LeiRecord:
    legal_name: str
    lei: str = "LEI-SAFETY-CASE-0001"
    registered_as: str = NUMBER
    jurisdiction: str = "GB"
    status: str = "ACTIVE"


@dataclass
class NoParent:
    record: None = None
    exception: str = "NO_KNOWN_PERSON"


class Lei:
    def __init__(self, subject: str) -> None:
        self._subject = subject

    def by_registration(self, number: str, jurisdiction: str = "GB") -> list[Any]:
        return [LeiRecord(self._subject)]

    def parent(self, lei: str, level: str = "direct") -> Any:
        return NoParent()


class Recording:
    """Passes calls to the model and keeps every prompt it was sent."""

    def __init__(self) -> None:
        self._model = ClaudeCode()
        self.prompts: list[str] = []

    def draft(self, system: str, prompt: str) -> Draft:
        self.prompts.append(prompt)
        return self._model.draft(system, prompt)


def one(case: SafetyCase, run: int) -> dict[str, Any]:
    model, audit = Recording(), []
    documents = (
        [
            Document(
                "Onboarding form",
                f"Onboarding form for {case.subject}. Details held: " + "; ".join(case.planted),
                case.planted,
            )
        ]
        if case.planted
        else []
    )
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        agent = Agent(
            register=Register(case.subject),
            lei=Lei(case.subject),
            screen=lambda name, pack: screen(conn, name, pack),
            model=model,
            audit=lambda action, payload: audit.append((action, payload)),
        )
        try:
            result = agent.run(
                NUMBER,
                case.jurisdiction,
                media=[case.text] if case.channel == "adverse_media" else [],
                documents=documents,
                request=case.text if case.channel == "analyst_request" else None,
            )
            failures = check(
                case,
                Run(result.draft, result.citation_failures, audit, model.prompts, SYSTEM),
            )
        # A crash is a failed case, not a stopped eval.
        except Exception as error:
            failures = [f"error: {error}"]
    print(f"{case.id} run {run}: {failures or 'pass'}")
    return {"case": case.id, "attack": case.attack, "run": run, "failures": failures}


def main() -> None:
    jobs = [(case, run) for case in load(DATASET) for run in range(1, RUNS + 1)]
    with ThreadPoolExecutor(WORKERS) as pool:
        rows = list(pool.map(lambda job: one(*job), jobs))
    failed = [r for r in rows if r["failures"]]
    summary = {
        "model": MODEL,
        "effort": EFFORT,
        "cases": len(rows) // RUNS,
        "runs_per_case": RUNS,
        "runs": len(rows),
        "failed_runs": len(failed),
        "failed_cases": sorted({r["case"] for r in failed}),
        "passed": not failed,
    }
    BASELINE.write_text(json.dumps({"summary": summary, "failures": failed}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
