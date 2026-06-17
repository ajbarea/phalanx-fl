"""OTel telemetry layer: round/client spans + FL metrics (in-memory exporters)."""

from __future__ import annotations

from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from phalanx.telemetry import (
    client_span,
    context_from_traceparent,
    init_telemetry,
    record_client_metrics,
    record_round_metrics,
    round_span,
    shutdown_telemetry,
    start_round_span,
    traceparent_for,
)


def _setup() -> tuple[InMemorySpanExporter, InMemoryMetricReader]:
    span_exporter = InMemorySpanExporter()
    metric_reader = InMemoryMetricReader()
    init_telemetry(
        service_name="phalanx-test",
        span_exporter=span_exporter,
        metric_reader=metric_reader,
    )
    return span_exporter, metric_reader


def _metric_names(metric_reader: InMemoryMetricReader) -> set[str]:
    data = metric_reader.get_metrics_data()
    assert data is not None
    return {m.name for rm in data.resource_metrics for sm in rm.scope_metrics for m in sm.metrics}


def test_round_span_carries_round_number() -> None:
    span_exporter, _ = _setup()
    with round_span(rnd=1):
        pass
    rounds = [s for s in span_exporter.get_finished_spans() if s.name == "fl.round"]
    assert rounds, "expected an fl.round span"
    assert dict(rounds[0].attributes or {})["fl.round"] == 1


def test_client_span_names_the_phase() -> None:
    span_exporter, _ = _setup()
    with client_span(rnd=2, partition_id=3, phase="train"):
        pass
    names = {s.name for s in span_exporter.get_finished_spans()}
    assert "fl.client.train" in names


def test_round_metrics_recorded() -> None:
    _, metric_reader = _setup()
    record_round_metrics(rnd=1, loss=0.5, accuracy=0.6, clients=2)
    names = _metric_names(metric_reader)
    assert "fl.round.loss" in names
    assert "fl.round.accuracy" in names


def test_client_metrics_recorded() -> None:
    _, metric_reader = _setup()
    record_client_metrics(partition_id=0, num_examples=128, loss=0.4)
    assert "fl.client.examples" in _metric_names(metric_reader)


def test_trace_context_bridges_round_span_to_client_span() -> None:
    span_exporter, _ = _setup()
    # Server: start the round span, carry its context as a W3C traceparent string.
    round_sp = start_round_span(rnd=1)
    traceparent = traceparent_for(round_sp)
    assert traceparent  # non-empty W3C header
    # Client: rebuild the parent context and open a client span under it.
    parent = context_from_traceparent(traceparent)
    with client_span(rnd=1, partition_id=0, phase="train", parent=parent):
        pass
    round_sp.end()

    spans = {s.name: s for s in span_exporter.get_finished_spans()}
    # One distributed trace: the client span is a child of the round span.
    client, server_round = spans["fl.client.train"], spans["fl.round"]
    assert client.context.trace_id == server_round.context.trace_id
    assert client.parent is not None
    assert client.parent.span_id == server_round.context.span_id


def test_client_span_without_parent_is_its_own_trace() -> None:
    span_exporter, _ = _setup()
    with client_span(rnd=1, partition_id=0, phase="train"):
        pass
    span = next(s for s in span_exporter.get_finished_spans() if s.name == "fl.client.train")
    assert span.parent is None  # no bridge -> root span, as before


def test_shutdown_flushes_and_is_idempotent() -> None:
    span_exporter, _ = _setup()
    with round_span(rnd=1):
        pass
    # Flush + shut down so buffered OTLP spans/metrics aren't lost on process exit.
    shutdown_telemetry()
    shutdown_telemetry()  # idempotent: a second call must not raise
    assert any(s.name == "fl.round" for s in span_exporter.get_finished_spans())
