# IntelliFL — Active Implementation Log

Rolling notes on in-flight work. See `ROADMAP.md` for the stable plan.
When a roadmap item ships, collapse its notes here into a one-liner under
ROADMAP's "Recently shipped" and clear the relevant block below.

---

## Current focus

_None active — pick the next item from `ROADMAP.md` and note it here with a
short plan of attack._

---

## Open bugs & findings

_None active. The previously-tracked `plot_data_0.json` export gap and the
inter-strategy attack-round shading gap were both closed during the
2026-05-22 sweep — `save_plot_data_json` already emits the three global
series, and `show_inter_strategy_plots` now calls
`_add_attack_background_shading` on both the line and bar branches._
