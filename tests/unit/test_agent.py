from dataclasses import dataclass
from typing import Any

import pytest
from lineage_agent.agent import Agent
from lineage_agent.claims import Claim, Draft
from lineage_agent.redaction import RedactionError, Redactor
from lineage_agent.tools.screening import Candidate

PSC = "/company/00000001/persons-with-significant-control/individual/abc"


class Register:
    def get(self, path: str) -> dict[str, Any] | None:
        data: dict[str, Any] = {
            "/company/00000001": {"company_name": "EXAMPLE TRADING LTD"},
            "/company/00000001/persons-with-significant-control": {
                "items": [
                    {
                        "kind": "individual-person-with-significant-control",
                        "links": {"self": PSC},
                    }
                ]
            },
            PSC: {
                "name": "Jane Quill",
                "natures_of_control": ["ownership-of-shares-75-to-100-percent"],
            },
        }
        return data.get(path.split("?")[0])


@dataclass
class Lei:
    lei: str = "LEI0000000000000001"
    legal_name: str = "EXAMPLE TRADING LTD"
    registered_as: str = "00000001"
    jurisdiction: str = "GB"
    status: str = "ACTIVE"


@dataclass
class Parent:
    record: Any = None
    exception: str | None = "NATURAL_PERSONS"


class Gleif:
    def by_registration(self, number: str, jurisdiction: str = "GB") -> list[Any]:
        return [Lei()]

    def parent(self, lei: str, level: str = "direct") -> Any:
        return Parent()


def screen(name: str, pack: str) -> list[Candidate]:
    if name == "Jane Quill":
        return [Candidate("opensanctions:pep:Q1", "Jane Quill", "pep", 1.0, "exact")]
    return []


def claim(text: str, source: str, quote: str) -> Claim:
    return Claim(text=text, source_id=source, quote=quote)


class Model:
    """Returns a bad draft first, then a good one, and records what it was sent."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def draft(self, system: str, prompt: str) -> Draft:
        self.prompts.append(prompt)
        quote = "made up" if len(self.prompts) == 1 else "[PERSON_1] controls EXAMPLE TRADING LTD"
        owner = claim("[PERSON_1] owns the company.", f"companies-house:psc:{PSC}", quote)
        return Draft(
            summary=[
                claim(
                    "The company is registered.",
                    "companies-house:company:00000001",
                    "Company EXAMPLE TRADING LTD, number 00000001.",
                )
            ],
            ownership=[owner],
            screening=[
                claim(
                    "[PERSON_1] is a PEP candidate.",
                    "screening:companies-house:psc:" + PSC,
                    "Candidate opensanctions:pep:Q1 (pep, strong)",
                )
            ],
            risk_rating="medium",
            risk_reasons=[owner],
        )


@pytest.fixture
def run() -> tuple[Any, Model, list[str]]:
    model, actions = Model(), []
    agent = Agent(Register(), Gleif(), screen, model, lambda a, p: actions.append(a))
    return agent.run("00000001", "uk"), model, actions


@pytest.mark.unit
def test_redrafts_until_every_quote_is_found(run: tuple[Any, Model, list[str]]) -> None:
    result, model, _ = run
    assert result.attempts == 2
    assert result.citation_failures == []
    assert "citation errors" in model.prompts[1]


@pytest.mark.unit
def test_the_model_never_sees_the_person_but_the_analyst_does(
    run: tuple[Any, Model, list[str]],
) -> None:
    result, model, _ = run
    assert all("Jane Quill" not in p for p in model.prompts)
    assert "[PERSON_1]" in model.prompts[0]
    assert result.draft.ownership[0].text == "Jane Quill owns the company."


@pytest.mark.unit
def test_every_step_is_audited_in_order(run: tuple[Any, Model, list[str]]) -> None:
    _, _, actions = run
    assert actions[0] == "plan"
    assert actions.count("model_call") == 2
    assert actions[-1] == "draft"


@pytest.mark.unit
def test_uae_plan_skips_the_uk_registry() -> None:
    agent = Agent(Register(), Gleif(), screen, Model())
    assert "registry_chain" not in agent.plan("uae")


@pytest.mark.unit
def test_restore_rejects_an_invented_placeholder() -> None:
    redactor = Redactor()
    redactor.add_person("Jane Quill")
    with pytest.raises(RedactionError):
        redactor.restore("[PERSON_7] is listed")


@pytest.mark.unit
def test_spellings_of_one_person_share_a_placeholder() -> None:
    redactor = Redactor()
    tag = redactor.add_person("Jane Quill", "QUILL, Jane")
    assert redactor.add_person("jane quill") == tag
    assert redactor.redact("QUILL, Jane and Jane Quill") == f"{tag} and {tag}"


@pytest.mark.unit
def test_claude_code_runs_headless_with_opus_at_medium_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    import subprocess

    from lineage_agent.model import ClaudeCode

    seen: dict[str, Any] = {}
    draft = Model().draft("", "")

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen["command"], seen["input"] = command, kwargs["input"]
        out = {"is_error": False, "subtype": "success", "structured_output": draft.model_dump()}
        return subprocess.CompletedProcess(command, 0, json.dumps(out), "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert ClaudeCode().draft("system", "the prompt") == draft
    command = seen["command"]
    assert command[command.index("--model") + 1] == "claude-opus-5-5"
    assert command[command.index("--effort") + 1] == "medium"
    assert command[command.index("--tools") + 1] == ""
    assert seen["input"] == "the prompt"


def agent_with(hits: dict[str, list[Candidate]], model: Any) -> Agent:
    return Agent(Register(), Gleif(), lambda name, pack: hits.get(name, []), model)


@pytest.mark.unit
def test_a_strong_pep_sets_a_medium_floor(run: tuple[Any, Model, list[str]]) -> None:
    result, model, _ = run
    assert result.minimum_rating == "medium"
    assert "Minimum risk rating for this case: medium" in model.prompts[0]
    assert result.alerts == []


@pytest.mark.unit
def test_a_weak_match_is_an_alert_and_leaves_the_floor_low() -> None:
    weak = Candidate(
        "opensanctions:sanctions:X1", "EXAMPLE TRADES LTD", "sanctions", 0.7, "similar"
    )
    result = agent_with({"EXAMPLE TRADING LTD": [weak]}, Model()).run("00000001", "uk")
    assert result.minimum_rating == "low"
    assert result.alerts == [
        "opensanctions:sanctions:X1 for companies-house:company:00000001",
        "opensanctions:sanctions:X1 for gleif:LEI0000000000000001",
    ]


@pytest.mark.unit
def test_a_rating_below_the_floor_is_sent_back() -> None:
    strong = Candidate("opensanctions:sanctions:X2", "Jane Quill", "sanctions", 1.0, "exact")
    model = Model()
    result = agent_with({"Jane Quill": [strong]}, model).run("00000001", "uk")
    assert result.minimum_rating == "high"
    assert any("below the minimum high" in f for f in result.citation_failures)
    assert "below the minimum high" in model.prompts[-1]
