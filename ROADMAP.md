# IntelliFL — Active TODO

Extracted from planning docs across `demo/`, root, and `.kiro/`. Each item references
its source doc. Items already implemented in source code have been removed.

**Authoritative References** — always check these for current best practices:
- [Flower Framework](https://flower.ai/docs/) | [Flower Datasets](https://flower.ai/docs/datasets/index.html) | [Partitioners Tutorial](https://flower.ai/docs/datasets/tutorial-use-partitioners.html)
- [Docker Build Best Practices](https://docs.docker.com/build/building/best-practices/) | [Compose Profiles](https://docs.docker.com/compose/how-tos/profiles/)
- [uv](https://docs.astral.sh/uv/) | [uv Docker Guide](https://docs.astral.sh/uv/guides/integration/docker/) | [Ruff](https://docs.astral.sh/ruff/) | [ty](https://docs.astral.sh/ty/)
- [Celery User Guide](https://docs.celeryq.dev/en/stable/userguide/index.html)
- [FastAPI Reference](https://fastapi.tiangolo.com/reference/) | [HuggingFace Docs](https://huggingface.co/docs)

---

## Recently shipped

- **Aggregation math refinements** (2026-04-10) — Krum / Multi-Krum use squared
  Euclidean distance per NIPS 2017 (not L2 norm); Krum / Multi-Krum / Bulyan
  scoring sums the *k* other closest neighbors (excluding self-distance);
  all strategies record `aggregation_participation=1` only for clients actually
  included in the round's global update, enabling accurate precision/recall.
- **Network models — Transformer merge** (2026-04-06) — Merged
  `bert_model_definition.py` and `text_classifier_model.py` into
  `transformer_models.py`; unified `load_hf_model(model_name, task, ...)` with
  task dispatch (`mlm` vs `seq_cls`); backward-compat wrappers delegate to it.
  All 344 tests pass. (Source: `NETWORK_MODELS_DRY_REFACTOR.md`.)

---

## Dataset System Rework

> Source: `demo/DATASET_REWORK_PLAN.md` (Phases 0-5)
> Ref: [HuggingFace Datasets](https://huggingface.co/docs/datasets) | [flwr-datasets v0.6.0](https://flower.ai/docs/datasets/index.html)

### Phase 0 — Cleanup & Foundation

- [ ] **0A: Drop `its`, `flair`, `lung_photos`**
  - Delete image transformer files: `its_image_transformer.py`, `flair_image_transformer.py`, `lung_photos_image_transformer.py`
  - Remove `its`/`flair`/`lung_photos` from `frontend/src/constants/datasets.js`
  - Add `cifar10`, `cinic10`, `pubmed_classification_20k` to frontend datasets
  - Remove dispatch branches in `federated_simulation.py`
  - Delete related simulation configs (`its_bulyan_vs_labelflip25.json`, etc.)
  - *(Note: `config/dataset_keyword_to_dataset_dir.json` entries cleaned up in Phase 4 when the entire file is deleted)*
- [ ] **0B: Add `_initialize_weights()` to `DynamicCNN`** (`dynamic_cnn.py`)
- [ ] **0C: Normalize `FederatedDatasetLoader.load_datasets()` return type** — currently returns 3 values `(trainloaders, valloaders, num_classes)`, should return 2 and store `num_classes` as instance attribute
- [ ] ~~**0D: Rename `cifar100_image_transformer` → `cifar_image_transformer`**~~ — Skip: Phase 5 plans to eliminate all transformer files via declarative JSON transforms. Renaming first is wasted churn.

### Phase 1 — Config Expansion & Config-Driven Dispatch

- [ ] **1A:** Expand `config/huggingface_datasets.json` with all 21 datasets (MedMNIST, FEMNIST, cifar10, cinic10, medquad, text datasets)
- [ ] **1B:** Rewrite `_assign_dataset_loaders_and_network_model()` — replace 4+ `elif dataset_keyword` branches with config-driven dispatch using `huggingface_datasets.json`
- [ ] **1C:** Use `load_hf_model()` from the Transformer Merge (above) instead of duplicating LoRA/non-LoRA BERT loading here

### Phase 2 — Migrate Image Datasets to FederatedDatasetLoader

- [ ] **2A:** Enhance `FederatedDatasetLoader` — add `subset`, `image_column`, `image_transform`, `load_dataset_kwargs` params; add `_TransformedImageDataset` wrapper
- [ ] **2B:** Migrate in tiers: cifar100 → 11 MedMNIST → FEMNIST (iid/niid) → cifar10/cinic10
- [ ] **2C:** Simplify `_create_image_loader()` to single `FederatedDatasetLoader` call
- [ ] **2E:** Delete `image_dataset_loader.py`, `huggingface_image_dataset_loader.py`, and their tests

### Phase 3 — Migrate Text Datasets to FederatedDatasetLoader

- [ ] **3A:** Create `TextMLMProcessor` in `intellifl/dataset_loaders/processors/text_mlm_processor.py`
- [ ] **3B:** Add `text_processor` support to `FederatedDatasetLoader`
- [ ] **3C:** Migrate text datasets: financial_phrasebank, lexglue, pubmed, medal, medquad
- [ ] **3E:** Delete `huggingface_text_dataset_loader.py`, `medquad_dataset_loader.py`, and their tests

### Phase 4 — Delete Legacy Infrastructure

- [ ] Simplify `entrypoint.sh` (remove S3 download logic)
- [ ] Update `docker-compose.yml` — remove `./datasets` volume, add `hf-cache` named volume, add `HF_HOME` env
- [ ] Delete `config/dataset_keyword_to_dataset_dir.json` and update all code that reads it (single deletion point — Phase 0A just removes individual entries' dispatch branches)
- [ ] Clean up imports in `federated_simulation.py`

### Phase 5 — Optional Enhancements

- [ ] Consolidate FEMNIST networks into DynamicCNN (add conv channel params)
- [ ] Declarative image transforms in JSON config (eliminate transformer files — this supersedes the Phase 0D rename)
- [ ] Add structured metadata for all datasets in frontend `HUGGINGFACE_DATASETS`
- [ ] Expose additional `flwr-datasets` partitioners (see **Modular Partitioning System** section below)

---

## Modular Partitioning System — Plug-and-Play

> Source: [`flwr_datasets.partitioner` API](https://flower.ai/docs/datasets/ref-api/flwr_datasets.partitioner.html) | [Partitioner Tutorial](https://flower.ai/docs/datasets/tutorial-use-partitioners.html)
> Currently only **3 of 15** usable partitioners are wired up (IID, Dirichlet, Pathological).
> Goal: let researchers pick any partitioner from a dropdown and configure its params via the UI.
> flwr-datasets is at v0.6.0; all partitioners inherit from the `Partitioner` ABC.

### Current State

`FederatedDatasetLoader._create_partitioner()` (line ~136) has a hard-coded `if/elif` chain for
`iid`, `dirichlet`, and `pathological`. The same pattern is duplicated in the legacy loaders
(`text_classification_loader.py`, `huggingface_image_dataset_loader.py`, `huggingface_text_dataset_loader.py`).
Once the Dataset System Rework (Phases 2-3) consolidates all loaders into `FederatedDatasetLoader`,
the registry only needs to live in one place.

### Phase 0 — Config-Driven Partitioner Registry

- [ ] **0A: Create partitioner registry** in `intellifl/dataset_loaders/partitioner_registry.py`
  - Map string keys to `flwr_datasets.partitioner` classes with their default params and param schemas
  - Cover all horizontal (sample-level) partitioners:

  | Key | Class | Key Params | Use Case |
  |-----|-------|------------|----------|
  | `iid` | `IidPartitioner` | — | Baseline, uniform random split |
  | `dirichlet` | `DirichletPartitioner` | `alpha` (float), `partition_by` | Non-IID via concentration param (lower α = more skew) |
  | `pathological` | `PathologicalPartitioner` | `num_classes_per_partition` | Each client sees only K classes |
  | `shard` | `ShardPartitioner` | `num_shards_per_partition`, `partition_by` | Fixed shard count per client (McMahan et al.) |
  | `linear` | `LinearPartitioner` | — | Partition sizes grow linearly with client ID |
  | `exponential` | `ExponentialPartitioner` | — | Partition sizes grow exponentially with client ID |
  | `square` | `SquarePartitioner` | — | Partition sizes grow quadratically with client ID |
  | `size` | `SizePartitioner` | `partition_sizes` (list[int]) | Exact sample counts per client |
  | `natural_id` | `NaturalIdPartitioner` | `partition_by` | Split by a natural ID column (e.g., user_id, hospital) |
  | `grouped_natural_id` | `GroupedNaturalIdPartitioner` | `partition_by` | Group multiple natural IDs into fewer partitions |
  | `inner_dirichlet` | `InnerDirichletPartitioner` | `partition_sizes`, `alpha` | Dirichlet label skew with fixed partition sizes |
  | `distribution` | `DistributionPartitioner` | `distribution`, `partition_by` | Explicit probability matrix per class per client |
  | `continuous` | `ContinuousPartitioner` | `partition_by` | Split by continuous (non-label) feature values |

  - Vertical partitioners (`VerticalEvenPartitioner`, `VerticalSizePartitioner`) are out of scope for now (feature-split FL is a different paradigm)

- [ ] **0B: Refactor `_create_partitioner()`** — replace if/elif chain with registry lookup + `**partitioning_params` pass-through
- [ ] **0C: Update `partitioning_params` validation** — validate user-supplied params against the registry schema before constructing the partitioner; surface clear errors for missing/invalid params

### Phase 1 — Config & Docs

- [ ] **1A: Update `docs/configuration.md`** — expand `partitioning_strategy` to list all supported keys with param tables
- [ ] **1B: Update `docs/datasets.md`** — add config snippets showing each partitioner in action (especially Shard, Linear, Dirichlet with different α values). *(This also satisfies the Docs section item "Add JSON config snippets per dataset" — no separate task needed.)*
- [ ] **1C: Add example simulation configs** — create 2-3 preset configs in `config/presets/` demonstrating non-IID scenarios (e.g., `pathological_2class.json`, `dirichlet_heterogeneous.json`, `shard_mcmahan.json`)

### Phase 2 — Frontend Integration

- [ ] **2A: Expand partitioning strategy dropdown** in `NewSimulation.jsx` — show all registered partitioners with human-readable labels
- [ ] **2B: Dynamic param form** — render param inputs based on the selected partitioner's schema (e.g., show `alpha` slider for Dirichlet, `num_classes_per_partition` for Pathological, nothing extra for IID/Linear/Exponential)
- [ ] **2C: Add tooltips/descriptions** — short explanation of each partitioner's behavior to help researchers choose (pull from registry metadata)

### Phase 3 — Visualization & Diagnostics (Optional)

- [ ] **3A: Partition distribution preview** — before running a simulation, show a bar chart of how many samples each client would get (and class distribution per client for label-based partitioners)
- [ ] **3B: Log partitioner choice + params** in simulation output/config.json for reproducibility
- [ ] **3C: Add partition stats to results** — per-client sample counts and label distributions in the results summary

---

## Celery Queue — Remaining Items

> Source: `demo/plans-and-specs/CELERY-QUEUE/`
> Core rework is done (Celery + SSE + StatusTracker, `worker_max_tasks_per_child`, `broker_pool_limit`).
> Ref: [Celery User Guide](https://docs.celeryq.dev/en/stable/userguide/index.html) (v5.5.x)

### Celery Config Hardening

- [ ] Add task time limits to `celery_app.py` — `task_time_limit=7200` (hard kill 2h), `task_soft_time_limit=6900` (cleanup at 1h55m)
- [x] ~~Add Redis memory policy in `docker-compose.yml`~~ — **Done**: `redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru` (docker-compose.yml line 98)
- [ ] Atomic status.json writes — use write-to-temp + rename pattern in `StatusTracker` to prevent corruption on crash

### Queue Reconciliation on Startup

- [ ] Create `intellifl/api/services/queue_reconciliation.py` — scan `out/` for status.json files stuck in `"queued"` with no matching Celery task in Redis, re-submit via `.delay()`
- [ ] Add reconciliation call in FastAPI `lifespan()` startup hook (non-blocking, log-only on failure)
- [ ] Add `POST /api/queue/reconcile` endpoint for manual bulk recovery
- [ ] Add `POST /api/simulations/{id}/requeue` endpoint for single-sim retry (accepts `queued` or `failed` status)
- [ ] Frontend requeue button on stale queued / failed simulation cards (optional)

---

## Docker & Containerization

> Source: `demo/plans-and-specs/CONTAINERIZATION/`
> Ref: [Docker Build Best Practices](https://docs.docker.com/build/building/best-practices/) | [Compose Profiles](https://docs.docker.com/compose/how-tos/profiles/) | [uv Docker Guide](https://docs.astral.sh/uv/guides/integration/docker/)

### uv Docker Best Practices (2026)

Current `Dockerfile` uses `curl | sh` to install uv. Update to match [official uv Docker guidance](https://docs.astral.sh/uv/guides/integration/docker/):

- [ ] **Replace curl installer with distroless copy** — `COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/` (eliminates curl dependency in builder, pinned to minor version)
- [ ] **Add `--compile-bytecode`** to `uv sync` in Dockerfile for faster cold-start in production
- [ ] **Add `.venv` to `.dockerignore`** — prevent local venv from leaking into build context

### Dev/Prod Split Rework

- [ ] Replace `docker-compose.override.yml` with service profiles (`--profile dev` / `--profile prod`)
  - Core services (api, redis, celery-worker, frontend-prod) → no profile (always run)
  - Dev tools (celery-monitor, frontend-dev with Vite) → `profiles: [dev]`
  - Current override uses `build: !reset` to swap the frontend image, which is fragile
  - Ref: [Compose Profiles docs](https://docs.docker.com/compose/how-tos/profiles/)
- [ ] Add `development` target to `frontend/Dockerfile` (multi-target: `development` for Vite dev server, `production` for nginx)

### Docker Image Hardening

- [ ] **Phase 1 (quick wins):** Pin base images by digest for supply chain integrity; add Docker Scout scanning to CI; generate SBOM for current images
- [ ] **Phase 2 (backend prep):** pyproject.toml already has `[dependency-groups] dev` — verify `uv sync --no-dev` excludes all dev deps cleanly; move dataset download from `entrypoint.sh` to build-time; inject git metadata at build time via `--build-arg`
- [ ] **Phase 3 (full migration):** Multi-stage Dockerfile with minimal PyTorch runtime stage; make terminal feature optional; init container for dataset downloads

### Infrastructure Improvements

- [ ] Bake Zensical into a `docs.Dockerfile` using `uv` (not `pip install` on every startup) — current docs container installs via pip each restart, inconsistent with project tooling
- [ ] Reduce API healthcheck `start_period` once dataset download moves out of entrypoint (currently 120s in compose, 60s in Dockerfile — should be consistent)

---

## Attack Visualization & Evaluation

> Source: `demo/plans-and-specs/ATTACK/`
> Attack snapshots frontend fix (Phase 1+2) is done. Items below are unimplemented.

### Composite Attack Visualization (IEEE Quality)

- [ ] Create `ieee_style_constants.py` — IEEE figure specs, colorblind-safe palette, dual PDF/PNG export
- [ ] Add `AttackStageRenderer` ABC + per-attack renderers (noise heatmap, label flip arrow, generic fallback)
- [ ] Add `AttackIntermediateState` dataclass + `apply_poisoning_attack_with_intermediates()` in `poisoning.py`
- [ ] Implement `save_composite_synopsis_v2()` — N+2 column layout: `[Original] → [Attack₁] → ... → [Final]`
- [ ] Wire intermediate state capture through `flower_client.py` → `attack_snapshots.py`

### Domain Entity Evaluator

- [ ] Create `intellifl/evaluation/` module with `DomainEntityEvaluator` class — measures model accuracy specifically on domain vocabulary terms (medical/financial/legal)
- [ ] Create `AttackEffectivenessAnalyzer` — pre/post attack comparison (targeted degradation, collateral damage, attack specificity)
- [ ] Integrate into `FlowerClient.test()` — add `evaluation_domain` param, return `EntityMetrics` alongside loss/accuracy
- [ ] Add domain metrics to experiment results JSON and snapshot HTML reports

### Attack System Improvements

- [ ] Add `snapshot_frequency` config option (e.g., every N rounds) to reduce GPU memory pressure during long simulations
- [ ] Consider additional LLM attack types (gradient inversion, prompt injection) for transformer fine-tuning paths

---

## FL Agent (Future)

> Source: `demo/plans-and-specs/FL_AGENT/`
> This is a multi-phase initiative. No code exists yet.

- [ ] Phase 1: Knowledge extraction — capture experiment hyperparameters/results for AI optimization
- [ ] Phase 2: MCP tools — expose FL operations as tool calls
- [ ] Phase 3: Agent integration — AI-driven experiment suggestions
- [ ] Phase 4: Frontend — agent UI integration
- [ ] AI strategy generation from research papers

---

## Docs

> Source: `demo/plans-and-specs/DOCS/`
> Old `DEVELOPMENT_SETUP.md` was fully stale (referenced deleted scripts/tools) — deleted, not extracted.

- [ ] Audit `zensical.toml` nav against actual `docs/` file structure — ensure new strategies/attacks/datasets are reflected in sidebar
- [ ] Auto-generate `api.md` from FastAPI routers/Pydantic models (or link to `/docs` Swagger endpoint). Ref: [FastAPI Reference](https://fastapi.tiangolo.com/reference/)
- [ ] ~~Add JSON config snippets per dataset in `docs/datasets.md`~~ — Covered by Partitioning System Phase 1B

---

## Code Quality & Refactoring

> Source: `demo/plans-and-specs/gemini-review/`
> Ref: [Ruff](https://docs.astral.sh/ruff/) | [ty](https://docs.astral.sh/ty/) (already configured in pyproject.toml)

- [ ] Break up `FederatedSimulation` god object (691 lines) — extract `StrategyFactory`, `ModelLoader`, or similar focused managers
- [ ] TypeScript migration for frontend — all core files are still `.jsx`, no `.tsx` exists yet
- [ ] Add custom API exception classes (`SimulationNotFoundError`, etc.) instead of generic `Exception` catches in routers
- [ ] Move in-scope Celery imports in routers to FastAPI dependency injection for testability

---

## Future Work

- Player data analysis and visualization
- Implement statistical tracking of token usage and playerbase data comparison
- Statistical evaluation of how users are treating agent / being treated differently