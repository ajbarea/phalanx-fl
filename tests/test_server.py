"""ObservableFedAvg's per-round telemetry hook.

Tests the pure observation path (MetricRecord -> span + metrics) with in-memory
exporters; the super()-wrapping strategy glue is covered by ``make smoke``.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from flwr.app import Array, ArrayRecord, Message, MetricRecord, RecordDict
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from phalanx.server_app import (
    ObservableFedAvg,
    _num_examples,
    effective_sample_size,
    observe_round,
)
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


def _reply(content: RecordDict) -> Message:
    """A client reply carrying `content` (the shape aggregate_train iterates)."""
    return Message(content=content, dst_node_id=0, message_type="train")


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


def test_effective_sample_size_is_exact_for_an_even_split() -> None:
    # Normalising each term before squaring reads 4.999999999999999 at n=5 and
    # 9.999999999999996 at n=10; Kish's form over the raw weights is exact.
    for n in range(2, 33):
        assert effective_sample_size([10] * n) == float(n), f"inexact at n={n}"


def test_effective_sample_size_never_exceeds_the_client_count() -> None:
    for weights in ([1, 2, 3], [7, 7, 7, 1], [10] * 9, [5, 4], [1] * 17):
        assert effective_sample_size(weights) <= len(weights) + 1e-12


def test_effective_sample_size_is_nan_when_nothing_aggregated() -> None:
    assert math.isnan(effective_sample_size([]))
    assert math.isnan(effective_sample_size([0, 0]))


def test_num_examples_reads_the_record_by_type_not_by_name() -> None:
    # client_app names its record "metrics"; nothing guarantees that, and flwr addresses
    # it by type. A differently-named record must still yield the weight.
    msg = _reply(RecordDict({"whatever-name": MetricRecord({"num-examples": 40.0})}))
    assert _num_examples(msg) == 40.0


def test_num_examples_is_none_when_the_reply_carries_no_count() -> None:
    # Must not raise: a telemetry read cannot be what aborts a round.
    assert _num_examples(_reply(RecordDict({"metrics": MetricRecord({"loss": 0.5})}))) is None
    assert _num_examples(_reply(RecordDict({}))) is None


def test_observe_round_records_ess_per_phase() -> None:
    span_exporter, metric_reader = _setup()
    observe_round(
        server_round=1,
        metrics=MetricRecord({"loss": 0.5, "accuracy": 0.6}),
        clients=2,
        evaluate_clients=3,
        train_ess=1.6,
        evaluate_ess=2.4,
    )
    span = next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round")
    attrs = _attrs(span)
    assert (attrs["fl.train_ess"], attrs["fl.evaluate_ess"]) == (1.6, 2.4)
    assert attrs["fl.evaluate_clients"] == 3
    assert {
        "fl.round.train_ess",
        "fl.round.evaluate_ess",
        "fl.round.evaluate_clients",
    } <= _metric_names(metric_reader)


def test_observe_round_ess_defaults_to_nan() -> None:
    span_exporter, _ = _setup()
    observe_round(server_round=1, metrics=None, clients=0)
    span = next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round")
    assert math.isnan(_attrs(span)["fl.train_ess"])
    assert math.isnan(_attrs(span)["fl.evaluate_ess"])


def _counted(n: float, message_type: str, **metrics: float) -> Message:
    content = RecordDict({"metrics": MetricRecord({"num-examples": n, **metrics})})
    if message_type == "train":
        content["arrays"] = ArrayRecord({"w": Array(np.ones(2, dtype=np.float32))})
    return Message(content=content, dst_node_id=0, message_type=message_type)


def test_each_phase_reports_the_ess_of_its_own_replies() -> None:
    # Train and evaluate sample different clients; each ESS must come from its own phase.
    span_exporter, _ = _setup()
    strategy = ObservableFedAvg()
    strategy.aggregate_train(1, [_counted(n, "train", train_loss=0.1) for n in (90, 10)])
    strategy.aggregate_evaluate(
        1, [_counted(n, "evaluate", loss=0.5, accuracy=0.6) for n in (10, 10, 10)]
    )
    attrs = _attrs(next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round"))
    assert math.isclose(attrs["fl.train_ess"], effective_sample_size([90, 10]))
    assert attrs["fl.evaluate_ess"] == 3.0
    assert (attrs["fl.clients"], attrs["fl.evaluate_clients"]) == (2, 3)
