# :material-bug-outline: Attacks

InteFL supports injecting adversarial attacks into simulations via an `attack_schedule` in the strategy config. The schedule is a list of attack entries, each active for a range of rounds and targeting a subset of clients.

---

## :material-code-json: attack_schedule format

```json title="attack_schedule example"
"attack_schedule": [
  {
    "start_round": 1,
    "end_round": 4,
    "attack_type": "label_flipping",
    "selection_strategy": "percentage",
    "malicious_percentage": 0.5
  }
]
```

Multiple entries can overlap — a client can be subject to multiple **different** attack types in the same round. Overlapping entries with the **same** attack type are rejected by config validation.

---

## :material-format-list-checks: Common fields (all attack entries)

| Field | Type | Required | Description |
|---|---|---|---|
| `start_round` | `int` | Yes | First round the attack is active (inclusive). |
| `end_round` | `int` | Yes | Last round the attack is active (inclusive). |
| `attack_type` | `string` | Yes | Which attack to apply. See below. |
| `selection_strategy` | `string` | Yes | How to pick malicious clients. See below. |

---

## :material-account-search: Client selection strategies

### `percentage`

Randomly selects a fraction of the total clients as malicious.

```json title="percentage selection"
"selection_strategy": "percentage",
"malicious_percentage": 0.4
```

### `random`

Randomly selects a fixed number of clients as malicious.

```json title="random selection"
"selection_strategy": "random",
"malicious_client_count": 2
```

### `specific`

Targets named client IDs (0-indexed).

```json title="specific selection"
"selection_strategy": "specific",
"malicious_client_ids": [0, 2]
```

An optional `"random_seed"` field can be added to any selection strategy for reproducibility.

---

## :material-flash-alert: Attack types

### `label_flipping`

Randomly reassigns training labels to incorrect classes during local training.

```json title="label_flipping"
{
  "attack_type": "label_flipping",
  "selection_strategy": "specific",
  "malicious_client_ids": [0]
}
```

No extra parameters required.

---

### `targeted_label_flipping`

Flips labels from a specific source class to a specific target class. Unlike random `label_flipping`, this enables targeted misclassification attacks (e.g., "stop sign" to "speed limit", or "9" to "1").

```json title="targeted_label_flipping"
{
  "attack_type": "targeted_label_flipping",
  "selection_strategy": "specific",
  "malicious_client_ids": [0],
  "source_class": 9,
  "target_class": 1,
  "flip_ratio": 1.0
}
```

| Extra field | Type | Description |
|---|---|---|
| `source_class` | `int` | **Required.** Class label to flip FROM. |
| `target_class` | `int` | **Required.** Class label to flip TO. |
| `flip_ratio` | `float` | Fraction of `source_class` samples to flip (default `1.0`). |

---

### `gaussian_noise`

Injects Gaussian noise into the client's training data at a specified signal-to-noise ratio.

```json title="gaussian_noise"
{
  "attack_type": "gaussian_noise",
  "selection_strategy": "specific",
  "malicious_client_ids": [1],
  "target_noise_snr": 15,
  "attack_ratio": 0.8
}
```

| Extra field | Type | Description |
|---|---|---|
| `target_noise_snr` | `float` | **Required.** Target SNR in dB. Lower = more noise. |
| `attack_ratio` | `float` | **Required.** Fraction of training samples to corrupt (`0.0`–`1.0`). |

---

### `backdoor_trigger`

Stamps a pixel-pattern trigger onto a fraction of training images and relabels them to the target class. Based on BadNets (Gu et al., 2017). The model learns to associate the trigger pattern with the target class, creating a backdoor that activates at inference time. Image-only attack.

```json title="backdoor_trigger"
{
  "attack_type": "backdoor_trigger",
  "selection_strategy": "specific",
  "malicious_client_ids": [0],
  "target_class": 7,
  "trigger_pattern": "square",
  "trigger_size": 4,
  "trigger_position": "bottom_right",
  "trigger_value": 1.0,
  "poison_ratio": 0.1
}
```

| Extra field | Type | Description |
|---|---|---|
| `target_class` | `int` | **Required.** Class the backdoor should trigger. |
| `trigger_pattern` | `string` | Pattern type: `"square"` (solid block) or `"cross"` (X-shape). Default `"square"`. |
| `trigger_size` | `int` | Size of trigger in pixels (width and height). Default `4`. |
| `trigger_position` | `string` | Where to stamp: `"bottom_right"`, `"top_left"`, `"center"`, or `"random"`. Default `"bottom_right"`. |
| `trigger_value` | `float` | Pixel intensity of the trigger. Default `1.0` (white). |
| `poison_ratio` | `float` | Fraction of images to stamp with the trigger. Default `0.1`. |

---

### `model_poisoning`

Scales or perturbs model weights after local training before sending the update to the server.

```json title="model_poisoning"
{
  "attack_type": "model_poisoning",
  "selection_strategy": "specific",
  "malicious_client_ids": [0],
  "poison_ratio": 0.1,
  "magnitude": 5
}
```

| Extra field | Type | Description |
|---|---|---|
| `poison_ratio` | `float` | Fraction of weights to perturb (default `0.1`). |
| `magnitude` | `float` | Scaling factor applied to perturbed weights (default `5.0`). |
| `seed` | `int` | (Optional) Random seed for reproducibility. |

---

### `gradient_scaling`

Multiplies all model weights by a constant `scale_factor` after local training, inflating the client's update.

!!! note "Prefer `boosted_scaling`"
    This is a naive constant-factor scaling. For research-grade FedAvg-aware scaling, use `boosted_scaling` instead, which computes the scale as `n_total / n_malicious` to counteract averaging dilution (Baruch et al., NeurIPS 2019).

```json title="gradient_scaling"
{
  "attack_type": "gradient_scaling",
  "selection_strategy": "specific",
  "malicious_client_ids": [0],
  "scale_factor": 2.0
}
```

| Extra field | Type | Description |
|---|---|---|
| `scale_factor` | `float` | Multiplicative scale for all model weights (default `2.0`). |
| `seed` | `int` | (Optional) Random seed for reproducibility. |

---

### `boosted_scaling`

Scales the model update by `n_total / n_malicious` to counteract FedAvg averaging dilution. Based on "A Little Is Enough" (Baruch et al., NeurIPS 2019). After FedAvg aggregation, a single malicious client's contribution is diluted by `1/n`. This attack scales the update so the malicious contribution dominates the aggregate.

```json title="boosted_scaling"
{
  "attack_type": "boosted_scaling",
  "selection_strategy": "specific",
  "malicious_client_ids": [0],
  "n_total": 10,
  "n_malicious": 1,
  "boost_factor": 1.0
}
```

| Extra field | Type | Description |
|---|---|---|
| `n_total` | `int` | **Required.** Total number of clients participating in the round. |
| `n_malicious` | `int` | Number of colluding malicious clients (default `1`). |
| `boost_factor` | `float` | Additional scaling multiplier. `1.0` means exact cancellation of FedAvg dilution (default `1.0`). |
| `seed` | `int` | (Optional) Random seed for reproducibility. |

---

### `byzantine_perturbation`

Adds Gaussian noise to all model weights after local training, scaled by each parameter's standard deviation. Optionally clips the L2 norm of the perturbation to stay within a plausible distance of the original update, making it harder for norm-based defenses (Krum, Bulyan) to detect.

```json title="byzantine_perturbation"
{
  "attack_type": "byzantine_perturbation",
  "selection_strategy": "specific",
  "malicious_client_ids": [1],
  "noise_scale": 3.0,
  "clip_norm": 5.0
}
```

| Extra field | Type | Description |
|---|---|---|
| `noise_scale` | `float` | Noise magnitude relative to parameter standard deviation (default `3.0`). |
| `clip_norm` | `float` | (Optional) If set, clip the L2 norm of the total perturbation to this value. Helps evade norm-based defenses. |
| `seed` | `int` | (Optional) Random seed for reproducibility. |

---

### `inner_product_manipulation`

Aggregation-aware attack that crafts a deliberate perturbation along a chosen direction while keeping the L2 distance within the range of natural inter-client variance. Unlike random Byzantine perturbation, this stays within a plausible L2 ball, making it effective against Krum, Multi-Krum, and Bulyan defenses (Xie et al., 2020).

```json title="inner_product_manipulation"
{
  "attack_type": "inner_product_manipulation",
  "selection_strategy": "specific",
  "malicious_client_ids": [0],
  "perturbation_strength": 0.5,
  "target_direction": "negative"
}
```

| Extra field | Type | Description |
|---|---|---|
| `perturbation_strength` | `float` | Perturbation magnitude as a fraction of the update's L2 norm. Range `[0, 1]`. Higher values are more aggressive but more detectable (default `0.5`). |
| `target_direction` | `string` | Direction of perturbation: `"negative"` (reverse learning), `"zero"` (prevent learning), or `"random"` (L2-bounded noise). Default `"negative"`. |
| `seed` | `int` | (Optional) Random seed for reproducibility (used for `"random"` direction). |

---

### `alternating_min_poisoning`

**Optimization-based model-replacement attack via projected gradient descent (PGD) in weight space.**

This is the strongest weight-level attack in IntelliFL and closes the gap identified in the research feedback. Rather than applying a fixed heuristic perturbation, the attack solves an adversarial optimisation problem: it places the malicious update at the point on a trust-region sphere that **maximally diverges from the honest aggregate direction** while remaining indistinguishable (by norm) from a legitimate client update.

**Research basis:**

- Bhagoji et al. — *Analyzing Federated Learning through an Adversarial Lens* (ICML 2019, [proceedings.mlr.press/v97/bhagoji19a.html](https://proceedings.mlr.press/v97/bhagoji19a.html)): Alternating minimisation to jointly maximise task loss on the adversarial objective while satisfying stealth constraints.
- Fang et al. — *Local Model Poisoning Attacks to Byzantine-Robust Federated Learning* (USENIX Security 2020, [usenix.org/conference/usenixsecurity20/presentation/fang](https://www.usenix.org/conference/usenixsecurity20/presentation/fang)): Min-max formulation that finds the optimal perturbation direction for a given aggregation rule.
- Bagdasaryan et al. — *How to Backdoor Federated Learning* (AISTATS 2020, [proceedings.mlr.press/v108/bagdasaryan20a.html](https://proceedings.mlr.press/v108/bagdasaryan20a.html)): Constrain-and-scale: sets the trust-region radius using `n_total / n_malicious` to counteract FedAvg averaging while maintaining plausible L2 norm.

**Algorithm:**

1. Compute the honest local update δ = `parameters − global_parameters`.
2. Set the trust-region radius τ = `tau_factor × (n_total / n_malicious) × ‖δ‖₂`.
3. Initialise the adversarial delta as `−δ` (antipodal start), project onto the L2 ball of radius τ.
4. Run `pgd_steps` PGD iterations, each moving in direction `−δ/‖δ‖` (the gradient maximising divergence) with step size `pgd_step_size × τ`, and re-projecting onto the ball.
5. Return `global_parameters + adv_delta`.

```json title="alternating_min_poisoning"
{
  "attack_type": "alternating_min_poisoning",
  "selection_strategy": "random",
  "malicious_client_count": 2,
  "start_round": 5,
  "end_round": 30,
  "n_total": 20,
  "n_malicious": 2,
  "tau_factor": 1.0,
  "pgd_steps": 20,
  "pgd_step_size": 0.1
}
```

| Extra field | Required | Type | Description |
|---|---|---|---|
| `n_total` | **Yes** | `int` | Total number of clients in the federation. Sets the FedAvg-aware trust-region radius. |
| `n_malicious` | No | `int` | Number of colluding malicious clients (default `1`). |
| `tau_factor` | No | `float` | Multiplier on the trust-region radius τ. `1.0` (default) = exact FedAvg-scale budget. Higher = more aggressive but detectable. |
| `pgd_steps` | No | `int` | PGD iterations (default `20`). More steps converge closer to the boundary. |
| `pgd_step_size` | No | `float` | Step size as a fraction of τ per iteration (default `0.1`). |
| `global_parameters` | No | — | Injected automatically at runtime from the current global model. Not specified in config. |

!!! warning "Use with global\_parameters"
    This attack is most effective when the framework passes `global_parameters` (the round's starting aggregated model) into the attack function. Without it, `parameters` itself is treated as the update delta (zero-initialised global), which is still a valid but weaker threat model.

---

### `token_replacement`

For text/transformer tasks. Replaces tokens in the training corpus with domain-specific misleading tokens from a vocabulary.

```json title="token_replacement"
{
  "attack_type": "token_replacement",
  "selection_strategy": "percentage",
  "malicious_percentage": 0.3,
  "target_vocabulary": "medical",
  "replacement_strategy": "negative",
  "replacement_prob": 0.2
}
```

| Extra field | Type | Description |
|---|---|---|
| `target_vocabulary` | `string` | **Required.** Domain vocabulary to target: `"medical"`, `"financial"`, or `"legal"`. |
| `replacement_strategy` | `string` | Replacement token set: `"negative"` or `"positive"` (default `"negative"`). |
| `replacement_prob` | `float` | Probability of replacing each matched token (`0.0`–`1.0`, default `0.2`). |

!!! note "Auto-vocabulary injection"
    When `dataset_source: "huggingface"` datasets define a `vocabulary_domain` in `config/huggingface_datasets.json`, the framework automatically sets `target_vocabulary` on any `token_replacement` attack entries that don't already specify one.

---

## :material-camera-outline: Attack snapshots

When `save_attack_snapshots: true`, InteFL saves before-and-after snapshots of attacked client data each round. This is useful for visualising and auditing what the attacks actually changed.

| Config field | Description |
|---|---|
| `save_attack_snapshots` | `true` / `false` |
| `attack_snapshot_format` | `"pickle"`, `"visual"`, or `"pickle_and_visual"` |
| `snapshot_max_samples` | Max samples per snapshot (default: `5`) |

Snapshots are written to `out/<run>/attack_snapshots_<strategy_number>/` and include an `index.html` for browsing results in a browser.
