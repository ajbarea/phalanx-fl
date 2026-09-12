# Getting Started

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Python 3.12 or 3.13

No GPU is required; the default stack installs CPU-only PyTorch.

## Install

```bash
git clone https://github.com/ajbarea/phalanx-fl.git
cd phalanx-fl
make sync        # uv sync --extra hf --extra torch (CPU torch + HF stack + dev tools)
```

## Run a federated simulation

```bash
make smoke       # fast 2-round run (sanity check)
make run         # full run (uses num-server-rounds from pyproject)
make trace       # run with OpenTelemetry traces printed to the console
```

The first run downloads the model (`google/bert_uncased_L-2_H-128_A-2`, ~18 MB) and
the IMDB dataset, then trains on CPU. Subsequent runs reuse the cache.

## Federation setup (flwr 1.36)

Federation settings live outside `pyproject.toml`: the SuperLink connection belongs
to the Flower config (`~/.flwr/config.toml`, or `$FLWR_HOME`), and Simulation Runtime
settings are SuperLink state. A `[tool.flwr.federations]` block left in
`pyproject.toml` is migrated out on the first `flwr run`, rewriting the file in place
([flwr#6824](https://github.com/flwrlabs/flower/issues/6824)).

The Makefile passes the federation per run instead, so a clone reproduces the default
five-node federation with no bootstrap step. Override it for a single run:

```bash
uv run flwr run . --federation-config 'num-supernodes=10 client-resources-num-cpus=2'
```

Override app run-config (rounds, partitioner, model) similarly:

```bash
uv run flwr run . --run-config 'num-server-rounds=5 partitioner=iid'
```

## Observability

Telemetry is recorded by default but **not exported** (no collector required, no
connection noise). To export traces + metrics over OTLP to a collector such as
Jaeger or Grafana Tempo:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
make run
```

To print spans to the terminal instead (no backend needed):

```bash
OTEL_TRACES_EXPORTER=console make run    # this is what `make trace` does
```

Each round produces an `fl.round` span (attributes: `fl.round`, `fl.loss`,
`fl.accuracy`, `fl.clients`) and FL metrics (`fl.round.loss`, `fl.round.accuracy`,
`fl.round.clients`); each participating client produces an `fl.client.train` or
`fl.client.evaluate` span and `fl.client.*` metrics.

## Develop

```bash
make lint        # ruff format --check + ruff check + ty
make test        # pytest
make audit       # pip-audit
```
