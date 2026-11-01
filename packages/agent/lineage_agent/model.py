"""The model interface the agent depends on, and the Claude implementation of it."""

from typing import Protocol

import anthropic

from lineage_agent.claims import Draft

MODEL = "claude-opus-5-5"


class ModelRefused(RuntimeError):
    pass


class Model(Protocol):
    def draft(self, system: str, prompt: str) -> Draft: ...


class Claude:
    """Drafts through the Anthropic API with structured output.

    Server-side fallbacks are on, so a request the main model declines on policy grounds is rerun
    on another model in the same call. A request that every model declines raises ModelRefused.
    """

    def __init__(self, client: anthropic.Anthropic | None = None, model: str = MODEL) -> None:
        self._client = client or anthropic.Anthropic()
        self._model = model

    def draft(self, system: str, prompt: str) -> Draft:
        response = self._client.beta.messages.parse(
            model=self._model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=Draft,
            output_config={"effort": "high"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise ModelRefused(str(response.stop_details))
        if response.parsed_output is None:
            raise ModelRefused(f"no structured output, stop reason {response.stop_reason}")
        return response.parsed_output
