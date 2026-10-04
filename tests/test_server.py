"""ObservableFedAvg's per-round telemetry hook.

Tests the pure observation path (MetricRecord -> span + metrics) with in-memory
exporters; the super()-wrapping strategy glue is covered by ``make smoke``.
"""

from __future__ import annotations

import math
from typing import Any, cast
from uuid import uuid4

import numpy as np
import pytest
from flwr.app import Array, ArrayRecord, ConfigRecord, Error, Message, MetricRecord, RecordDict
from flwr.common.constant import ErrorCode
from flwr.server.superlink.linkstate.utils import create_message_error_unavailable_res_message
from flwr.supercore.task_identity import TaskIdentity
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from phalanx.server_app import (
    _ERROR_TYPES,
    ObservableFedAvg,
    _num_examples,
    build_strategy,
    effective_sample_size,
    failure_type,
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


@pytest.fixture(autouse=True)
def task_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the task identity flwr's runtime sets before a ServerApp builds messages."""
    monkeypatch.setattr(TaskIdentity, "_task_id", 1)
    monkeypatch.setattr(TaskIdentity, "_run_id", 1)
    monkeypatch.setattr(TaskIdentity, "_node_id", 1)


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
    observe_round(
        server_round=1, metrics=MetricRecord({"loss": 0.5, "accuracy": 0.6}), train_clients=2
    )

    rounds = [s for s in span_exporter.get_finished_spans() if s.name == "fl.round"]
    assert rounds, "expected an fl.round span"
    attrs = _attrs(rounds[0])
    assert attrs["fl.round"] == 1
    assert attrs["fl.loss"] == 0.5
    assert attrs["fl.accuracy"] == 0.6
    assert attrs["fl.train_clients"] == 2
    assert {"fl.round.loss", "fl.round.accuracy"} <= _metric_names(metric_reader)


def test_observe_round_tolerates_missing_metrics() -> None:
    span_exporter, _ = _setup()
    # No replies aggregated (None) and a metrics record without loss/accuracy.
    observe_round(server_round=1, metrics=None, train_clients=0)
    observe_round(server_round=2, metrics=MetricRecord({"num-examples": 5}), train_clients=1)

    rounds = [s for s in span_exporter.get_finished_spans() if s.name == "fl.round"]
    by_round = {_attrs(s)["fl.round"]: _attrs(s) for s in rounds}
    assert math.isnan(by_round[1]["fl.loss"])
    assert math.isnan(by_round[2]["fl.accuracy"])


def test_a_round_that_tolerated_client_failures_is_not_an_error() -> None:
    # semconv: an error the operation handled and completed despite is not its error.
    span_exporter, _ = _setup()
    observe_round(
        server_round=1,
        metrics=MetricRecord({"loss": 0.5, "accuracy": 0.6}),
        train_clients=2,
        failures=1,
    )
    span = next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round")
    assert span.status.status_code == StatusCode.UNSET
    assert "error.type" not in _attrs(span)
    assert _attrs(span)["fl.failures"] == 1


def test_observe_round_clean_round_is_not_error() -> None:
    span_exporter, _ = _setup()
    observe_round(
        server_round=1, metrics=MetricRecord({"loss": 0.5, "accuracy": 0.6}), train_clients=2
    )
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
        train_clients=2,
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
    observe_round(server_round=1, metrics=None, train_clients=0)
    span = next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round")
    assert math.isnan(_attrs(span)["fl.train_ess"])
    assert math.isnan(_attrs(span)["fl.evaluate_ess"])


def _counted(n: float, message_type: str, **metrics: float) -> Message:
    content = RecordDict({"metrics": MetricRecord({"num-examples": n, **metrics})})
    if message_type == "train":
        content["arrays"] = ArrayRecord({"w": Array(np.ones(2, dtype=np.float32))})
    return Message(content=content, dst_node_id=0, message_type=message_type)


def _failed(message_type: str) -> Message:
    request = Message(content=RecordDict(), dst_node_id=0, message_type=message_type)
    return Message(Error(code=0, reason="client crashed"), reply_to=request)


def test_each_phase_reports_the_ess_of_its_own_replies() -> None:
    # Train and evaluate sample different clients; each ESS must come from its own phase.
    # Uneven evaluate sizes keep ESS apart from the client count, and the errored reply
    # counts as a failure, not a client.
    span_exporter, _ = _setup()
    strategy = ObservableFedAvg()
    strategy.aggregate_train(1, [_counted(n, "train", train_loss=0.1) for n in (90, 10)])
    strategy.aggregate_evaluate(
        1,
        [_counted(n, "evaluate", loss=0.5, accuracy=0.6) for n in (10, 30, 20)]
        + [_failed("evaluate")],
    )
    attrs = _attrs(next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round"))
    assert math.isclose(attrs["fl.train_ess"], effective_sample_size([90, 10]))
    assert math.isclose(attrs["fl.evaluate_ess"], effective_sample_size([10, 30, 20]))
    assert (attrs["fl.train_clients"], attrs["fl.evaluate_clients"]) == (2, 3)
    assert attrs["fl.failures"] == 1


def test_ess_reads_the_key_fedavg_weights_by() -> None:
    span_exporter, _ = _setup()
    strategy = ObservableFedAvg(weighted_by_key="rows")
    replies = [
        Message(
            content=RecordDict({"m": MetricRecord({"rows": n, "loss": 0.5})}),
            dst_node_id=0,
            message_type="evaluate",
        )
        for n in (10, 30)
    ]
    strategy.aggregate_evaluate(1, replies)
    attrs = _attrs(next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round"))
    assert math.isclose(attrs["fl.evaluate_ess"], effective_sample_size([10, 30]))


def _update(n: float, value: float) -> Message:
    content = RecordDict(
        {
            "metrics": MetricRecord({"num-examples": n}),
            "arrays": ArrayRecord({"w": Array(np.full(2, value, dtype=np.float32))}),
        }
    )
    return Message(content=content, dst_node_id=0, message_type="train")


@pytest.mark.parametrize("name", ["krum", "multikrum", "trimmed-mean", "median", "bulyan"])
def test_robust_rules_report_no_train_ess(name: str) -> None:
    # They select or trim instead of taking FedAvg's num-examples mean, so a Kish ESS over
    # those weights would describe an aggregate they never computed. Evaluation is still
    # FedAvg's weighted mean, so its ESS stands. Seven updates satisfy Bulyan's n >= 4f + 3.
    span_exporter, _ = _setup()
    cfg = {
        "strategy": name,
        "fraction-train": 1.0,
        "fraction-evaluate": 1.0,
        "num-malicious": 1,
        "num-nodes-to-select": 6,
        "trim-beta": 0.2,
    }
    strategy = build_strategy(cfg)
    sizes, values = (90, 10, 40, 20, 30, 50, 60), (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 9.0)
    arrays, _ = strategy.aggregate_train(
        1, [_update(n, v) for n, v in zip(sizes, values, strict=True)]
    )
    assert arrays is not None
    strategy.aggregate_evaluate(
        1, [_counted(n, "evaluate", loss=0.5, accuracy=0.6) for n in (10, 30)]
    )
    attrs = _attrs(next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round"))
    assert math.isnan(attrs["fl.train_ess"])
    assert math.isclose(attrs["fl.evaluate_ess"], effective_sample_size([10, 30]))


def test_a_declined_aggregation_marks_its_round() -> None:
    # Bulyan needs 4f + 3 = 7 replies at f = 1; with 3 it returns no arrays, so the global
    # model stays put and the round must say so rather than read as a defended round.
    span_exporter, _ = _setup()
    strategy = build_strategy(
        {
            "strategy": "bulyan",
            "fraction-train": 1.0,
            "fraction-evaluate": 1.0,
            "num-malicious": 1,
        }
    )
    arrays, _ = strategy.aggregate_train(
        1, [_update(n, v) for n, v in ((10, 0.0), (20, 0.1), (30, 0.2))]
    )
    assert arrays is None
    strategy.aggregate_evaluate(1, [_counted(10, "evaluate", loss=0.5, accuracy=0.6)])
    span = next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round")
    assert "fl.aggregation_skipped" in [e.name for e in span.events]
    assert span.status.status_code == StatusCode.ERROR
    assert strategy.skipped_rounds == {1}


def test_attacker_ranks_read_the_metric_record_by_type() -> None:
    # A reply may name its MetricRecord anything; FedAvg accepts it, so must the bookkeeping.
    _setup()
    strategy = ObservableFedAvg()
    replies = [
        Message(
            content=RecordDict(
                {
                    "m": MetricRecord({"num-examples": 10, "malicious": int(v > 1)}),
                    "a": ArrayRecord({"w": Array(np.full(2, v, dtype=np.float32))}),
                }
            ),
            dst_node_id=0,
            message_type="train",
        )
        for v in (0.0, 0.1, 9.0)
    ]
    strategy.aggregate_train(1, replies)
    assert strategy.attacker_ranks == {1: [1]}


def _global(accuracy: float) -> Any:
    def evaluate(arrays: ArrayRecord) -> MetricRecord:
        return MetricRecord({"loss": 0.4, "accuracy": accuracy, "num-examples": 100})

    return evaluate


def _run_round(strategy: ObservableFedAvg, server_round: int = 1) -> None:
    strategy.aggregate_train(server_round, [_counted(n, "train", train_loss=0.1) for n in (5, 5)])
    strategy.aggregate_evaluate(
        server_round, [_counted(n, "evaluate", loss=0.5, accuracy=0.9) for n in (5, 5)]
    )


def _rounds(exporter: InMemorySpanExporter) -> list[Any]:
    return [s for s in exporter.get_finished_spans() if s.name == "fl.round"]


def test_global_evaluation_closes_the_round_it_scored() -> None:
    # flwr runs evaluate_fn after aggregate_evaluate, so the span must wait for it.
    span_exporter, metric_reader = _setup()
    strategy = ObservableFedAvg(global_evaluate=_global(0.71))
    _run_round(strategy)
    assert not _rounds(span_exporter), "round span ended before the global evaluation"

    strategy._evaluate_global(1, ArrayRecord())
    (span,) = _rounds(span_exporter)
    attrs = _attrs(span)
    assert (attrs["fl.global_accuracy"], attrs["fl.accuracy"]) == (0.71, 0.9)
    assert {"fl.round.global_accuracy", "fl.round.global_loss"} <= _metric_names(metric_reader)


def test_global_evaluation_of_the_initial_adapters_opens_no_round() -> None:
    span_exporter, metric_reader = _setup()
    strategy = ObservableFedAvg(global_evaluate=_global(0.5))
    assert strategy._evaluate_global(0, ArrayRecord())["accuracy"] == 0.5
    assert not _rounds(span_exporter)
    assert "fl.round.global_accuracy" in _metric_names(metric_reader)


def test_without_a_global_evaluator_the_round_closes_at_aggregate_evaluate() -> None:
    span_exporter, _ = _setup()
    _run_round(ObservableFedAvg())
    (span,) = _rounds(span_exporter)
    assert math.isnan(_attrs(span)["fl.global_accuracy"])


def test_start_refuses_a_second_evaluate_fn() -> None:
    strategy = ObservableFedAvg(global_evaluate=_global(0.5))
    with pytest.raises(ValueError, match="not both"):
        strategy.start(
            grid=cast(Any, None), initial_arrays=ArrayRecord(), evaluate_fn=lambda r, a: None
        )


def test_a_failing_global_evaluation_still_closes_its_round() -> None:
    # The round's client metrics are aggregated before evaluate_fn runs; a failure there
    # must not drop them, and the span must say why the run stopped.
    span_exporter, metric_reader = _setup()

    def broken(arrays: ArrayRecord) -> MetricRecord:
        raise RuntimeError("hub unreachable")

    strategy = ObservableFedAvg(global_evaluate=broken)
    _run_round(strategy)
    with pytest.raises(RuntimeError, match="hub unreachable"):
        strategy._evaluate_global(1, ArrayRecord())
    (span,) = _rounds(span_exporter)
    assert span.status.status_code == StatusCode.ERROR
    assert any(e.name == "fl.global_evaluation_failed" for e in span.events)
    assert _attrs(span)["fl.accuracy"] == 0.9
    assert "fl.round.loss" in _metric_names(metric_reader)


class _Grid:
    """Two always-available nodes that answer every message, as flwr's Grid would."""

    def get_node_ids(self) -> list[int]:
        return [1, 2]

    def send_and_receive(self, messages: Any, timeout: float | None = None) -> list[Message]:
        replies = []
        for msg in messages:
            metrics = MetricRecord({"num-examples": 10, "loss": 0.5, "accuracy": 0.8})
            content = RecordDict({"metrics": metrics})
            if msg.metadata.message_type == "train":
                content["arrays"] = msg.content.array_records["arrays"]
            replies.append(Message(content, reply_to=msg))
        return replies


def test_start_closes_every_round_after_its_global_evaluation() -> None:
    # Drives flwr's own Strategy.start, so the ordering the deferral relies on
    # (evaluate_fn after aggregate_evaluate, round 0 first) is pinned across upgrades.
    span_exporter, _ = _setup()
    seen: list[int] = []

    def evaluate(arrays: ArrayRecord) -> MetricRecord:
        seen.append(len(_rounds(span_exporter)))  # rounds already closed at this call
        return MetricRecord({"loss": 0.4, "accuracy": 0.6})

    strategy = ObservableFedAvg(fraction_train=1.0, fraction_evaluate=1.0, global_evaluate=evaluate)
    initial = ArrayRecord({"w": Array(np.ones(2, dtype=np.float32))})
    result = strategy.start(grid=cast(Any, _Grid()), initial_arrays=initial, num_rounds=3)

    assert seen == [0, 0, 1, 2]  # round 0 first, then each round still open when scored
    spans = _rounds(span_exporter)
    assert [_attrs(s)["fl.round"] for s in spans] == [1, 2, 3]
    assert all(_attrs(s)["fl.global_accuracy"] == 0.6 for s in spans)
    assert sorted(result.evaluate_metrics_serverapp) == [0, 1, 2, 3]


def _points(reader: InMemoryMetricReader, name: str) -> list[Any]:
    data = reader.get_metrics_data()
    assert data is not None
    return [
        point
        for rm in data.resource_metrics
        for sm in rm.scope_metrics
        for metric in sm.metrics
        if metric.name == name
        for point in metric.data.data_points
    ]


def test_round_duration_is_the_round_span_duration() -> None:
    span_exporter, reader = _setup()
    observe_round(server_round=4, metrics=None, train_clients=2)
    span = next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round")
    assert span.start_time is not None and span.end_time is not None
    (point,) = _points(reader, "fl.round.duration")
    assert point.count == 1
    assert point.sum == pytest.approx((span.end_time - span.start_time) / 1e9)
    assert dict(point.attributes) == {"fl.round": 4}


def test_payload_bytes_are_counted_per_type_and_direction() -> None:
    # Through flwr's own start loop: every message out and every reply back is counted,
    # and each round span's totals add up to what the histogram recorded.
    span_exporter, reader = _setup()
    strategy = ObservableFedAvg(fraction_train=1.0, fraction_evaluate=1.0)
    initial = ArrayRecord({"w": Array(np.ones(256, dtype=np.float32))})
    strategy.start(grid=cast(Any, _Grid()), initial_arrays=initial, num_rounds=2)

    points = _points(reader, "fl.message.size")
    by_key = {
        (p.attributes["fl.message.type"], p.attributes["fl.message.direction"]): p for p in points
    }
    assert set(by_key) == {
        ("train", "server_to_client"),
        ("train", "client_to_server"),
        ("evaluate", "server_to_client"),
        ("evaluate", "client_to_server"),
    }
    assert all(p.count == 4 for p in points)  # 2 nodes x 2 rounds
    assert by_key[("train", "server_to_client")].min >= initial.count_bytes()

    spans = _rounds(span_exporter)
    for direction in ("server_to_client", "client_to_server"):
        recorded = sum(p.sum for (_, d), p in by_key.items() if d == direction)
        assert sum(_attrs(s)[f"fl.round.message.size.{direction}"] for s in spans) == recorded


def test_error_replies_carry_no_payload() -> None:
    _, reader = _setup()
    strategy = ObservableFedAvg()
    strategy.aggregate_evaluate(1, [_failed("evaluate")])
    assert _points(reader, "fl.message.size") == []


def test_round_duration_survives_an_unsampled_round(monkeypatch: pytest.MonkeyPatch) -> None:
    # An unsampled span has no timestamps; metrics are not sampled, so every round counts.
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_off")
    _, reader = _setup()
    strategy = ObservableFedAvg(fraction_train=1.0, fraction_evaluate=1.0)
    initial = ArrayRecord({"w": Array(np.ones(2, dtype=np.float32))})
    strategy.start(grid=cast(Any, _Grid()), initial_arrays=initial, num_rounds=3)
    points = _points(reader, "fl.round.duration")
    assert sorted(p.attributes["fl.round"] for p in points) == [1, 2, 3]
    assert all(p.count == 1 and p.sum >= 0 for p in points)


def test_a_round_whose_replies_all_fail_reads_zero_bytes_back() -> None:
    span_exporter, _ = _setup()
    strategy = ObservableFedAvg(fraction_train=1.0, fraction_evaluate=1.0)
    arrays = ArrayRecord({"w": Array(np.ones(2, dtype=np.float32))})
    strategy.configure_train(1, arrays, ConfigRecord(), cast(Any, _Grid()))
    strategy.aggregate_train(1, [_failed("train"), _failed("train")])
    strategy.aggregate_evaluate(1, [])
    attrs = _attrs(next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round"))
    assert attrs["fl.round.message.size.client_to_server"] == 0
    assert attrs["fl.round.message.size.server_to_client"] > 0


def _error_reply(code: int, reason: str = "boom", message_type: str = "train") -> Message:
    request = Message(content=RecordDict(), dst_node_id=0, message_type=message_type)
    return Message(Error(code=code, reason=reason), reply_to=request)


@pytest.mark.parametrize(
    ("code", "reason", "expected"),
    [
        (ErrorCode.CLIENT_APP_RAISED_EXCEPTION, "boom", "client_app_exception"),
        (ErrorCode.LOAD_CLIENT_APP_EXCEPTION, "boom", "client_app_load_error"),
        (ErrorCode.CLIENT_APP_CRASHED, "boom", "client_app_crashed"),
        (ErrorCode.NODE_UNAVAILABLE, "boom", "node_unavailable"),
        (ErrorCode.UNKNOWN, "<class 'ray.exceptions.OutOfMemoryError'>:<'killed'>", "oom"),
        (ErrorCode.UNKNOWN, "<class 'ray.exceptions.RayActorError'>:<'died'>", "worker_died"),
        (ErrorCode.UNKNOWN, "<class 'ray.exceptions.ActorDiedError'>:<'died'>", "worker_died"),
        (ErrorCode.UNKNOWN, "<class 'ValueError'>:<'bad'>", "_OTHER"),
        (ErrorCode.UNKNOWN, "no class here", "_OTHER"),
        (99, "a code flwr has not defined", "_OTHER"),
    ],
)
def test_failure_type_classifies_flowers_error(code: int, reason: str, expected: str) -> None:
    assert failure_type(_error_reply(code, reason)) == expected


def test_every_flower_error_code_has_an_error_type() -> None:
    # A code flwr adds upstream fails here instead of reading as _OTHER in traces.
    codes = {v for k, v in vars(ErrorCode).items() if k.isupper() and k != "UNKNOWN"}
    assert codes == set(_ERROR_TYPES)


_UNREACHABLE = 2**63 + 42  # node ids are uint64; this one is past int64


class _FlakyGrid(_Grid):
    """Node 1 raises, node 2 answers, node 3 never replies, and the SuperLink reports
    the last node unavailable. Ids are written on push, as flwr's InMemoryGrid does."""

    def get_node_ids(self) -> list[int]:
        return [1, 2, 3, _UNREACHABLE]

    def send_and_receive(self, messages: Any, timeout: float | None = None) -> list[Message]:
        replies = []
        for msg in messages:
            msg.metadata.__dict__["_message_id"] = str(uuid4())
            node = msg.metadata.dst_node_id
            if node == _UNREACHABLE:
                reply = create_message_error_unavailable_res_message(msg.metadata, "node_unavail")
            elif node == 1:
                error = Error(code=ErrorCode.CLIENT_APP_RAISED_EXCEPTION, reason="boom")
                reply = Message(error, reply_to=msg)
            elif node == 2:
                (reply,) = super().send_and_receive([msg])
            else:
                continue
            replies.append(reply)
        return replies


def test_failed_and_missing_replies_are_classified_and_tolerated() -> None:
    span_exporter, reader = _setup()
    strategy = ObservableFedAvg(fraction_train=1.0, fraction_evaluate=1.0)
    initial = ArrayRecord({"w": Array(np.ones(2, dtype=np.float32))})
    strategy.start(grid=cast(Any, _FlakyGrid()), initial_arrays=initial, num_rounds=1)

    (span,) = _rounds(span_exporter)
    failures = [dict(e.attributes or {}) for e in span.events if e.name == "fl.client.failure"]
    seen = [(f["fl.message.type"], f["error.type"], f["fl.node.id"]) for f in failures]
    # The SuperLink's reply names itself as source; matched by id, the unavailable node is
    # counted once, under its own id, with no phantom timeout.
    assert sorted(seen) == sorted(
        (phase, error_type, node)
        for phase in ("train", "evaluate")
        for error_type, node in (
            ("client_app_exception", "1"),
            ("timeout", "3"),
            ("node_unavailable", str(_UNREACHABLE)),
        )
    )
    assert span.status.status_code == StatusCode.UNSET  # node 2's update still aggregated
    assert _attrs(span)["fl.failures"] == 6
    assert strategy.client_failures == {
        1: {"client_app_exception": 2, "timeout": 2, "node_unavailable": 2}
    }
    counted = {
        (p.attributes["fl.message.type"], p.attributes["error.type"]): p.value
        for p in _points(reader, "fl.round.failures")
    }
    assert counted == {
        (phase, error_type): 1
        for phase in ("train", "evaluate")
        for error_type in ("client_app_exception", "timeout", "node_unavailable")
    }


def test_a_round_with_no_client_update_is_an_error() -> None:
    span_exporter, reader = _setup()
    strategy = ObservableFedAvg(fraction_train=1.0, fraction_evaluate=1.0)
    arrays = ArrayRecord({"w": Array(np.ones(2, dtype=np.float32))})
    strategy.configure_train(1, arrays, ConfigRecord(), cast(Any, _Grid()))
    strategy.aggregate_train(1, [_error_reply(ErrorCode.CLIENT_APP_CRASHED)])
    strategy.aggregate_evaluate(1, [])
    span = next(s for s in span_exporter.get_finished_spans() if s.name == "fl.round")
    assert span.status.status_code == StatusCode.ERROR
    assert _attrs(span)["error.type"] == "no_client_updates"
    (point,) = _points(reader, "fl.round.duration")
    assert point.attributes["error.type"] == "no_client_updates"
    assert strategy.no_update_rounds == {1}
