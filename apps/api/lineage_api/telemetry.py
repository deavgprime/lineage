"""Send traces over OTLP when OTEL_EXPORTER_OTLP_ENDPOINT is set; otherwise do nothing.

The endpoint can be any OpenTelemetry collector, or Langfuse's OTLP endpoint with its keys in
OTEL_EXPORTER_OTLP_HEADERS. Request spans record the route and status, never query strings, bodies
or headers, and health checks are not traced.
"""

import os
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.trace import Span

_provider: TracerProvider | None = None


def _drop_query(span: Span, scope: dict[str, Any]) -> None:
    """Record the path only. Query strings can carry anything, and a client's IP address is
    personal data, so neither reaches a trace."""
    if not span.is_recording():
        return
    path = scope.get("path", "")
    server = scope.get("server") or ("", "")
    base = f"{scope.get('scheme', 'http')}://{server[0]}{path}"
    for key, value in (("http.url", base), ("url.full", base), ("http.target", path)):
        span.set_attribute(key, value)
    for key in ("url.query", "net.peer.ip", "client.address"):
        span.set_attribute(key, "")


def configure(app: FastAPI, exporter: SpanExporter | None = None) -> bool:
    """Instrument the app. Returns whether traces are being exported."""
    global _provider
    if exporter is None and not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    if _provider is None:
        name = os.environ.get("OTEL_SERVICE_NAME", "lineage-api")
        _provider = TracerProvider(resource=Resource.create({"service.name": name}))
        trace.set_tracer_provider(_provider)
    _provider.add_span_processor(BatchSpanProcessor(exporter or OTLPSpanExporter()))
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health/.*",
        exclude_spans=["receive", "send"],
        server_request_hook=_drop_query,
        http_capture_headers_server_request=[],
        http_capture_headers_server_response=[],
    )
    return True


def flush() -> None:
    """Send any spans still waiting, such as at shutdown or in a test."""
    if _provider is not None:
        _provider.force_flush()
