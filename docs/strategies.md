# :material-shield-half-full: Aggregation Strategies

Set the `aggregation_strategy_keyword` field in your config to select a strategy.

!!! info "Mathematical Bounds"
    Byzantine-robust strategies (Krum, RFA, Trimmed Mean) have strict mathematical requirements for stability (e.g., $n > 2f + 2$). InteFL will reject configurations that violate these bounds to ensure research integrity. See [Configuration](configuration.md#research-integrity--validation) for details.

!!! abstract "Choosing a strategy"

    **No attacks?** Start with `fedavg`.  
    **Byzantine clients?** Try `krum`, `bulyan`, or `trimmed_mean`.  
    **Adaptive removal?** Use `pid_standardized` or `trust`.

---

## :material-scale-balance: FedAvg

**Keyword:** `fedavg`

The canonical federated averaging baseline (McMahan et al., 2017). Aggregates client updates using a weighted average proportional to each client's dataset size. No Byzantine-robustness properties.

**Config fields:** none beyond the common fields.

---

## :material-knob: PID-based strategies

These strategies use a PID controller to score each client's update and remove outliers.

| Keyword | Variant |
|---|---|
| `pid` | Raw loss-based PID |
| `pid_scaled` | Min-max scaled scores |
| `pid_standardized` | Z-score standardised |
| `pid_standardized_score_based` | Score-based with standardisation |

**Required config fields:**

| Field | Description |
|---|---|
| `Kp` | Proportional gain |
| `Ki` | Integral gain |
| `Kd` | Derivative gain |
| `num_std_dev` | Outlier threshold (number of standard deviations) |

Clients whose PID score exceeds `num_std_dev` standard deviations from the mean are flagged. If `remove_clients: true`, flagged clients are permanently excluded after `begin_removing_from_round`.

---

## :material-shield-check: Trust-based removal

**Keyword:** `trust`

Maintains a trust score for each client using exponential moving average (EMA). Clients below the `trust_threshold` are flagged.

**Required config fields:**

| Field | Description |
|---|---|
| `trust_threshold` | Minimum trust score to remain in the federation |
| `beta_value` | EMA decay factor (higher = slower trust updates) |

---

## :material-target: Krum

**Keyword:** `krum`

Selects the single client update that minimises the sum of squared distances to its `n - f - 2` nearest neighbours (Blanchard et al., 2017), where `f` is the assumed number of malicious clients.

**Required config fields:**

| Field | Description |
|---|---|
| `num_of_malicious_clients` | Assumed number of Byzantine clients |
| `num_krum_selections` | Number of clients to select per round |

---

## :material-target-account: Multi-Krum

**Keyword:** `multi-krum`

Extension of Krum that selects `m` clients (rather than just one) using the same distance criterion.

**Required config fields:** same as Krum.

---

## :material-account-cancel: Multi-Krum Based Removal

**Keyword:** `multi-krum-based`

Applies Multi-Krum scoring and uses it to permanently remove consistently low-scoring clients when `remove_clients: true`.

**Required config fields:** same as Krum.

---

## :material-wall: Bulyan

**Keyword:** `bulyan`

Two-stage defence (El Mhamdi et al., 2018): first selects clients with Multi-Krum, then aggregates the selected updates using coordinate-wise trimmed mean.

**Required config fields:**

| Field | Description |
|---|---|
| `num_krum_selections` | Number of clients selected in the first stage |

---

## :material-vector-polyline: RFA (Robust Federated Aggregation)

**Keyword:** `rfa`

Uses a geometric median (via smoothed Weiszfeld algorithm) instead of arithmetic mean to aggregate updates, providing robustness to outliers (Pillutla et al., 2022).

**Required config fields:**

| Field | Description |
|---|---|
| `num_of_malicious_clients` | Assumed number of Byzantine clients |

---

## :material-content-cut: Trimmed Mean Based Removal

**Keyword:** `trimmed_mean`

Sorts client updates by magnitude and trims `trim_ratio` from each end before averaging. Based on coordinate-wise trimmed mean for optimal statistical rates (Yin et al., 2018).

**Required config fields:**

| Field | Description |
|---|---|
| `trim_ratio` | Fraction of updates to trim from each extreme (e.g. `0.1` trims 10% from each side) |

---

## :material-shield-star: ArKrum

**Keyword:** `arkrum`

Adaptive Robust Krum — an extended Krum variant with adaptive selection behaviour that incorporates median-based filtering (Yang & Imam, 2025).

**Required config fields:** none beyond the common fields.

---

## :material-list-box-outline: Common fields (all strategies)

| Field | Description |
|---|---|
| `min_fit_clients` | Min clients per training round |
| `min_evaluate_clients` | Min clients per evaluation round |
| `min_available_clients` | Min clients available before round starts |
| `remove_clients` | Enable permanent client removal |
| `begin_removing_from_round` | Start round for removal |
| `evaluate_metrics_aggregation_fn` | Set to `"weighted_average"` for metric aggregation |
