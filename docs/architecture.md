# Architecture

Phalanx is a standard Flower **app-model** application (flwr 1.36 Message API) plus
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

`ObservableFedAvg` subclasses Flower's `FedAvg` and overrides `configure_train` /
`configure_evaluate` (to open the round span and attach its `traceparent`),
`aggregate_train` (to count participating clients) and `aggregate_evaluate` (to read the
aggregated loss/accuracy and call `observe_round`). FedAvg's key-matched aggregation works
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
`fl.accuracy`, `fl.train_clients`, `fl.evaluate_clients`, `fl.train_ess`,
`fl.evaluate_ess`, `fl.failures`) and the matching `fl.round.*` metrics. Train and
evaluate sample their clients independently, so the attributes are named for their phase:
`fl.train_clients` and `fl.train_ess` describe the replies that produced the adapters, `fl.evaluate_clients`
and `fl.evaluate_ess` the replies behind `fl.loss` / `fl.accuracy`.
Client-side, each pass emits an `fl.client.train` or
`fl.client.evaluate` span and `fl.client.examples` / `fl.client.loss` metrics.

The round span's W3C `traceparent` rides the broadcast `ConfigRecord`, so each client
span, though it runs in a separate Ray process, is a child of its round span: one trace
per round.
