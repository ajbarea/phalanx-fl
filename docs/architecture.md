# Architecture

Phalanx is a standard Flower **app-model** application (flwr 1.36 Message API) plus
an OpenTelemetry layer. Four modules, no framework of our own:

| Module | Role |
|--------|------|
| `phalanx/task.py` | Model (HF transformer + PEFT/LoRA), data (`flwr-datasets`, IID or Dirichlet non-IID), label-flip poisoning, `train_fn`/`test_fn`/`heldout_fn`, and adapter-state helpers. |
| `phalanx/client_app.py` | `ClientApp` with `@app.train` / `@app.evaluate`. Loads the broadcast adapters into a frozen-backbone LoRA model, trains/evaluates on its partition, replies with adapters only. Partitions in `malicious-partitions` flip their training labels and may scale their update by `boost`. Wraps each pass in a client span. |
| `phalanx/server_app.py` | `ServerApp` with `@app.main`, plus `ObservableMixin` and `build_strategy`. Builds the initial adapter state, runs `strategy.start(...)` with the configured aggregation rule, emits per-round telemetry, and scores a held-out split when `heldout-split` is set. |
| `phalanx/telemetry.py` | OpenTelemetry tracer/meter providers, round/client span context managers, and FL metric instruments. Exporters are pluggable: OTLP, console, or in-memory (for tests). |

## One federated round

`strategy.start()` drives this loop for `num-server-rounds`:

```
ServerApp.main
  └─ build_strategy(cfg).start(initial_arrays = adapter state, evaluate_fn = held-out scorer)
       for each round:
         configure_train   → broadcast adapters to sampled clients
         ClientApp.train    → set adapters, train locally, return adapter delta   [fl.client.train span]
         aggregate_train    → the configured rule over the returned adapters
         configure_evaluate → broadcast updated adapters
         ClientApp.evaluate → evaluate locally, return loss/accuracy              [fl.client.evaluate span]
         aggregate_evaluate → FedAvg over metrics  →  observe_round(...)          [fl.round span + metrics]
```

## Adapter-only federation

The model is a HuggingFace sequence-classification transformer wrapped with a PEFT
`LoraConfig`. Only the LoRA adapters and the newly-initialised classification head
(PEFT `modules_to_save`) are trainable, and only those tensors are federated
(`get_adapter_state` / `set_adapter_state`). The frozen backbone never leaves a
client, so each `ArrayRecord` on the wire is small (tens of KB, not the full model).

`ObservableMixin` sits in front of any Flower strategy in the MRO and overrides
`aggregate_train` (to count participating clients) and `aggregate_evaluate` (to read
the aggregated loss/accuracy and call `observe_round`). `build_strategy` pairs it with
the rule named by `strategy`: `FedAvg` (as `ObservableFedAvg`), `Krum`, `MultiKrum`,
`FedTrimmedAvg`, `FedMedian` or `Bulyan`. Key-matched aggregation works because
`get_adapter_state` returns a stable set of keys across the server and all clients.

## Poisoning and robustness

A client listed in `malicious-partitions` relabels its `flip-from` training examples
as `flip-to` from `attack-start-round` on, and may scale its update away from the
global model by `boost` (`g + boost * (l - g)`). Its local test split stays clean.
Each train reply carries a `malicious` flag that only `ObservableMixin`'s bookkeeping
reads: per round it records the attacker's outlier rank, its distance from the
coordinate-wise median of all updates (1 = farthest). With `heldout-split` set, the
server scores the global adapters every round on that clean split for loss, accuracy
and attack success rate (the share of true `flip-from` examples predicted `flip-to`).
All three land in the run manifest beside the client-side metrics.

## The OpenTelemetry layer

`telemetry.py` keeps its tracer/meter providers module-local (off the OTel globals)
so tests can re-initialise between cases. `init_telemetry` chooses an exporter:

- an injected in-memory exporter (unit tests),
- a console exporter when `OTEL_TRACES_EXPORTER=console`,
- an OTLP exporter when `OTEL_EXPORTER_OTLP_ENDPOINT` is set,
- otherwise telemetry is recorded but not exported.

Server-side, each round emits an `fl.round` span (`fl.round`, `fl.loss`,
`fl.accuracy`, `fl.clients`) and the metrics `fl.round.loss` / `fl.round.accuracy` /
`fl.round.clients`. Client-side, each pass emits an `fl.client.train` or
`fl.client.evaluate` span and `fl.client.examples` / `fl.client.loss` metrics.

Because the simulation runs clients in separate Ray processes, client spans are
independent traces in v1. Linking them as children of the server's round span via
`Message.metadata` trace-context propagation is the v2 direction (see `ROADMAP.md`).
