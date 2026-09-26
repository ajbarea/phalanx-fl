"""phalanx-fl ServerApp: FedAvg over LoRA adapters, observed with OpenTelemetry.

``ObservableFedAvg`` subclasses Flower's ``FedAvg`` and hooks the per-round entry
points inside ``strategy.start()``: it counts participating clients in
``aggregate_train`` and, after ``aggregate_evaluate``, emits an ``fl.round`` span
plus aggregated loss/accuracy/participation/ESS metrics, each named for its phase.
With a global evaluator, the span stays open until the aggregated adapters have also
been scored on the global test set (flwr's ``evaluate_fn``, which runs after
``aggregate_evaluate``). Only the LoRA adapters are federated (the initial arrays come
from the adapter state, not the full model).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from typing import Any

from flwr.app import ArrayRecord, ConfigRecord, Context, Message, MetricRecord
from flwr.serverapp import Grid, ServerApp
from flwr.serverapp.strategy import FedAvg, Result
from opentelemetry.trace import Status, StatusCode

from phalanx.provenance import run_manifest, write_manifest
from phalanx.telemetry import (
    init_telemetry,
    record_global_metrics,
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


def effective_sample_size(weights: Iterable[float]) -> float:
    """Clients effectively contributing to the aggregate: Kish's ``(Σwᵢ)² / Σwᵢ²``.

    Equals the client count when every client carries the same weight, falls toward 1.0
    as one client's share dominates, and is NaN when nothing was aggregated. FedAvg
    weights by ``num-examples``, so under a skewed partition ESS reports how much less
    than ``clients`` the round actually averaged over.

    Train and evaluate sample their clients independently, so each phase gets its own:
    ``fl.train_ess`` over the replies that produced the adapters, ``fl.evaluate_ess``
    over the replies behind ``fl.loss`` / ``fl.accuracy``.
    """
    w = [float(x) for x in weights]
    total = math.fsum(w)
    if not w or total <= 0:
        return float("nan")
    # Kish's form over the raw weights, not 1/Σ(wᵢ/Σw)²: dividing each term by the total
    # first leaves an equal split reading 4.999999999999999 for five clients.
    return total * total / math.fsum(x * x for x in w)


def _num_examples(msg: Message, key: str = "num-examples") -> float | None:
    """The weight a client reported under ``key``, or None when the reply carries none.

    Addresses the record by type rather than by the literal name ``client_app`` happens
    to use, the way flwr's own aggregation does — a telemetry read must not be the thing
    that aborts a round. MetricRecord values are a broad numeric union, so the cast
    reads through Any, as ``_round_summary`` does for loss/accuracy.
    """
    record = next(iter(msg.content.metric_records.values()), None)
    if record is None or key not in record:
        return None
    metrics: Any = record
    return float(metrics[key])


def _reply_ess(replies: Iterable[Message], key: str) -> float:
    """ESS over the weights FedAvg aggregates the replies by (its ``weighted_by_key``)."""
    counts = (_num_examples(m, key) for m in replies if not m.has_error())
    return effective_sample_size(n for n in counts if n is not None)


def observe_round(
    *,
    server_round: int,
    metrics: MetricRecord | None,
    train_clients: int,
    evaluate_clients: int = 0,
    failures: int = 0,
    train_ess: float = float("nan"),
    evaluate_ess: float = float("nan"),
    global_metrics: MetricRecord | None = None,
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
    span.set_attribute("fl.train_clients", train_clients)
    span.set_attribute("fl.evaluate_clients", evaluate_clients)
    span.set_attribute("fl.train_ess", train_ess)
    span.set_attribute("fl.evaluate_ess", evaluate_ess)
    span.set_attribute("fl.failures", failures)
    global_loss, global_accuracy = _round_summary(global_metrics)
    span.set_attribute("fl.global_loss", global_loss)
    span.set_attribute("fl.global_accuracy", global_accuracy)
    if failures:
        # Surface client/worker failures in the trace, not just the participation count.
        span.add_event("fl.client_failures", {"count": failures})
        span.set_status(Status(StatusCode.ERROR, f"{failures} client failure(s) this round"))
    record_round_metrics(
        rnd=server_round,
        loss=loss,
        accuracy=accuracy,
        train_clients=train_clients,
        evaluate_clients=evaluate_clients,
        failures=failures,
        train_ess=train_ess,
        evaluate_ess=evaluate_ess,
    )
    if global_metrics is not None:
        record_global_metrics(rnd=server_round, loss=global_loss, accuracy=global_accuracy)
    span.end()


def _by_round(records: dict[int, MetricRecord]) -> dict[str, dict[str, Any]]:
    return {str(rnd): dict(rec) for rnd, rec in records.items()}


GlobalEvaluator = Callable[[ArrayRecord], MetricRecord]


class ObservableFedAvg(FedAvg):
    """FedAvg that emits OTel round spans + FL metrics each round.

    ``global_evaluate`` scores the aggregated adapters on the global test set each round,
    and on the initial adapters as round 0. The strategy passes it to ``start`` as
    ``evaluate_fn`` itself, so the round it closes is always the one it observed.
    """

    def __init__(
        self, *args: Any, global_evaluate: GlobalEvaluator | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self._global_evaluate = global_evaluate
        self._round_train_clients: dict[int, int] = {}
        self._round_train_ess: dict[int, float] = {}
        self._round_failures: dict[int, int] = {}
        self._round_spans: dict[int, Any] = {}
        self._awaiting_global: dict[int, dict[str, Any]] = {}

    def start(
        self,
        grid: Grid,
        initial_arrays: ArrayRecord,
        num_rounds: int = 3,
        timeout: float = 3600,
        train_config: ConfigRecord | None = None,
        evaluate_config: ConfigRecord | None = None,
        evaluate_fn: Callable[[int, ArrayRecord], MetricRecord | None] | None = None,
    ) -> Result:
        if self._global_evaluate is not None:
            if evaluate_fn is not None:
                raise ValueError("pass global_evaluate or evaluate_fn, not both")
            evaluate_fn = self._evaluate_global
        return super().start(
            grid=grid,
            initial_arrays=initial_arrays,
            num_rounds=num_rounds,
            timeout=timeout,
            train_config=train_config,
            evaluate_config=evaluate_config,
            evaluate_fn=evaluate_fn,
        )

    def _evaluate_global(self, server_round: int, arrays: ArrayRecord) -> MetricRecord:
        assert self._global_evaluate is not None
        metrics = self._global_evaluate(arrays)
        observed = self._awaiting_global.pop(server_round, None)
        if observed is None:  # round 0: the initial adapters, before any round span
            loss, accuracy = _round_summary(metrics)
            record_global_metrics(rnd=server_round, loss=loss, accuracy=accuracy)
        else:
            observe_round(**observed, global_metrics=metrics)
        return metrics

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
        self._round_train_clients[server_round] = sum(1 for m in replies if not m.has_error())
        self._round_failures[server_round] = sum(1 for m in replies if m.has_error())
        self._round_train_ess[server_round] = _reply_ess(replies, self.weighted_by_key)
        return super().aggregate_train(server_round, replies)

    def aggregate_evaluate(
        self, server_round: int, replies: Iterable[Message]
    ) -> MetricRecord | None:
        replies = list(replies)
        eval_failures = sum(1 for m in replies if m.has_error())
        metrics = super().aggregate_evaluate(server_round, replies)
        observed: dict[str, Any] = {
            "server_round": server_round,
            "metrics": metrics,
            "train_clients": self._round_train_clients.pop(server_round, 0),
            "evaluate_clients": len(replies) - eval_failures,
            "failures": self._round_failures.pop(server_round, 0) + eval_failures,
            "train_ess": self._round_train_ess.pop(server_round, float("nan")),
            "evaluate_ess": _reply_ess(replies, self.weighted_by_key),
            "span": self._round_spans.pop(server_round, None),
        }
        if self._global_evaluate is None:
            observe_round(**observed)
        else:
            self._awaiting_global[server_round] = observed
        return metrics


@app.main()
def main(grid: Grid, context: Context) -> None:
    """Federate LoRA adapters with FedAvg; observe every round over OTLP."""
    # deferred: heavy torch/HF import
    from phalanx.task import (
        default_device,
        get_adapter_state,
        get_model,
        load_global_test,
        sample_count,
        set_adapter_state,
        test_fn,
    )

    cfg: Any = context.run_config  # flwr config values are a broad union; read as Any
    init_telemetry(service_name=str(cfg["otel-service-name"]))

    # Initial global state = the LoRA adapters only (not the frozen base model).
    model = get_model(str(cfg["model-name"]), num_labels=int(cfg["num-labels"]))
    initial_arrays = ArrayRecord(get_adapter_state(model))

    testloader = load_global_test(
        str(cfg["model-name"]),
        dataset=str(cfg["dataset"]),
        size=int(cfg["global-eval-size"]),
    )
    device = default_device()
    model.to(device)

    def global_evaluate(arrays: ArrayRecord) -> MetricRecord:
        set_adapter_state(model, arrays.to_torch_state_dict())
        loss, accuracy = test_fn(model, testloader, device)
        return MetricRecord(
            {"loss": loss, "accuracy": accuracy, "num-examples": sample_count(testloader)}
        )

    strategy = ObservableFedAvg(
        fraction_train=float(cfg["fraction-train"]),
        fraction_evaluate=float(cfg["fraction-evaluate"]),
        global_evaluate=global_evaluate,
    )
    try:
        result = strategy.start(
            grid=grid,
            initial_arrays=initial_arrays,
            num_rounds=int(cfg["num-server-rounds"]),
        )
        # Static provenance for the run, beside the dynamic OTel trace.
        write_manifest(
            run_manifest(
                run_config=dict(cfg),
                metrics=_by_round(result.evaluate_metrics_clientapp),
                global_metrics=_by_round(result.evaluate_metrics_serverapp),
            )
        )
    finally:
        shutdown_telemetry()  # flush buffered OTLP spans/metrics before exit
