import json
from collections import Counter
from pathlib import Path

import pytest
from lineage_agent.names import script_of
from lineage_ingest.policy import POLICIES, read_policy

ROWS = [
    json.loads(line)
    for line in (
        Path(__file__).resolve().parents[2] / "packages" / "evals" / "datasets" / "policy.jsonl"
    )
    .read_text(encoding="utf-8")
    .splitlines()
]
POLICY_REFS = {
    s.ref
    for name in ("uk", "uae")
    for s in read_policy(POLICIES / f"{name}-kyc-policy.md").sections
}


@pytest.mark.unit
def test_every_relevant_policy_paragraph_exists() -> None:
    for row in ROWS:
        for ref in row["relevant"]:
            if not ref.startswith("Regulation "):
                assert ref in POLICY_REFS, (row["id"], ref)
            assert ref.startswith("Regulation ") or ref.split(" KYC")[0].lower() == row["pack"]


@pytest.mark.unit
def test_both_packs_have_answerable_and_unanswerable_questions() -> None:
    assert len({r["id"] for r in ROWS}) == len(ROWS)
    for pack in ("uk", "uae"):
        kinds = Counter(r["answerable"] for r in ROWS if r["pack"] == pack)
        assert kinds[True] >= 10 and kinds[False] >= 1
        assert all(r["answerable"] == bool(r["relevant"]) for r in ROWS)
    assert any(script_of(r["question"]) == "arabic" for r in ROWS)
