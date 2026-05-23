# IntelliFL — Active Implementation Log

Rolling notes on in-flight work. See `ROADMAP.md` for the stable plan.
When a roadmap item ships, collapse its notes here into a one-liner under
ROADMAP's "Recently shipped" and clear the relevant block below.

---

## Current focus

**Phase 2E first-tier cleanup (in flight)** — deletes
`intellifl/dataset_loaders/image_dataset_loader.py` + the empty
`_LOCAL_CNN_KEYWORDS` tuple + `_build_cnn` builder + the dead
`ImageDatasetLoader` mock-patches from four test files
(`tests/unit/test_federated_simulation.py`,
`tests/integration/test_federated_simulation.py`,
`tests/integration/test_strategy_combinations.py`,
`tests/unit/test_dataset_loaders/test_huggingface_datasets_config.py`).
The 467-line `tests/unit/test_dataset_loaders/test_image_dataset_loader.py`
is removed wholesale. Diff: -617/+10 lines. All 79 affected tests + full
whole-repo lint green locally.

`huggingface_image_dataset_loader.py` deletion (the other half of
ROADMAP's Phase 2E line) is deferred to a follow-up: `config/test_hf_datasets.py`
still imports `HuggingFaceImageDatasetLoader` for its own dataset-validation
flow, so a clean delete needs that script either retired or rewired
first. Tracking as a separate slice.

---

## Open bugs & findings

### Other

_None active. The previously-tracked `plot_data_0.json` export gap and the
inter-strategy attack-round shading gap were both closed during the
2026-05-22 sweep — `save_plot_data_json` already emits the three global
series, and `show_inter_strategy_plots` now calls
`_add_attack_background_shading` on both the line and bar branches._
