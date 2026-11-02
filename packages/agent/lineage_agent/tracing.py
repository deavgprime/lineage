"""OpenTelemetry spans for the agent's steps.

The agent depends only on the OpenTelemetry API, so spans cost nothing until a process configures an
exporter (the API does, see lineage_api.telemetry). Span names and attributes carry steps, counts,
timings and ids, never names, identifiers, prompts or answers: traces leave the bank's audit
boundary for a tracing tool, and personal data must not go with them.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span

tracer = trace.get_tracer("lineage.agent")

# Only numbers, booleans and these keys may become attributes. Everything else stays out of spans.
SAFE_KEYS = frozenset(
    {
        "tool",
        "attempt",
        "attempts",
        "hits",
        "found",
        "citation_failures",
        "people",
        "identifiers",
        "pack",
        "steps",
        "passages",
        "status",
        "stage",
        "rating",
        "role",
    }
)


def safe_attributes(payload: dict[str, Any], prefix: str = "lineage.") -> dict[str, Any]:
    """The parts of an audit payload that may go on a span."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        short_word = key in SAFE_KEYS and isinstance(value, str) and len(value) <= 40
        if isinstance(value, bool | int | float) or short_word:
            out[prefix + key] = value
        elif key in SAFE_KEYS and isinstance(value, list):
            out[prefix + key] = len(value)
    return out


@contextmanager
def step(name: str, **attributes: Any) -> Iterator[Span]:
    with tracer.start_as_current_span(name, attributes=safe_attributes(attributes)) as span:
        yield span


def event(action: str, payload: dict[str, Any]) -> None:
    """Mark an audit action on the current span, with its safe attributes only."""
    trace.get_current_span().add_event(action, safe_attributes(payload))
