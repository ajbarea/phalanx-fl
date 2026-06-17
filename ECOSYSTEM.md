# phalanx-fl — Dependency Rationale

Why each dependency exists and when to reconsider it. `pyproject.toml` is the
source of truth for *what* and *which version*; this file is the *why*.

Phalanx's organizing principle: **ride the latest Flower release always.** Adapt
the app to `flwr`, never pin `flwr` back. The dependency choices below follow from
that, plus the OpenTelemetry observability layer that is the project's differentiator.

---

## Core runtime

- **`flwr[simulation]>=1.31`** — Flower, on the current **Message API** app-model
  (`ServerApp`/`@app.main`, `ClientApp`/`@app.train`, `ArrayRecord`/`Message`/`RecordDict`,
  `strategy.start`). The `[simulation]` extra pulls the Ray-backed Simulation Engine
  that `flwr run . local-simulation` drives. Floor is `>=1.31`; bump it forward as
  Flower releases, never back.
- **`flwr-datasets>=0.6`** — federated dataset partitioning (`FederatedDataset`,
  `DirichletPartitioner`, `IidPartitioner`). This is what makes the showcase non-IID.
  Note: `flwr-datasets` 0.6.0 caps `datasets<5.0`, which is why the `hf` extra pins
  `datasets>=2.15,<5` (see below). Bump alongside `flwr`.
- **`opentelemetry-sdk` + `opentelemetry-exporter-otlp` (>=1.30)** — the observability
  layer (`phalanx/telemetry.py`). The SDK provides the tracer/meter providers and the
  in-memory/console exporters; the OTLP exporter ships round/client spans + FL metrics
  to a collector (Jaeger, Tempo, an OTel Collector). This is the part stock Flower does
  not provide, so it is a first-class runtime dep, not optional.
- **`numpy>=2`** — array interchange; transitively required across the stack, pinned
  to the 2.x line for consistency with torch 2.12 / transformers 5.

## `hf` extra — model + data

- **`transformers>=5.10`** — HuggingFace Transformers, on the current 5.x line.
  Caveat baked into the model choice: transformers 5 is **strict about `model_type`**
  in a model's `config.json`. The common `prajjwal1/bert-tiny` re-upload omits it and
  fails to load on 5.x; the showcase therefore uses **`google/bert_uncased_L-2_H-128_A-2`**
  (Google's original tiny BERT, same size, complete config).
- **`peft>=0.10`** — LoRA adapters. Only the adapters (plus the newly-initialised
  classification head, via PEFT `modules_to_save`) are federated; the frozen backbone
  stays on each client. Keeps the payload on the wire small.
- **`datasets>=2.15,<5`** — HF datasets. The `<5` ceiling is **not** ours; it is forced
  by `flwr-datasets` 0.6.0. transformers 5 only needs `>=2.15`, so the window is
  consistent. Revisit the ceiling when `flwr-datasets` lifts its cap.
- **`evaluate>=0.4`** — the accuracy metric in `test_fn`.
- **`scikit-learn>=1.3`** — required by `evaluate`'s accuracy metric backend.

## `torch` extra — training, CPU by default

- **`torch>=2.12` + `torchvision>=0.15`** — the training path. Routed to the
  `pytorch-cpu` index via `[tool.uv.sources]` so CPU dev and CI do not pull ~2 GB of
  CUDA wheels. GPU is opt-in: switch the index to `cu128` and re-sync (commented in
  `pyproject.toml`). Mirrors the velocity-fl convention for portfolio coherence.

## Dev group

- **`pytest` + `pytest-asyncio` + `pytest-cov` + `hypothesis`** — test stack.
- **`pip-audit`** — supply-chain advisory scan (`make audit`, CI audit job).
- **`ruff` + `ty`** — lint/format + type-check (`make lint`). Floors track the sister repos.
- **`zensical`** — the documentation site generator (`make docs`).
