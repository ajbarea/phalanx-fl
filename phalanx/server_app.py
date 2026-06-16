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

from flwr.app import ArrayRecord, Context, Message, MetricRecord
from flwr.serverapp import Grid, ServerApp
from flwr.serverapp.strategy import FedAvg

from phalanx.telemetry import init_telemetry, record_round_metrics, round_span

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


def observe_round(*, server_round: int, metrics: MetricRecord | None, clients: int) -> None:
    """Emit the per-round span + FL metrics from the aggregated evaluation record."""
    loss, accuracy = _round_summary(metrics)
    with round_span(server_round) as span:
        span.set_attribute("fl.loss", loss)
        span.set_attribute("fl.accuracy", accuracy)
        span.set_attribute("fl.clients", clients)
        record_round_metrics(rnd=server_round, loss=loss, accuracy=accuracy, clients=clients)


class ObservableFedAvg(FedAvg):
    """FedAvg that emits OTel round spans + FL metrics each round."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._round_clients: dict[int, int] = {}

    def aggregate_train(
        self, server_round: int, replies: Iterable[Message]
    ) -> tuple[ArrayRecord | None, MetricRecord | None]:
        replies = list(replies)
        self._round_clients[server_round] = sum(1 for m in replies if not m.has_error())
        return super().aggregate_train(server_round, replies)

    def aggregate_evaluate(
        self, server_round: int, replies: Iterable[Message]
    ) -> MetricRecord | None:
        metrics = super().aggregate_evaluate(server_round, replies)
        observe_round(
            server_round=server_round,
            metrics=metrics,
            clients=self._round_clients.pop(server_round, 0),
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
    strategy.start(
        grid=grid,
        initial_arrays=initial_arrays,
        num_rounds=int(cfg["num-server-rounds"]),
    )
