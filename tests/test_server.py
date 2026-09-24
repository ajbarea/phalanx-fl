"""ObservableFedAvg's per-round telemetry hook.

Tests the pure observation path (MetricRecord -> span + metrics) with in-memory
exporters; the super()-wrapping strategy glue is covered by the flwr-run smoke.
"""

from __future__ import annotations

import math
from typing import Any

from flwr.app import MetricRecord
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from phalanx.server_app import effective_sample_size, observe_round
from phalanx.telemetry import init_telemetry


def _setup() -> tuple[InMemorySpanExporter, InMemoryMetricReader]:
    span_exporter = InMemorySpanExporter()
    metric_reader = InMemoryMetricReader()
    init_telemetry(
        service_name="phalanx-test",
        span_exporter=span_exporter,
        metric_reader=metric_reader,
    )
    return span_exporter, metric_reader


def _attrs(span: Any) -> dict[str, Any]:
    """A span's attributes as a plain dict (never None)."""
    return dict(span.attributes or {})


def _metric_names(reader: InMemoryMetricReader) -> set[str]:
    data = reader.get_metrics_data()
    assert data is not None
    return {m.name for rm in data.resource_metrics for sm in rm.scope_metrics for m in sm.metrics}


def test_observe_round_tags_span_with_aggregated_metrics() -> None:
    span_exporter, metric_reader = _setup()
    observe_round(server_round=1, metrics=MetricRecord({"loss": 0.5, "accuracy": 0.6}), clients=2)

    rounds = [s for s in span_exporter.get_finished_spans() if s.name == "fl.round"]
    assert rounds, "expected an fl.round span"
    attrs = _attrs(rounds[0])
    assert attrs["fl.round"] == 1
    assert attrs["fl.loss"] == 0.5
    assert attrs["fl.accuracy"] == 0.6
    assert attrs["fl.clients"] == 2
    assert {"fl.round.loss", "fl.round.accuracy"} <= _metric_names(metric_reader)


def test_observe_round_tolerates_missing_metrics() -> None:
    span_exporter, _ = _setup()
    # No replies aggregated (None) and a metrics record without loss/accuracy.
    observe_round(server_round=1, metrics=None, clients=0)
    observe_round(server_round=2, metrics=MetricRecord({"num-examples": 5}), clients=1)

    rounds = [s for s in span_exporter.get_finished_spans() if s.name == "fl.round"]
    by_round = {_attrs(s)["fl.round"]: _attrs(s) for s in rounds}
    assert math.isnan(by_round[1]["fl.loss"])
    assert math.isnan(by_round[2]["fl.accuracy"])


def test_observe_round_flags_client_failures() -> None:
    span_exporter, metric_reader = _setup()
    observe_round(
        server_round=1,
        metrics=MetricRecord({"loss": 0.5, "accuracy": 0.6}),
        clients=2,
        failures=1,
    )
    span = next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round")
    assert span.status.status_code == StatusCode.ERROR
    assert any(e.name == "fl.client_failures" for e in span.events)
    assert _attrs(span)["fl.failures"] == 1
    assert "fl.round.failures" in _metric_names(metric_reader)


def test_observe_round_clean_round_is_not_error() -> None:
    span_exporter, _ = _setup()
    observe_round(server_round=1, metrics=MetricRecord({"loss": 0.5, "accuracy": 0.6}), clients=2)
    span = next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round")
    assert span.status.status_code != StatusCode.ERROR


def test_effective_sample_size_reports_weight_concentration() -> None:
    # Uniform weights average over every client; a dominant client collapses ESS to ~1.
    assert effective_sample_size([10, 10, 10, 10]) == 4.0
    assert effective_sample_size([1, 1]) == 2.0
    assert math.isclose(effective_sample_size([999_999, 1]), 1.0, abs_tol=1e-4)
    # Scale-invariant: only the shares matter, not the absolute counts.
    assert math.isclose(effective_sample_size([3, 1]), effective_sample_size([300, 100]))
    # Between the extremes for a skewed but not degenerate split.
    assert 1.0 < effective_sample_size([8, 1, 1]) < 3.0


def test_effective_sample_size_is_nan_when_nothing_aggregated() -> None:
    assert math.isnan(effective_sample_size([]))
    assert math.isnan(effective_sample_size([0, 0]))


def test_observe_round_records_ess() -> None:
    span_exporter, metric_reader = _setup()
    observe_round(
        server_round=1,
        metrics=MetricRecord({"loss": 0.5, "accuracy": 0.6}),
        clients=2,
        ess=1.6,
    )
    span = next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round")
    assert _attrs(span)["fl.ess"] == 1.6
    assert "fl.round.ess" in _metric_names(metric_reader)


def test_observe_round_ess_defaults_to_nan() -> None:
    span_exporter, _ = _setup()
    observe_round(server_round=1, metrics=None, clients=0)
    span = next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round")
    assert math.isnan(_attrs(span)["fl.ess"])
