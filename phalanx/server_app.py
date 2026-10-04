"""phalanx-fl ServerApp: robust aggregation over LoRA adapters, observed with OpenTelemetry.

``ObservableMixin`` hooks the per-round entry points inside ``strategy.start()`` of
any of Flower's FedAvg-family strategies: it counts participating clients in
``aggregate_train`` and, after ``aggregate_evaluate``, emits an ``fl.round`` span
plus aggregated loss/accuracy/participation/ESS metrics, each named for its phase.
``strategy`` in the run config picks the aggregation rule; ``ObservableFedAvg`` is the
default.
With a global evaluator, the span stays open until the aggregated adapters have also
been scored on the global test set (flwr's ``evaluate_fn``, which runs after
``aggregate_evaluate``). Only the LoRA adapters are federated (the initial arrays come
from the adapter state, not the full model).
"""

from __future__ import annotations

import math
import re
import time
from collections import Counter
from collections.abc import Callable, Iterable
from typing import Any

import numpy as np
from flwr.app import ArrayRecord, ConfigRecord, Context, Message, MetricRecord
from flwr.common.constant import ErrorCode
from flwr.serverapp import Grid, ServerApp
from flwr.serverapp.strategy import (
    Bulyan,
    FedAvg,
    FedMedian,
    FedTrimmedAvg,
    Krum,
    MultiKrum,
    Result,
)
from opentelemetry.trace import Status, StatusCode

from phalanx.provenance import run_manifest, write_manifest
from phalanx.telemetry import (
    init_telemetry,
    record_failures,
    record_global_metrics,
    record_message_size,
    record_round_duration,
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


def _metric(msg: Message, key: str) -> float | None:
    """The value a client reported under ``key``, or None when the reply carries none.

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


def _num_examples(msg: Message, key: str = "num-examples") -> float | None:
    """The weight a client reported under ``key`` (FedAvg's ``weighted_by_key``)."""
    return _metric(msg, key)


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
    global_error: str | None = None,
    aggregation_skipped: bool = False,
    no_client_updates: bool = False,
    payload_bytes: dict[str, int] | None = None,
    started: float | None = None,
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
    for direction, nbytes in (payload_bytes or {}).items():
        span.set_attribute(f"fl.round.message.size.{direction}", nbytes)
    global_loss, global_accuracy = _round_summary(global_metrics)
    span.set_attribute("fl.global_loss", global_loss)
    span.set_attribute("fl.global_accuracy", global_accuracy)
    # Client failures the round tolerated leave its status unset (semconv: a handled
    # error is not the operation's error); each one is an fl.client.failure event,
    # added when its reply arrived. Only a round that itself failed is ERROR.
    error: tuple[str, str] | None = None
    if no_client_updates:
        span.add_event("fl.no_client_updates")
        error = ("no_client_updates", "no client returned an update; global model unchanged")
    if aggregation_skipped:
        # The rule declined (e.g. Bulyan below 4f + 3 replies): the global model did not
        # change, so this round's global metrics re-score the previous round's adapters.
        span.add_event("fl.aggregation_skipped")
        error = ("aggregation_skipped", "aggregation skipped; global model unchanged")
    if global_error is not None:
        span.add_event("fl.global_evaluation_failed", {"error": global_error})
        error = ("global_evaluation_failed", global_error)
    if error is not None:
        span.set_attribute("error.type", error[0])
        span.set_status(Status(StatusCode.ERROR, error[1]))
    record_round_metrics(
        rnd=server_round,
        loss=loss,
        accuracy=accuracy,
        train_clients=train_clients,
        evaluate_clients=evaluate_clients,
        train_ess=train_ess,
        evaluate_ess=evaluate_ess,
    )
    if global_metrics is not None:
        record_global_metrics(rnd=server_round, loss=global_loss, accuracy=global_accuracy)
    span.end()
    # A recording span's own timestamps make the metric exactly its duration. An unsampled
    # span has none, and metrics are not sampled, so fall back to the strategy's clock.
    start, end = getattr(span, "start_time", None), getattr(span, "end_time", None)
    error_type = error[0] if error is not None else None
    if start is not None and end is not None:
        record_round_duration(rnd=server_round, seconds=(end - start) / 1e9, error_type=error_type)
    elif started is not None:
        seconds = time.perf_counter() - started
        record_round_duration(rnd=server_round, seconds=seconds, error_type=error_type)


def outlier_rank(updates: list[np.ndarray], index: int) -> int:
    """Rank of ``updates[index]`` by distance from the coordinate-wise median (1 = farthest)."""
    median = np.median(np.stack(updates), axis=0)
    distances = [float(np.linalg.norm(u - median)) for u in updates]
    return 1 + sum(d > distances[index] for d in distances)


def _flatten(message: Message) -> np.ndarray:
    record = next(iter(message.content.array_records.values()))
    return np.concatenate([a.ravel() for a in record.to_numpy_ndarrays()])


# error.type for a failed client reply: low-cardinality and documented, as semconv asks.
_ERROR_TYPES = {
    ErrorCode.LOAD_CLIENT_APP_EXCEPTION: "client_app_load_error",
    ErrorCode.CLIENT_APP_RAISED_EXCEPTION: "client_app_exception",
    ErrorCode.MESSAGE_UNAVAILABLE: "message_unavailable",
    ErrorCode.REPLY_MESSAGE_UNAVAILABLE: "reply_unavailable",
    ErrorCode.NODE_UNAVAILABLE: "node_unavailable",
    ErrorCode.MOD_FAILED_PRECONDITION: "mod_failed_precondition",
    ErrorCode.INVALID_FAB: "invalid_fab",
    ErrorCode.CLIENT_APP_CRASHED: "client_app_crashed",
}
# The simulation reports a worker's own failure as UNKNOWN, reason "<class 'x.Name'>:<'msg'>".
_WORKER_ERRORS = {
    "OutOfMemoryError": "oom",
    "RayActorError": "worker_died",
    "ActorDiedError": "worker_died",
}
_REASON_CLASS = re.compile(r"<class '(?:[\w.]+\.)?(\w+)'>")
TIMEOUT = "timeout"  # no reply arrived before send_and_receive's timeout


def failure_type(message: Message) -> str:
    """The ``error.type`` of a failed reply; ``_OTHER`` when Flower's code says no more."""
    error = message.error
    if error.code == ErrorCode.UNKNOWN:
        match = _REASON_CLASS.match(error.reason or "")
        return _WORKER_ERRORS.get(match.group(1), "_OTHER") if match else "_OTHER"
    return _ERROR_TYPES.get(error.code, "_OTHER")


def _payload_bytes(message: Message) -> int:
    """Record payload bytes as Flower counts them (``count_bytes``); 0 for an error reply."""
    if not message.has_content():
        return 0
    return sum(record.count_bytes() for record in message.content.values())


def _by_round(records: dict[int, MetricRecord]) -> dict[str, dict[str, Any]]:
    return {str(rnd): dict(rec) for rnd, rec in records.items()}


GlobalEvaluator = Callable[[ArrayRecord], MetricRecord]


def _train_is_weighted_mean(cls: type) -> bool:
    """Whether ``cls`` aggregates training replies with FedAvg's ``num-examples`` mean.

    Kish's ESS describes a weighted mean over the replies it is computed from. The median,
    the trimmed mean and Bulyan do not take that mean; Krum and Multi-Krum take it over
    the replies they select, which this mixin does not see. An ESS over every reply would
    describe neither, so for these rules the train ESS is NaN.
    """
    owner = next(
        c
        for c in cls.__mro__
        if "aggregate_train" in vars(c) and not issubclass(c, ObservableMixin)
    )
    return owner is FedAvg


class ObservableMixin(FedAvg):
    """Emits OTel round spans + FL metrics each round for the strategy it precedes in the MRO.

    Also records, per round, the outlier rank of each reply flagged ``malicious`` (see
    ``outlier_rank``): the bookkeeping behind "does the attacker stand out?". The flag is
    read here only, never by the aggregation rule.

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
        self._round_bytes: dict[int, dict[str, int]] = {}
        self._round_started: dict[int, float] = {}
        self._train_weighted = _train_is_weighted_mean(type(self))
        self._sent: dict[tuple[int, str], list[Message]] = {}
        self.attacker_ranks: dict[int, list[int]] = {}
        self.skipped_rounds: set[int] = set()
        self.no_update_rounds: set[int] = set()
        self.client_failures: dict[int, dict[str, int]] = {}

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
        observed = self._awaiting_global.pop(server_round, None)
        try:
            metrics = self._global_evaluate(arrays)
        except Exception as exc:
            # The round's client metrics are already aggregated; close it before the
            # failure ends the run, so the trace keeps the round and says why it stopped.
            if observed is not None:
                observe_round(**observed, global_error=repr(exc))
            raise
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
        self._round_started[server_round] = time.perf_counter()
        # Both directions from the start, so a round whose replies all fail reads 0.
        self._round_bytes[server_round] = {"server_to_client": 0, "client_to_server": 0}
        config["traceparent"] = traceparent_for(span)
        messages = list(super().configure_train(server_round, arrays, config, grid))
        self._count_bytes(server_round, messages, "train", "server_to_client")
        self._sent[(server_round, "train")] = messages
        return messages

    def configure_evaluate(
        self, server_round: int, arrays: ArrayRecord, config: ConfigRecord, grid: Grid
    ) -> Iterable[Message]:
        span = self._round_spans.get(server_round)
        if span is not None:
            config["traceparent"] = traceparent_for(span)
        messages = list(super().configure_evaluate(server_round, arrays, config, grid))
        self._count_bytes(server_round, messages, "evaluate", "server_to_client")
        self._sent[(server_round, "evaluate")] = messages
        return messages

    def _record_failures(self, server_round: int, replies: list[Message], message_type: str) -> int:
        """Classify failed and missing replies onto the round span; return how many.

        Replies are matched to the messages sent by id: the grid writes each message's id
        into it on push, and a reply the SuperLink makes for an unreachable node carries
        the SuperLink as its source but the original message's id as ``reply_to``.
        """
        span = self._round_spans.get(server_round)
        counts: Counter[str] = Counter()
        sent = self._sent.pop((server_round, message_type), [])
        node_by_id = {m.metadata.message_id: m.metadata.dst_node_id for m in sent}
        matched = all(node_by_id) and len(node_by_id) == len(sent)

        def node_of(reply: Message) -> int:
            node = node_by_id.get(reply.metadata.reply_to_message_id) if matched else None
            return reply.metadata.src_node_id if node is None else node

        def note(error_type: str, attributes: dict[str, Any]) -> None:
            counts[error_type] += 1
            if span is not None:
                span.add_event(
                    "fl.client.failure",
                    {"error.type": error_type, "fl.message.type": message_type, **attributes},
                )

        # Node ids are uint64; as strings they stay exact and always encode over OTLP.
        for reply in replies:
            if reply.has_error():
                note(
                    failure_type(reply),
                    {"fl.error.code": reply.error.code, "fl.node.id": str(node_of(reply))},
                )
        if matched:
            answered = {reply.metadata.reply_to_message_id for reply in replies}
            missing = [node for mid, node in node_by_id.items() if mid not in answered]
        else:  # a grid that assigns no ids: match by node instead
            answered_nodes = {node_of(reply) for reply in replies}
            missing = [m.metadata.dst_node_id for m in sent]
            missing = [node for node in missing if node not in answered_nodes]
        for node_id in missing:
            note(TIMEOUT, {"fl.node.id": str(node_id)})
        round_counts = self.client_failures.setdefault(server_round, {})
        for error_type, count in counts.items():
            record_failures(
                rnd=server_round, message_type=message_type, error_type=error_type, count=count
            )
            round_counts[error_type] = round_counts.get(error_type, 0) + count
        if not round_counts:
            del self.client_failures[server_round]
        return sum(counts.values())

    def _count_bytes(
        self, server_round: int, messages: list[Message], message_type: str, direction: str
    ) -> None:
        totals = self._round_bytes.setdefault(server_round, {})
        for message in messages:
            if message.has_error():
                continue
            nbytes = _payload_bytes(message)
            record_message_size(nbytes=nbytes, message_type=message_type, direction=direction)
            totals[direction] = totals.get(direction, 0) + nbytes

    def aggregate_train(
        self, server_round: int, replies: Iterable[Message]
    ) -> tuple[ArrayRecord | None, MetricRecord | None]:
        replies = list(replies)
        self._count_bytes(server_round, replies, "train", "client_to_server")
        self._round_train_clients[server_round] = sum(1 for m in replies if not m.has_error())
        self._round_failures[server_round] = self._record_failures(server_round, replies, "train")
        self._round_train_ess[server_round] = (
            _reply_ess(replies, self.weighted_by_key) if self._train_weighted else float("nan")
        )
        arrays, metrics = super().aggregate_train(server_round, replies)
        # After the rule, which validates the replies, so bookkeeping cannot abort a round.
        ok = [m for m in replies if not m.has_error()]
        if arrays is None and ok:
            self.skipped_rounds.add(server_round)
        elif arrays is None:
            self.no_update_rounds.add(server_round)
        flagged = [i for i, m in enumerate(ok) if _metric(m, "malicious")]
        if flagged:
            updates = [_flatten(m) for m in ok]
            self.attacker_ranks[server_round] = [outlier_rank(updates, i) for i in flagged]
        return arrays, metrics

    def aggregate_evaluate(
        self, server_round: int, replies: Iterable[Message]
    ) -> MetricRecord | None:
        replies = list(replies)
        self._count_bytes(server_round, replies, "evaluate", "client_to_server")
        eval_errors = sum(1 for m in replies if m.has_error())
        eval_failures = self._record_failures(server_round, replies, "evaluate")
        metrics = super().aggregate_evaluate(server_round, replies)
        observed: dict[str, Any] = {
            "server_round": server_round,
            "metrics": metrics,
            "train_clients": self._round_train_clients.pop(server_round, 0),
            "evaluate_clients": len(replies) - eval_errors,
            "failures": self._round_failures.pop(server_round, 0) + eval_failures,
            "train_ess": self._round_train_ess.pop(server_round, float("nan")),
            "evaluate_ess": _reply_ess(replies, self.weighted_by_key),
            "aggregation_skipped": server_round in self.skipped_rounds,
            "no_client_updates": server_round in self.no_update_rounds,
            "payload_bytes": self._round_bytes.pop(server_round, {}),
            "started": self._round_started.pop(server_round, None),
            "span": self._round_spans.pop(server_round, None),
        }
        if self._global_evaluate is None:
            observe_round(**observed)
        else:
            self._awaiting_global[server_round] = observed
        return metrics


class ObservableFedAvg(ObservableMixin, FedAvg):
    """FedAvg that emits OTel round spans + FL metrics each round."""


_STRATEGIES: dict[str, type[FedAvg]] = {
    "fedavg": FedAvg,
    "krum": Krum,
    "multikrum": MultiKrum,
    "trimmed-mean": FedTrimmedAvg,
    "median": FedMedian,
    "bulyan": Bulyan,
}


def build_strategy(cfg: Any, global_evaluate: GlobalEvaluator | None = None) -> ObservableMixin:
    """The observable strategy named by ``cfg["strategy"]``, configured from ``cfg``."""
    name = str(cfg["strategy"])
    if name not in _STRATEGIES:
        raise ValueError(f"unknown strategy {name!r}; choose from {sorted(_STRATEGIES)}")
    base = _STRATEGIES[name]
    kwargs: dict[str, Any] = {
        "fraction_train": float(cfg["fraction-train"]),
        "fraction_evaluate": float(cfg["fraction-evaluate"]),
        "global_evaluate": global_evaluate,
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


@app.main()
def main(grid: Grid, context: Context) -> None:
    """Federate LoRA adapters with the configured strategy; observe every round over OTLP."""
    # deferred: heavy torch/HF import
    from phalanx.task import (
        default_device,
        get_adapter_state,
        get_model,
        global_eval_fn,
        load_global_test,
        sample_count,
        server_entropy,
        set_adapter_state,
        set_seed,
    )

    cfg: Any = context.run_config  # flwr config values are a broad union; read as Any
    init_telemetry(service_name=str(cfg["otel-service-name"]))
    # The seed fixes the initial adapters, so round 0 is the same in every run of one seed
    # and the scenarios of a sweep pair up.
    set_seed(server_entropy(int(cfg["seed"])))

    # Initial global state = the LoRA adapters only (not the frozen base model).
    model = get_model(
        str(cfg["model-name"]),
        num_labels=int(cfg["num-labels"]),
        target_modules=str(cfg["lora-target-modules"]),
    )
    initial_arrays = ArrayRecord(get_adapter_state(model))

    testloader = load_global_test(
        str(cfg["model-name"]),
        dataset=str(cfg["dataset"]),
        text_column=str(cfg["text-column"]),
        size=int(cfg["global-eval-size"]),
    )
    device = default_device()
    model.to(device)
    flip = (int(cfg["flip-from"]), int(cfg["flip-to"]))

    def global_evaluate(arrays: ArrayRecord) -> MetricRecord:
        set_adapter_state(model, arrays.to_torch_state_dict())
        metrics: Any = global_eval_fn(model, testloader, device, flip)
        return MetricRecord({**metrics, "num-examples": sample_count(testloader)})

    strategy = build_strategy(cfg, global_evaluate)
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
                extra={
                    "attacker_outlier_rank": {
                        str(rnd): r for rnd, r in strategy.attacker_ranks.items()
                    },
                    "aggregation_skipped_rounds": sorted(strategy.skipped_rounds),
                    "client_failures": {
                        str(rnd): counts for rnd, counts in strategy.client_failures.items()
                    },
                },
            )
        )
    finally:
        shutdown_telemetry()  # flush buffered OTLP spans/metrics before exit
