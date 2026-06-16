<div align="center">

<img src="docs/assets/phalanx-hero.png" alt="Phalanx" width="600">

# Phalanx

### Federated learning on the latest Flower, with OpenTelemetry-native observability

*A research testbed built on the current Flower (`flwr`) app-model: a federated LoRA fine-tune of a tiny BERT over non-IID data, aggregating only the adapters, with every round and client emitted as OpenTelemetry traces and metrics.*

[![CI Pipeline](https://github.com/ajbarea/phalanx-fl/actions/workflows/ci.yml/badge.svg)](https://github.com/ajbarea/phalanx-fl/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ajbarea/phalanx-fl/graph/badge.svg?token=NTyqWs5w9l)](https://codecov.io/gh/ajbarea/phalanx-fl)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flower](https://img.shields.io/badge/Flower-v1.31+-00C896?style=flat-square)](https://flower.ai)
[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-traces_%2B_metrics-425CC7?style=flat-square&logo=opentelemetry&logoColor=white)](https://opentelemetry.io)
[![uv](https://img.shields.io/badge/uv-package_manager-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)

</div>

---

## What is this?

Phalanx is a federated-learning research testbed that rides the **latest** Flower release: the `flwr` Message API, `flwr-datasets`, HuggingFace Transformers, and PEFT/LoRA. Its distinguishing feature is **OpenTelemetry-native observability**. The server emits a span and FL metrics for every round; each client emits a span for its local train and evaluate passes. You can watch a federated run in any OTLP backend (Jaeger, Grafana Tempo, an OpenTelemetry Collector), which stock Flower does not provide out of the box.

The default showcase is a federated **LoRA** fine-tune of Google's tiny BERT on IMDB sentiment, partitioned non-IID with a Dirichlet partitioner. Only the LoRA adapters and the classification head are federated; the frozen backbone stays on each client, so the payload on the wire is small.

```text
$ make trace                      # local simulation, traces printed to the console

[ROUND 1/3]
aggregate_train: Received 2 results and 0 failures
aggregate_evaluate: Received 2 results and 0 failures
  -> Aggregated MetricRecord: {'loss': 0.67, 'accuracy': 0.62}
# plus an `fl.round` OTel span (fl.round, fl.loss, fl.accuracy, fl.clients) per round,
# and an `fl.client.{train,evaluate}` span per participating client.
```

---

## Quick start

```bash
git clone https://github.com/ajbarea/phalanx-fl.git
cd phalanx-fl

make sync        # install deps (CPU torch + HF stack + dev tools)
make smoke       # fast 2-round federated simulation
make trace       # run with OTel traces printed to the console (no collector needed)
```

`make run` runs the full simulation, `make test` runs the suite, `make lint` runs ruff + ty. Run `make` with no target for the full list.

### Federation setup (flwr 1.31)

flwr 1.31 keeps simulation and federation settings in `~/.flwr/config.toml`, not in `pyproject.toml`. The `[tool.flwr.federations.local-simulation]` block shipped in `pyproject.toml` is migrated there automatically on your first `flwr run` (flwr then comments the local copy out; see [flwr#6824](https://github.com/flwrlabs/flower/issues/6824)). Override the federation size per run without editing any file:

```bash
uv run flwr run . local-simulation --federation-config 'options.num-supernodes=10'
```

### Observability

By default telemetry is recorded but not exported (no connection noise). Point it at a collector to export traces and metrics over OTLP:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
make run
```

Or print spans to the terminal with `OTEL_TRACES_EXPORTER=console` (this is what `make trace` does).

---

## Architecture

A standard Flower app-model layout:

| Module | Role |
|--------|------|
| `phalanx/task.py` | Model (HF transformer + PEFT/LoRA), data (`flwr-datasets`, IID or Dirichlet non-IID), train/eval, adapter-state helpers |
| `phalanx/client_app.py` | `ClientApp`: loads broadcast adapters, trains locally, replies with adapters only; wraps each pass in a client span |
| `phalanx/server_app.py` | `ServerApp` + `ObservableFedAvg`: FedAvg over adapters; emits an `fl.round` span + aggregated loss/accuracy/participation metrics each round |
| `phalanx/telemetry.py` | OpenTelemetry layer: tracer/meter providers, round/client spans, FL metrics; OTLP / console / in-memory exporters |

**Stack:** [Flower](https://flower.ai) (Message API + Simulation Engine) · [PyTorch](https://pytorch.org) + [HuggingFace Transformers](https://huggingface.co/docs/transformers) + [PEFT/LoRA](https://huggingface.co/docs/peft) · [flwr-datasets](https://flower.ai/docs/datasets/) · [OpenTelemetry](https://opentelemetry.io) · [uv](https://docs.astral.sh/uv/) + [Ruff](https://docs.astral.sh/ruff/) + [ty](https://docs.astral.sh/ty/)

---

## Configuration

Run config lives in `pyproject.toml` under `[tool.flwr.app.config]`, overridable per run with `--run-config`:

| Key | Default | Meaning |
|-----|---------|---------|
| `num-server-rounds` | `3` | number of FL rounds |
| `model-name` | `google/bert_uncased_L-2_H-128_A-2` | HF model (tiny BERT) |
| `dataset` | `stanfordnlp/imdb` | HF dataset |
| `num-labels` | `2` | classification labels |
| `partitioner` | `dirichlet` | `dirichlet` (non-IID) or `iid` |
| `dirichlet-alpha` | `0.5` | lower means more label skew |
| `local-epochs` | `1` | local epochs per round |
| `fraction-train` / `fraction-evaluate` | `0.1` | client sampling fractions |
| `otel-service-name` | `phalanx-fl` | OTel `service.name` resource attribute |

```bash
uv run flwr run . local-simulation --run-config 'num-server-rounds=5 partitioner=iid'
```

---

## Documentation

Full docs at **[ajbarea.github.io/phalanx-fl](https://ajbarea.github.io/phalanx-fl/)**, built with [Zensical](https://zensical.dev).

---

## Why "Phalanx"

Greek φάλαγξ: the infantry formation where many soldiers advance as one disciplined line, each shield interlocked with the next. That is the shape of federated learning here. Many clients train in step and their updates aggregate into a single model that moves as one. The observability layer is the vantage point above the formation, where every unit and every round is in view.

---

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand-white.png">
  <img src="docs/assets/brand.png" alt="" height="16" />
</picture>&nbsp;&nbsp;2026 <a href="https://ajbarea.github.io/">AJ Barea</a>

</div>
