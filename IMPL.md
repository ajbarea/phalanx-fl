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
