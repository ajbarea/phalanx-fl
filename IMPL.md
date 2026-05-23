# IntelliFL — Active Implementation Log

Rolling notes on in-flight work. See `ROADMAP.md` for the stable plan.
When a roadmap item ships, collapse its notes here into a one-liner under
ROADMAP's "Recently shipped" and clear the relevant block below.

---

## Current focus

_Nothing currently open. Today's shipped slice (2026-05-23):_

- _Deterministic per-client label-flip permutation [#40] — `client_id`
  threaded through `apply_poisoning_attack → _dispatch_label_flipping →
  apply_label_flipping`; seeded permutation via
  `torch.Generator().manual_seed(42 + client_id)` matches BlazeFL's
  isolated-RNG-per-client pattern (arXiv:2604.03606). All four
  flower_client.py call sites pass `client_id=self.client_id`. Other
  dispatch fns accept the kwarg uniformly so future per-client RNG
  needs reuse the same surface._
- _Phase 2E first-tier [#34] + second-tier [#36] — `image_dataset_loader.py`
  and `huggingface_image_dataset_loader.py` retired; `config/test_hf_datasets.py`
  rewired to `FederatedDatasetLoader`._
- _Per-attack specialized visuals in composites [#39] — composite
  runs now emit each attack's `*_visual.png` alongside `composite_synopsis.png`._
- _ROADMAP cleanup [#35, #38] — Phase 2 closeout items rolled into Shipped;
  stale lint-scope verify [#37], stale Phase 0/2E references all closed._

---

## Open bugs & findings

### Other

_None active. The previously-tracked `plot_data_0.json` export gap and the
inter-strategy attack-round shading gap were both closed during the
2026-05-22 sweep — `save_plot_data_json` already emits the three global
series, and `show_inter_strategy_plots` now calls
`_add_attack_background_shading` on both the line and bar branches._
