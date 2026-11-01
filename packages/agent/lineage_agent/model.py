"""The model interface the agent depends on, and two ways to reach Claude through it.

`ClaudeCode` runs Claude Code in headless mode, which uses the subscription signed in on the
machine. `Claude` calls the Anthropic API and needs an API key. Both use Claude Opus 5.5 at medium
effort and return the same structured draft.
"""

import json
import os
import subprocess
import tempfile
from typing import Final, Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from lineage_agent.claims import Draft

MODEL = "claude-opus-5-5"
EFFORT: Final = "medium"
TIMEOUT = 900

T = TypeVar("T", bound=BaseModel)


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
        return self.structured(system, prompt, Draft)

    def structured(self, system: str, prompt: str, output: type[T]) -> T:
        response = self._client.beta.messages.parse(
            model=self._model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=output,
            output_config={"effort": EFFORT},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise ModelRefused(str(response.stop_details))
        if response.parsed_output is None:
            raise ModelRefused(f"no structured output, stop reason {response.stop_reason}")
        return response.parsed_output


class ClaudeCode:
    """Drafts through `claude -p` with Claude Code's own tools, settings and MCP servers off."""

    def __init__(self, model: str = MODEL, effort: str = EFFORT, binary: str = "claude") -> None:
        self._model = model
        self._effort = effort
        self._binary = binary

    def draft(self, system: str, prompt: str) -> Draft:
        return self.structured(system, prompt, Draft)

    def structured(self, system: str, prompt: str, output: type[T]) -> T:
        schema = json.dumps(output.model_json_schema())
        command = [
            self._binary,
            "-p",
            "--model",
            self._model,
            "--effort",
            self._effort,
            "--system-prompt",
            system,
            "--json-schema",
            schema,
            "--output-format",
            "json",
            "--tools",
            "",
            "--strict-mcp-config",
            "--setting-sources",
            "",
            "--no-session-persistence",
        ]
        # An empty working directory, so no project instructions are picked up.
        with tempfile.TemporaryDirectory() as cwd:
            done = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=TIMEOUT,
                env={k: v for k, v in os.environ.items()},
                check=False,
            )
        if done.returncode != 0:
            raise ModelRefused(f"claude exited with {done.returncode}: {done.stderr.strip()[:300]}")
        result = json.loads(done.stdout)
        if result.get("is_error") or result.get("structured_output") is None:
            raise ModelRefused(f"no structured output: {result.get('subtype')}")
        return output.model_validate(result["structured_output"])
