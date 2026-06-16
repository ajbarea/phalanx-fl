"""OTel-native FL observability: round/client spans + FL metrics.

phalanx's differentiator over stock Flower. The server's ``ObservableFedAvg`` opens a
span per FL round and records aggregated loss/accuracy/participation; clients open a
span per local train/evaluate pass. Exporters are pluggable: an OTLP endpoint
(``OTEL_EXPORTER_OTLP_ENDPOINT``) in production, injected in-memory exporters in tests.

Providers are kept module-local (not on the OTel globals) so tests can re-initialise
between cases without the "Overriding current provider is not allowed" warning.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
)

_DEFAULT_SERVICE = "phalanx-fl"

_tracer: Any = None
_meter: Any = None
_instruments: dict[str, Any] = {}


def init_telemetry(
    *,
    service_name: str = _DEFAULT_SERVICE,
    span_exporter: SpanExporter | None = None,
    metric_reader: MetricReader | None = None,
    otlp_endpoint: str | None = None,
) -> None:
    """Configure tracing + metrics.

    Tests inject ``span_exporter`` / ``metric_reader`` (in-memory). In production set
    ``OTEL_EXPORTER_OTLP_ENDPOINT`` (or pass ``otlp_endpoint``) to export over OTLP;
    with neither, telemetry is recorded but not exported (no-op, no connection noise).
    """
    global _tracer, _meter, _instruments

    resource = Resource.create({"service.name": service_name})
    endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    tracer_provider = TracerProvider(resource=resource)
    if span_exporter is not None:
        tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    elif os.getenv("OTEL_TRACES_EXPORTER") == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    elif endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    _tracer = tracer_provider.get_tracer("phalanx")

    readers: list[MetricReader] = []
    if metric_reader is not None:
        readers.append(metric_reader)
    elif endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )

        readers.append(PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint)))
    meter_provider = MeterProvider(resource=resource, metric_readers=readers)
    _meter = meter_provider.get_meter("phalanx")

    _instruments = {
        "round_loss": _meter.create_gauge("fl.round.loss"),
        "round_accuracy": _meter.create_gauge("fl.round.accuracy"),
        "round_clients": _meter.create_gauge("fl.round.clients"),
        "client_examples": _meter.create_counter("fl.client.examples"),
        "client_loss": _meter.create_gauge("fl.client.loss"),
    }


def _ensure_init() -> None:
    if _tracer is None or _meter is None:
        init_telemetry()


@contextmanager
def round_span(rnd: int) -> Iterator[Any]:
    """Server-side span covering one FL round."""
    _ensure_init()
    with _tracer.start_as_current_span("fl.round", attributes={"fl.round": rnd}) as span:
        yield span


@contextmanager
def client_span(*, rnd: int, partition_id: int, phase: str) -> Iterator[Any]:
    """Client-side span covering one local train/evaluate pass."""
    _ensure_init()
    attrs = {"fl.round": rnd, "fl.partition_id": partition_id, "fl.phase": phase}
    with _tracer.start_as_current_span(f"fl.client.{phase}", attributes=attrs) as span:
        yield span


def record_round_metrics(*, rnd: int, loss: float, accuracy: float, clients: int) -> None:
    """Record aggregated server-round metrics (loss, accuracy, participation)."""
    _ensure_init()
    attrs = {"fl.round": rnd}
    _instruments["round_loss"].set(loss, attributes=attrs)
    _instruments["round_accuracy"].set(accuracy, attributes=attrs)
    _instruments["round_clients"].set(clients, attributes=attrs)


def record_client_metrics(*, partition_id: int, num_examples: int, loss: float) -> None:
    """Record per-client local metrics (sample count, local loss)."""
    _ensure_init()
    attrs = {"fl.partition_id": partition_id}
    _instruments["client_examples"].add(num_examples, attributes=attrs)
    _instruments["client_loss"].set(loss, attributes=attrs)
