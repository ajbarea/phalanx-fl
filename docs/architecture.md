# Architecture

Phalanx is a standard Flower **app-model** application (flwr 1.31 Message API) plus
an OpenTelemetry layer. Four modules, no framework of our own:

| Module | Role |
|--------|------|
| `phalanx/task.py` | Model (HF transformer + PEFT/LoRA), data (`flwr-datasets`, IID or Dirichlet non-IID), `train_fn`/`test_fn`, and adapter-state helpers. |
| `phalanx/client_app.py` | `ClientApp` with `@app.train` / `@app.evaluate`. Loads the broadcast adapters into a frozen-backbone LoRA model, trains/evaluates on its partition, replies with adapters only. Wraps each pass in a client span. |
| `phalanx/server_app.py` | `ServerApp` with `@app.main`, plus `ObservableFedAvg`. Builds the initial adapter state, runs `strategy.start(...)`, and emits per-round telemetry. |
| `phalanx/telemetry.py` | OpenTelemetry tracer/meter providers, round/client span context managers, and FL metric instruments. Exporters are pluggable: OTLP, console, or in-memory (for tests). |

## One federated round

`strategy.start()` drives this loop for `num-server-rounds`:

```
ServerApp.main
  └─ ObservableFedAvg.start(initial_arrays = adapter state)
       for each round:
         configure_train   → broadcast adapters to sampled clients
         ClientApp.train    → set adapters, train locally, return adapter delta   [fl.client.train span]
         aggregate_train    → FedAvg over the returned adapters
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

`ObservableFedAvg` subclasses Flower's `FedAvg` and overrides `aggregate_train`
(to count participating clients) and `aggregate_evaluate` (to read the aggregated
loss/accuracy and call `observe_round`). FedAvg's key-matched aggregation works
because `get_adapter_state` returns a stable set of keys across the server and all
clients.

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
