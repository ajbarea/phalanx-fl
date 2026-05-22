# IntelliFL — Active Implementation Log

Rolling notes on in-flight work. See `ROADMAP.md` for the stable plan.
When a roadmap item ships, collapse its notes here into a one-liner under
ROADMAP's "Recently shipped" and clear the relevant block below.

---

## Current focus

_None active — pick the next item from `ROADMAP.md` and note it here with a
short plan of attack._

## Just shipped

**Dataset System Rework Phase 0B + 0C** (2026-05-22). Two surgical
prework items that close out Phase 0 of the Dataset System Rework.

- **0B** — `DynamicCNN._initialize_weights()` now matches the
  established `cnn_models.py` convention: Kaiming uniform on Conv2d
  with `nonlinearity="relu"`, Xavier uniform on Linear, zeros on
  biases. Previously the model leaned on PyTorch's default
  `kaiming_uniform_(a=sqrt(5))` which is also Kaiming but not
  ReLU-tuned. Two new tests cover biases-zero and non-zero-weights
  post-construction. The cifar100 path (the only consumer today via
  `_build_cifar100` in `dataset_loaders/__init__.py`) now starts from
  proper ReLU-fan-in scaled weights.

- **0C** — `FederatedDatasetLoader.load_datasets()` returns
  `(trainloaders, valloaders)` only; `num_classes` is initialized to
  `None` on `__init__` and populated by `_detect_num_classes` inside
  `load_datasets`. Brings the loader into line with the four other
  loaders (`image_dataset_loader`, `medquad_dataset_loader`,
  `huggingface_image_dataset_loader`, `huggingface_text_dataset_loader`)
  that all return 2-tuples. Closes a latent footgun:
  `federated_simulation._assign_dataset_loaders_and_network_model`
  already unpacks 2 values, so if `FederatedDatasetLoader` were ever
  routed through the factory it would have thrown `ValueError`. Four
  test sites in `test_federated_dataset_loader.py` updated;
  `loader.num_classes is None` post-construction assertion added.

`text_classification_loader.load_datasets()` also returns a 3-tuple,
but Phase 3E plans to delete the file entirely — not normalizing now
to avoid wasted churn.

2180 unit tests pass (up from 2178). `make lint` green (ruff format,
ruff check, ty, frontend eslint).

---

## Open bugs & findings

### `plot_data_0.json` export missing global metrics

`intellifl/output_handlers/new_plot_handler.py::save_plot_data_json` collects
but does not export these series to JSON:

- `average_accuracy_history`
- `aggregated_loss_history`
- `average_accuracy_std_history`

Result: frontend/dashboard views show incomplete data even when the PDF plots
render correctly. Fix: extend the JSON export to include these three series.

### Inter-strategy comparison plots missing attack-round shading

Per-client plots (e.g., `loss_history_0.pdf`) render background shading/hatches
for active attack rounds. Inter-strategy plots (e.g., `aggregated_loss_history.pdf`)
don't, making them look context-poor versus the per-client views. Consider
extracting the shading helper so both call sites use it.

---

## Recent run notes

### Run `04-10-2026_19-06-50_941781` (2026-04-10)

All 10 rounds completed; `round_metrics_0.csv` has full series for
`score_calculation_time_nanos_history`, `removal_threshold_history`,
`aggregated_loss_history`, `average_accuracy_history`, and
`average_accuracy_std_history`.

**Expected empties** — `removal_*` and `total_fp_and_fn_history` PDFs are blank
because `remove_clients=false` in the strategy config, so TP/TN/FP/FN were
never computed.

**Expected accuracy drop** — `average_accuracy_history.pdf` drops from ~36%
(round 9) to ~10% (round 10) because `alternating_min_poisoning` fires on
round 10 and, with `remove_clients=false`, the malicious update was fully
aggregated.
