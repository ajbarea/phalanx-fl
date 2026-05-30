# Phalanx — Active TODO

Extracted from planning docs across `demo/`, root, and `.kiro/`. Each item references
its source doc. Items already implemented in source code have been removed.

**Authoritative References** — always check these for current best practices:
- [Flower Framework](https://flower.ai/docs/) | [Flower Datasets](https://flower.ai/docs/datasets/index.html) | [Partitioners Tutorial](https://flower.ai/docs/datasets/tutorial-use-partitioners.html)
- [Docker Build Best Practices](https://docs.docker.com/build/building/best-practices/) | [Compose Profiles](https://docs.docker.com/compose/how-tos/profiles/)
- [uv](https://docs.astral.sh/uv/) | [uv Docker Guide](https://docs.astral.sh/uv/guides/integration/docker/) | [Ruff](https://docs.astral.sh/ruff/) | [ty](https://docs.astral.sh/ty/)
- [Celery User Guide](https://docs.celeryq.dev/en/stable/userguide/index.html)
- [FastAPI Reference](https://fastapi.tiangolo.com/reference/) | [HuggingFace Docs](https://huggingface.co/docs)

---

## Rebrand: InteFL / IntelliFL → Phalanx (de-fork) — display rebrand shipped 2026-05-27

> Decision 2026-05-27 (AJ): phalanx-fl has diverged far enough from the team's **InteFL**
> RIT-capstone fork that it is its own project, not a fork. The **user-facing** brand is now
> **Phalanx** everywhere; the internal Python package keeps the name `intellifl` (see "Deliberately
> kept" — the package rename was considered and declined).

**Shipped — display de-brand (2026-05-27):** every `IntelliFL` / `InteFL` display string → **Phalanx**
across README, `docs/**` prose, `frontend/` (`index.html` `<title>`, `App.jsx` logo alt, assistant adapter),
the FastAPI app (`title="Phalanx API"`), dev-CLI `--help` text + script banners (setup / clean / validate /
upgrade), `Dockerfile` + `frontend/Dockerfile` OCI labels, and the `Makefile` / `.shellcheckrc` / `.env.example` /
`IMPL.md` headers. Verified: lowercase-`intellifl` count unchanged (1037, package untouched); no test asserts
the old brand strings; `make lint` green. The generated `CITATION.bib` was **left crediting the team framework** —
see "Preserve" below.

**Deliberately kept — NOT drift, do not re-flag:** the package rename was **declined** (AJ, 2026-05-27). The
internal identifier `intellifl` is invisible to users, and a ~1037-reference rename (package dir, every import,
`tests/`, `pyproject.toml` `name`, the `intellifl-dev` console script) is high-risk for zero user-visible gain.
These stay as-is on purpose: the `intellifl/` package + `intellifl-dev` CLI, the `--intefl-*` CSS variables in
`docs/stylesheets/extra.css` (awaiting a from-scratch stylesheet rewrite), and `sonar.projectKey=fl-execution-framework`.
Repo = `phalanx-fl`, brand = "Phalanx", package = `intellifl` is a normal and fine split.

**Preserve (lineage / correct attribution — never rebrand):** `docs/research/rit-capstone-2025-intellifl/`, the
capstone nav label in `zensical.toml`, and the "IntelliFL predecessor" prose in `docs/research/index.md` document
the project's *origin* as the RIT IntelliFL/InteFL capstone. **Generated `CITATION.bib` keeps `author = {IntelliFL
Execution Framework}` + the team repo `dmitrykoro/fl-execution-framework`** (AJ, 2026-05-27): that is the real,
team-published framework the experiments actually run on, and there is no separate Phalanx paper — so crediting
IntelliFL is the scholarly-correct attribution, not fork residue. The de-fork story is "Phalanx grew out of the
InteFL capstone," not "InteFL never existed."

---

## Recently shipped

One-line per item, newest first. Detail lives in git history; entries here
keep durable design notes and invariants only.

- **2026-05-29** — **README/docs claim guard (`scripts/check_readme_claims.py`)**. A drift audit found three stale README claims with no gate behind them: the Flower badge (`v1.26.1` while pyproject pinned `flwr>=1.28`), the Python badge (`3.11+` vs `requires-python >=3.12`), and "9 Aggregation Strategies" (the `STRATEGY_REGISTRY` has 10 distinct builders; the roster omitted Multi-Krum-based removal). Fixed the prose, then added a deterministic CI guard (runs in the Security Audit job) asserting the strategy count (`len(set(STRATEGY_REGISTRY.values()))`), attack count (`len(DATA_ATTACK_TYPE_NAMES)+len(WEIGHT_ATTACK_TYPE_NAMES)`), and the Python/Flower badges against their source of truth in code + `pyproject.toml`, across README and `docs/index.md`. Registry documented under `## fragile_docs` in skill-context. research(2026-05): deterministic assertion over LLM-based doc-drift detection for exact counts/versions — exact-match claims want a reproducible gate, not a probabilistic check; the count gate also flags when the manually-maintained roster *list* needs an update.
- **2026-05-28** — **Interactive-plot termination marker + toast (React)**. The Plots tab now surfaces early termination: `save_plot_data_json` includes the `termination` summary in `plot_data_<n>.json` (served straight through `StrategyPlotData.data`), and `InteractivePlots` reads `plotData.termination` to fire a sonner `toast.warning` on load and draw an amber dashed `ReferenceLine` at the termination round — on both the single-metric chart and every synchronized compare panel (threaded as a `terminationRound` prop mirroring `defenseStartRound`). The plot-data-JSON contract was YAGNI-deferred until this consumer landed. Verified in a real browser (headless Chrome over the live stack). Closes the termination-visibility arc end-to-end: `termination.json` → matplotlib marker → dashboard banner → interactive plot marker + toast.
- **2026-05-28** — **Early-termination banner on the run dashboard + DRY termination reader**. `generate_main_dashboard` now renders a high-visibility amber banner ("⚠ This run terminated early at round N — <reason>") at the top of the run's `index.html`, reading `out/<run>/termination.json`. The reader is consolidated to one source of truth — `read_termination_summary(output_dir)` in `termination_policies.py`, beside the writer and the now-shared `TERMINATION_SUMMARY_FILENAME` constant; `new_plot_handler._read_termination_event` delegates to it so the plot marker and the banner can't drift on parse/path logic. Scoping correction: the *per-strategy* attack-snapshot HTML (`summary.json`/`index.html`) is gated on `attack_schedule`, so it can't host a removal-driven termination event (which fires with or without attacks) — the always-generated main dashboard is the run-level surface. Closes the backend half of termination visibility (JSON + matplotlib marker + dashboard banner); only the React/interactive-plot marker remains.
- **2026-05-28** — **Early-termination marker on accuracy/loss plots**. `show_plots_within_strategy` now draws a dotted black vertical line at the early-termination round (labelled with the reason) on every per-client metric plot, consuming the `out/<run>/termination.json` shipped earlier today. Two small helpers: `_read_termination_event(directory_handler)` reads the JSON from `directory_handler.dirname` (returns None when absent/malformed — the run didn't terminate early), and `_add_termination_marker(ax, event)` draws the `axvline` (no-op unless `terminated_early` and a non-null round). Read from disk, not the in-memory `TerminationHandler`, because strategy-object mutations don't survive Flower's `run_simulation` boundary (same reason termination.json is written in-worker). The event is read once before the metric loop. This is the **server-side matplotlib** slice; the React/interactive-plot marker + toast remain (YAGNI-deferred the plot-data-JSON contract until the frontend consumer lands). research(2026-05): reuses the existing `_add_attack_background_shading` annotation pattern; vertical event markers are standard for run-truncation events in ML training curves.
- **2026-05-28** — **Cross-modal attack/model_type validation**. `_validate_attack_schedule` now rejects an `attack_schedule` entry whose data modality the model can't consume: image-only attacks (`gaussian_noise`, `backdoor_trigger` — they act on `(N,C,H,W)` pixel tensors) on a `transformer`, or text-only `token_replacement` on a `cnn`. Both label-flip variants and all six weight/gradient-space attacks are modality-agnostic and pass on either. `ATTACK_MODALITY` (in `validate_strategy_config.py`) is the single source of truth: it also *is* the schema `attack_type` enum (`list(ATTACK_MODALITY)`) and is completeness-tested against the data + weight dispatch registries **and** the `model_type` enum, so a future attack or model_type can't slip in modality-unchecked (the model_type guard closes a fail-open gap). cnn↔image, transformer↔text — no ViT path. Stop-before-start: a mismatched attack silently no-ops or crashes mid-run, wasting a GPU/LLM run. Verified safe against the whole config + test corpus first (zero existing mismatched pairs; `advanced_attacks_config.json`'s CNN-attacks-then-Transformer-token split is a multi-strategy study, validated per sub-strategy). research(2026-05): allowlist-by-modality (whitelist > blocklist for config-boundary validation — a new attack must be classified before it runs) per arXiv:2603.20615 modality-segregated FL eval (TFLlib's image/text/tabular lanes) + 2026 input-validation surveys.
- **2026-05-28** — **Config validator aggregates errors (fail-on-first → collect-all)**. `validate_strategy_config` reports every problem in one pass: phase 1 collects all schema violations via `Draft202012Validator.iter_errors`; if the schema is clean, phase 2 runs each semantic/strategy check and collects their failures. Two-phase because the semantic checks assume type-valid input (they index `config[...]` and do arithmetic), so schema-first keeps them crash-safe. Design choice: aggregation lives in the orchestrator (collect at the top level), **not** by rewriting every `_validate_*` helper to return error lists — the helpers still raise, so their direct-call unit tests and exact messages are unchanged, and a lone error is re-raised verbatim (only multi-error configs get the numbered "CONFIG REJECTED: N … found" report). `_populate_client_selection` is paired with `_validate_attack_schedule` since it assumes the per-entry fields that validator checks (else it `TypeError`s on a bad schedule). research(2026-05): jsonschema `iter_errors` mirrors Pydantic v2's gather-then-raise; jsonschema isn't ExceptionGroup-native yet (PEP 654).
- **2026-05-28** — **Early-termination event written to run output**. When a removal run terminates early, `TerminationHandler._mark_termination` writes `out/<run>/termination.json` (`terminated_early`/`termination_round`/`termination_reason`/`termination_policy`) so researchers see the event without grepping logs. Written in-worker at termination time, reusing the proven `DirectoryHandler.dirname` path — Flower's `run_simulation` returns no History and strategy-object mutations don't reliably propagate back across the simulation boundary, so a post-run read of `self._aggregation_strategy.termination_handler` is unsafe. `output_dir` is injected at construction (DI keeps the handler decoupled + unit-testable); the three removal strategies (trust/rfa/pid) pass it. Premise correction from the old item: there is no run-level `summary.json` — that name is the attack-snapshot metadata file — hence `termination.json`.
- **2026-05-28** — **Krum-family removal floor guard**. `krum_based_removal.configure_fit` now stops removing once the effective (non-removed) federation would fall below `f + 3` — the point where Krum's score (a sum of distances to `n - f - 2` neighbors) loses its last neighbor and degenerates to NaN. Previously it removed one client per round unbounded; `multi_krum_based_removal` already had the analogous cap. research(2026-05): Krum needs `n >= 2f + 3` for its Byzantine guarantee (config-validated) and `n >= f + 3` for a computable score (the runtime floor); Blanchard et al., NIPS 2017.
- **2026-05-28** — **Bulyan config validation (`n >= 4f + 3`)**. `_validate_dependent_params` now rejects Bulyan configs with too few clients for the declared Byzantine count, mirroring the existing Krum `n > 2f + 2` check. Bulyan's coordinate-wise trimmed mean over the Multi-Krum selection needs the stricter `4f + 3` margin (research(2026-05): Mhamdi et al., *The Hidden Vulnerability of Distributed Learning in Byzantium*, ICML 2018). Closes the gap where an infeasible Bulyan config silently produced garbage instead of stopping before the run. Also fixed a sweep test that paired Bulyan with n=7/f=2 (invalid) and added the missing Bulyan byzantine-violation test (Krum/Multi-Krum already had one).
- **2026-05-28** — **Removal-config misconfigs are now hard rejections**. `validate_removal_configuration` promotes its two former warnings — `begin_removing_from_round >= num_of_rounds` (removal never fires) and STRICT termination + `min_fit_clients == num_of_clients` (first removal ends the run) — to `ValidationError` with Reason/Fix messages, and is now a `None`-returning validator consistent with its `_validate_*` siblings (the vestigial `(config, warnings)` tuple + dead warning-logging path removed). Stop-before-start over wasting a GPU/LLM run on a config that silently no-ops. research(2026-05): kept fail-on-first to match the rest of the validator; aggregating all config errors at the boundary is a separate migration, filed under Code Quality.
- **2026-05-25** — **GitHub Actions SHA-pinned (supply-chain hardening)**. Every workflow `uses:` ref pinned to a full commit SHA (`# vX.Y.Z` comment kept); Dependabot `github-actions` gains a 7-day cooldown. Mutable tags enabled the tj-actions/changed-files attack (2025-03); SHA-pinning runs exactly the reviewed code, with freshness via the existing Dependabot version updates. Fleet convention + rationale in techne `docs/conventions.md`. research(2026-05): GitHub "Secure use reference"; CNCF GH-Actions CI-deps recipe.
- **2026-05-23** — **ArKrum Fang-Krum known-weakness note (reference-port parity with vFL)**. `intellifl/simulation_strategies/arkrum_strategy.py` class docstring gains a *Known weaknesses* subsection mirroring vFL's `docs/strategies.md` entry — dense-cluster vulnerability (inherited from rKrum/Krum) and Fang-style aggregator-aware attacks (9.6% acc vs 94-96% on vFL's nightly, parameter-free f̂ returns 0 against min-max perturbation; SpectralKrum arXiv:2512.11760 confirms the same limit). For Fang-robust federation, prefer GeometricMedian or coordinate-wise statistics.
- **2026-05-23** — **Deterministic label-flip permutation per client** [#40]. `apply_label_flipping` accepts a `client_id`; when set, seeds via `torch.Generator().manual_seed(42 + client_id)` so dynamic `attack_schedule` runs no longer average to clean-baseline noise. Matches BlazeFL's isolated-RNG-per-client pattern — research(2026-05): arXiv:2604.03606. All dispatch fns accept the kwarg uniformly so future per-client RNG needs (e.g. gaussian noise jitter) reuse the same surface.
- **2026-05-22 → 23** — **Dataset System Rework Phases 1A–2B closed**. Canonical HF mirrors locked: MedMNIST (`albertvillanova/medmnist-v2` + per-variant subset), FEMNIST (`flwrlabs/femnist`, 62 classes — not the 10-class digit subset AJ-side preprocessing produced), CIFAR-10/CINIC-10 / lex_glue / MedQuAD. `FederatedDatasetLoader` gained `subset` / `image_column` / `image_transform` / `partition_by` slices; precedence is `StrategyConfig` > JSON per-dataset default > Dirichlet alpha=0.5 fallback. **Adding the next HF-backed CNN dataset is now JSON + transformer registration — no Python builder code.**
- **2026-05-21** — **`ray_logger.py` kept** post-Flower 1.28+ audit. Covers strategy-level timing aggregation, CRASH/OOM/TIMEOUT/NODE_DEATH event taxonomy, persistent `ray_simulation_summary_*.json`, `ray.nodes()` snapshot — none of which Flower provides natively.
- **2026-04-10** — **Aggregation math invariants** (load-bearing across all Byzantine-robust strategies). Krum / Multi-Krum use squared Euclidean per NIPS 2017; Krum / Multi-Krum / Bulyan sum the *k* closest neighbors excluding self; `aggregation_participation=1` only when actually included in the round's global update.

Out-of-scope dispatch sites (deliberately not consolidated):
- `simulation_strategies/pid_based_removal_strategy.py` — branches inside the strategy impl, not at the construction seam.
- `config_loaders/validate_strategy_config.py` — per-strategy validation rules; moving these would decentralize, not centralize.

---

## Flower Message API migration (1.29)

> Audited 2026-05-30 against current Flower. Ref: [Flower changelog](https://flower.ai/docs/framework/ref-changelog.html) | [Upgrade to Message API](https://flower.ai/docs/framework/how-to-upgrade-to-message-api.html)

Flower 1.29 (2026-04) is steering to the **Message API**: new strategies live in
`flwr.serverapp.strategy`, the `ServerApp` constructor's direct
`strategy`/`config`/`server` args are deprecated in favor of `server_fn` /
`@app.main()`, `Context`/`ClientApp` move to `flwr.app`/`flwr.clientapp`, and
`flwr.simulation.run_simulation` + the long-running `flwr-*` commands give way to
`flwr run` / SuperExec. The legacy surfaces still work in 1.29 (migration
*encouraged*, no hard removal date), so this is plan-ahead, not a fire-drill.

**Where phalanx already is:** `federated_simulation.py` runs on the
`ServerApp(server_fn=…)` + `ClientApp(client_fn=…)` pattern (so the deprecated
constructor-args path doesn't apply) and already guards the `run_simulation`
deprecation defensively (falls back to the private `_run_simulation`).

**The gap — phalanx's core IP:** all ten Byzantine-robust strategies subclass the
prior-generation `flwr.server.strategy.FedAvg` (`fedavg`, `multi_krum`, `bulyan`,
`arkrum`, `trimmed_mean`, and the `trust`/`pid`/`rfa`/`krum`/`multi_krum`/`trimmed_mean`
removal variants) and override `configure_fit` / `aggregate_fit` against
`Parameters` / `FitRes`. The Message API reshapes that seam (Message/record-based,
not the `Parameters`/`FitRes` contract), so porting the roster is a real interface
migration, not a mechanical import swap. Gate on: (a) `flwr.serverapp.strategy`
reaching parity with the legacy `FedAvg` hooks phalanx overrides; (b) an upstream
legacy-removal signal; (c) a port-one-strategy-first spike (FedAvg) to size the
per-strategy cost before committing the whole roster. `research(2026-05)`: Flower
1.29 changelog + Upgrade-to-Message-API guide — legacy `flwr.server.strategy` is
functional-but-superseded; new strategies in `flwr.serverapp.strategy`.

---

## Dataset System Rework

> Source: `demo/DATASET_REWORK_PLAN.md` (Phases 0-5)
> Ref: [HuggingFace Datasets](https://huggingface.co/docs/datasets) | [flwr-datasets v0.6.0](https://flower.ai/docs/datasets/index.html)

### Phase 0 — Cleanup & Foundation — shipped 2026-05-21/22

0A dropped `its`/`flair`/`lung_photos` (backend + frontend + tests). 0B added `DynamicCNN._initialize_weights()`. 0C normalized `FederatedDatasetLoader.load_datasets()` to 2-tuple with `num_classes` instance attr. 0D skipped — Phase 5 eliminates all transformer files via declarative JSON transforms; renaming first would be wasted churn.

Known carry-overs into Phase 1A: `cifar10` and `cinic10` frontend dropdown entries (need backend `_cnn_loader_map` dispatch first). `text_classification_loader.load_datasets()` still returns a 3-tuple but is slated for Phase 3E deletion — leave as-is.

### Phase 1 — Config Expansion & Config-Driven Dispatch

- [x] **1A:** Expand `config/huggingface_datasets.json` with all 21 datasets — shipped 2026-05-22 (see Recently shipped above).
- [x] **1B (CNN slice, shipped 2026-05-22):** `_build_cnn` reads `image_transformer` from `config/huggingface_datasets.json` instead of the now-deleted `_CNN_DATASET_TRANSFORMER_MAP` Python dict. The CNN keyword tuple stays in code (`_LOCAL_CNN_KEYWORDS`) as the source of truth for "which datasets use `ImageDatasetLoader` + local files" — that property will move into JSON in Phase 2A alongside the migration to `FederatedDatasetLoader`. Schema test extended to assert every `_LOCAL_CNN_KEYWORDS` entry has a resolvable, non-null transformer name.
- [x] **1B (text + cifar100 collapse, subsumed):** `_build_cnn` is gone (Phase 2E); the per-keyword dispatch already collapsed to a per-family shape with `_build_hf_text`, `_build_hf_image_cnn`, and `_build_hf_medmnist_cnn` all routed via `LOADER_REGISTRY`. No further consolidation work remains here.
- [x] **2A (cifar10 / cinic10 wiring, shipped 2026-05-22):** transformers registered, JSON entries' `image_transformer` set, `LOADER_REGISTRY` extended via `_HF_IMAGE_CNN_KEYWORDS` tuple (cifar100 / cifar10 / cinic10). `_build_cifar100` renamed `_build_hf_image_cnn` since it's now generic across the HF-backed CNN family.
- [x] **1B (femnist partitioner, subsumed):** Phase 2B FEMNIST migration shipped `femnist_iid` + `femnist_niid` through `_build_federated_dataset_loader`, which reads `partitioning_strategy` + `partition_by` directly from JSON. The `_CNN_DATASET_TRANSFORMER_MAP` keyword check no longer exists.
- [ ] **1C:** Use `load_hf_model()` from the Transformer Merge (above) instead of duplicating LoRA/non-LoRA BERT loading here

### Phase 2 — Migrate Image Datasets to FederatedDatasetLoader

- [x] **2A (shipped 2026-05-22):** `FederatedDatasetLoader` gained `subset`, `image_column`, `image_transform`, `partition_by` + `natural_id` strategy across slices #22-#25. `load_dataset_kwargs` deferred until first concrete caller (YAGNI).
- [x] **2B:** All three tiers shipped. CIFAR family (cifar100 + cifar10 + cinic10) 2026-05-22; 11 MedMNIST + FEMNIST (iid/niid as 62-class with per-dataset `partitioning_strategy` default in JSON — iid for femnist_iid, natural_id with partition_by=writer_id for femnist_niid) 2026-05-23.
- [x] **2C (subsumed):** `_create_image_loader()` no longer exists — image-loader dispatch now flows through `_build_hf_image_cnn` / `_build_hf_medmnist_cnn` and the shared `_build_federated_dataset_loader` helper. The 2C scope collapsed into 2A/2B work.
- [x] **2E (closed):** `image_dataset_loader.py` + `_LOCAL_CNN_KEYWORDS` + `_build_cnn` deleted in [#34] (first tier, 2026-05-23). `huggingface_image_dataset_loader.py` + its 467-line test suite deleted in second tier (2026-05-23); `config/test_hf_datasets.py::_test_image_dataset` rewired to `FederatedDatasetLoader` with the same JSON-precedence rules as production builders.

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

`FederatedDatasetLoader._create_partitioner()` now delegates to the
`partitioner_registry` (Phase 0 shipped 2026-05-23); the old hard-coded
`if/elif` chain is gone. The image-loader side of the consolidation
finished with Phase 2E (`huggingface_image_dataset_loader.py` deleted in
[#36]). The text loaders (`text_classification_loader.py`,
`huggingface_text_dataset_loader.py`) still carry their own partitioner
dispatch and will collapse into the registry as Phase 3 lands.

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

- [x] **Zensical bake into `docs.Dockerfile`** — shipped 2026-05-23. The `docs` service in `docker-compose.yml` now builds from `docs.Dockerfile` instead of `pip install`ing zensical on every container start. Uses the same uv distroless pattern as the main Dockerfile (`COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/`); pins zensical to `0.0.32` (cross-sister `/techne:sisters` audit catches drift). Trade-off: ~15s one-time build cost vs ~5s saved per restart + version reproducibility.
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
- [x] **Per-attack specialized visuals in composites — shipped 2026-05-23.** New `extract_individual_attack_types` helper unfolds a list config into `[(itype, sub_cfg), …]`; `save_visual_snapshot` iterates and dispatches per-type so `label_flipping_visual.png`, `backdoor_trigger_visual.png`, `gaussian_noise_difference_heatmap.png`, the per-type confusion matrix and summary all emit alongside `composite_synopsis.png`. Singles preserve their legacy `{attack_type}_visual.png` naming. Coverage: 13 new helper tests + 3 composite-dispatch tests verifying call_count + per-type filenames.

### Domain Entity Evaluator

- [ ] Create `intellifl/evaluation/` module with `DomainEntityEvaluator` class — measures model accuracy specifically on domain vocabulary terms (medical/financial/legal)
- [ ] Create `AttackEffectivenessAnalyzer` — pre/post attack comparison (targeted degradation, collateral damage, attack specificity)
- [ ] Integrate into `FlowerClient.test()` — add `evaluation_domain` param, return `EntityMetrics` alongside loss/accuracy
- [ ] Add domain metrics to experiment results JSON and snapshot HTML reports

### Attack System Improvements

- [ ] Add `snapshot_frequency` config option (e.g., every N rounds) to reduce GPU memory pressure during long simulations
- [ ] Consider additional LLM attack types (gradient inversion, prompt injection) for transformer fine-tuning paths
- [ ] **Audit attack-snapshot filename collisions** — verify `client_X/round_Y/{attack_type}_visual.png`, `*_metadata.json`, `*_weight_metadata.json`, summary, and pickle paths cannot collide when the same `output_dir` is reused, when composite `extract_attack_type` concatenations clash with single-attack names, or when the same client/round is re-snapshotted. Trigger: open question whether comparison view / confusion matrix / metadata / summary / visual / pickle artifacts overwrite each other.
- [x] **Cross-modal attack compatibility validation — shipped 2026-05-28** (see Recently shipped). `_validate_attack_schedule` rejects modality-mismatched scheduled attacks (image-only `gaussian_noise`/`backdoor_trigger` on a transformer; text-only `token_replacement` on a cnn). Keyed off `model_type` (cnn↔image, transformer↔text), not `dataset_keyword`: model_type is the schema-required, enum-constrained modality signal, and there's no validator rule coupling dataset to model anyway. `ATTACK_MODALITY` is the SoT (also backs the schema enum) and is completeness-tested against the dispatch registries + model_type enum.
- [ ] **Document attack-snapshot file emission contract** — codify which files (`{attack_type}_visual.png`, `composite_synopsis.png`, `*_metadata.json`, `*_weight_metadata.json`, summary, pickle) `save_visual_snapshot` (`attack_snapshots.py:291-360`) is expected to emit under which conditions (4D image vs text, single vs composite, snapshot_frequency gate). Repro: `out/01-09-2026_18-16-07/attack_snapshots_0/client_1/round_7/` is missing `label_flipping_visual.png` despite round 7 containing label flipping. Trigger: undocumented per-round artifact set surprises consumers and breaks downstream HTML reports.
- [x] **Deterministic label-flip permutation per client — shipped 2026-05-23.** `apply_label_flipping` now accepts `client_id`; when set, the permutation draws from `torch.Generator().manual_seed(42 + client_id)` instead of the global RNG. Thread runs `apply_poisoning_attack → _dispatch_label_flipping → apply_label_flipping`; all 4 flower_client.py call sites (CNN train/eval + transformer train/eval) pass `client_id=self.client_id`. Other dispatch fns accept the kwarg and ignore it so the dispatcher call stays uniform. Pattern follows BlazeFL's isolated-RNG-per-client design (research(2026-05): arXiv:2604.03606). Coverage: 4 new unit tests (`test_same_client_id_yields_stable_permutation`, `test_different_client_ids_diverge`, `test_client_id_independent_of_global_rng`, `test_client_id_none_preserves_legacy_random_behavior`) + 1 integration test verifying `apply_poisoning_attack` forwards client_id correctly.

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

- [x] **`## Sister ecosystem` block in README — shipped 2026-05-21.** README.md:165 now carries the cross-sister narrative naming Kourai Khryseai / VelocityFL / ajbarea.github.io / techne / LDQIS with roles + one-line links.
- [ ] **Cite Project Glasswing posture in README security framing** — Anthropic's April 2026 trustworthy-software initiative (AWS / Apple / Google / JPMorganChase / NVIDIA / Palo Alto Networks / Linux Foundation + 40 more) sets the 2026 frame for Byzantine-robust FL work. One-paragraph mention is enough; don't over-claim. Ref: <https://www.anthropic.com/glasswing>.
- [ ] **Stale-assumption audit (whenever the FL ecosystem moves)** — Krum / Multi-Krum / Bulyan defenses were calibrated to specific attack assumptions; mock-client patterns and the (now-removed) `ray_config` shim were shaped around Flower 1.9-era API quirks; transformer-loader paths encode a particular HF Transformers generation. When Flower / a new aggregation paper / a new HF Transformers major / a new defense technique lands, audit which scaffolding exists to compensate for a now-closed gap and collapse what no longer earns its keep. (Flower's 1.29 Message-API shift audited 2026-05-30 → tracked under `## Flower Message API migration`.) **Inverse of speculative-generality YAGNI:** YAGNI polices new code being written; this audit polices existing code as the ecosystem moves around it. Captured as a recurring invariant — fires on external events, not on a fixed schedule. `research(2026-05)`: pattern adapted from [Anthropic engineering, Managed Agents](https://www.anthropic.com/engineering/managed-agents) (*"harnesses encode assumptions about what Claude can't do on its own. However, those assumptions need to be frequently questioned because they can go stale."*); mirrored cross-sister from kourai-khryseai's M22-M25 platform-reliability sweep.

---

## Docs

> Source: `demo/plans-and-specs/DOCS/`
> Old `DEVELOPMENT_SETUP.md` was fully stale (referenced deleted scripts/tools) — deleted, not extracted.

- [ ] Audit `zensical.toml` nav against actual `docs/` file structure — ensure new strategies/attacks/datasets are reflected in sidebar
- [ ] Auto-generate `api.md` from FastAPI routers/Pydantic models (or link to `/docs` Swagger endpoint). Ref: [FastAPI Reference](https://fastapi.tiangolo.com/reference/)

---

## Code Quality & Refactoring

> Source: `demo/plans-and-specs/gemini-review/`
> Ref: [Ruff](https://docs.astral.sh/ruff/) | [ty](https://docs.astral.sh/ty/) (already configured in pyproject.toml)

- [ ] Break up `FederatedSimulation` (currently 392 lines, down from 691 in earlier audit) — extract `StrategyFactory`, `ModelLoader`, or similar focused managers if the class grows again or the per-method responsibilities blur. Less urgent now; revisit when adding the next major orchestration concern.
- [ ] TypeScript migration for frontend — all core files are still `.jsx`, no `.tsx` exists yet
- [ ] Add custom API exception classes (`SimulationNotFoundError`, etc.) instead of generic `Exception` catches in routers. **Scoping note (2026-05-28):** reconsider before implementing — FastAPI idiom favors raising `HTTPException(status_code=...)` directly (already used throughout the routers), and most `except Exception` sites sit at system boundaries (Celery, subprocess, filesystem) where a broad catch is correct, not a smell. The clear win here was DRY, not new exception types: the duplicated "read config.json → 404/500" block (`get_simulation_details` + `get_simulation_config`) was consolidated into `_read_simulation_config` (2026-05-28). If revisited, scope to genuine domain 404s, not a blanket catch-narrowing pass.
- [ ] Move in-scope Celery imports in routers to FastAPI dependency injection for testability
- [ ] **Add ArKrum regression baselines** — `arkrum_strategy.py` and configs `femnist_arkrum_baseline.json` / `femnist_arkrum_vs_labelflip.json` are shipped, but neither has a fixture in `tests/fixtures/baselines/`, leaving ArKrum the lone aggregation strategy without regression coverage (vs Krum/MKrum/Bulyan/RFA/TrimMean/Trust/PID-x4 all baselined). Generate and commit both `.baseline.json` files. Trigger: prevent silent ArKrum drift; close coverage asymmetry surfaced from a stale 2026-01-18 batch log.
- [x] **Strategy math floors live at config-time validation — Bulyan added 2026-05-28** (see Recently shipped). Correction: these floors belong in `_validate_dependent_params`, not `TerminationHandler`. Krum/Multi-Krum require **n ≥ 2f+3** (already validated as `n > 2f+2`) and Bulyan **n ≥ 4f+3** (added). The prior wording ("plumb Krum n≥4f+3 into the handler") was doubly off: Krum's bound is 2f+3, not 4f+3 (that's Bulyan's), and `TerminationHandler` is constructed only by the PID/Trust/RFA *removal* strategies — which aggregate the survivors (geometric-median / FedAvg-style) and have no Krum-style floor — so plumbing aggregator bounds into it is a no-op for its actual users.
- [x] **Runtime removal floor for Krum-family removal — shipped 2026-05-28** (see Recently shipped). Audit result: `multi_krum_based_removal` already capped removal (keeps ≥ `num_krum_selections`); `krum_based_removal` did **not** — it removed one client per round unbounded, so removal could drive the effective federation below Krum's score floor (`n_eff - f - 2 >= 1` neighbor ⇒ `n_eff >= f + 3`) and produce NaN. Added the missing cap. The stricter `n >= 2f + 3` *starting* bound stays the config-time check; the runtime floor is the weaker `f + 3` because removal legitimately drops the count as it drops the f Byzantine clients.
- [x] **Surface termination events in experiment output — backend shipped 2026-05-28** (see Recently shipped). All three backend surfaces now carry the event: `out/<run>/termination.json` (machine-readable), a dotted vertical marker on the matplotlib accuracy/loss plots, and an amber banner atop the run dashboard `index.html`. Scoping correction: the per-strategy attack-snapshot HTML is `attack_schedule`-gated, so the always-generated main dashboard (not the snapshot report) is the correct run-level home. Remaining frontend (React) work tracked in the next item.
- [x] **Frontend (React) alert + plot marker for early termination — shipped 2026-05-28** (see Recently shipped). `save_plot_data_json` now emits the `termination` payload alongside the metric histories (the YAGNI-deferred JSON contract, added now that its consumer landed); `InteractivePlots` fires a sonner `toast.warning` on load and draws an amber dashed `ReferenceLine` at the termination round on both the single-metric `LineChart` and every `SynchronizedMetricsChart` panel (compare view). Verified in a real browser (headless Chrome over the running stack). Completes the termination-visibility arc end-to-end: `termination.json` → matplotlib marker → dashboard banner → interactive plot marker + toast.
- [x] **Convert removal-config warnings to hard rejections — shipped 2026-05-28** (see Recently shipped).
- [x] **Config validator aggregates errors — shipped 2026-05-28** (see Recently shipped). `validate_strategy_config` now reports all problems in one pass. Done at the orchestrator level (collect-and-aggregate around the existing checks), not by rewriting every `_validate_*` helper, so helper messages + their direct-call tests stay unchanged. Historical rationale: 2026 best practice for config-*boundary* validation is to aggregate all errors and report them together (Pydantic v2 / `ExceptionGroup` style) so a researcher fixes every problem in one pass instead of iterating one error at a time. This is a cross-cutting refactor across all `_validate_*` helpers — do it wholesale, not piecemeal (a single aggregated check among fail-fast ones would be inconsistent). research(2026-05): config-validation surveys + Pydantic v2 strict-mode error collection; PEP 654 ExceptionGroups. Trigger: surfaced while converting removal warnings to raises — the fail-fast/aggregate split is a deliberate design axis worth a dedicated pass.
- [x] **Static + dynamic attack coexistence is intentional — closed, no gate added 2026-05-28** (was: "Reject ambiguous static/dynamic attack configs") — `validate_strategy_config.py:480-489` rejects `preserve_dataset + attack_schedule`, but a config with both `num_of_malicious_clients > 0` / non-null `attack_type` (static, filesystem-poisoning path) AND a non-empty `attack_schedule` (dynamic, in-memory path) silently passes — the merge fix (commit `f875d4ba0`) settled which value wins, but the deeper ambiguity remains. Add `_validate_attack_schedule` rejection requiring `attack_type: null` and `num_of_malicious_clients: 0` when `attack_schedule` has entries. Trigger: "fields bleed between strategies unexpectedly"; aligns with stop-before-start preference. **Scoping note (2026-05-28):** as literally worded this item is unsafe — there is **no top-level `attack_type`** (it's a per-entry property of `attack_schedule`, schema line ~129), and `num_of_malicious_clients > 0` (which drives *static filesystem dataset-poisoning* via `dataset_loaders/__init__.py:157`) **intentionally coexists** with an `attack_schedule` in current valid configs (e.g. `test_validate_strategy_config_valid_trust_strategy` pairs `num_of_malicious_clients: 2` with a schedule and passes). Requiring `num_of_malicious_clients: 0` would break those. **Decision (2026-05-28):** closed, no gate added. Static dataset-poisoning (`num_of_malicious_clients`, applied at load time) and dynamic in-memory `attack_schedule` attacks are distinct, legitimately-combinable threat vectors — data-poisoning vs model/update-poisoning — and combined/hybrid-attack simulation is standard FL robustness practice (research(2026-05): arXiv:2004.10020 + the data-vs-model-poisoning taxonomy). `_validate_attack_schedule` already encodes a deliberate stacking policy (different-type attacks may stack; only same-type round overlaps reject), and the lone coexistence rejection — `preserve_dataset + attack_schedule` — fires because those are *incompatible execution modes* (pre-poisoned filesystem vs in-memory), not because two poisoning vectors coexist. `num_of_malicious_clients` is an orthogonal vector, so no gate applies. Locked by a negative-space `# research:` comment in `_validate_attack_schedule` plus a pointer comment on `test_validate_strategy_config_valid_trust_strategy`; a separate focused test was judged duplicative (it would clone a ~40-field valid config to assert what the existing test already exercises).
- [ ] **Stop button doesn't actually halt a running simulation** — frontend "Stop" control reported as non-functional once a sim is in flight; need to wire it to a backend cancellation path (Celery revoke + Ray actor shutdown) and reflect the `stopped` state in the UI. Trigger: researchers expect Stop to mean stop, not "request that hangs in pending."
- [ ] **Frontend integrated terminal not showing repo scripts** — the embedded terminal (Ctrl+\`) starts in a context where `clean.sh` and other root-level scripts are invisible; suspect uid/working-dir mismatch (running as `appuser` inside the container, no shell rc loaded). Either pin the cwd to the project root, source the venv on shell start, or document the difference vs. the host terminal. Trigger: researcher can't run dev scripts from the panel that's supposed to support exactly that.
- [x] **Loading-state copy unified across result tabs — shipped 2026-05-28.** Insights/Plots/Attacks/Metrics each had divergent no-data UI (badge vs plaintext vs spinner) with four different copy strings. Replaced by one shared `SimulationResultState` (`common/Empty/`): an informative **pending** state (busy indicator + "{Noun} will appear here once the simulation finishes.") for the running/queued case, a **failed** alert, and an **empty** alert — `noun` per tab. research(2026-05): a simulation is a long-running async job, so the in-progress case gets a busy indicator + explicit "what's coming" message, not a skeleton (which implies imminent content). Failed-state render verified in-browser; running-state left for an eyeball at `:5174` (a fabricated `running` run, since real sims need deps/datasets we don't have locally).
- [x] **Dark-mode background brightness — audited 2026-05-28.** Browser audit (headless Chrome, forced-dark) found the dashboard and detail/Insights surfaces well-balanced; the actual glare was the **attack-visualization images** — light-themed matplotlib PNGs (confusion matrices, comparison grids, digit samples) served to both themes, blazing white on the dark surface. Fixed by matting them: a shared `.attack-viz-image` class frames each on a white mat with padding, rounded corners, a subtle border, and a soft drop-shadow in dark mode so they read as framed exhibits, not UI bugs (regenerating per-theme PNGs server-side was rejected as disproportionate). research(2026-05): image-matting is the standard treatment for static light images on dark UIs (vs. live charts, which get a dark theme). Re-open only if a specific CSS-styled panel (not a generated image) still reads too bright.
- [ ] **Preset card tag taxonomy** — preset card tags drift across new vs. legacy cards; `Showcase` may not deserve its own tag. Pick a closed vocabulary (e.g., `baseline`, `defense`, `attack`, `nlp`, `multi-attack`) from looking at `frontend/src/constants/presets.js` + `config/simulation_strategies/testing/`, apply consistently. Trigger: tags currently feel ad-hoc and don't help filtering.
- [ ] **Token Replacement attack viz: tab content + layout** — in the Attacks tab for `token_replacement` runs, the 🖼️ Samples and 📝 Token Diff tabs render the same content; Original-on-top / Poisoned-on-bottom should be side-by-side (Original left, Poisoned right) so metrics fit in one row; the "Understanding Attack Snapshots" caption is also leaking into both tabs. Trigger: the duplication makes the UI look broken even when the data is right.
- [x] **`lint` Makefile target scope verified 2026-05-23.** `scripts/lint.py` runs `ruff format .` + `ruff check .` repo-wide (covers `intellifl/`, `tests/`, `scripts/`), `ty check intellifl tests`, and `npm run lint` → `eslint .` from the `frontend/` dir (covers the whole frontend tree, not just `src/`). No gap; older note was stale.
- [ ] **Native-Windows / native-macOS support pass** — orchestration is already in a Python CLI (`intellifl-dev`, every `Makefile` target dispatches `@$(UV_DEV) <cmd>`), so the architecture is fine. What's still platform-fragile: (a) `Makefile:101-105` uses `tail` directly for `logs` / `logs-tail`, which fails outside Git Bash / WSL on native Windows — replace with a Python `intellifl-dev logs [--follow]` subcommand; (b) audit `intellifl-dev` console output for UTF-8 / emoji handling on `cp1252` Windows terminals (per `tests/common.py`'s existing UTF-8 setup); (c) add CI matrix for `windows-latest` + `macos-latest` + `ubuntu-latest` so portability is enforced, not assumed. Trigger: team uses Macs; today everything works in Git Bash but break on cmd/PowerShell, and there's no CI signal preventing regressions.
- [ ] **Frontend live hardware utilization HUD** — researcher-facing CPU / GPU / memory readout in the simulation dashboard so long-running runs surface resource pressure without a terminal `nvitop`. Trigger: GPU sims fail late and silently when memory pressure hits; visibility helps catch it earlier.
- [ ] **`CITATION.bib` generation per output run** — pair with the existing `MANIFEST.json` (`intellifl/utils/reproducibility.py:114`) so each run is self-citing. IEEE/ACM artifact-evaluation guides expect a `CITATION` alongside `MANIFEST`. Trigger: research-artifact polish; closes part of the "experimenting with IEEE artifact best practice" claim AJ has already made externally.
- [ ] **Output directory IEEE-artifact restructure** — `out/<run>/` is currently flat (config + CSVs + PDFs + logs + `MANIFEST.json` all at root). Restructure into `config/`, `data/{metrics,attack_analysis}/`, `visualizations/{accuracy,loss,removal,analysis}/`, `logs/`, `latex/`, `reports/`; keep `MANIFEST.json` + `status.json` + (planned) `CITATION.bib` + `README.md` at run root. Add per-run `README.md` with quick stats, key findings, file-organization map, and reproducibility metadata (git commit, system info, config checksum). Trigger: aligns with FAIR + IEEE artifact-evaluation badge criteria ("Available", "Reusable"); pairs with the `CITATION.bib` item above and the existing `MANIFEST.json` infra.
- [ ] **Session history persistence — Postgres + SQLModel + asyncpg** — currently no DB layer for per-user session history beyond Redis-via-Celery for live queue state. Add `postgres:17-alpine` as a Docker Compose service (separate volume), use SQLModel + asyncpg from the FastAPI backend so saved configs, run history, comments, and any future user-scoped artifacts are queryable. Standard FastAPI 2026 setup: `postgresql+asyncpg://...` URL, async session factory, `init_db()` on startup. Trigger: capstone-era session retention story — Redis is fine for ephemeral queue state but loses everything on restart; researchers want runs queryable across sessions. `research(2026-05)`: the 2026-standard FastAPI async DB stack is **SQLAlchemy 2.0 async + asyncpg + Alembic** with DI-managed sessions — SQLModel still ships no native `AsyncEngine`/`AsyncSession` wrappers (you wrap it with SQLAlchemy's async session and add Alembic anyway, and it lags both SQLAlchemy and Pydantic), so revisit "SQLModel + asyncpg" before building: either commit to SQLAlchemy 2.0 async directly, or keep SQLModel knowing the async path is SQLAlchemy's underneath + needs Alembic for migrations. `postgresql+asyncpg://` (already specified) is required — bare `postgresql://` silently blocks the event loop under load. Source: TestDriven.io "FastAPI with Async SQLAlchemy, SQLModel, and Alembic"; SQLAlchemy 2.0 async docs.
- [ ] **Comments cleanup audit + linting silence-tag review** — sweep codebase for direct references to planning docs in comments (e.g. `# Phase C9`, spec-step labels) that leaked from spec implementation; separately, audit existing `# noqa: ...` / `# type: ignore` silence tags so each represents a real exemption rather than convenience suppression. The WHAT-comment side is `techne:deslop` skill territory; the silence-tag side is its own `ruff`/`ty` sweep. Trigger: comment hygiene before paper-submission code review; closes "1. comment cleanup is absolutely necessary…" from the polish backlog.
- [ ] **Queue UX: unify "View Global Queue" and "View Queue Status" routes** — dashboard surfaces a "Simulation in progress…" banner with a `View Global Queue` button that lands on `🧪 Experiment Queue`; the new-simulation page shows the same banner with a `View Queue Status` button that lands on `⏳ Experiment Queue Status`. These are two different pages reached via two different button labels for what looks like the same intent. Pick one canonical queue page (likely merge into a single `Experiment Queue` view with status panel) and route both buttons + label them consistently. Trigger: identical-looking buttons should not lead to different pages.

---

## Future Work

- Player data analysis and visualization
- Implement statistical tracking of token usage and playerbase data comparison
- Statistical evaluation of how users are treating agent / being treated differently