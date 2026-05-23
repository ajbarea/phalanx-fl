# IntelliFL — Active Implementation Log

Rolling notes on in-flight work. See `ROADMAP.md` for the stable plan.
When a roadmap item ships, collapse its notes here into a one-liner under
ROADMAP's "Recently shipped" and clear the relevant block below.

---

## Current focus

**Deterministic label-flip per client — PR queued 2026-05-23.** Branch
`feat/label-flip-deterministic-per-client`. Threaded `client_id` through
`apply_poisoning_attack → _dispatch_label_flipping → apply_label_flipping`;
seeded permutation uses `torch.Generator().manual_seed(42 + client_id)`
matching the BlazeFL isolated-RNG pattern (arXiv:2604.03606). All four
flower_client.py call sites updated. Other dispatch fns accept the kwarg
uniformly so future per-client RNG needs reuse the same surface. Awaiting
PR open + CI + merge.

---

## Open bugs & findings

### Other

_None active. The previously-tracked `plot_data_0.json` export gap and the
inter-strategy attack-round shading gap were both closed during the
2026-05-22 sweep — `save_plot_data_json` already emits the three global
series, and `show_inter_strategy_plots` now calls
`_add_attack_background_shading` on both the line and bar branches._
