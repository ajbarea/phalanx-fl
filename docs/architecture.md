# Architecture

Phalanx is a standard Flower **app-model** application (flwr 1.39 Message API) plus
an OpenTelemetry layer. Four modules, no framework of our own:

| Module | Role |
|--------|------|
| `phalanx/task.py` | Model (HF transformer + PEFT/LoRA), data (`flwr-datasets`, IID or Dirichlet non-IID), label-flip poisoning, `train_fn`/`test_fn`/`global_eval_fn`, and adapter-state helpers. |
| `phalanx/client_app.py` | `ClientApp` with `@app.train` / `@app.evaluate`. Loads the broadcast adapters into a frozen-backbone LoRA model, trains/evaluates on its partition, replies with adapters only. Partitions in `malicious-partitions` flip their training labels and may scale their update by `boost`. Wraps each pass in a client span. |
| `phalanx/server_app.py` | `ServerApp` with `@app.main`, plus `ObservableMixin` and `build_strategy`. Builds the initial adapter state, runs `strategy.start(...)` with the configured aggregation rule, emits per-round telemetry, and scores the aggregated adapters on the global test set each round, attack success included. |
| `phalanx/telemetry.py` | OpenTelemetry tracer/meter providers, round/client span context managers, and FL metric instruments. Exporters are pluggable: OTLP, console, or in-memory (for tests). |

## One federated round

`strategy.start()` drives this loop for `num-server-rounds`:

```
ServerApp.main
  └─ build_strategy(cfg, global_evaluate).start(initial_arrays = adapter state)
       global_evaluate(initial adapters)  → round 0 on the global test set       [fl.round.global_* metrics]
       for each round:
         configure_train   → broadcast adapters to sampled clients
         ClientApp.train    → set adapters, train locally, return adapter delta   [fl.client.train span]
         aggregate_train    → the configured rule over the returned adapters
         configure_evaluate → broadcast updated adapters
         ClientApp.evaluate → evaluate locally, return loss/accuracy              [fl.client.evaluate span]
         aggregate_evaluate → FedAvg over metrics
         global_evaluate    → aggregated adapters on the global test set  →  observe_round(...)
                                                                                  [fl.round span + metrics]
```

Two accuracies per round, deliberately. The clients' figure (`fl.accuracy`) is a
`num-examples`-weighted mean over holdouts carved from each client's own partition, so
under Dirichlet it inherits the partition's label skew. The global figure
(`fl.global_accuracy`) scores the aggregated adapters server-side on the dataset's
`test` split, which the partitioner never sees, so it compares across partitioners and
alphas. The gap between them is the skew.

## Adapter-only federation

The model is a HuggingFace sequence-classification transformer wrapped with a PEFT
`LoraConfig`. Only the LoRA adapters and the newly-initialised classification head
(PEFT `modules_to_save`) are trainable, and only those tensors are federated
(`get_adapter_state` / `set_adapter_state`). The frozen backbone never leaves a
client, so each `ArrayRecord` on the wire is small (tens of KB, not the full model).

`ObservableMixin` sits in front of any of Flower's FedAvg-family strategies in the MRO
and overrides `configure_train` / `configure_evaluate` (to open the round span and
attach its `traceparent`), `aggregate_train` (to count participating clients),
`aggregate_evaluate` (to read the aggregated loss/accuracy) and `start` (to pass its
global evaluation as flwr's `evaluate_fn`, which runs after `aggregate_evaluate` and
closes the round with `observe_round`). `build_strategy` pairs it with the rule named
by `strategy`: `FedAvg` (as `ObservableFedAvg`), `Krum`, `MultiKrum`, `FedTrimmedAvg`,
`FedMedian` or `Bulyan`. The median, trimmed mean and Bulyan take no `num-examples`
mean, and Krum and Multi-Krum take it only over the replies they select, so their
`fl.train_ess` is NaN; evaluation is still FedAvg's weighted mean, so `fl.evaluate_ess`
holds for every rule. A rule that declines to aggregate (Bulyan below `4f + 3` replies)
leaves the global model unchanged; the round span then carries an `fl.aggregation_skipped`
event and an error status, and the manifest lists the round in `aggregation_skipped_rounds`. Key-matched aggregation works because
`get_adapter_state` returns a stable set of keys across the server and all clients.

## Poisoning and robustness

A client listed in `malicious-partitions` relabels its `flip-from` training examples
as `flip-to` from `attack-start-round` on, and may scale its update away from the
global model by `boost` (`g + boost * (l - g)`). Its local test split stays clean.
Each train reply carries a `malicious` flag that only `ObservableMixin`'s bookkeeping
reads: per round it records the attacker's outlier rank, its distance from the
coordinate-wise median of all updates (1 = farthest). The global evaluation also
reports the attack success rate: the share of true `flip-from` test examples predicted
`flip-to`. It and the outlier ranks land in the run manifest beside the client-side
metrics.

## The OpenTelemetry layer

`telemetry.py` keeps its tracer/meter providers module-local (off the OTel globals)
so tests can re-initialise between cases. `init_telemetry` chooses an exporter:

- an injected in-memory exporter (unit tests),
- a console exporter when `OTEL_TRACES_EXPORTER=console`,
- an OTLP exporter when `OTEL_EXPORTER_OTLP_ENDPOINT` is set,
- otherwise telemetry is recorded but not exported.

Server-side, each round emits an `fl.round` span (`fl.round`, `fl.loss`,
`fl.accuracy`, `fl.global_loss`, `fl.global_accuracy`, `fl.train_clients`,
`fl.evaluate_clients`, `fl.train_ess`, `fl.evaluate_ess`, `fl.failures`) and the matching
`fl.round.*` metrics; `fl.round.global_*` also has a round 0, the initial adapters. Train
and evaluate sample their clients independently, so the attributes are named for their
phase: `fl.train_clients` and `fl.train_ess` describe the replies that produced the
adapters, `fl.evaluate_clients`
and `fl.evaluate_ess` the replies behind `fl.loss` / `fl.accuracy`.
Client-side, each pass emits an `fl.client.train` or
`fl.client.evaluate` span and `fl.client.examples` / `fl.client.loss` metrics.

Each round also records `fl.round.duration` (histogram, `s`), read from the round span's own
start and end, and each message's size as `fl.message.size` (histogram, `By`) with
`fl.message.type` (`train` | `evaluate`) and `fl.message.direction` (`server_to_client` |
`client_to_server`). The size is Flower's `count_bytes` over the message's records, keys
and array serialization metadata included: payload bytes, not network bytes, since a
simulation has no wire. Error replies carry no payload and are not counted. The round span
holds the round's totals as `fl.payload_bytes.server_to_client` / `.client_to_server`.
Instruments declare semconv units: `1` for loss and accuracy, `{client}` for client counts
and ESS.

The round span's W3C `traceparent` rides the broadcast `ConfigRecord`, so each client
span, though it runs in a separate Ray process, is a child of its round span: one trace
per round.
