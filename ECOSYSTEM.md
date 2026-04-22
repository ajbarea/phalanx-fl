# phalanx-fl — Dependency Rationale

Why each dep exists, what it's load-bearing for, and when to reconsider. The
`pyproject.toml` is the source of truth for *what*; this file is the source
of truth for *why*.

Shared toolchain-pin rationale (pytest 9.0.3 floor, ruff/ty floors,
`requires-python = ">=3.11,<3.14"`) lives with the
[aj-sisters](../.claude/skill-context.md) drift-detection skill — those are
cross-repo policy, not phalanx-specific decisions.

phalanx is the heaviest of the three sisters: an FL research framework with
a FastAPI control plane, Celery+Redis async job queue, Flower simulation
core, Ray execution backend, and a PyTorch training path. The dep list
reflects that breadth.

---

## Runtime dependencies

### FL + training stack

- **`flwr>=1.28`** — Flower federated-learning framework. Imported in ~32
  modules (client, strategy, simulation, context). The project's
  organizing abstraction: custom strategies in
  `intellifl.simulation_strategies` subclass Flower's `Strategy` and
  plug into `intellifl.federated_simulation` via `flwr.simulation`.
  Pinned at `>=1.28` because the 1.28 API introduced the server/client
  app split we rely on; earlier versions have a different runtime model.
- **`flwr-datasets`** — partitioning helpers for non-IID FL
  experiments. Lives alongside `flwr`; bump together.
- **`ray>=2.54.1`** — distributed execution backend for Flower
  simulations (`flwr.simulation.run_simulation` uses Ray under the hood
  when scaled). Direct imports in `simulation_runner` and
  `utils.ray_logger`. The `>=2.54.1` floor pins a specific patch that
  fixes a logger-shutdown hang. Platform-workaround shim
  (`utils.ray_config`) removed 2026-04-22 — Flower 1.28+ handles the
  env-var and dashboard fiddling that the shim used to cover for
  Flower 1.9.
- **`torch`** + **`torchvision`** — client-side training and the vision
  datasets (MNIST, CIFAR-10, FEMNIST). Uses the `pytorch-cu128` explicit
  index via `[tool.uv.sources]` to get CUDA 12.8 wheels on Linux/Windows.
- **`transformers`** — HF models for the NLP / LLM experiments (Llama
  fine-tuning path). Imported in 5 modules.
- **`peft`** — LoRA / parameter-efficient fine-tuning adapters on top of
  `transformers`. Imported in 4 modules.

### Data stack

- **`datasets`** — HF datasets loader for FEMNIST and the other benchmark
  corpora. Pulls `pyarrow` transitively (see "Pruning candidates").
- **`huggingface_hub[hf_xet]`** — indirect; transformers + datasets both
  pull huggingface_hub. The `[hf_xet]` extra enables HF's Xet protocol
  (chunk-based deduplicated transfers, faster for large repeated
  downloads). No direct imports in our code; the extra is a runtime
  optimization.
- **`numpy`**, **`scipy`**, **`pandas`**, **`scikit-learn`** — the
  scientific-Python baseline, used across analysis scripts and
  `output_handlers`.
- **`matplotlib`** — server-side plot generation in
  `intellifl.output_handlers.new_plot_handler` and the
  `attack_utils.snapshot_animation` snapshot renderer. Runtime dep
  because results are rendered into PNGs as part of the run, not
  post-hoc.

### API + orchestration

- **`fastapi`** + **`uvicorn[standard]`** — the control-plane HTTP API
  (`intellifl.api`). `uvicorn[standard]` includes `httptools` and
  `uvloop` for production-grade perf.
- **`sse-starlette`** — Server-Sent Events for streaming simulation
  progress to the frontend. One import site
  (`intellifl/api/routers/simulations.py`) but it's on the primary UX
  path (live progress bars).
- **`celery[redis]`** — distributed task queue for simulation runs.
  **Decided to stay** (2026-04-22 audit): the load-bearing use case is
  *serialisation*, not scale. Without Celery, concurrent frontend users
  clicking "run simulation" would launch multiple sims on one box and
  crash it; Celery with single-worker concurrency queues them instead.
  BackgroundTasks wouldn't give durable queues across server restart.
  The `[redis]` extra pins redis as the broker/backend; dev tests
  against a real redis via `testcontainers[redis]`. Imported in
  `celery_app`, `simulation_tasks`, and several API routers.
- **`pydantic`** — request/response schemas for FastAPI + data-model
  validation across the stack.
- **`jsonschema`** — config-file validation for the research-experiment
  format. Imported in 3 files. Distinct from pydantic because the
  schemas are user-authored JSON (not Python-declared models).

### System + utilities

- **`psutil`** — process/memory monitoring in 7 modules. Used to detect
  stuck simulations and report resource usage.
- **`python-dotenv`** — `.env` loading for local dev config (secrets,
  HF tokens, etc.).
- **`pyyaml`** — experiment-config format (YAML files describing
  simulation matrices).
- **`tqdm`** — progress bars in long-running training loops and dataset
  downloads.
- **`rich`** — terminal rendering for CLI output (logs, tables, panels).
- **`pywinpty; sys_platform == 'win32'`** — Windows PTY support for the
  `intellifl-dev` cross-platform launcher. Gated to Windows so Linux/Mac
  don't pull it.

---

## Dev dependencies

### Test stack

phalanx runs the richest pytest plugin set of the three sisters because
FL simulations are inherently flaky at the edges (Ray actors, Celery
workers, real redis in containers, randomness in partitioning).

- **`pytest>=9.0.3`** — matches sister floors (vFL and kourai both on
  9.0.3).
- **`pytest-asyncio`** — async API + Celery AsyncResult tests.
- **`pytest-cov`** — coverage; also the dependency for Codecov
  integration.
- **`pytest-mock`** — lightweight mocker fixture.
- **`pytest-randomly`** — randomizes test order per run. Catches
  order-dependent flakes; `--randomly-seed=last` in `addopts` lets CI
  reproduce a failing order. Paired with `-W error::DeprecationWarning`
  to fail hard on any deprecation that surfaces.
- **`pytest-repeat`** — re-run flaky tests to distinguish determinism
  bugs from env-specific ones. Used surgically, not globally.
- **`pytest-xdist`** — parallel test execution. Paired with markers
  `parallel` / `serial` so inherently-sequential tests (anything
  touching the real Celery broker) stay on the serial lane.
- **`hypothesis`** — property tests for the strategy + aggregation logic.
- **`testcontainers[redis]`** — spins up a real Redis container for
  integration tests that exercise the Celery queue end-to-end. The
  canonical "don't mock the broker" pattern.
- **`pip-audit`** — CVE scanning across the resolved dep tree. Run in
  CI alongside lint. (mutmut was dropped 2026-04-22 — aspirational
  tooling that never ran; `uv add --group dev mutmut` to bring it back
  if a cadence ever gets defined.)

### Build + lint

- **`ruff>=0.9`** — combined linter + formatter. `target-version =
  "py312"` is set to the upper-end of the supported range; phalanx is
  aggressive about using newer-Python idioms. Lint rule set
  (`E F I W UP B C4 SIM`) is narrower than kourai's; the `ignore` list
  reflects pragmatic compromises against noisy-in-this-codebase rules
  (B904 `raise from`, SIM108 ternary preference).
- **`ty>=0.0.25`** — Astral's type checker. `[tool.ty.analysis]
  replace-imports-with-any` is extensive here because many of the ML
  stack's types are incomplete (torch, ray, flwr, transformers,
  datasets). The `[[tool.ty.overrides]]` for `tests/**` silences
  type-argument strictness in tests — pragmatic given hypothesis'
  dynamic typing.

### Docs

- **`mkdocs`** + **`mkdocs-material`** — *legacy.* The repo has migrated
  to `zensical` (`zensical.toml` exists; no `mkdocs.yml`). These two
  deps should be removed on the next housekeeping pass.
- **`zensical`** — the actual docs generator. Same tooling across all
  three sisters; aj-sisters audits for drift.

---

## Past pruning

The 2026-04-22 audit removed eleven top-level declarations that had zero
import sites in `intellifl/` and `tests/`:
`accelerate`, `click`, `dill`, `fsspec`, `httpx`, `huggingface_hub`,
`multiprocess`, `opencv-python-headless`, `pyarrow`, `requests`,
`mkdocs`, `mkdocs-material`. The runtime deps that were already being
pulled transitively (e.g., `huggingface_hub` via `transformers` and
`datasets`) remain in the resolved tree; their top-level declaration
was redundant, not load-bearing. `mkdocs` + `mkdocs-material` were
actually removed from the dep tree because nothing else needed them
(docs migrated to `zensical`). The runtime-dep count dropped from
~35 to ~25.

If one of the transitively-resolved deps ever falls out of resolution
(because its parent drops it), the tests/ty will fail immediately on
the real code paths — which is the correct behaviour.

---

## Open questions

- **`utils/ray_logger.py` (369 lines)** — structured worker-crash / OOM
  logging. Unclear how much of this Flower 1.28+ now provides natively.
  Evaluation planned (see ROADMAP dep-hygiene); removing it would
  further shrink the Ray-surface footprint in phalanx.
- **File-consolidation pass.** Most of `intellifl/*_handlers/`,
  `intellifl/simulation_strategies/`, and `intellifl/dataset_loaders/`
  are dozens-of-files-one-class-each; `network_models` was already
  collapsed to a single dispatcher (2026-04-06). Propagating that
  pattern is captured in the ROADMAP.
