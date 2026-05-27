<div align="center">

<img src="docs/assets/phalanx-hero.png" alt="Phalanx" width="600">

# Phalanx

### Federated Learning Execution & Research Framework

*Configure, execute, and compare federated learning strategies with plug-and-play aggregation, Byzantine fault tolerance, and adversarial attack simulation.*

[![CI Pipeline](https://github.com/ajbarea/phalanx-fl/actions/workflows/ci.yml/badge.svg)](https://github.com/ajbarea/phalanx-fl/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ajbarea/phalanx-fl/graph/badge.svg?token=NTyqWs5w9l)](https://codecov.io/gh/ajbarea/phalanx-fl)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flower](https://img.shields.io/badge/Flower-v1.26.1-00C896?style=flat-square)](https://flower.ai)
[![uv](https://img.shields.io/badge/uv-package_manager-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)
[![Docs](https://img.shields.io/badge/Docs-Zensical-blue?style=flat-square)](https://ajbarea.github.io/phalanx-fl/)

</div>

---

## What is this?

Phalanx is a full-stack platform for running federated learning simulations with configurable aggregation strategies, adversarial attacks, and comprehensive metrics collection. Define experiments in JSON, execute them with one command, and compare results across strategies.

```bash
$ uv run intellifl-dev sim

Running: femnist_krum_vs_labelflip20.json
  Strategy 1/2: krum (10 clients, 3 malicious)
    Round  1/20 — loss: 2.31, accuracy: 0.12
    Round 20/20 — loss: 0.42, accuracy: 0.91
  Strategy 2/2: bulyan (10 clients, 3 malicious)
    ...
  Plots saved to out/20260407_experiment/
```

---

## Quick Start

### Prerequisites

- [uv](https://docs.astral.sh/uv/) 0.5.3+
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for full-stack services)

### Get running

```bash
git clone https://github.com/ajbarea/phalanx-fl.git
cd phalanx-fl

uv sync --locked              # Install all dependencies
uv run intellifl-dev sim      # Run default simulation
uv run intellifl-dev help     # See all commands
```

### Full stack (API + frontend + Redis + Celery)

```bash
cp .env.example .env          # Create environment config
uv run intellifl-dev dev      # Start all services with hot reload
```

| Service | URL |
|---------|-----|
| Frontend UI | `http://localhost:5173` |
| Backend API | `http://localhost:8000` |
| API Docs (Swagger) | `http://localhost:8000/docs` |

See the [Getting Started](https://ajbarea.github.io/phalanx-fl/getting-started/) guide for production deployment, GPU setup, and troubleshooting.

---

## What's included

| | |
|---|---|
| **9 Aggregation Strategies** | FedAvg, Krum, Multi-Krum, Bulyan, RFA, Trimmed Mean, PID, Trust, ArKrum |
| **11 Attack Types** | Label flipping, backdoor triggers, model poisoning, gradient scaling, Byzantine perturbation, and more |
| **20+ Datasets** | FEMNIST, CIFAR-100, 11 MedMNIST variants, HuggingFace text datasets |

Full details: [Strategies](https://ajbarea.github.io/phalanx-fl/strategies/) | [Attacks](https://ajbarea.github.io/phalanx-fl/attacks/) | [Datasets](https://ajbarea.github.io/phalanx-fl/datasets/)

---

## Configuration

Experiments are defined in JSON with `shared_settings` + a `simulation_strategies` array:

```json
{
  "shared_settings": {
    "num_of_rounds": 20,
    "num_of_clients": 10,
    "dataset_keyword": "femnist_iid",
    "training_device": "cpu"
  },
  "simulation_strategies": [
    {
      "aggregation_strategy_keyword": "krum",
      "attack_schedule": [
        {
          "start_round": 1, "end_round": 20,
          "attack_type": "label_flipping",
          "selection_strategy": "specific",
          "malicious_client_ids": [0, 1, 2]
        }
      ]
    },
    {
      "aggregation_strategy_keyword": "bulyan"
    }
  ]
}
```

See the [Configuration Reference](https://ajbarea.github.io/phalanx-fl/configuration/) for all parameters.

---

## Development

```bash
uv run intellifl-dev help       # All commands
uv run intellifl-dev lint       # Ruff + ty
uv run intellifl-dev test       # Full test suite (unit + integration + perf)
uv run intellifl-dev audit      # Security vulnerability scan
uv run intellifl-dev baselines  # Record smoke test baselines
```

See the [CLI Reference](https://ajbarea.github.io/phalanx-fl/cli/) for the complete command list.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Frontend (React + Vite)                        │
│  New Simulation → Details → Results             │
└──────────────────┬──────────────────────────────┘
                   │ REST + SSE
┌──────────────────▼──────────────────────────────┐
│  FastAPI                                        │
│  /api/simulations  /api/terminal  /api/devices  │
└──────────────────┬──────────────────────────────┘
                   │ Celery + Redis
┌──────────────────▼──────────────────────────────┐
│  Celery Worker                                  │
│  SimulationRunner → FederatedSimulation          │
│    ├── ConfigLoader + Validator                  │
│    ├── DatasetHandler + FederatedDatasetLoader   │
│    ├── Strategy (Krum/Bulyan/PID/Trust/RFA/...)  │
│    ├── FlowerClient (CNN or Transformer+LoRA)    │
│    ├── StatusTracker (SSE ← status.json)         │
│    └── PlotHandler + CSVExport                   │
└─────────────────────────────────────────────────┘
```

**Stack:** [Flower](https://flower.ai) + [Ray](https://ray.io) | [PyTorch](https://pytorch.org) + [HuggingFace](https://huggingface.co/docs/transformers) + [PEFT/LoRA](https://huggingface.co/docs/peft) | [FastAPI](https://fastapi.tiangolo.com) + [Celery](https://docs.celeryq.dev) + Redis | React + Vite | [uv](https://docs.astral.sh/uv/) | [Ruff](https://docs.astral.sh/ruff/) + [ty](https://docs.astral.sh/ty/)

---

## Documentation

Full docs at **[ajbarea.github.io/phalanx-fl](https://ajbarea.github.io/phalanx-fl/)**, built with [Zensical](https://zensical.dev).

| Page | Content |
|------|---------|
| [Getting Started](https://ajbarea.github.io/phalanx-fl/getting-started/) | Installation, first simulation, Docker + local setup |
| [CLI Reference](https://ajbarea.github.io/phalanx-fl/cli/) | All developer commands |
| [Configuration](https://ajbarea.github.io/phalanx-fl/configuration/) | Full parameter reference |
| [Datasets](https://ajbarea.github.io/phalanx-fl/datasets/) | Supported datasets and partitioning |
| [Strategies](https://ajbarea.github.io/phalanx-fl/strategies/) | Aggregation algorithm details |
| [Attacks](https://ajbarea.github.io/phalanx-fl/attacks/) | Attack types and scheduling |
| [Architecture](https://ajbarea.github.io/phalanx-fl/architecture/) | System design |
| [API Reference](https://ajbarea.github.io/phalanx-fl/api/) | REST endpoints |

---

## Coverage

<div align="center">

[![codecov sunburst](https://codecov.io/gh/ajbarea/phalanx-fl/graphs/sunburst.svg?token=NTyqWs5w9l)](https://app.codecov.io/gh/ajbarea/phalanx-fl)

</div>

## Why "phalanx"

Greek φάλαγξ: the infantry line of interlocked shields, where each guards the man beside him and no single break undoes the wall. That's the wager of robust federated learning — strength in many clients, the line holding even when some shields turn (Byzantine faults, poisoned updates).

---

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand-white.png">
  <img src="docs/assets/brand.png" alt="" height="16" />
</picture>&nbsp;&nbsp;2026 <a href="https://ajbarea.github.io/">AJ Barea</a>

</div>
