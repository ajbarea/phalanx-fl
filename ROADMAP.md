# Phalanx — Roadmap

Phalanx is a federated-learning research **testbed built on the latest Flower
(`flwr`) app-model**, with **OpenTelemetry-native observability** as its
distinguishing feature. The default showcase is a federated **LoRA** fine-tune of a
tiny BERT on non-IID sentiment data, aggregating **only the adapters**.

> **Why it exists:** ride the current `flwr` release always (Message API,
> `flwr-datasets`, HF/PEFT, OTLP), adapting the app to Flower rather than pinning
> Flower back. The OTel-native round/client traces + FL metrics are the part Flower
> doesn't ship out of the box — the systems angle worth writing up.

**Authoritative references** — check these before design decisions:
- [Flower Framework](https://flower.ai/docs/framework/) · [Message API](https://flower.ai/docs/framework/how-to-upgrade-to-message-api.html) · [Flower configuration](https://flower.ai/docs/framework/ref-flower-configuration.html)
- [Flower Datasets](https://flower.ai/docs/datasets/) · [Partitioners](https://flower.ai/docs/datasets/ref-api/flwr_datasets.partitioner.html)
- [PEFT / LoRA](https://huggingface.co/docs/peft) · [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/) · [OTel GenAI semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/)

---

## v1 — clean-slate rebuild

The app-model core: `task.py` (HF+LoRA model, `flwr-datasets` non-IID), `client_app.py`
(adapter-only train/eval), `server_app.py` (`ObservableFedAvg`), `telemetry.py` (OTel).

- [x] `telemetry.py` — OTel TracerProvider/MeterProvider, round/client spans, FL metrics; OTLP + console + in-memory exporters.
- [x] `ObservableFedAvg` — subclasses `FedAvg`, emits an `fl.round` span + aggregated loss/accuracy/participation metrics each round.
- [x] Adapter-only federation — LoRA adapters + the task head federated; frozen BERT backbone stays local.
- [x] `flwr run` simulation verified — federates adapters (0 failures) and emits round + client spans; IID accuracy improves monotonically (0.51 → 0.58).
- [x] Clean-slate sweep — removed the retrofitted `intellifl` app + old infra; rebuilt Makefile/CI/docs around `flwr run` + ruff/ty/pytest.
- [x] Quickstart docs — `flwr run`, the OTLP/Jaeger setup, console traces, the config knobs.

**Scope discipline (YAGNI):** one scenario (IMDB sentiment), IID + Dirichlet
partitioners, FedAvg. Strategies / datasets / partitioners grow only when a concrete
use lands.

---

## v2 — the observability research bit

- [ ] **Trace-context propagation over `Message.metadata`** — inject the server's
  round span context into the client `Message` so client spans become *children* of
  the round span, yielding a single distributed trace per FL round across the Ray
  simulation boundary. This is the genuinely novel piece (Flower ships no OTel↔FL
  bridge); deferred from v1 as the highest-risk / highest-reward item.
- [ ] **Round wall-time + comm-cost metrics** — per-round duration histogram and
  bytes-on-the-wire (adapter payload size), alongside loss/accuracy/participation.
- [ ] **Jaeger / OTel-Collector `compose` recipe** — one command to bring up a backend
  and view phalanx traces, so the differentiator is visible without external setup.
- [ ] **OTel GenAI semconv alignment** — emit eval results as the
  `gen_ai.evaluation.result` event where it fits, paired with app-namespaced metrics.

---

## v3+ — breadth (each gated on a real use, not built ahead)

- [ ] More strategies via `flwr.serverapp.strategy` (FedProx, FedAdam, robust aggregators).
- [ ] More `flwr-datasets` partitioners surfaced through run-config (pathological, shard, …).
- [ ] More tasks / datasets beyond IMDB sentiment.
- [ ] **Client-side differential privacy** (Opacus) — optional `target_epsilon`/`delta`,
  per-round budget logged beside the FL metrics. Pairs with the robustness story.

---

## Recurring invariant — ride the ecosystem

Phalanx's reason to exist is staying current with Flower. When `flwr`,
`flwr-datasets`, `transformers`, or `peft` ship a new major, audit what scaffolding
exists to compensate for a now-closed gap and collapse what no longer earns its keep
(the inverse of speculative-generality YAGNI: this polices *existing* code as the
ecosystem moves). Fires on external releases, not a fixed schedule.

---

## Paper positioning

Phalanx is **not its own paper** — SoT is `papers/LINEAGE.md` (read it; don't
duplicate). It folds into the systems / benchmark line (P1 / the future
`federated-forge`) framed strictly as **systems + reproducibility**, never a novel
FL/anomaly algorithm (that is the lab's PID-MADE line — cite and disclose it). The
OTel-native observability is the contribution worth writing up.
