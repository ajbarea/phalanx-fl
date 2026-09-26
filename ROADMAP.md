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
- [x] Deterministic client training — `set_seed` keys Python/NumPy/torch per `(round, client)` and disables nondeterministic CUDA kernels, so each client's local training replays.
- [ ] Run-level replay — Flower samples clients with unseeded `random.sample` over node IDs that are random per run, so one config picks different clients each run (identical smoke runs ended at 0.979 and 0.721). Needs a seeded sampler ordered by `partition-id` and a test that two runs match round for round (the reproducibility floor a systems paper needs).
- [x] OTel flush on exit — `shutdown_telemetry` force-flushes the OTLP buffers (and runs at `atexit`), so the final round's spans/metrics aren't dropped when the process exits.
- [x] Run-provenance manifest — `phalanx/provenance.py` writes a per-run JSON (git SHA + branch, package versions, run-config, per-round metrics) beside the trace: the static half of the reproducibility story (FAIR / IEEE artifact criteria).

**Verified findings from the rebuild (2026-06-16, empirical).** Collapsed here from IMPL
when that work shipped, because they are the kind of thing that gets re-learned otherwise.

- `transformers` 5 is strict about `model_type`. `prajjwal1/bert-tiny` has none in its
  config and fails to load; that, not arbitrary conservatism, is why the Flower example
  caps `transformers<5`. Showcase model is `google/bert_uncased_L-2_H-128_A-2`.
- The adapter payload is the LoRA tensors **plus the classifier head**: PEFT puts the
  randomly-initialised SEQ_CLS head in `modules_to_save`, so it federates alongside.
  `set_peft_model_state_dict` mutates its input dict in place.
- `flwr` 1.31 moved federation/SuperLink config out of `pyproject.toml` into
  `~/.flwr/config.toml`. App run-config stays in `[tool.flwr.app.config]`; per-run
  simulation overrides go via `--federation-config`.
- `flwr run` submits to a local SuperLink and returns; the sim runs detached. Use
  `--stream` to stay attached and capture the OTel console spans.
- `num-examples` is `len(loader.dataset)`, not `len(loader)`: the DataLoader length is a
  batch count, and FedAvg weights the adapters and the reported metrics by this key, so
  a batch count over-weighted the smallest partitions (#102).
- The "round-2 Dirichlet collapse" was the client figure, not the model. On the global
  test split (2026-09-26, three draws per arm, `results/global-eval-arms/`), under
  Dirichlet (alpha 0.5) the aggregated adapters never learn. Global accuracy is exactly
  0.500 in every round of two draws, consistent with predicting one label on the balanced
  split, and peaks at 0.547 in `dirichlet-2`; global loss ends above its round-0 value in
  two of three. The client figure for the same
  rounds spans 0.021 to 0.709 across draws: it measures which skewed shards were
  sampled, and that is what read as a round-2 collapse. IID, on the same code path,
  improves every round in every draw (0.509 to 0.611-0.612), so an aggregation bug is
  still ruled out.

**Scope discipline (YAGNI):** one scenario (IMDB sentiment), IID + Dirichlet
partitioners, FedAvg. Strategies / datasets / partitioners grow only when a concrete
use lands.

---

## v2 — the observability research bit

- [x] **Trace-context bridge — one distributed trace per FL round.** The round span
  spans the whole round (`configure_train` → `aggregate_evaluate`); its W3C
  `traceparent` rides the broadcast `ConfigRecord`, and each client extracts it so its
  `fl.client.{train,evaluate}` span is a *child* of the round span. Server + all client
  spans land in a single trace, viewable end-to-end in Jaeger. The genuinely novel
  OTel↔FL piece (Flower ships no such bridge). `phalanx/telemetry.py` `traceparent_for`
  / `context_from_traceparent`.
- [x] **Aggregation-weight ESS, per phase — `fl.round.train_ess` / `fl.round.evaluate_ess`.**
  Kish's `(Σwᵢ)²/Σwᵢ²` over the `num-examples` weights FedAvg actually aggregates by:
  equal to the client count when shares are even, falling toward 1.0 as one client
  dominates. Under Dirichlet skew it reports how much less than the client count a round
  really averaged over, which participation counts cannot show. Train and evaluate
  sample different clients, so each phase reports its own, beside its own client count.
- [x] **Global test set — `fl.round.global_accuracy`.** The server scores the aggregated
  adapters on the dataset's `test` split, which the partitioner never sees, each round
  and at round 0. The clients' figure stays beside it: a `num-examples`-weighted mean
  over holdouts carved from their own partitions, which under Dirichlet inherits the
  label skew. The pair is what shows skew-driven divergence; the arms above are the first
  reading of it.
- [ ] **Round wall-time + comm-cost metrics** — per-round duration histogram and
  bytes-on-the-wire (adapter payload size), alongside loss/accuracy/participation.
- [ ] **Jaeger / OTel-Collector `compose` recipe** — one command to bring up a backend
  and view phalanx traces, so the differentiator is visible without external setup.
- [ ] **OTel GenAI semconv alignment** — emit eval results as the
  `gen_ai.evaluation.result` event where it fits, paired with app-namespaced metrics.
- [ ] **FL fault observability** — map client/worker failures to span `ERROR` status +
  span events (the old `intellifl/utils/ray_logger.py` taxonomy: CRASH / OOM / TIMEOUT /
  NODE_DEATH). Turns the observability layer from happy-path-only into a fault story —
  worth extracting from the old app, re-expressed as OTel rather than bespoke logging.

---

## corpus — moved to `sphragis`

The Gerrit review corpus and its measurement instruments now live in their own repository,
[`ajbarea/sphragis`](https://github.com/ajbarea/sphragis), along with the spec and the plans.

They were built here and moved on 2026-09-13. The reason is a policy conflict rather than
tidiness: this repo's standing invariant is to ride the latest Flower release, and a paper
artifact has to reproduce years from now. Two release policies cannot share one lockfile, and
the strain was already showing in Dependabot alerts pinned by `flwr` on code that never
imported `flwr`.

`provenance.py` keeps `provenance_header()`; sphragis copied it rather than depending on this
repo.

RQ2 federates adapters on this repo's Flower stack. That dependency is deliberately not built
yet and gets decided when RQ2 starts.

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

SoT is `papers/LINEAGE.md` (read it; don't duplicate). Two distinct things now live here,
and they are not the same paper.

**The Flower/OTel testbed is not its own paper.** It folds into the systems / benchmark
line (P1 / the future `federated-forge`) framed strictly as **systems + reproducibility**,
never a novel FL/anomaly algorithm (that is the lab's PID-MADE line — cite and disclose
it). The OTel-native observability is the contribution worth writing up.

**P4 moved with the corpus.** The MSR 2027 registered report on whether organizations leave a
learnable fingerprint in code review is now `sphragis`'s paper, drafted in
`papers/org-fingerprint/STAGE1-SKELETON.md`. This repo is cited by it as the Flower stack RQ2
would federate on, not as the apparatus.

**Nearest rolling neighbour, do not overclaim against it.** Martian's Code Review Bench
(March 2026) is already a monthly-versioned, continuously refreshed code-review benchmark
over 200,000+ GitHub PRs. So "first rolling code-review benchmark" is not available. It
differs on all three axes that matter here: it scores **issue identification** by
precision/recall against a curated gold set rather than **refinement** by exact match, it
uses an LLM judge, and it does not partition by organization. It is an industry lab
release, not peer reviewed. Cite it; claim the organization partition and the declared
provenance boundary, not the rolling collection.
