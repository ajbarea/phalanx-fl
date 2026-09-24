"""phalanx-fl ServerApp: robust aggregation over LoRA adapters, observed with OpenTelemetry.

``ObservableMixin`` hooks the per-round entry points inside ``strategy.start()`` of
any Flower strategy: it counts participating clients in ``aggregate_train`` and,
after ``aggregate_evaluate``, emits an ``fl.round`` span plus aggregated
loss/accuracy/participation metrics. ``strategy`` in the run config picks the
aggregation rule; ``ObservableFedAvg`` is the default. Only the LoRA adapters are
federated (the initial arrays come from the adapter state, not the full model).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
from flwr.app import ArrayRecord, ConfigRecord, Context, Message, MetricRecord
from flwr.serverapp import Grid, ServerApp
from flwr.serverapp.strategy import (
    Bulyan,
    FedAvg,
    FedMedian,
    FedTrimmedAvg,
    Krum,
    MultiKrum,
    Strategy,
)
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


def outlier_rank(updates: list[np.ndarray], index: int) -> int:
    """Rank of ``updates[index]`` by distance from the coordinate-wise median (1 = farthest)."""
    median = np.median(np.stack(updates), axis=0)
    distances = [float(np.linalg.norm(u - median)) for u in updates]
    return 1 + sum(d > distances[index] for d in distances)


def _flatten(message: Message) -> np.ndarray:
    return np.concatenate(
        [a.ravel() for a in message.content.array_records["arrays"].to_numpy_ndarrays()]
    )


class ObservableMixin(Strategy):
    """Emits OTel round spans + FL metrics each round for the strategy it precedes in the MRO.

    Also records, per round, the outlier rank of each reply flagged ``malicious`` (see
    ``outlier_rank``): the bookkeeping behind "does the attacker stand out?". The flag is
    read here only, never by the aggregation rule.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._round_clients: dict[int, int] = {}
        self._round_failures: dict[int, int] = {}
        self._round_spans: dict[int, Any] = {}
        self.attacker_ranks: dict[int, list[int]] = {}

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
        ok = [m for m in replies if not m.has_error()]
        flagged = [i for i, m in enumerate(ok) if m.content["metrics"].get("malicious", 0)]
        if flagged:
            updates = [_flatten(m) for m in ok]
            self.attacker_ranks[server_round] = [outlier_rank(updates, i) for i in flagged]
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


class ObservableFedAvg(ObservableMixin, FedAvg):
    """FedAvg that emits OTel round spans + FL metrics each round."""


_STRATEGIES: dict[str, type[Strategy]] = {
    "fedavg": FedAvg,
    "krum": Krum,
    "multikrum": MultiKrum,
    "trimmed-mean": FedTrimmedAvg,
    "median": FedMedian,
    "bulyan": Bulyan,
}


def build_strategy(cfg: Any) -> Any:
    """The observable strategy named by ``cfg["strategy"]``, configured from ``cfg``."""
    name = str(cfg["strategy"])
    if name not in _STRATEGIES:
        raise ValueError(f"unknown strategy {name!r}; choose from {sorted(_STRATEGIES)}")
    base = _STRATEGIES[name]
    kwargs: dict[str, Any] = {
        "fraction_train": float(cfg["fraction-train"]),
        "fraction_evaluate": float(cfg["fraction-evaluate"]),
    }
    if name in ("krum", "multikrum", "bulyan"):
        kwargs["num_malicious_nodes"] = int(cfg["num-malicious"])
    if name == "multikrum":
        kwargs["num_nodes_to_select"] = int(cfg["num-nodes-to-select"])
    if name == "trimmed-mean":
        kwargs["beta"] = float(cfg["trim-beta"])
    observable = (
        ObservableFedAvg
        if base is FedAvg
        else type(f"Observable{base.__name__}", (ObservableMixin, base), {})
    )
    return observable(**kwargs)


def heldout_evaluator(cfg: Any) -> Any:
    """A ``strategy.start`` ``evaluate_fn`` scoring the global adapters on a clean split."""
    import torch

    from phalanx.task import get_model, heldout_fn, load_heldout, set_adapter_state

    model_name = str(cfg["model-name"])
    loader = load_heldout(
        model_name,
        dataset=str(cfg["dataset"]),
        split=str(cfg["heldout-split"]),
        text_column=str(cfg["text-column"]),
    )
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = get_model(
        model_name,
        num_labels=int(cfg["num-labels"]),
        target_modules=str(cfg["lora-target-modules"]),
    ).to(device)
    flip = (int(cfg["flip-from"]), int(cfg["flip-to"]))

    def evaluate(server_round: int, arrays: ArrayRecord) -> MetricRecord:
        set_adapter_state(model, arrays.to_torch_state_dict())
        metrics: Any = heldout_fn(model, loader, device, flip)  # dict invariance vs MetricRecord
        return MetricRecord(metrics)

    return evaluate


@app.main()
def main(grid: Grid, context: Context) -> None:
    """Federate LoRA adapters with the configured strategy; observe every round over OTLP."""
    # deferred: heavy torch/HF import
    from phalanx.task import get_adapter_state, get_model, set_seed

    cfg: Any = context.run_config  # flwr config values are a broad union; read as Any
    init_telemetry(service_name=str(cfg["otel-service-name"]))
    set_seed(int(cfg["seed"]))  # same seed, same initial head, so scenarios pair up

    # Initial global state = the LoRA adapters only (not the frozen base model).
    model = get_model(
        str(cfg["model-name"]),
        num_labels=int(cfg["num-labels"]),
        target_modules=str(cfg["lora-target-modules"]),
    )
    initial_arrays = ArrayRecord(get_adapter_state(model))

    strategy = build_strategy(cfg)
    evaluate_fn = heldout_evaluator(cfg) if str(cfg["heldout-split"]) else None
    try:
        result = strategy.start(
            grid=grid,
            initial_arrays=initial_arrays,
            num_rounds=int(cfg["num-server-rounds"]),
            evaluate_fn=evaluate_fn,
        )
        # Static provenance for the run, beside the dynamic OTel trace.
        eval_metrics = {
            str(rnd): dict(rec) for rnd, rec in result.evaluate_metrics_clientapp.items()
        }
        heldout = {str(rnd): dict(rec) for rnd, rec in result.evaluate_metrics_serverapp.items()}
        ranks = {str(rnd): r for rnd, r in strategy.attacker_ranks.items()}
        write_manifest(
            run_manifest(
                run_config=dict(cfg),
                metrics=eval_metrics,
                extra={"heldout_metrics": heldout, "attacker_outlier_rank": ranks},
            )
        )
    finally:
        shutdown_telemetry()  # flush buffered OTLP spans/metrics before exit
