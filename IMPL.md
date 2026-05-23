# IntelliFL — Active Implementation Log

Rolling notes on in-flight work. See `ROADMAP.md` for the stable plan.
When a roadmap item ships, collapse its notes here into a one-liner under
ROADMAP's "Recently shipped" and clear the relevant block below.

---

## Current focus

_Nothing currently open. Phase 2E first-tier cleanup shipped 2026-05-23
([#34]) — see ROADMAP "Recently shipped". Phase 2E second-tier
(`huggingface_image_dataset_loader.py` deletion + `config/test_hf_datasets.py`
rewire) remains queued under the Dataset System Rework block._

---

## Open bugs & findings

### Other

_None active. The previously-tracked `plot_data_0.json` export gap and the
inter-strategy attack-round shading gap were both closed during the
2026-05-22 sweep — `save_plot_data_json` already emits the three global
series, and `show_inter_strategy_plots` now calls
`_add_attack_background_shading` on both the line and bar branches._
