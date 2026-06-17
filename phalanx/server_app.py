"""phalanx-fl ServerApp: FedAvg over LoRA adapters, observed with OpenTelemetry.

``ObservableFedAvg`` subclasses Flower's ``FedAvg`` and hooks the per-round entry
points inside ``strategy.start()``: it counts participating clients in
``aggregate_train`` and, after ``aggregate_evaluate``, emits an ``fl.round`` span
plus aggregated loss/accuracy/participation metrics. Only the LoRA adapters are
federated (the initial arrays come from the adapter state, not the full model).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from flwr.app import ArrayRecord, ConfigRecord, Context, Message, MetricRecord
from flwr.serverapp import Grid, ServerApp
from flwr.serverapp.strategy import FedAvg
from opentelemetry.trace import Status, StatusCode

from phalanx.provenance import run_manifest, write_manifest
from phalanx.telemetry import (
    init_telemetry,
    record_round_metrics,
    shutdown_telemetry,
    start_round_span,
    traceparent_for,
)

app = ServerApp()


def _round_summary(metrics: MetricRecord | None) -> tuple[float, float]:
    """Pull (loss, accuracy) out of an aggregated MetricRecord; NaN when absent."""
    if metrics is None:
        return float("nan"), float("nan")
    # MetricRecord values are a broad numeric union; read as Any for the float cast.
    values: Any = metrics
    loss = float(values["loss"]) if "loss" in metrics else float("nan")
    accuracy = float(values["accuracy"]) if "accuracy" in metrics else float("nan")
    return loss, accuracy


def observe_round(
    *,
    server_round: int,
    metrics: MetricRecord | None,
    clients: int,
    failures: int = 0,
    span: Any | None = None,
) -> None:
    """Decorate the round span with aggregated metrics + status, then end it.

    The strategy passes the span it started in ``configure_train`` (so the clients'
    spans are its children); with no span a fresh one is created and ended — the path
    the unit tests exercise.
    """
    loss, accuracy = _round_summary(metrics)
    if span is None:
        span = start_round_span(server_round)
    span.set_attribute("fl.loss", loss)
    span.set_attribute("fl.accuracy", accuracy)
    span.set_attribute("fl.clients", clients)
    span.set_attribute("fl.failures", failures)
    if failures:
        # Surface client/worker failures in the trace, not just the participation count.
        span.add_event("fl.client_failures", {"count": failures})
        span.set_status(Status(StatusCode.ERROR, f"{failures} client failure(s) this round"))
    record_round_metrics(
        rnd=server_round,
        loss=loss,
        accuracy=accuracy,
        clients=clients,
        failures=failures,
    )
    span.end()


class ObservableFedAvg(FedAvg):
    """FedAvg that emits OTel round spans + FL metrics each round."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._round_clients: dict[int, int] = {}
        self._round_failures: dict[int, int] = {}
        self._round_spans: dict[int, Any] = {}

    def configure_train(
        self, server_round: int, arrays: ArrayRecord, config: ConfigRecord, grid: Grid
    ) -> Iterable[Message]:
        # Open the round span here so its context can ride to the clients as a W3C
        # traceparent — their spans become children of this round (one trace per round).
        span = start_round_span(server_round)
        self._round_spans[server_round] = span
        config["traceparent"] = traceparent_for(span)
        return super().configure_train(server_round, arrays, config, grid)

    def configure_evaluate(
        self, server_round: int, arrays: ArrayRecord, config: ConfigRecord, grid: Grid
    ) -> Iterable[Message]:
        span = self._round_spans.get(server_round)
        if span is not None:
            config["traceparent"] = traceparent_for(span)
        return super().configure_evaluate(server_round, arrays, config, grid)

    def aggregate_train(
        self, server_round: int, replies: Iterable[Message]
    ) -> tuple[ArrayRecord | None, MetricRecord | None]:
        replies = list(replies)
        self._round_clients[server_round] = sum(1 for m in replies if not m.has_error())
        self._round_failures[server_round] = sum(1 for m in replies if m.has_error())
        return super().aggregate_train(server_round, replies)

    def aggregate_evaluate(
        self, server_round: int, replies: Iterable[Message]
    ) -> MetricRecord | None:
        replies = list(replies)
        eval_failures = sum(1 for m in replies if m.has_error())
        metrics = super().aggregate_evaluate(server_round, replies)
        observe_round(
            server_round=server_round,
            metrics=metrics,
            clients=self._round_clients.pop(server_round, 0),
            failures=self._round_failures.pop(server_round, 0) + eval_failures,
            span=self._round_spans.pop(server_round, None),
        )
        return metrics


@app.main()
def main(grid: Grid, context: Context) -> None:
    """Federate LoRA adapters with FedAvg; observe every round over OTLP."""
    from phalanx.task import get_adapter_state, get_model  # deferred: heavy torch/HF import

    cfg: Any = context.run_config  # flwr config values are a broad union; read as Any
    init_telemetry(service_name=str(cfg["otel-service-name"]))

    # Initial global state = the LoRA adapters only (not the frozen base model).
    model = get_model(str(cfg["model-name"]), num_labels=int(cfg["num-labels"]))
    initial_arrays = ArrayRecord(get_adapter_state(model))

    strategy = ObservableFedAvg(
        fraction_train=float(cfg["fraction-train"]),
        fraction_evaluate=float(cfg["fraction-evaluate"]),
    )
    try:
        result = strategy.start(
            grid=grid,
            initial_arrays=initial_arrays,
            num_rounds=int(cfg["num-server-rounds"]),
        )
        # Static provenance for the run, beside the dynamic OTel trace.
        eval_metrics = {
            str(rnd): dict(rec) for rnd, rec in result.evaluate_metrics_clientapp.items()
        }
        write_manifest(run_manifest(run_config=dict(cfg), metrics=eval_metrics))
    finally:
        shutdown_telemetry()  # flush buffered OTLP spans/metrics before exit
