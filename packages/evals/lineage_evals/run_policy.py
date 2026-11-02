"""Score policy retrieval and policy answers on the labelled questions.

    DATABASE_URL=... python -m lineage_evals.run_policy [--retrieval-only]

Retrieval: for each question, rank every candidate the vector and keyword searches propose with the
reranker, and check whether a relevant section is in the top 5 and the top 10. Questions with no
answer in the corpus are left out of recall.

Answers: ask each question eight times through the full path on Claude Opus 5.5 at medium effort.
Every statement must be cited, a judge on the same model scores each statement against the passage
it cites, and questions with no answer must be declined. Results go to `baselines/policy.json`.
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import psycopg
from lineage_agent.model import EFFORT, MODEL, ClaudeCode
from lineage_agent.pii import PresidioScanner
from lineage_agent.policy_qa import LocalReranker, PgRetriever, ask
from lineage_ingest.policy import MODELS, LocalEmbedder

from lineage_evals.citations import FAITHFUL_GATE, RUNS, score

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "datasets" / "policy.jsonl"
BASELINE = ROOT / "baselines" / "policy.json"
WORKERS = 4


def load(path: Path = DATASET) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def retrieval(url: str, questions: list[dict[str, Any]], retriever_parts: Any) -> dict[str, Any]:
    embedder, reranker = retriever_parts
    hits = {5: 0, 10: 0}
    rows = []
    with psycopg.connect(url) as conn:
        retriever = PgRetriever(conn, lambda q: embedder.embed([q])[0], reranker)
        for q in questions:
            if not q["answerable"]:
                continue
            ranked = [p.ref for p in retriever.search(q["question"], q["pack"], top=None)]
            first = next((i + 1 for i, ref in enumerate(ranked) if ref in q["relevant"]), None)
            for k in hits:
                hits[k] += first is not None and first <= k
            rows.append({"id": q["id"], "first_relevant_rank": first, "top3": ranked[:3]})
    n = len(rows)
    return {
        "questions": n,
        "recall_at_5": round(hits[5] / n, 3),
        "recall_at_10": round(hits[10] / n, 3),
        "by_question": rows,
    }


def answers(url: str, questions: list[dict[str, Any]], retriever_parts: Any) -> dict[str, Any]:
    embedder, reranker = retriever_parts
    scanner = PresidioScanner()

    def one(q: dict[str, Any], run: int) -> dict[str, Any]:
        model = ClaudeCode()
        started = time.monotonic()
        with psycopg.connect(url) as conn:
            retriever = PgRetriever(conn, lambda text: embedder.embed([text])[0], reranker)
            result = ask(q["question"], q["pack"], retriever, model, scanner)
        seconds = round(time.monotonic() - started, 1)
        answer = result.answer
        answered = bool(answer and answer.answered and not result.citation_failures)
        row: dict[str, Any] = {
            "id": q["id"],
            "run": run,
            "seconds": seconds,
            "answered": answered,
            "correctly_declined": None if q["answerable"] else not answered,
            "cited": not result.citation_failures,
            "claims": 0,
            "supported": 0,
            "unsupported": [],
        }
        if answered and answer:
            evidence = "\n\n".join(
                f'<evidence id="{p.id}">\n{p.text}\n</evidence>' for p in result.passages
            )
            draft = json.dumps(
                {
                    "summary": [s.model_dump() for s in answer.statements],
                    "ownership": [],
                    "screening": [],
                    "risk_reasons": [],
                }
            )
            judged = score(model, evidence, draft)
            row |= {
                "claims": judged.claims,
                "supported": judged.supported,
                "unsupported": judged.unsupported,
            }
        print(f"{q['id']} run {run}: answered={answered} {row['supported']}/{row['claims']}")
        return row

    jobs = [(q, run) for q in questions for run in range(1, RUNS + 1)]
    with ThreadPoolExecutor(WORKERS) as pool:
        rows = list(pool.map(lambda job: one(*job), jobs))
    answerable = [r for r in rows if r["correctly_declined"] is None]
    declines = [r for r in rows if r["correctly_declined"] is not None]
    claims = sum(r["claims"] for r in rows)
    supported = sum(r["supported"] for r in rows)
    times = sorted(r["seconds"] for r in rows)
    return {
        "runs": len(rows),
        "runs_per_question": RUNS,
        "answered": round(sum(r["answered"] for r in answerable) / len(answerable), 3),
        "cited": round(sum(r["cited"] for r in rows) / len(rows), 3),
        "claims": claims,
        "faithful": round(supported / claims, 4) if claims else 1.0,
        "declined_when_unanswerable": round(
            sum(r["correctly_declined"] for r in declines) / len(declines), 3
        ),
        "p95_seconds": times[max(0, -(-95 * len(times) // 100) - 1)],
        "unsupported": [u for r in rows for u in r["unsupported"]],
        "unanswered": sorted({r["id"] for r in answerable if not r["answered"]}),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrieval-only", action="store_true")
    args = ap.parse_args()
    url = os.environ["DATABASE_URL"]
    questions = load()
    parts = (LocalEmbedder(), LocalReranker(str(MODELS)))
    result: dict[str, Any] = {"model": MODEL, "effort": EFFORT}
    result["retrieval"] = retrieval(url, questions, parts)
    print(json.dumps({k: v for k, v in result["retrieval"].items() if k != "by_question"}))
    passed = True
    if not args.retrieval_only:
        result["answers"] = answers(url, questions, parts)
        a = result["answers"]
        passed = (
            a["cited"] == 1.0
            and a["faithful"] >= FAITHFUL_GATE
            and a["declined_when_unanswerable"] == 1.0
        )
        print(json.dumps({k: v for k, v in a.items() if k not in ("unsupported",)}, indent=2))
    result["passed"] = passed
    BASELINE.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
