import pytest
from lineage_agent.agent import Agent
from lineage_agent.pii import PresidioScanner
from lineage_agent.tracing import safe_attributes
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from test_agent import Gleif, Model, Register, screen

EXPORTER = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
trace.set_tracer_provider(_provider)

PERSONAL = ["Jane Quill", "Harlan Voss", "GB-881204563", "27 Mill Lane", "EXAMPLE TRADING LTD"]


@pytest.mark.unit
def test_only_counts_and_known_short_words_become_attributes() -> None:
    attributes = safe_attributes(
        {
            "tool": "screening",
            "hits": 2,
            "query": "a1b2c3",
            "company_number": "00000001",
            "steps": ["registry_chain", "draft"],
            "reason": "Harlan Voss is a director",
        }
    )
    assert attributes == {"lineage.tool": "screening", "lineage.hits": 2, "lineage.steps": 2}


@pytest.mark.unit
def test_a_drafted_file_is_traced_without_personal_data() -> None:
    EXPORTER.clear()
    agent = Agent(Register(), Gleif(), screen, Model(), scanner=PresidioScanner())
    media = "Harlan Voss, a director, holds passport GB-881204563 and lives at 27 Mill Lane."
    agent.run("00000001", "uk", media=[media])
    spans = EXPORTER.get_finished_spans()
    names = [s.name for s in spans]
    assert names.count("agent.run") == 1
    assert {"agent.tool", "agent.model_call", "agent.citation_check"} <= set(names)
    run = next(s for s in spans if s.name == "agent.run")
    assert all(s.context.trace_id == run.context.trace_id for s in spans)
    assert run.attributes is not None and run.attributes["lineage.attempts"] == 2
    events = [e.name for s in spans for e in s.events]
    assert {"plan", "tool_call", "redaction", "model_call", "draft"} <= set(events)
    values = [
        str(v)
        for s in spans
        for attrs in [s.attributes or {}, *[e.attributes or {} for e in s.events]]
        for v in attrs.values()
    ]
    assert not [v for v in values for p in PERSONAL if p.casefold() in v.casefold()]
    assert all(len(v) <= 40 for v in values)
