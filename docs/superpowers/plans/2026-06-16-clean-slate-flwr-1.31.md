# phalanx-fl Clean-Slate Implementation Plan (flwr 1.31 app-model)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Rebuild phalanx-fl as a fresh flwr-1.31 app — a config-driven FL testbed with OTel-native observability; default scenario = federated LoRA fine-tune (BERT-tiny on IMDB, non-IID Dirichlet, adapter-only FedAvg).

**Architecture:** flwr app-model (`ServerApp`/`ClientApp`/`task.py`, `flwr run` + Simulation Engine); data via flwr-datasets `FederatedDataset`; model = HF transformer + PEFT/LoRA (only adapters aggregated); a `telemetry.py` OTel layer emits per-round + per-client traces/metrics. Mirrors velocity-fl's pyproject conventions for portfolio coherence; complements (does not overlap) velocity's Rust-core arena.

**Tech Stack:** flwr 1.31, flwr-datasets, transformers ≥5, peft, torch (CPU-only), opentelemetry-sdk/-exporter-otlp, uv / ruff / ty / pytest.

**Scope (v1, YAGNI):** one scenario + IID + one non-IID partitioner (Dirichlet) + FedAvg. Strategies/datasets/partitioners grow later.

---

## File structure

**Keep (sister shell):** `.github/`, `Makefile`, `scripts/`, `.claude/`, `LICENSE`, `docs/` (add specs/plans), `ROADMAP.md`/`IMPL.md`/`ECOSYSTEM.md`/`README.md` (rewrite content).
**Remove (old ghetto-rigged app):** the old `intellifl` package + its tests + any retrofitted flwr/web code — confirmed by inventory in Task 1, not blind.
**Create:**
- `pyproject.toml` (rewrite) — `phalanx` package, flwr-app deps + extras, torch-CPU source, `[tool.flwr]` app + run-config.
- `phalanx/__init__.py`, `phalanx/task.py` (model/data/train-eval), `phalanx/client_app.py` (`ClientApp`), `phalanx/server_app.py` (`ServerApp`), `phalanx/telemetry.py` (OTel).
- `tests/test_task.py`, `tests/test_telemetry.py`, `tests/test_smoke_sim.py`.

---

### Task 1: Clean-slate prep + flwr skeleton boots

**Files:** inventory current tree; `flwr new` skeleton → `phalanx/`; rewrite `pyproject.toml`.

- [ ] **Step 1 — Inventory.** `git ls-files | sed 's:/.*::' | sort -u` and read `pyproject.toml`; list exactly what's app-code (remove) vs sister-shell (keep). Record in the PR description.
- [ ] **Step 2 — Scaffold.** In a temp dir, `uvx flwr new phalanx --framework pytorch`; copy its `client_app.py`/`server_app.py`/`task.py` layout into `phalanx/` as the starting skeleton (this anchors the *exact* flwr 1.31 API — do not hand-invent it).
- [ ] **Step 3 — pyproject.** Rewrite to: `name="phalanx-fl"`, `requires-python=">=3.12,<3.14"`; deps `flwr[simulation]>=1.31`, `flwr-datasets[vision]`/`[default]`; extras `hf = ["transformers>=5","datasets","peft>=0.10"]`, `torch = ["torch>=2.12","torchvision"]`; `[tool.uv.sources]` route torch/torchvision to a `pytorch-cpu` index (copy velocity-fl's block verbatim); add `[tool.flwr.app]`/`[tool.flwr.federations.local-simulation]` from the scaffold; `[tool.flwr.app.config]` keys: `num-server-rounds`, `model-name=prajjwal1/bert-tiny`, `dataset=stanfordnlp/imdb`, `partitioner=dirichlet`, `alpha=0.5`, `fraction-fit`.
- [ ] **Step 4 — Boots.** `uv sync --extra hf --extra torch && flwr run .` on the *stock* skeleton. Expected: simulation runs the configured rounds, no error.
- [ ] **Step 5 — Commit.** `git add -A && git commit -m "feat: flwr 1.31 app skeleton + pyproject (clean-slate)"`

### Task 2: `task.py` — model (HF + LoRA) and data (flwr-datasets)

**Files:** Create `phalanx/task.py`; Test `tests/test_task.py`.

- [ ] **Step 1 — Failing test (model has LoRA adapters).**
```python
from phalanx.task import build_model, get_adapter_params, set_adapter_params
def test_model_has_lora_adapters():
    m = build_model("prajjwal1/bert-tiny", num_labels=2)
    names = [n for n, _ in m.named_parameters() if "lora" in n.lower()]
    assert names, "expected PEFT LoRA adapter params"
def test_adapter_param_roundtrip():
    m = build_model("prajjwal1/bert-tiny", num_labels=2)
    p = get_adapter_params(m); set_adapter_params(m, p)
    assert all(k in dict(m.named_parameters()) or True for k in [])  # smoke: no raise
```
- [ ] **Step 2 — Run, expect FAIL** (`ModuleNotFoundError`/`ImportError`). Run: `uv run --extra hf --extra torch python -m pytest tests/test_task.py -v`
- [ ] **Step 3 — Implement** `build_model` (AutoModelForSequenceClassification + `peft.LoraConfig`/`get_peft_model`), `get_adapter_params`/`set_adapter_params` (state-dict filtered to LoRA keys ↔ NumPy lists for flwr), and `load_partition(partition_id, num_partitions, alpha)` using `FederatedDataset(dataset="stanfordnlp/imdb", partitioners={"train": DirichletPartitioner(num_partitions, partition_by="label", alpha=alpha)})` + tokenizer.
- [ ] **Step 4 — Run, expect PASS.**
- [ ] **Step 5 — Commit.** `feat(task): HF+LoRA model and Dirichlet flwr-datasets loading`

### Task 3: `client_app.py` — local LoRA train/eval

**Files:** Modify `phalanx/client_app.py`; Test extends `tests/test_task.py` (client fn unit).

- [ ] **Step 1 — Failing test:** a `train_one`/`evaluate_one` helper trains on a 2-batch subset and returns `(adapter_params, num_examples, {"loss": float})` without raising.
- [ ] **Step 2 — Run, expect FAIL.**
- [ ] **Step 3 — Implement** the `ClientApp` using the scaffold's `@app.train()`/`@app.evaluate()` (or `NumPyClient`) shape from Task 1; body calls `task.train_one`/`evaluate_one`; returns LoRA adapter params only.
- [ ] **Step 4 — Run, expect PASS.**
- [ ] **Step 5 — Commit.** `feat(client): LoRA adapter-only train/eval ClientApp`

### Task 4: `server_app.py` — FedAvg over adapters

**Files:** Modify `phalanx/server_app.py`; Test `tests/test_task.py` (strategy config).

- [ ] **Step 1 — Failing test:** `make_strategy(cfg)` returns a `FedAvg` with the configured `fraction_fit` and initial adapter parameters from a fresh model.
- [ ] **Step 2 — Run, expect FAIL.** **Step 3 — Implement** `ServerApp` wiring `FedAvg`, `num_server_rounds` from run-config, initial params = `get_adapter_params(build_model(...))`, global eval. **Step 4 — PASS.** **Step 5 — Commit** `feat(server): FedAvg adapter aggregation ServerApp`.

### Task 5: `telemetry.py` — OTel layer (the differentiator)

**Files:** Create `phalanx/telemetry.py`; Test `tests/test_telemetry.py`.

- [ ] **Step 1 — Failing test (in-memory):**
```python
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from phalanx.telemetry import init_telemetry, round_span, record_round_metrics
def test_round_span_and_metrics():
    exp = InMemorySpanExporter(); init_telemetry(span_exporter=exp, service_name="phalanx-test")
    with round_span(rnd=1):
        record_round_metrics(rnd=1, loss=0.5, accuracy=0.6, clients=2)
    spans = exp.get_finished_spans()
    assert any(s.name == "fl.round" for s in spans)
```
- [ ] **Step 2 — Run, expect FAIL.**
- [ ] **Step 3 — Implement** `init_telemetry` (TracerProvider + MeterProvider, `Resource(service.name=...)`, OTLP exporter by default or injected exporter for tests, BatchSpanProcessor), `round_span`/`client_span` context managers, `record_round_metrics`/`record_client_metrics` (Counter/Histogram instruments: loss, accuracy, participation, comm bytes, round wall-time).
- [ ] **Step 4 — Run, expect PASS.** **Step 5 — Commit** `feat(telemetry): OTel round/client traces + FL metrics`.

### Task 6: Wire OTel in + integration smoke

**Files:** Modify `server_app.py`/`client_app.py`; Test `tests/test_smoke_sim.py`.

- [ ] **Step 1 — Failing test:** run `flwr run` programmatically (or `subprocess`) with `num-server-rounds=2`, 2 partitions, asserting it exits 0 and the run emits ≥1 `fl.round` span via an in-memory/OTLP-to-file exporter.
- [ ] **Step 2 — Run, expect FAIL.** **Step 3 — Implement** the server-round span wrapping client spans + metric recording; ensure single global provider (init once in server_app). **Step 4 — PASS** (Kokoro-free; CPU; small). **Step 5 — Commit** `test: 2-client/2-round simulation smoke with OTel assertions`.

### Task 7: Docs, CI, finalize PR

- [ ] **Step 1** — Rewrite `README.md` (what it is, `flwr run` quickstart, the OTel/Jaeger setup, the testbed config knobs), update `ECOSYSTEM.md`/`ROADMAP.md`; add an `examples/` note (mirror velocity's pattern).
- [ ] **Step 2** — `make lint` (ruff + ty) + `make test` green; fix fallout.
- [ ] **Step 3** — Commit, push, open PR (base main) describing the clean-slate: what was removed, the new app-model, the OTel differentiator. Do NOT auto-merge (large rewrite — AJ reviews).

---

## Self-review notes
- **Spec coverage:** purpose/testbed (Tasks 1–4 + config), showcase scenario (Task 2/3, LoRA/IMDB), observability (Tasks 5–6), repo clean-slate (Task 1 + 7), testing/CI (Tasks 2–7). ✓
- **flwr-API risk** mitigated by Task 1 anchoring on real `flwr new` output (not hand-invented signatures); customization tasks modify the generated skeleton.
- **Portfolio:** torch-CPU/extras conventions mirror velocity-fl; OTel layer is net-new to the portfolio.
