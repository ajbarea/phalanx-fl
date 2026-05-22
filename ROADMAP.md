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

## Dependency hygiene

Captured from the ECOSYSTEM.md audit (2026-04-22). Decisions reached
during that pass are logged inline; remaining items need real work
before they close.

### Resolved (2026-04-22)

- **Celery+Redis stays.** The load-bearing use case is *serialisation*,
  not scale: without it, concurrent frontend users clicking "run sim"
  would crash the box. Celery with single-worker concurrency enforces
  "one sim at a time, durable queue across restarts". BackgroundTasks
  wouldn't survive a server restart mid-queue, and a bare semaphore
  wouldn't either.
- **Ray stays as a hard dep; `utils/ray_config.py` removed.** The
  platform-workaround shim covered Flower 1.9 quirks that Flower 1.28+
  now handles natively. `simulation_runner` and `utils/ray_logger`
  still import Ray directly; those stay.
- **`mutmut` dropped.** Aspirational tooling; no cadence defined, no
  runs recorded. `uv add --group dev mutmut` revives it if and when a
  real schedule materialises.
- **`huggingface_hub[hf_xet]` dropped.** The Xet-protocol boost is
  unmeasured for our download pattern (MNIST + CIFAR-10 + FEMNIST +
  maybe a Llama checkpoint) and the motivation was curiosity rather
  than observed savings. Re-add if a real bottleneck shows up.

### Resolved (2026-05-21)

- **`utils/ray_logger.py` evaluation (369 lines).** Re-read against
  Flower >= 1.28 native observability (web-search verified, May 2026).
  Verdict: **keep, document the gap**. Flower covers driver-side
  worker log streaming + per-client `client_resources` + raw OOM
  propagation, but does not provide (1) strategy-level timing
  aggregation — `RaySimulationMonitor.record_round` works at
  phalanx-fl's multi-FL-round "strategy" granularity which Flower
  doesn't know about; (2) classified event taxonomy
  (`CRASH / OOM / TIMEOUT / NODE_DEATH`) for structured grepping;
  (3) a persistent `ray_simulation_summary_<id>.json` artifact for
  post-mortem; (4) closing cluster-health snapshot via `ray.nodes()`.
  Added module-header docstring naming each unique surface vs the
  shadows. No code deletion warranted; the module earns its 369 lines.

### Still open

- **File-consolidation pass (in progress)** — apply the `network_models`
  precedent to the other one-class-per-file packages. Each is a
  standalone refactor; all follow the same shape (registry dict +
  dispatch function). Big diff, small semantic change.
  - [x] `intellifl/simulation_strategies/` — shipped 2026-05-21.
    `__init__.py` now exports `build_strategy()` + `STRATEGY_REGISTRY`;
    the 80-line `if/elif` dispatch in
    `federated_simulation._assign_aggregation_strategy` collapsed to a
    single `build_strategy()` call. Strategy class files unchanged
    (each is too substantial to inline cleanly). PID variants
    consolidated into one builder reading the variant off the keyword.
  - [x] `intellifl/dataset_loaders/` — shipped 2026-05-22.
    `__init__.py` exports `build_dataset_loader_and_model()` +
    `LOADER_REGISTRY` + the `get_hf_dataset_config` /
    `resolve_image_transformer` helpers that used to live in
    `federated_simulation`. The 170-line `if/elif` chain in
    `_assign_dataset_loaders_and_network_model` collapsed to one
    factory call returning `(loader, model)`. Also collapsed three
    near-identical LLM-construction blocks (medquad / HF text / medal)
    into one private `_build_llm_model()` helper. Tests now patch
    `intellifl.dataset_loaders.{ImageDatasetLoader, MedQuADDatasetLoader,
    build_cnn_model, load_model}` instead of the prior
    `intellifl.federated_simulation.*` paths. Cleanup follow-on:
    `config/test_hf_datasets.py` delegates to
    `resolve_image_transformer` instead of carrying its own stale
    copy of the transformer registry (Phase 0A drift fix).
  - [N/A] `intellifl/*_handlers/` and `intellifl/client_models/` —
    audited 2026-05-22 after `simulation_strategies` and
    `dataset_loaders` landed. None of these packages carries a
    keyword-dispatch chain in `federated_simulation` or anywhere else:
    `dataset_handlers/` is a single `DatasetHandler` class,
    `output_handlers/` is one `DirectoryHandler` + utility plotting
    functions, `client_models/` is one `FlowerClient`. `attack_handlers/`
    was a ROADMAP placeholder that doesn't exist in the tree. The
    registry+dispatch pattern doesn't apply — no consolidation surface
    to collapse. File-consolidation pass closes out here; if a future
    dispatch surface accretes in any of these packages, file a new
    item rather than reviving this one.

The two remaining keyword-dispatch sites in the codebase are
deliberately out of scope:
  - `simulation_strategies/pid_based_removal_strategy.py` branches
    on the PID variant inside the strategy implementation, not at the
    construction seam.
  - `config_loaders/validate_strategy_config.py` dispatches
    per-strategy validation rules. Moving these to be co-located with
    each strategy builder is a different shape of refactor
    (decentralization, not the centralization the consolidation pass
    targets); revisit only if validation rules start drifting from
    builder expectations.

## Dataset System Rework

> Source: `demo/DATASET_REWORK_PLAN.md` (Phases 0-5)
> Ref: [HuggingFace Datasets](https://huggingface.co/docs/datasets) | [flwr-datasets v0.6.0](https://flower.ai/docs/datasets/index.html)

### Phase 0 — Cleanup & Foundation

- [x] **0B: Add `_initialize_weights()` to `DynamicCNN`** — shipped 2026-05-22.
  Matches the established `cnn_models.py` convention: Kaiming uniform on
  Conv2d (`nonlinearity="relu"`), Xavier uniform on Linear, zeros on
  biases. Closes the silent-default gap where `DynamicCNN` (used by the
  cifar100 path) leaned on PyTorch's `kaiming_uniform_(a=sqrt(5))`
  default — which is also Kaiming but with a different fan mode that
  isn't ReLU-tuned. Verified by two new tests in
  `test_dynamic_cnn.py::TestDynamicCNNInitialization` asserting
  biases-zero + non-zero weights post-construction. 2180 unit tests
  pass.
- [x] **0C: Normalize `FederatedDatasetLoader.load_datasets()` return type**
  — shipped 2026-05-22. Returns `(trainloaders, valloaders)` only;
  `num_classes` is stored as `self.num_classes` (initialized `None`,
  populated by `_detect_num_classes` inside `load_datasets`). Brings
  the loader into line with `image_dataset_loader`,
  `medquad_dataset_loader`, `huggingface_image_dataset_loader`, and
  `huggingface_text_dataset_loader` (all 2-tuple). The 3-tuple form
  was a latent footgun: production call site
  `federated_simulation._assign_dataset_loaders_and_network_model`
  already unpacks 2 values, so any future routing of
  `FederatedDatasetLoader` through the factory would have thrown
  `ValueError: too many values to unpack`. Four call sites in
  `test_federated_dataset_loader.py` updated; new `loader.num_classes
  is None` post-construction assertion added. `text_classification_loader`
  also returns a 3-tuple, but it's slated for deletion in Phase 3
  (Dataset System Rework Phase 3E) — not normalizing now to avoid
  wasted churn.
- [x] **0A: Drop `its`, `flair`, `lung_photos`** — shipped 2026-05-21.
  Deleted 3 transformer files + 3 GPU sim configs, removed from
  `federated_simulation.py` (imports, registry, dispatch),
  `network_models/__init__.py` (3 dataset configs),
  `config_loaders/validate_strategy_config.py` (validation enum),
  `frontend/src/constants/datasets.js`, and
  `frontend/src/utils/configValidation.js` (modality maps + pattern
  list — also corrected a miscategorization of `flair` as a text
  dataset). Test cleanup: 130 reference touchpoints across the test
  suite — placeholder `dataset_keyword: "its"` mocks rewritten to
  `bloodmnist`, parametrize rows for the dropped datasets dropped, a
  `test_high_resolution_datasets` helper that only had 224×224
  coverage retired (no remaining 224×224 datasets in the supported
  set). 2178 unit + 151 integration tests pass; lint clean.
  **`cifar10` / `cinic10` deliberately NOT added to frontend** — backend
  has no `_cnn_loader_map` dispatch for either; adding to frontend
  alone would create dead UX. `pubmed_classification_20k` WAS added
  to frontend (backend already supports it via the text-dataset path).
  Filed `cifar10` and `cinic10` frontend additions as part of Phase 1A
  (config expansion) where the backend wiring lands first.
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
- [ ] **1C: Add example simulation configs** — create 3-5 preset configs in `config/scenarios/` demonstrating researcher-grade scenarios. Original three: `pathological_2class.json`, `dirichlet_heterogeneous.json`, `shard_mcmahan.json`. Audit-of-audit additions (2026-05-21, Copilot-derived): `medical_imaging_iid_robust.json` (MedMNIST IID + Krum/Bulyan/RFA, "does robustness come free on IID data?"), `medical_imaging_non_iid_robust.json` (MedMNIST non-IID + Krum/Bulyan/Trust, "how does robustness degrade with heterogeneity?"), `femnist_label_flip_comparison.json` (FedAvg/Krum/Trust under 20% label-flip), `heterogeneous_byzantine_worst_case.json` (FEMNIST non-IID + gradient scaling + label-flip on overlapping clients). Each scenario file is strict JSON; explanatory text + research question + expected outcomes live in a sibling `.md` alongside (don't use JSON5/JSONC — `json.load` rejects comments). Pair with a CLI surface: `intellifl-dev sim --scenario NAME` + `--list-scenarios`, registry at `config/scenarios/registry.json`. Trigger: lower barrier to first experiment; newcomers see what's possible before wrestling with config.

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
- [ ] **Preserve per-attack specialized visuals in composites** — `save_visual_snapshot` (`attack_snapshots.py:333-360`) emits `composite_synopsis.png` for list configs but `label_flipping_visual.png` (and other per-type visuals) are silently dropped: `extract_attack_type` (`_helpers.py:8-15`) joins composite types with `_` (e.g. `label_flipping_gaussian_noise`), so the per-type branch (`if attack_type == "label_flipping"`) never matches. Trigger: composite runs should still emit each attack's specialized visual alongside the synopsis.

### Domain Entity Evaluator

- [ ] Create `intellifl/evaluation/` module with `DomainEntityEvaluator` class — measures model accuracy specifically on domain vocabulary terms (medical/financial/legal)
- [ ] Create `AttackEffectivenessAnalyzer` — pre/post attack comparison (targeted degradation, collateral damage, attack specificity)
- [ ] Integrate into `FlowerClient.test()` — add `evaluation_domain` param, return `EntityMetrics` alongside loss/accuracy
- [ ] Add domain metrics to experiment results JSON and snapshot HTML reports

### Attack System Improvements

- [ ] Add `snapshot_frequency` config option (e.g., every N rounds) to reduce GPU memory pressure during long simulations
- [ ] Consider additional LLM attack types (gradient inversion, prompt injection) for transformer fine-tuning paths
- [ ] **Audit attack-snapshot filename collisions** — verify `client_X/round_Y/{attack_type}_visual.png`, `*_metadata.json`, `*_weight_metadata.json`, summary, and pickle paths cannot collide when the same `output_dir` is reused, when composite `extract_attack_type` concatenations clash with single-attack names, or when the same client/round is re-snapshotted. Trigger: open question whether comparison view / confusion matrix / metadata / summary / visual / pickle artifacts overwrite each other.
- [ ] **Cross-modal attack compatibility validation** — `validate_strategy_config.py:449-478` rejects same-type overlap and `preserve_dataset` / `strict_mode` mode-incompatibilities, but doesn't reject nonsensical stacks like `gaussian_noise` on tokenized text data. Add modality-aware validation that pairs each scheduled attack against the model/dataset modality (image vs text) and rejects mismatches. Trigger: developers stacking attacks that silently no-op on the wrong modality.
- [ ] **Document attack-snapshot file emission contract** — codify which files (`{attack_type}_visual.png`, `composite_synopsis.png`, `*_metadata.json`, `*_weight_metadata.json`, summary, pickle) `save_visual_snapshot` (`attack_snapshots.py:291-360`) is expected to emit under which conditions (4D image vs text, single vs composite, snapshot_frequency gate). Repro: `out/01-09-2026_18-16-07/attack_snapshots_0/client_1/round_7/` is missing `label_flipping_visual.png` despite round 7 containing label flipping. Trigger: undocumented per-round artifact set surprises consumers and breaks downstream HTML reports.
- [ ] **Deterministic label-flip permutation per client** — `apply_label_flipping` (`intellifl/attack_utils/poisoning.py:50`) calls `torch.randperm(num_classes)` with no seed, so every invocation within a single malicious client draws a fresh permutation: each batch sees a different "0→4, then 0→7, then 0→2" mapping rather than a stable flip. The model treats this as random label noise and averages it out, so dynamic `attack_schedule` runs converge close to clean baselines while the static filesystem-rename path (which corrupts the dataset once) shows the expected divergence. Thread `client_id` through `apply_poisoning_attack` (`poisoning.py:596`) and `_dispatch_label_flipping` (`poisoning.py:445`) so each malicious client gets one fixed permutation seeded by its ID. Trigger: dynamic vs static produce visibly different per-client loss curves on the same config; without this, `attack_schedule`-based experiments silently understate attack severity.

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

## Privacy

> Source: 2026-05-21 audit-of-audits (2026-05-21 audit-of-audits review). Byzantine robustness + DP is the 2026 gold-standard pairing; phalanx today exposes neither DP knobs nor budget tracking. Ref: [Fed-BioMed Opacus tutorial](https://fedbiomed.gitlabpages.inria.fr/latest/tutorials/security/differential-privacy-with-opacus-on-fedbiomed/) (canonical client-side DP pattern, 2026).

- [ ] **Client-side DP via Opacus integration** — add optional `differential_privacy` block to `shared_settings` exposing `target_epsilon`, `target_delta`, `noise_mechanism` (gaussian/laplace). Wire Opacus's `PrivacyEngine` into the client training loop; log per-round consumed epsilon budget alongside loss/accuracy. Trigger: many FL deployments need both robustness and DP — phalanx covers robustness today, DP is the missing axis. Tier 2 medium-lift; pairs with vFL's server-side DP exploration as a complementary research story (client-side here, server-side aggregation kernel there).
- [ ] **Federated unlearning research lane** — benchmark gradient-ascent vs knowledge-distillation vs retraining-without unlearning methods across phalanx's 9-strategy matrix. Refs: [arXiv 2512.23171](https://arxiv.org/abs/2512.23171) (primal-dual VFL unlearning, 2026), [Nature Scientific Reports 2026](https://www.nature.com/articles/s41598-026-51158-x) (decoupling forgetting and preservation via KD), [arXiv 2504.05822](https://arxiv.org/pdf/2504.05822) (negated pseudo-gradients). Research-tier — file as a Tier 3 milestone, not Phase 1 work; position phalanx as the standard sandbox for federated-unlearning evaluation.

---

## Fairness

> Source: 2026-05-21 audit-of-audits. Phalanx has MedMNIST + medical imaging in the dataset list but no fairness instrumentation. Per 2026 ML-culture norms, demographic-aware metrics are first-class — research that ignores them is increasingly hard to publish.

- [ ] **Demographic-aware accuracy reporting** — extend `shared_settings` with a `fairness_evaluation` block: `demographic_groups`, `metrics` (`accuracy_per_group`, `equalized_odds`, `demographic_parity`). Per-strategy comparison: "does Krum amplify bias vs FedAvg under label-flip?" Wire into existing report-generation surface. Trigger: medical-imaging FL needs fairness data; today phalanx reports only aggregate accuracy.
- [ ] **Stratified attack selection** — extend attack_schedule's `selection_strategy` beyond exact-IDs / count / proportion to include `stratified_by_label_imbalance` (entropy or KL-divergence against global label distribution). Attackers don't choose victims uniformly; stratified selection mimics realistic adversarial behavior. Cheap to ship (one round of `scipy.stats.entropy` per client during setup, cached). Pairs with the fairness work above — biased attacks should be detectable in demographic-aware metrics.

---

## Audit-of-audit follow-ups (2026-05-21)

> Source: 2026-05-21 audit-of-audits review (deleted after extraction). Items that survived audit-of-audit verdict review but don't fit the existing Privacy / Fairness / Dataset / Attack sections cleanly.

- [ ] **Adaptive strategy selection (research-tier)** — add an `adaptive_mode` block to strategy configs allowing mid-experiment pivoting based on observed metrics (e.g. `pivot_metric: accuracy`, `fallback_strategy: krum`, `fallback_threshold: 0.50`, `check_every_rounds: 5`). Log the switch decision with reason ("accuracy < 0.50 at round 5, switched FedAvg → Krum") so the data is mineable later for a strategy-predictor follow-up. Position phalanx as a *learning* tool, not just a comparison tool. Tier 2 medium-lift.
- [ ] **Real-time performance profiling per strategy** — augment existing accuracy/loss reporting with compute-time-in-aggregation-kernel (CPU cycles / GPU memory), per-client bandwidth (bytes in/out), rounds-to-target-accuracy. Useful for edge-deployment readers who care about latency/bandwidth budgets, not just convergence. Render as a strategy report card alongside the convergence curves. Tier 1 low-lift.
- [ ] **Auto-comparison report generation across strategies** — after a multi-strategy run completes, generate an HTML report bundling: summary table (loss / accuracy / robustness / compute time), overlaid convergence curves, attack-impact-delta analysis, hyperparameter-sensitivity violin plots, Pareto-frontier recommendation (best-accuracy / best-latency / best-robustness). Researchers spend ~30% of post-experiment time on hand-rolled report generation; this closes the loop. Tier 1 medium-lift.
- [ ] **`--export-deployment` for Flower production configs** — phalanx is already Flower-based, so this is not a "translate to Flower" task; it's "scrub sim-only assumptions (mock dataset paths, fake clients) and emit a Flower config that needs only real-data + auth glued in." Closes the sim → deployment gap. Tier 1 medium-lift.

---

## Cross-sister polish (2026-05-21)

> Source: 2026-05-21 audit-of-audits review "Insights worth keeping" — ecosystem-narrative items that span all the active sisters. Mirror items live in the matching ROADMAP for the other sisters.

- [ ] **Add `## Sister ecosystem` block to README** — name the other active sisters (Kourai Khryseai, VelocityFL, ajbarea.github.io, techne) with their roles (innovation / research / performance / governance / visibility) and one-line links. Today sister cross-references happen only via dev-infra (techne.toml, skill-context) and never at the narrative layer; the LDQIS lab page already tells this story coherently but the sisters themselves do not.
- [ ] **Cite Project Glasswing posture in README security framing** — Anthropic's April 2026 trustworthy-software initiative (AWS / Apple / Google / JPMorganChase / NVIDIA / Palo Alto Networks / Linux Foundation + 40 more) sets the 2026 frame for Byzantine-robust FL work. One-paragraph mention is enough; don't over-claim. Ref: <https://www.anthropic.com/glasswing>.
- [ ] **Stale-assumption audit (whenever the FL ecosystem moves)** — Krum / Multi-Krum / Bulyan defenses were calibrated to specific attack assumptions; mock-client patterns and the (now-removed) `ray_config` shim were shaped around Flower 1.9-era API quirks; transformer-loader paths encode a particular HF Transformers generation. When Flower / a new aggregation paper / a new HF Transformers major / a new defense technique lands, audit which scaffolding exists to compensate for a now-closed gap and collapse what no longer earns its keep. **Inverse of speculative-generality YAGNI:** YAGNI polices new code being written; this audit polices existing code as the ecosystem moves around it. Captured as a recurring invariant — fires on external events, not on a fixed schedule. `research(2026-05)`: pattern adapted from [Anthropic engineering, Managed Agents](https://www.anthropic.com/engineering/managed-agents) (*"harnesses encode assumptions about what Claude can't do on its own. However, those assumptions need to be frequently questioned because they can go stale."*); mirrored cross-sister from kourai-khryseai's M22-M25 platform-reliability sweep.

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
- [ ] **Add ArKrum regression baselines** — `arkrum_strategy.py` and configs `femnist_arkrum_baseline.json` / `femnist_arkrum_vs_labelflip.json` are shipped, but neither has a fixture in `tests/fixtures/baselines/`, leaving ArKrum the lone aggregation strategy without regression coverage (vs Krum/MKrum/Bulyan/RFA/TrimMean/Trust/PID-x4 all baselined). Generate and commit both `.baseline.json` files. Trigger: prevent silent ArKrum drift; close coverage asymmetry surfaced from a stale 2026-01-18 batch log.
- [ ] **Strategy-aware termination math constraints** — `TerminationHandler.should_terminate` (`intellifl/simulation_strategies/termination_policies.py:108`) enforces generic min-client thresholds but doesn't know each strategy's mathematical lower bound (Krum n ≥ 4f+3, Bulyan stricter, MultiKrum n ≥ k). Plumb each strategy's bound into the handler so removal that would break aggregation triggers termination rather than silent NaN/divide-by-zero. Trigger: math constraints reached should stop, not corrupt.
- [ ] **Surface termination events in experiment output** — `TerminationHandler.get_termination_summary()` returns `terminated_early`/`termination_round`/`termination_reason`/`termination_policy` but the dict isn't threaded into `out/<run>/summary.json`, snapshot HTML, or the accuracy/loss plots. Wire it so the researcher sees "terminated round 7: GRACEFUL hit 0 clients" without grepping logs. Trigger: UX must make removal failure visible.
- [ ] **Frontend alerts + plot annotation for early termination** — surface a toast/alert in the React UI when a run terminates early under a removal policy, and add a vertical marker / shaded region at the termination round on the accuracy/loss plots with the reason. Trigger: researchers should see "removal gone too far" at a glance, not as a status-code surprise.
- [ ] **Convert removal-config warnings to hard rejections** — `validate_removal_configuration` (`intellifl/config_loaders/validate_strategy_config.py:581-622`) appends warnings for `begin_removing >= num_rounds` and `STRICT + min_fit==num_clients` then proceeds. Repo owner prefers stop-before-start over silent waste of GPU/LLM training time on a misconfigured run. Promote both to `raise ValidationError` with concrete fix messages, matching the strict_mode+remove_clients rejection pattern already at line 624. Trigger: stop the experiment, don't mutate the researcher's config.
- [ ] **Reject ambiguous static/dynamic attack configs** — `validate_strategy_config.py:480-489` rejects `preserve_dataset + attack_schedule`, but a config with both `num_of_malicious_clients > 0` / non-null `attack_type` (static, filesystem-poisoning path) AND a non-empty `attack_schedule` (dynamic, in-memory path) silently passes — the merge fix (commit `f875d4ba0`) settled which value wins, but the deeper ambiguity remains. Add `_validate_attack_schedule` rejection requiring `attack_type: null` and `num_of_malicious_clients: 0` when `attack_schedule` has entries. Trigger: "fields bleed between strategies unexpectedly"; aligns with stop-before-start preference.
- [ ] **Stop button doesn't actually halt a running simulation** — frontend "Stop" control reported as non-functional once a sim is in flight; need to wire it to a backend cancellation path (Celery revoke + Ray actor shutdown) and reflect the `stopped` state in the UI. Trigger: researchers expect Stop to mean stop, not "request that hangs in pending."
- [ ] **Frontend integrated terminal not showing repo scripts** — the embedded terminal (Ctrl+\`) starts in a context where `clean.sh` and other root-level scripts are invisible; suspect uid/working-dir mismatch (running as `appuser` inside the container, no shell rc loaded). Either pin the cwd to the project root, source the venv on shell start, or document the difference vs. the host terminal. Trigger: researcher can't run dev scripts from the panel that's supposed to support exactly that.
- [ ] **Inconsistent loading-state copy across simulation result tabs** — when a sim is in progress, Insights shows a badge ("Insights will be generated once the simulation completes…"), Plots shows plaintext ("No plot data available"), Attacks shows another badge ("Attack snapshots will be available once the simulation completes."), Metrics shows a spinner + "Metrics will appear as the simulation progresses…". Pick one loading-state component (skeleton vs. badge vs. spinner) and one copy template. Trigger: the four tabs look unrelated during the most-watched moment of a researcher's workflow.
- [ ] **Dark-mode background brightness regressions** — several panels are too bright in dark mode after recent theme changes; needs an audit pass against the dark-mode token palette. Trigger: usability regression in the theme researchers actually use during long sessions.
- [ ] **Preset card tag taxonomy** — preset card tags drift across new vs. legacy cards; `Showcase` may not deserve its own tag. Pick a closed vocabulary (e.g., `baseline`, `defense`, `attack`, `nlp`, `multi-attack`) from looking at `frontend/src/constants/presets.js` + `config/simulation_strategies/testing/`, apply consistently. Trigger: tags currently feel ad-hoc and don't help filtering.
- [ ] **Token Replacement attack viz: tab content + layout** — in the Attacks tab for `token_replacement` runs, the 🖼️ Samples and 📝 Token Diff tabs render the same content; Original-on-top / Poisoned-on-bottom should be side-by-side (Original left, Poisoned right) so metrics fit in one row; the "Understanding Attack Snapshots" caption is also leaking into both tabs. Trigger: the duplication makes the UI look broken even when the data is right.
- [ ] **Verify `lint` Makefile target scope** — older note flags `lint` as only running against `tests/`. Confirm the current `intellifl-dev lint` (`Makefile:58`) actually checks `intellifl/`, `frontend/src/`, and `scripts/`, not just tests. Trigger: silent gap if lint is scoped wrong; quick verify before next CI run.
- [ ] **Native-Windows / native-macOS support pass** — orchestration is already in a Python CLI (`intellifl-dev`, every `Makefile` target dispatches `@$(UV_DEV) <cmd>`), so the architecture is fine. What's still platform-fragile: (a) `Makefile:101-105` uses `tail` directly for `logs` / `logs-tail`, which fails outside Git Bash / WSL on native Windows — replace with a Python `intellifl-dev logs [--follow]` subcommand; (b) audit `intellifl-dev` console output for UTF-8 / emoji handling on `cp1252` Windows terminals (per `tests/common.py`'s existing UTF-8 setup); (c) add CI matrix for `windows-latest` + `macos-latest` + `ubuntu-latest` so portability is enforced, not assumed. Trigger: team uses Macs; today everything works in Git Bash but break on cmd/PowerShell, and there's no CI signal preventing regressions.
- [ ] **Frontend live hardware utilization HUD** — researcher-facing CPU / GPU / memory readout in the simulation dashboard so long-running runs surface resource pressure without a terminal `nvitop`. Trigger: GPU sims fail late and silently when memory pressure hits; visibility helps catch it earlier.
- [ ] **`CITATION.bib` generation per output run** — pair with the existing `MANIFEST.json` (`intellifl/utils/reproducibility.py:114`) so each run is self-citing. IEEE/ACM artifact-evaluation guides expect a `CITATION` alongside `MANIFEST`. Trigger: research-artifact polish; closes part of the "experimenting with IEEE artifact best practice" claim AJ has already made externally.
- [ ] **Output directory IEEE-artifact restructure** — `out/<run>/` is currently flat (config + CSVs + PDFs + logs + `MANIFEST.json` all at root). Restructure into `config/`, `data/{metrics,attack_analysis}/`, `visualizations/{accuracy,loss,removal,analysis}/`, `logs/`, `latex/`, `reports/`; keep `MANIFEST.json` + `status.json` + (planned) `CITATION.bib` + `README.md` at run root. Add per-run `README.md` with quick stats, key findings, file-organization map, and reproducibility metadata (git commit, system info, config checksum). Trigger: aligns with FAIR + IEEE artifact-evaluation badge criteria ("Available", "Reusable"); pairs with the `CITATION.bib` item above and the existing `MANIFEST.json` infra.
- [ ] **Session history persistence — Postgres + SQLModel + asyncpg** — currently no DB layer for per-user session history beyond Redis-via-Celery for live queue state. Add `postgres:17-alpine` as a Docker Compose service (separate volume), use SQLModel + asyncpg from the FastAPI backend so saved configs, run history, comments, and any future user-scoped artifacts are queryable. Standard FastAPI 2026 setup: `postgresql+asyncpg://...` URL, async session factory, `init_db()` on startup. Trigger: capstone-era session retention story — Redis is fine for ephemeral queue state but loses everything on restart; researchers want runs queryable across sessions.
- [ ] **Comments cleanup audit + linting silence-tag review** — sweep codebase for direct references to planning docs in comments (e.g. `# Phase C9`, spec-step labels) that leaked from spec implementation; separately, audit existing `# noqa: ...` / `# type: ignore` silence tags so each represents a real exemption rather than convenience suppression. The WHAT-comment side is `techne:deslop` skill territory; the silence-tag side is its own `ruff`/`ty` sweep. Trigger: comment hygiene before paper-submission code review; closes "1. comment cleanup is absolutely necessary…" from the polish backlog.
- [ ] **Queue UX: unify "View Global Queue" and "View Queue Status" routes** — dashboard surfaces a "Simulation in progress…" banner with a `View Global Queue` button that lands on `🧪 Experiment Queue`; the new-simulation page shows the same banner with a `View Queue Status` button that lands on `⏳ Experiment Queue Status`. These are two different pages reached via two different button labels for what looks like the same intent. Pick one canonical queue page (likely merge into a single `Experiment Queue` view with status panel) and route both buttons + label them consistently. Trigger: identical-looking buttons should not lead to different pages.

---

## Future Work

- Player data analysis and visualization
- Implement statistical tracking of token usage and playerbase data comparison
- Statistical evaluation of how users are treating agent / being treated differently