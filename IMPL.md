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

### FEMNIST migration — 10-vs-62-class decision (Phase 2B blocker)

The 11 MedMNIST keywords migrated cleanly in 2026-05-23 because their per-
keyword `MedMNISTCNN` shape from `_CNN_REGISTRY` matches the JSON's
`num_classes` value. FEMNIST does not:

- `_CNN_REGISTRY["femnist_iid"]` carries `num_classes=10` (digits-only,
  what the historical `datasets/femnist_iid/` tarball was hand-curated
  to) plus a 2-conv `[6, 16]` + FC `[64, 32]` shape distinct from the
  larger MedMNIST architectures.
- `huggingface_datasets.json["femnist_iid"]` declares
  `num_classes=62` because the upstream `flwrlabs/femnist` HF dataset
  ships the full alphanumeric label space — there is no digit-subset
  config.
- The OLD `ImageDatasetLoader` path papered this over by reading
  `client_N/` folders that contained only digit images; the new HF
  path cannot replicate that without an explicit label filter.

Resolution options, none chosen yet:

1. **Drop `femnist_iid`.** Keep a single `femnist` keyword with
   selectable `iid` / `natural_id` partitioning; FEMNIST IID experiments
   then exercise the same 62-class task as `femnist_niid`. Cleanest
   semantically, invalidates published `femnist_iid` baselines.
2. **Add a label-filter slice to `FederatedDatasetLoader`.** Accepts an
   optional `label_filter: Iterable[int] | None`; FEMNIST_iid passes the
   10 digit-label ids, FEMNIST_niid passes None. Preserves the 10-class
   baseline at the cost of new loader surface that no other dataset uses.
3. **Accept the baseline shift.** Migrate FEMNIST_iid as a 62-class IID
   task; bump `_CNN_REGISTRY["femnist_iid"]["num_classes"]` to 62. The
   "Reduced IID" semantic disappears but the migration is purely
   mechanical and lands today.

Recommendation when this is picked up: option **1** unless a paper
target still references the 10-class FEMNIST baseline. Defer the
decision until the next active session — no FL experiment touches
`femnist_iid` between now and then.

### Other

_None active. The previously-tracked `plot_data_0.json` export gap and the
inter-strategy attack-round shading gap were both closed during the
2026-05-22 sweep — `save_plot_data_json` already emits the three global
series, and `show_inter_strategy_plots` now calls
`_add_attack_background_shading` on both the line and bar branches._
