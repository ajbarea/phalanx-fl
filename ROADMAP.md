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

- **2026-05-23** — Modular Partitioning System Phase 0. New `intellifl/dataset_loaders/partitioner_registry.py` carries a string-keyed registry over 13 `flwr_datasets.partitioner` classes (10 net-new wirings on top of the existing iid / dirichlet / pathological / natural_id quartet — `linear`, `exponential`, `square`, `shard`, `continuous`, `grouped_natural_id`, `size`, `inner_dirichlet`, `distribution`). Each registry entry is a per-class builder function that explicitly enumerates the params it reads + defaults, so the surface is auditable from one file. `_require(params, key, strategy)` and `_require_partition_col(col, strategy)` helpers raise uniform `ValueError`s with the strategy name + missing key inline. `FederatedDatasetLoader._create_partitioner` collapsed from a 47-line if/elif chain into a 7-line `partition_col` resolution + `create_partitioner(...)` delegate (natural-id family refuses the label-column fallback). 23 new unit tests in `tests/unit/test_dataset_loaders/test_partitioner_registry.py` cover happy paths, required-param surfaces, partition_by precedence, and the 13-key registry shape. Phase 1 (config + docs) + Phase 2 (frontend dropdown) deferred until first concrete UX surfacing.
- **2026-05-23** — Dataset System Rework Phase 2B (MedMNIST family migration): the 11 MedMNIST keywords (`pneumoniamnist` / `bloodmnist` / `breastmnist` / `pathmnist` / `dermamnist` / `octmnist` / `retinamnist` / `tissuemnist` / `organamnist` / `organcmnist` / `organsmnist`) migrated from the local `ImageDatasetLoader` (pre-partitioned `datasets/<keyword>/client_N/` folders) to `FederatedDatasetLoader` reading `albertvillanova/medmnist-v2` + per-variant subset. New `_build_hf_medmnist_cnn` builder pairs the HF loader with the existing per-keyword `MedMNISTCNN` architecture via `build_cnn_model(keyword)`, so network shape stays identical across the migration. Loader construction extracted into `_build_federated_dataset_loader(keyword, config)` shared with `_build_hf_image_cnn`; same helper also wires JSON's `partition_by` so FEMNIST's eventual natural_id migration is one keyword-tuple change away. Latent bug fixed in passing: builders now read `partitioning_strategy` via `getattr` since `StrategyConfig` carries it as a Pydantic `extra="allow"` attribute that can be absent. Schema test grew two new assertions over `_HF_MEDMNIST_CNN_KEYWORDS` (resolvable transformer + canonical mirror + `_CNN_REGISTRY` coverage). FEMNIST migration deferred — `flwrlabs/femnist` gives 62 classes while `_CNN_REGISTRY["femnist_iid"]` carries `num_classes=10`; the resolution is logged in IMPL.md.
- **2026-05-22** — Dataset System Rework Phase 2B (CIFAR family migration): `_build_hf_image_cnn` rewired from `HuggingFaceImageDatasetLoader` to `FederatedDatasetLoader` for the three keywords in `_HF_IMAGE_CNN_KEYWORDS` (`cifar100` / `cifar10` / `cinic10`). The new loader reads `partitioning_strategy` + `partitioning_params` from `StrategyConfig` instead of hard-coding Dirichlet alpha=0.5; when the config leaves both unset, the builder defaults to `("dirichlet", {"alpha": 0.5})` to preserve the OLD loader's label-skew non-IID shape. CIFAR family's per-keyword JSON (`hf_dataset_path`, `image_column`, `label_column`, `image_transformer`, shape params) is unchanged. All 2211 unit tests pass + lint clean post-migration; `HuggingFaceImageDatasetLoader` is now orphan code (no dispatch caller) awaiting Phase 2E deletion. MedMNIST + FEMNIST migration tiers remain.
- **2026-05-22** — Dataset System Rework Phase 2A (`partition_by` slice + `natural_id` strategy): `FederatedDatasetLoader` gains `partition_by: str | None = None`; Dirichlet / Pathological partitioners use it when set, fall back to `label_column` otherwise. New `natural_id` partitioning strategy wraps `NaturalIdPartitioner(partition_by=...)` — the FEMNIST `femnist_niid` path partitions by `writer_id` (one client per writer, auto-discovered from the column's unique values). Raises `ValueError` if `natural_id` is requested without `partition_by`. Six new tests cover storage, Dirichlet override, default-None fallback, natural_id partitioner creation, and the missing-partition-by guard.
- **2026-05-22** — Dataset System Rework Phase 2A (`image_column` slice): `FederatedDatasetLoader` gains `image_column: str | None = None`; explicit overrides take priority over the auto-detect in `_standardize_columns`, falling back to the ("image", "img") alias scan when set to a missing column or left at default. Reconciles the existing JSON entries that already carry per-dataset `image_column` ("img" for CIFAR variants, "image" for MedMNIST + FEMNIST + CINIC-10) with the loader that previously couldn't read them. Five new tests cover storage, explicit-wins, default-None auto-detect, and missing-column fallback.
- **2026-05-22** — Dataset System Rework Phase 2A (`subset` slice): `FederatedDatasetLoader` gains `subset: str | None = None` and forwards it to `FederatedDataset(subset=...)`, which routes through to `datasets.load_dataset(name=...)`. Required for multi-config HF datasets: MedMNIST v2 (`albertvillanova/medmnist-v2` + per-variant subset) and lex_glue (`coastalcph/lex_glue` + `"ledgar"` / `"eurlex"` subset). None default omits the kwarg entirely so single-config datasets (CIFAR-10, MNIST, FEMNIST) call FederatedDataset with the same minimal signature as before. Four new tests cover storage, default-None omission, and pass-through when set. Phase 2B MedMNIST migration unblocked.
- **2026-05-22** — Dataset System Rework Phase 2A (`image_transform` slice): `FederatedDatasetLoader` gains `image_transform: Callable | None = None` + the new `_TransformedImageDataset` wrapper that applies the transform lazily per `__getitem__`. Default `None` preserves existing behavior; setting a transform routes every sample through the callable after `set_format("torch")`, so future migrations from `HuggingFaceImageDatasetLoader` can hand cifar10 / cinic10 / MedMNIST datasets the same normalization their dedicated transformers carry. Five new tests cover storage, invocation, label pass-through, and inner-dataset immutability.
- **2026-05-22** — Dataset System Rework Phase 2A (cifar10 / cinic10 wiring): `cifar10_image_transformer` + `cinic10_image_transformer` registered with canonical normalization stats (CIFAR-10 `(0.4914, 0.4822, 0.4465) / (0.247, 0.243, 0.262)` from PyTorch community refs; CINIC-10 `(0.479, 0.472, 0.430) / (0.242, 0.238, 0.259)` from BayesWatch/cinic-10 / AntonFriberg pytorch-cinic-10 — both verified via 2026-05 web-search). `_build_cifar100` renamed `_build_hf_image_cnn` (generalised to read every shape param from JSON); LOADER_REGISTRY adds `cifar10` and `cinic10` keys behind a `_HF_IMAGE_CNN_KEYWORDS` tuple. Schema test grew a parallel `test_hf_image_cnn_keywords_have_resolvable_transformer` assertion mirroring the `_LOCAL_CNN_KEYWORDS` contract. Adding the next HF-backed CNN dataset is now JSON + transformer registration — no Python builder code.
- **2026-05-22** — Dataset System Rework Phase 1B (CNN slice): `_CNN_DATASET_TRANSFORMER_MAP` (Python dict, dual source of truth with `huggingface_datasets.json`) deleted; `_build_cnn` now resolves the transformer via `resolve_image_transformer(hf_cfg["image_transformer"])`. Keyword list moved to `_LOCAL_CNN_KEYWORDS` tuple (a smaller surface — the property "uses local `ImageDatasetLoader`" stays in code because it isn't yet expressed in JSON). Schema test extended to assert every CNN keyword has a resolvable non-null transformer name. No behavior change for the 13 affected datasets.
- **2026-05-22** — Dataset System Rework Phase 1A: `config/huggingface_datasets.json` expanded from 5 to 21 entries, covering the full keyword set (`pubmed_classification_20k` / `financial_phrasebank` / `lexglue` / `medal` / `medquad` text + `cifar100` / `cifar10` / `cinic10` / `femnist_iid` / `femnist_niid` / 11 MedMNIST 2D image). Canonical HF mirrors verified via May 2026 web-search (`albertvillanova/medmnist-v2` for MedMNIST configs; `flwrlabs/femnist` + `flwrlabs/cinic10` for Flower-blessed paths; `uoft-cs/cifar10` paralleling the existing cifar100 sibling; `lavita/MedQuAD`). New `tests/unit/test_dataset_loaders/test_huggingface_datasets_config.py` locks the schema: 7 assertions covering modality partition, per-modality required fields, image-shape sanity, MedMNIST channel↔transformer agreement against the medmnist `INFO` dict, and LOADER_REGISTRY ⊆ JSON keys. The dispatch isn't rewired yet — Phase 1B handles that.
- **2026-05-22** — Dataset System Rework Phase 0B+0C: `DynamicCNN._initialize_weights()` matches `cnn_models.py` Kaiming/Xavier convention; `FederatedDatasetLoader.load_datasets()` returns 2-tuple with `num_classes` as instance attribute.
- **2026-05-22** — File-consolidation pass closed out. `simulation_strategies/` (shipped 2026-05-21) and `dataset_loaders/` (shipped 2026-05-22) collapsed their if/elif dispatch chains into registry+factory shape; remaining `*_handlers/` and `client_models/` audited as N/A — no dispatch surface to consolidate.
- **2026-05-21** — `ray_logger.py` audited against Flower 1.28+ native observability. Keep + document the gap: covers strategy-level timing aggregation, classified event taxonomy (CRASH/OOM/TIMEOUT/NODE_DEATH), persistent `ray_simulation_summary_*.json`, and `ray.nodes()` snapshot — none of which Flower provides natively.
- **2026-04-22** — ECOSYSTEM.md dependency audit. Celery+Redis kept (serialisation, not scale); `utils/ray_config.py` removed (Flower 1.28+ handles the 1.9-era quirks natively); `mutmut` + `huggingface_hub[hf_xet]` dropped (aspirational / unmeasured).
- **2026-04-10** — Aggregation math: Krum / Multi-Krum use squared Euclidean per NIPS 2017; Krum / Multi-Krum / Bulyan sum the *k* closest neighbors excluding self; all strategies record `aggregation_participation=1` only when actually included in the round's global update.
- **2026-04-06** — Network models transformer merge: `bert_model_definition.py` + `text_classifier_model.py` → `transformer_models.py`; unified `load_hf_model(model_name, task, ...)` with `mlm` / `seq_cls` task dispatch.

Out-of-scope dispatch sites (deliberately left as-is):
- `simulation_strategies/pid_based_removal_strategy.py` — branches inside the strategy impl, not at the construction seam.
- `config_loaders/validate_strategy_config.py` — per-strategy validation rules; moving these would be decentralization, not the centralization the consolidation pass targeted.

## Dataset System Rework

> Source: `demo/DATASET_REWORK_PLAN.md` (Phases 0-5)
> Ref: [HuggingFace Datasets](https://huggingface.co/docs/datasets) | [flwr-datasets v0.6.0](https://flower.ai/docs/datasets/index.html)

### Phase 0 — Cleanup & Foundation — shipped 2026-05-21/22

0A dropped `its`/`flair`/`lung_photos` (backend + frontend + tests). 0B added `DynamicCNN._initialize_weights()`. 0C normalized `FederatedDatasetLoader.load_datasets()` to 2-tuple with `num_classes` instance attr. 0D skipped — Phase 5 eliminates all transformer files via declarative JSON transforms; renaming first would be wasted churn.

Known carry-overs into Phase 1A: `cifar10` and `cinic10` frontend dropdown entries (need backend `_cnn_loader_map` dispatch first). `text_classification_loader.load_datasets()` still returns a 3-tuple but is slated for Phase 3E deletion — leave as-is.

### Phase 1 — Config Expansion & Config-Driven Dispatch

- [x] **1A:** Expand `config/huggingface_datasets.json` with all 21 datasets — shipped 2026-05-22 (see Recently shipped above).
- [x] **1B (CNN slice, shipped 2026-05-22):** `_build_cnn` reads `image_transformer` from `config/huggingface_datasets.json` instead of the now-deleted `_CNN_DATASET_TRANSFORMER_MAP` Python dict. The CNN keyword tuple stays in code (`_LOCAL_CNN_KEYWORDS`) as the source of truth for "which datasets use `ImageDatasetLoader` + local files" — that property will move into JSON in Phase 2A alongside the migration to `FederatedDatasetLoader`. Schema test extended to assert every `_LOCAL_CNN_KEYWORDS` entry has a resolvable, non-null transformer name.
- [ ] **1B (text + cifar100 collapse):** `_build_cifar100` and `_build_hf_text` both already read the JSON; the remaining work is consolidating them with `_build_cnn` once Phase 2 migrates all image datasets to `FederatedDatasetLoader` (eliminating the dual `ImageDatasetLoader` / `HuggingFaceImageDatasetLoader` split). The dispatch becomes a small per-modality function set rather than per-keyword.
- [x] **2A (cifar10 / cinic10 wiring, shipped 2026-05-22):** transformers registered, JSON entries' `image_transformer` set, `LOADER_REGISTRY` extended via `_HF_IMAGE_CNN_KEYWORDS` tuple (cifar100 / cifar10 / cinic10). `_build_cifar100` renamed `_build_hf_image_cnn` since it's now generic across the HF-backed CNN family.
- [ ] **1B (femnist partitioner):** resolve `femnist_iid` vs `femnist_niid` partitioner from JSON's new `partition_by` field (`writer_id` for niid → `NaturalIdPartitioner`; default IID otherwise). Currently the FEMNIST loader handles both via the existing `_CNN_DATASET_TRANSFORMER_MAP` keyword check; Phase 2 will route through `FederatedDatasetLoader` partitioner registry.
- [ ] **1C:** Use `load_hf_model()` from the Transformer Merge (above) instead of duplicating LoRA/non-LoRA BERT loading here

### Phase 2 — Migrate Image Datasets to FederatedDatasetLoader

- [x] **2A (shipped 2026-05-22):** `FederatedDatasetLoader` gained `subset`, `image_column`, `image_transform`, `partition_by` + `natural_id` strategy across slices #22-#25. `load_dataset_kwargs` deferred until first concrete caller (YAGNI).
- [ ] **2B:** Migrate in tiers: ✅ CIFAR family (cifar100 + cifar10 + cinic10) shipped 2026-05-22; ✅ 11 MedMNIST shipped 2026-05-23; ⏳ FEMNIST (iid/niid — deferred pending 10-vs-62-class decision, see IMPL.md)
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
> 13 of 15 usable partitioners wired via `intellifl/dataset_loaders/partitioner_registry.py` (Phase 0, 2026-05-23). The two vertical partitioners are out of scope; `IdToSizeFncPartitioner` is an abstract-ish parent for Linear/Exponential/Square and intentionally not surfaced.
> Goal: let researchers pick any partitioner from a dropdown and configure its params via the UI.
> flwr-datasets is at v0.6.0; all partitioners inherit from the `Partitioner` ABC.

### Current State

`FederatedDatasetLoader._create_partitioner()` (line ~136) has a hard-coded `if/elif` chain for
`iid`, `dirichlet`, and `pathological`. The same pattern is duplicated in the legacy loaders
(`text_classification_loader.py`, `huggingface_image_dataset_loader.py`, `huggingface_text_dataset_loader.py`).
Once the Dataset System Rework (Phases 2-3) consolidates all loaders into `FederatedDatasetLoader`,
the registry only needs to live in one place.

### Phase 0 — Config-Driven Partitioner Registry — shipped 2026-05-23

- [x] **0A: Create partitioner registry** in `intellifl/dataset_loaders/partitioner_registry.py` — 13 horizontal partitioners wired via per-class builder functions; required-param validation raises clear `ValueError` keyed by strategy + missing key. Vertical partitioners + `IdToSizeFncPartitioner` documented under `OUT_OF_SCOPE_PARTITIONERS`.

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

- [x] **0B: Refactor `_create_partitioner()`** — `FederatedDatasetLoader._create_partitioner` now delegates to `partitioner_registry.create_partitioner` after resolving `partition_col` from `self.partition_by or self.label_column` (natural-id family refuses the label-column fallback). 32 lines of if/elif replaced with a 7-line dispatch.
- [x] **0C: Validation** — required-param surface is enforced per-builder via `_require(params, key, strategy)`; missing keys raise `ValueError` with the strategy name + missing key inline. No centralized JSON-schema validation today — each builder enumerates its own required + defaulted params, which keeps the surface auditable from one file. Pydantic schema layer deferred until Phase 2B's frontend dropdown needs a serializable schema.

### Phase 1 — Config & Docs

- [ ] **1A: Update `docs/configuration.md`** — expand `partitioning_strategy` to list all supported keys with param tables
- [ ] **1B: Update `docs/datasets.md`** — add config snippets showing each partitioner in action (especially Shard, Linear, Dirichlet with different α values). *(This also satisfies the Docs section item "Add JSON config snippets per dataset" — no separate task needed.)*
- [ ] **1C: Add example simulation configs** — 3-5 preset scenarios in `config/scenarios/` (`pathological_2class.json`, `dirichlet_heterogeneous.json`, `shard_mcmahan.json`, `medical_imaging_iid_robust.json`, `medical_imaging_non_iid_robust.json`, `femnist_label_flip_comparison.json`, `heterogeneous_byzantine_worst_case.json`). Each pairs with a sibling `.md` carrying the research question + expected outcomes (strict JSON has no comment syntax). Wire a CLI surface: `intellifl-dev sim --scenario NAME` + `--list-scenarios`, registry at `config/scenarios/registry.json`. Goal: lower barrier to first experiment.

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

- [x] **Task time limits** — `task_time_limit=7200` (hard SIGKILL at 2h) + `task_soft_time_limit=6900` (SoftTimeLimitExceeded at 1h55m for graceful cleanup) added to `celery_app.py` 2026-05-23.
- [x] **Redis memory policy** — `redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru` (docker-compose.yml line 98).
- [x] **Atomic status.json writes** — `StatusTracker._write_status` writes to `.json.tmp` then `replace`s into place; already shipped under `intellifl/utils/status_tracker.py`. The ROADMAP entry pre-dated the implementation.

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

### uv Docker Best Practices (2026) — shipped 2026-05-23

- [x] **Distroless copy** — Dockerfile builder now does `COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/` instead of `curl | sh`. Pinned to a patch version (cross-sister audit catches drift); curl removed from the builder's apt install set (runner stage still needs it for entrypoint.sh dataset download + healthcheck).
- [x] **`--compile-bytecode`** added to `uv sync` in Dockerfile builder for faster Python cold-start in production.
- [x] **`.venv` in `.dockerignore`** — already present at line 40; ROADMAP entry pre-dated the addition.

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