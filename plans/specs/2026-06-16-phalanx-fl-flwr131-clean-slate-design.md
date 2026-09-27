# phalanx-fl v2 — Clean-Slate Design (flwr 1.31 app-model)

**Date:** 2026-06-16 · **Status:** Accepted (autonomous design; AJ greenlit the recs — skim and redirect if anything's off)

## Purpose

A fresh federated-learning research app rebuilt on the **current flwr app-model**, replacing the retrofitted ("ghetto-rigged") phalanx that chased each flwr release via adapters. Goals, in order:

1. **Research testbed** — a config-driven harness for AJ's FL experiments (swap model / dataset / partitioner / strategy without touching app code).
2. **Showcase** — demonstrably "FL done right on latest flwr," a counterpoint to the team's flwr-1.9.0 InteFL; portfolio-grade.

**Principle:** ride the latest flwr always; adapt the app to flwr, never pin flwr back. No published research depends on old phalanx, so switching cost is near zero.

## Decisions

- **Repo:** clean-slate the existing `phalanx-fl` repo — keep the brand + the already-wired sister CI / Dependabot / auto-merge / tooling; replace the app code.
- **Stack (all latest, designed in):** flwr 1.31 app-model (`flwr run`, ServerApp / ClientApp / task.py, Simulation Engine); flwr-datasets (`FederatedDataset` + partitioners); HuggingFace transformers + datasets; PEFT/LoRA for the showcase; OpenTelemetry (traces + metrics); uv / ruff / ty + sister CI.
- **Default scenario:** federated **LoRA fine-tune** of a small HF transformer (BERT-tiny to start) on a text-classification HF dataset (IMDB), partitioned **non-IID** via flwr-datasets — mirrors the flwr `quickstart-huggingface` + `FlowerTune LLM` (flwr 1.31) patterns, so it's current and well-trodden. Only LoRA adapters are aggregated (tiny, privacy-preserving).
- **v1 scope (YAGNI):** one scenario + IID + one non-IID partitioner (Dirichlet) + FedAvg. Grow strategies / datasets / partitioners later.

## Architecture (flwr app-model)

- `phalanx/task.py` — model (HF + PEFT/LoRA), train/eval loops, data via flwr-datasets `FederatedDataset`.
- `phalanx/client_app.py` — `ClientApp`: local LoRA train/eval on its partition; returns adapter params + metrics.
- `phalanx/server_app.py` — `ServerApp`: Strategy (FedAvg v1), adapter aggregation, global eval, round orchestration.
- `pyproject.toml [tool.flwr]` — run-config (rounds, partitions, model id, dataset id, partitioner, strategy params). Same code runs simulation and deployment.
- `phalanx/telemetry.py` — OTel setup (Tracer/Meter providers, OTLP exporter, `Resource(service.name=phalanx-fl)`, BatchSpanProcessor).

## Observability (the differentiator)

OTel-native FL instrumentation — there is no out-of-box flwr↔OTel integration, so this is novel and doubles as a research instrument:

- **Traces:** one span per federation round (server) wrapping child spans per participating client (local train/eval) — round→client causality.
- **Metrics:** per-round global loss/accuracy; per-client local loss, sample count, participation; communication volume (LoRA adapter bytes); round wall-time.
- **Export:** OTLP → Collector → Jaeger (traces) + Prometheus/Grafana (metrics). Makes FL dynamics visible — straggler clients, non-IID divergence — directly useful for the research angle.

## Testing / CI

- Unit tests for `task.py` (model build, data loading, partitioning).
- Integration smoke via flwr's Simulation Engine: a tiny 2-client / 2-round run asserting rounds complete and metrics populate.
- Sister CI conventions (lint / ty / test / audit / pin-check) + the auto-merge fleet (already wired in this repo).

## Portfolio context

phalanx-fl (Python, latest-flwr app-model) and **velocity-fl** (Rust core) are complementary FL-systems vehicles; findings from both feed AJ's research (logged in `papers/`). The OTel observability layer and the non-IID heterogeneity harness are the most paper-able angles.

## Open / revisit

- Repo clean-slate vs. new repo — chose clean-slate (inherits sister tooling).
- Default model/dataset — chose BERT-tiny/IMDB for fast simulation; swappable by config.
