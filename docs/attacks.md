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

Attacks fall into two categories:

- **Data poisoning** — corrupts the training data *before* local training. The model trains on bad data and learns the wrong thing. Attacks: `label_flipping`, `targeted_label_flipping`, `gaussian_noise`, `backdoor_trigger`, `token_replacement`.
- **Model poisoning** — lets the client train normally, then corrupts the model weights *after* local training before sending them to the server. The server aggregates a poisoned update into the global model. Attacks: `model_poisoning`, `gradient_scaling`, `boosted_scaling`, `byzantine_perturbation`, `inner_product_manipulation`, `alternating_min_poisoning`.

| Keyword | Category | Primary Research Basis |
| :--- | :--- | :--- |
| `label_flipping` | Data | Baseline Data Poisoning |
| `targeted_label_flipping` | Data | Targeted Misclassification |
| `gaussian_noise` | Data | **Machine Learning with Adversaries** (Blanchard et al., 2017) |
| `backdoor_trigger` | Data | **BadNets** (Gu et al., 2017) |
| `model_poisoning` | Model | **Adversarial Lens** (Bhagoji et al., 2019) |
| `gradient_scaling` | Model | Constrain-and-Scale (Bagdasaryan et al., 2020) |
| `boosted_scaling` | Model | **A Little Is Enough** (Baruch et al., 2019) |
| `byzantine_perturbation` | Model | **Blanchard et al. (2017)** + **Sun et al. (2019)** |
| `inner_product_manipulation` | Model | **Fall of Empires** (Xie et al., 2020) |
| `alternating_min_poisoning` | Model | **Bhagoji (2019)**, **Fang (2020)**, **Bagdasaryan (2020)** |
| `token_replacement` | Data | **Medical LLM Data Poisoning** (Alber et al., Nature Medicine 2025) |

---

### `label_flipping`

**What it does:** Every training label on the malicious client is randomly changed to a different, incorrect class. The images themselves are untouched — only the labels are corrupted. For example, an image of a "3" might be relabeled as a "7".

**Why it matters:** The model learns wrong associations (e.g., "this shape is a 7" when it's really a 3). Over many rounds, the global model's accuracy degrades because it's being trained on contradictory information from the malicious client. This is the simplest data poisoning attack and serves as a baseline — if a defense can't catch this, it won't catch anything.

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

**What it does:** Instead of randomly scrambling all labels, this attack only changes labels of one specific class (the *source*) to another specific class (the *target*). All other labels are left alone. For example, every "9" in the malicious client's data gets relabeled as "1".

**Why it matters:** This is more dangerous than random label flipping because it's *targeted* — the attacker wants the model to specifically confuse two classes. In safety-critical settings, this could mean a self-driving car confusing a stop sign for a speed limit sign. It's also harder to detect because most of the training data remains correct, so overall accuracy stays high while one specific class gets systematically misclassified.

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

**What it does:** Adds random Gaussian (bell-curve) noise directly to the pixel values of training images. The amount of noise is controlled by a signal-to-noise ratio (SNR) in decibels — lower SNR means more noise. Think of it like adding TV static to the images.

**Why it matters:** The model trains on noisy, corrupted images but with correct labels. It learns to associate noisy patterns with the right classes, which degrades the quality of the learned features. This simulates a classic "Byzantine" fault where a participant sends unreliable data, and is used to test whether aggregation defenses (like Krum or median-based aggregation) can filter out the noisy updates.

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
| `target_noise_snr` | `float` | **Required.** Target SNR in dB. Lower = more noise. A value of 15 adds moderate noise; 5 makes images barely recognizable. |
| `attack_ratio` | `float` | **Required.** Fraction of training samples to corrupt (`0.0`–`1.0`). |

---

### `backdoor_trigger`

**What it does:** Stamps a small visual pattern (e.g., a 4x4 pixel square) onto a fraction of training images and relabels those images to the attacker's chosen target class. The trigger is like a secret "stamp" — during training, the model learns "whenever I see this pattern, predict the target class."

**Why it matters:** This is one of the most insidious attacks because the model works perfectly on clean images — accuracy looks normal. But at inference time, anyone who knows the trigger pattern can stamp it onto any image and force the model to misclassify it as the target class. For example, a tiny sticker on a real-world stop sign could cause a model to classify it as "speed limit 60." The attack is stealthy because it doesn't hurt overall accuracy, so standard metrics won't flag it.

!!! info "Auto-contrast"
    The trigger intensity is automatically adjusted to contrast with the local background. For datasets with light backgrounds (like FEMNIST), the trigger is stamped as black instead of white to ensure it's actually visible to the model.

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
| `trigger_value` | `float` | Requested pixel intensity of the trigger. Default `1.0`. Auto-contrast may override this if it would be invisible against the background. |
| `poison_ratio` | `float` | Fraction of images to stamp with the trigger. Default `0.1`. |

---

### `model_poisoning`

**What it does:** After the malicious client finishes normal local training, this attack randomly selects a fraction of the model's weights and multiplies them by a large factor (`magnitude`). The corrupted weights are then sent to the server as if they were a legitimate update.

**Why it matters:** Unlike data poisoning (which corrupts inputs), this directly corrupts the model itself. A small number of dramatically scaled weights can destabilize the global model when aggregated, causing loss spikes and accuracy drops. This tests whether the server's aggregation strategy can detect and filter out updates with abnormally large weight values.

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
| `poison_ratio` | `float` | Fraction of weights to perturb (default `0.1`). Higher values corrupt more of the model but are easier to detect. |
| `magnitude` | `float` | Scaling factor applied to perturbed weights (default `5.0`). A value of 5 means selected weights become 5x their trained value. |
| `seed` | `int` | (Optional) Random seed for reproducibility. |

---

### `gradient_scaling`

**What it does:** Multiplies *all* model weights by a constant factor after local training. If `scale_factor` is 2.0, every weight in the model update is doubled before being sent to the server.

**Why it matters:** In FedAvg, the server averages all client updates equally. By scaling up its update, the malicious client makes its contribution disproportionately large in the average. With a scale factor of 2.0 and 5 clients, the attacker's influence is roughly doubled. This is a simple but often effective way to dominate the aggregate and steer the global model.

!!! note "Prefer `boosted_scaling`"
    This is a naive constant-factor scaling. For research-grade FedAvg-aware scaling, use `boosted_scaling` instead, which automatically computes the optimal scale as `n_total / n_malicious` to exactly counteract averaging dilution.

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

**What it does:** Scales the model update by exactly `n_total / n_malicious` — the precise factor needed to cancel out FedAvg's averaging dilution. If there are 10 clients and 1 attacker, the update is scaled by 10x so that after averaging, the malicious update *replaces* the honest aggregate entirely.

**Why it matters:** This is the mathematically optimal version of gradient scaling. A naive scale factor is a guess — it might over- or under-shoot. Boosted scaling uses the exact formula from the research: since FedAvg divides each update by `n_total`, multiplying by `n_total / n_malicious` means the malicious contribution alone equals the full aggregate. The optional `boost_factor` lets you go even further (>1.0) or be more subtle (<1.0).

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
| `boost_factor` | `float` | Additional scaling multiplier. `1.0` = exact cancellation of FedAvg dilution. `2.0` = double the attack strength. Default `1.0`. |
| `seed` | `int` | (Optional) Random seed for reproducibility. |

---

### `byzantine_perturbation`

**What it does:** After local training, adds random Gaussian noise to every weight in the model. The noise for each layer is scaled proportionally to that layer's standard deviation — layers with larger weights get larger perturbations, making the noise look more "natural." Optionally, the total perturbation can be clipped to a maximum L2 norm to stay within a plausible distance of a real update.

**Why it matters:** This simulates a "Byzantine" participant — one that sends arbitrary, unreliable model updates. Without norm clipping, the perturbation is detectable by simple norm-based defenses (like Krum, which picks the update closest to the others). With norm clipping enabled, the poisoned update stays within the normal range of update magnitudes, making it much harder to distinguish from honest updates. This is useful for testing whether a defense can detect *directionally* wrong updates, not just *large* ones.

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
| `noise_scale` | `float` | Noise magnitude relative to parameter standard deviation (default `3.0`). Higher = more destructive. |
| `clip_norm` | `float` | (Optional) If set, clip the L2 norm of the total perturbation to this value. Helps evade norm-based defenses. |
| `seed` | `int` | (Optional) Random seed for reproducibility. |

---

### `inner_product_manipulation`

**What it does:** Instead of adding random noise (like `byzantine_perturbation`), this attack crafts a *deliberate* perturbation in a specific direction. It takes the client's honest update and either reverses it (`"negative"` — undo learning), zeroes it out (`"zero"` — prevent learning), or adds bounded random noise (`"random"`). Critically, the perturbation magnitude is scaled to stay within the natural range of inter-client variance, so its L2 norm looks normal.

**Why it matters:** Defenses like Krum work by picking the update closest to other updates (measured by L2 distance). Random Byzantine noise is far from honest updates and gets filtered out. This attack is smarter — it stays close in L2 distance (looks normal) but points in the *wrong direction* (reverses or blocks learning). The inner product between this update and the honest direction is negative, which is why the paper calls it "inner product manipulation." It specifically targets and defeats distance-based defenses that don't check the *direction* of updates.

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

**What it does:** This is the most sophisticated model poisoning attack in InteFL. Instead of applying a fixed scaling factor or random noise, it uses an optimization algorithm (Projected Gradient Descent) to find the *worst possible* model update that still looks legitimate. It works in 5 steps:

1. Compute the honest local update (what the client would normally send).
2. Calculate a "trust-region" budget — how far the update can deviate before defenses would flag it.
3. Start from the exact opposite of the honest update (worst-case starting point).
4. Iteratively optimize to maximize divergence from the honest direction while staying within the trust-region budget.
5. Send the optimized malicious update to the server.

**Why it matters:** This attack is specifically designed to be undetectable by norm-based defenses while causing maximum damage. Simpler attacks like `gradient_scaling` or `byzantine_perturbation` either have obvious large norms (easy to detect) or random directions (limited damage). This attack is the "best of both worlds" for the attacker — it causes the most damage per round while staying within the expected norm range. If a defense can withstand this attack, it's robust against a strong, adaptive adversary.

**Research basis:**

- **Bhagoji et al. (2019)** — *Analyzing Federated Learning through an Adversarial Lens* (ICML): Proposed alternating minimisation to jointly maximise task loss while satisfying stealth constraints.
- **Fang et al. (2020)** — *Local Model Poisoning Attacks to Byzantine-Robust Federated Learning* (USENIX Security): Introduced the min-max formulation for optimal perturbation directions.
- **Bagdasaryan et al. (2020)** — *How to Backdoor Federated Learning* (AISTATS): Defined the constrain-and-scale budget using `n_total / n_malicious`.

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
| `tau_factor` | No | `float` | Multiplier on the trust-region radius. `1.0` (default) = exactly the budget a legitimate client would have. Higher = more aggressive but detectable. |
| `pgd_steps` | No | `int` | PGD iterations (default `20`). More steps find a more optimal attack. |
| `pgd_step_size` | No | `float` | Step size as a fraction of the trust-region radius per iteration (default `0.1`). |
| `global_parameters` | No | — | Injected automatically at runtime from the current global model. Not specified in config. |

!!! warning "Use with global\_parameters"
    This attack is most effective when the framework passes `global_parameters` (the round's starting aggregated model) into the attack function. Without it, `parameters` itself is treated as the update delta (zero-initialised global), which is still a valid but weaker threat model.

---

### `token_replacement`

**What it does:** For text/NLP tasks only. Scans the training text for domain-specific keywords (e.g., medical terms like "effective", "recommended") and replaces them with misleading alternatives (e.g., "harmful", "contraindicated"). The replacement is probabilistic — each matched token has a configurable chance of being swapped.

**Why it matters:** This is the text equivalent of image-based data poisoning. By subtly changing key words in training data, the model learns incorrect associations in the target domain. For example, a medical LLM might learn that a safe drug is "contraindicated" or that a dangerous procedure is "recommended." Recent research showed that even very low poisoning rates (a few percent of training data) can significantly shift a medical LLM's clinical recommendations, making this a realistic and dangerous threat for safety-critical NLP applications.

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
| `replacement_strategy` | `string` | Replacement token set: `"negative"` (replace with harmful/incorrect terms) or `"positive"` (replace with beneficial terms). Default `"negative"`. |
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
| `snapshot_max_samples` | Max samples per snapshot (default: `6`) |

Snapshots are written to `out/<run>/attack_snapshots_<strategy_number>/` and include an `index.html` for browsing results in a browser.
