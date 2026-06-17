# Phalanx — Active Implementation Log

Rolling notes on in-flight work. See `ROADMAP.md` for the stable plan.
When a roadmap item ships, collapse its notes here into a one-liner under
ROADMAP's "Recently shipped" and clear the relevant block below.

---

## Current focus

### Clean-slate rebuild on flwr 1.31 app-model (branch `feat/clean-slate-flwr-1.31`)

Rebuilding phalanx-fl fresh on the current Flower **Message API** (flwr 1.31),
replacing the retrofitted `intellifl` app. Decision + rationale: see the
`project_phalanx_clean_restart` memory and
`docs/superpowers/specs/2026-06-16-phalanx-fl-flwr131-clean-slate-design.md`.
Plan: `docs/superpowers/plans/2026-06-16-clean-slate-flwr-1.31.md`.

**API anchored (2026-06-16)** on Flower's canonical `examples/quickstart-huggingface`
(`flwr-version-target = 1.31.0`):
- Server: `app = ServerApp()` + `@app.main()` → `main(grid: Grid, context: Context)`;
  `ArrayRecord(state_dict)`; `FedAvg(fraction_train=…)`; `strategy.start(grid=, initial_arrays=, num_rounds=)`.
- Client: `app = ClientApp()` + `@app.train()`/`@app.evaluate()` → `(msg: Message, context: Context) -> Message`;
  read `msg.content["arrays"]`, reply `RecordDict({"arrays": ArrayRecord(...), "metrics": MetricRecord(...)})`.

**Decisions (web-researched 2026-06):**
- **OTel per-round hook** = subclass `FedAvg`, override `configure_train` /
  `aggregate_train` / `aggregate_evaluate` (the per-round entry points inside
  `strategy.start()`'s loop). Open the round span in `configure_train`, close after
  `aggregate_evaluate`; record aggregated loss/accuracy/participation as metrics.
  Client spans emit inside the client `@app.train`/`@app.evaluate` fns (per-process,
  correct for the Ray sim). research(2026-06): Flower Message-API strategy guide.
- **Trace-context-over-`Message.metadata`** (linking client spans to the server round
  span) is the genuinely-novel bit but the riskiest → scoped as explicit **v2** in
  ROADMAP (YAGNI for v1).
- **Versions** stay latest stable (phalanx rides latest always): transformers 5.12,
  peft 0.19, torch 2.12 (CPU index). The flwr example's `transformers<5` cap is
  conservative pinning, not a hard incompatibility; verified empirically in the run loop.

**Differentiator vs the canonical example:** the example federates the *full* model;
phalanx federates **LoRA adapters only** (`get_peft_model_state_dict`) + **OTel-native
round/client traces+metrics**.

**Done:** spec, plan, `pyproject.toml` (flwr 1.31 + extras + torch-CPU source),
`phalanx/task.py` (HF+LoRA model, Dirichlet non-IID, train/eval, adapter helpers).

**Build status:** telemetry.py ✅ · server_app.py ✅ · client_app.py ✅ · task.py ✅ ·
tests (10 unit) ✅ · clean-slate sweep ✅ (old app + infra removed; Makefile/CI/pyproject
rebuilt) · docs rewrite ✅ (README/ROADMAP/IMPL/ECOSYSTEM + site index/getting-started/
architecture + nav + skill-context + .env.example). Remaining: ty clean → commit → PR
(base `main`, **no auto-merge** — big rewrite, AJ reviews).

**`flwr run` verified end-to-end (2026-06-16):**
- **Dirichlet run** (2 rounds): full pipeline runs — `aggregate_train`/`aggregate_evaluate`
  report "2 results, 0 failures" both rounds; server emits `fl.round` spans
  (`fl.round`/`fl.loss`/`fl.accuracy`/`fl.clients`) + FL metrics; clients emit
  `fl.client.{train,evaluate}` spans with `service.name=phalanx-fl`. train_loss decreased
  0.654 → 0.610. Round-2 *eval* accuracy collapsed (0.62 → 0.02) — non-IID eval-partition
  skew, **not** an aggregation bug.
- **IID confirmation run** (rules out a bug): accuracy improves monotonically
  **0.510 → 0.581** across rounds, both losses decrease. Confirms FedAvg-over-adapters is
  correct; the dirichlet collapse is genuine non-IID dynamics (observable in the traces —
  which is the point of the OTel layer).

**Verified findings (2026-06-16, empirical — corrected stale assumptions):**
- **transformers 5 is strict about `model_type`.** `prajjwal1/bert-tiny` (the model the
  flwr example uses) has *no* `model_type` in its config.json and **fails to load on
  transformers 5** (4.x was lenient — that's the real reason the example caps
  `transformers<5`, not arbitrary conservatism). Fix: switched the showcase model to
  **`google/bert_uncased_L-2_H-128_A-2`** — Google's original tiny BERT, same
  2-layer/128-hidden size, but ships a complete config. Keeps transformers 5 (latest).
- **Adapter payload = LoRA tensors + the classifier head.** PEFT puts the
  randomly-initialised SEQ_CLS head in `modules_to_save`, so it is trained and federated
  alongside the LoRA adapters (the frozen BERT backbone is not). `get_adapter_state`
  returns consistent keys across calls; FedAvg's key-matched aggregation works.
  (`set_peft_model_state_dict` mutates its input dict in place — caught a test bug.)
- **flwr 1.31 moved federation/SuperLink config OUT of pyproject** into the global
  `~/.flwr/config.toml`; `[tool.flwr.federations]` is legacy and auto-commented on first
  `flwr run`. App run-config (rounds/model) stays in pyproject `[tool.flwr.app.config]`.
  Per-run simulation overrides go via `--federation-config 'options.num-supernodes=N'`
  (known gap, flwr #6824: no per-project sim config anymore). Repro plan: Makefile/README
  pass `--federation-config`; pyproject's commented legacy block to be removed in the sweep.
- **`flwr run` submits to a local SuperLink and returns**; the sim runs detached. Use
  **`--stream`** to stay attached and capture ServerApp/ClientApp logs (where the OTel
  console spans land). `OTEL_TRACES_EXPORTER=console` prints traces with no collector.
- Resolved stack: flwr 1.31.0, flwr-datasets 0.6.0, transformers 5.12.1, peft 0.18.1,
  torch 2.12.0+cpu, datasets 4.8.4 (capped <5 by flwr-datasets), opentelemetry-sdk 1.42.1.

---

## Open bugs & findings

_None active._
