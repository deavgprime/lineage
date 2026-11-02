from typing import Any

import pytest
from lineage_agent.claims import Claim
from lineage_agent.pii import PresidioScanner
from lineage_agent.policy_qa import Passage, PolicyAnswer, ask

PASSAGES = [
    Passage(
        "doc:4.1", "UK KYC policy 4.1", "Beneficial ownership", "Owners above 25 percent.", "P"
    ),
    Passage(
        "doc:10.1", "UK KYC policy 10.1", "Record keeping", "Records are kept five years.", "P"
    ),
]


class Retriever:
    def search(self, question: str, pack: str) -> list[Passage]:
        return PASSAGES


class Model:
    def __init__(self, *answers: PolicyAnswer) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []

    def structured(self, system: str, prompt: str, output: type[Any]) -> Any:
        self.prompts.append(prompt)
        return self.answers.pop(0)


def statement(source: str, quote: str) -> Claim:
    return Claim(text="Records are kept for five years.", source_id=source, quote=quote)


@pytest.mark.unit
def test_an_uncited_answer_is_sent_back_until_it_cites() -> None:
    model = Model(
        PolicyAnswer(answered=True, statements=[statement("doc:10.1", "seven years")]),
        PolicyAnswer(answered=True, statements=[statement("doc:10.1", "kept five years")]),
    )
    actions: list[str] = []
    result = ask(
        "How long do we keep records?",
        "uk",
        Retriever(),
        model,
        None,
        lambda a, p: actions.append(a),
    )
    assert result.attempts == 2 and result.citation_failures == []
    assert "citation errors" in model.prompts[1]
    assert actions == ["policy_search", "model_call", "model_call", "policy_answer"]


@pytest.mark.unit
def test_an_answer_with_no_statements_is_not_accepted() -> None:
    empty = PolicyAnswer(answered=True, statements=[])
    result = ask("Anything?", "uk", Retriever(), Model(empty, empty, empty))
    assert result.citation_failures == ["an answer needs at least one cited statement"]


@pytest.mark.unit
def test_personal_data_in_the_question_never_reaches_the_model() -> None:
    model = Model(PolicyAnswer(answered=False, statements=[], note="Not in the passages."))
    ask(
        "Can we onboard Harlan Voss, passport GB-881204563?",
        "uk",
        Retriever(),
        model,
        PresidioScanner(),
    )
    assert "Harlan Voss" not in model.prompts[0]
    assert "GB-881204563" not in model.prompts[0]
    assert "[PERSON_1]" in model.prompts[0] and "[ID_1]" in model.prompts[0]
