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

## Federation setup (flwr 1.31)

flwr 1.31 stores simulation/federation settings in `~/.flwr/config.toml`, not in
`pyproject.toml`. The `[tool.flwr.federations.local-simulation]` block shipped in
`pyproject.toml` is migrated there automatically on your **first** `flwr run` (flwr
then comments the local copy out; see [flwr#6824](https://github.com/flwrlabs/flower/issues/6824)).
You normally do not need to touch this.

Override the federation size for a single run without editing any file:

```bash
uv run flwr run . local-simulation --federation-config 'options.num-supernodes=10'
```

Override app run-config (rounds, partitioner, model) similarly:

```bash
uv run flwr run . local-simulation --run-config 'num-server-rounds=5 partitioner=iid'
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
