import json
from typing import Any

import pytest
from lineage_evals.citations import Judgement, Verdict, judge_prompt, score

CLAIM = {"text": "[PERSON_1] controls Example Ltd.", "source_id": "ch:1", "quote": "controls"}
DRAFT = json.dumps(
    {
        "summary": [CLAIM],
        "ownership": [CLAIM | {"text": "[PERSON_1] is a director."}],
        "screening": [],
        "risk_rating": "low",
        "risk_reasons": [CLAIM | {"text": "Low risk."}],
    }
)


class FakeJudge:
    def __init__(self, *verdicts: Verdict) -> None:
        self.verdicts = list(verdicts)
        self.prompts: list[str] = []

    def structured(self, system: str, prompt: str, output: type[Any]) -> Any:
        self.prompts.append(prompt)
        return Judgement(verdicts=self.verdicts)


@pytest.mark.unit
def test_counts_unsupported_and_skipped_claims() -> None:
    judge = FakeJudge(
        Verdict(claim=1, supported=True, reason="stated"),
        Verdict(claim=2, supported=False, reason="the record does not say director"),
    )
    result = score(judge, "<evidence/>", DRAFT)
    assert (result.claims, result.supported) == (3, 1)
    assert "does not say director" in result.unsupported[0]
    assert "no verdict" in result.unsupported[1]


@pytest.mark.unit
def test_judge_sees_numbered_claims_with_placeholders_only() -> None:
    prompt = judge_prompt('<evidence id="ch:1">[PERSON_1] controls</evidence>', DRAFT)
    assert "1. [ch:1] [PERSON_1] controls Example Ltd." in prompt
    assert "3. [ch:1] Low risk." in prompt


@pytest.mark.unit
def test_percentile_is_nearest_rank() -> None:
    from lineage_evals.run_citations import percentile

    values = [float(v) for v in range(1, 21)]
    assert percentile(values, 0.95) == 19.0
    assert percentile(values, 0.5) == 10.0
    assert percentile([7.0], 0.95) == 7.0
