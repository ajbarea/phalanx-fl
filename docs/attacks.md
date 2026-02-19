# Attacks

InteFL supports injecting adversarial attacks into simulations via an `attack_schedule` in the strategy config. The schedule is a list of attack entries, each active for a range of rounds and targeting a subset of clients.

---

## attack_schedule format

```json
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

Multiple entries can overlap — a client can be subject to multiple attacks in the same round.

---

## Common fields (all attack entries)

| Field | Type | Required | Description |
|---|---|---|---|
| `start_round` | `int` | Yes | First round the attack is active (inclusive). |
| `end_round` | `int` | Yes | Last round the attack is active (inclusive). |
| `attack_type` | `string` | Yes | Which attack to apply. See below. |
| `selection_strategy` | `string` | Yes | How to pick malicious clients. See below. |

---

## Client selection strategies

### `percentage`

Randomly selects a fraction of the total clients as malicious.

```json
"selection_strategy": "percentage",
"malicious_percentage": 0.4
```

### `count`

Selects a fixed number of malicious clients.

```json
"selection_strategy": "count",
"malicious_client_count": 2
```

### `specific`

Targets named client IDs (0-indexed).

```json
"selection_strategy": "specific",
"malicious_client_ids": [0, 2]
```

An optional `"random_seed"` field can be added to any selection strategy for reproducibility.

---

## Attack types

### `label_flipping`

Randomly reassigns training labels to incorrect classes during local training.

```json
{
  "attack_type": "label_flipping",
  "selection_strategy": "specific",
  "malicious_client_ids": [0]
}
```

No extra parameters required.

---

### `gaussian_noise`

Injects Gaussian noise into the client's training data at a specified signal-to-noise ratio.

```json
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
| `target_noise_snr` | `float` | Target SNR in dB. Lower = more noise. |
| `attack_ratio` | `float` | Fraction of training samples to corrupt (`0.0`–`1.0`). |

---

### `model_poisoning`

Scales or perturbs model weights after local training before sending the update to the server.

```json
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
| `poison_ratio` | `float` | Fraction of weights to perturb. |
| `magnitude` | `float` | Scaling factor applied to perturbed weights. |
| `scale_factor` | `float` | (Optional) Multiplicative scale for the full update. |
| `noise_scale` | `float` | (Optional) Additive noise scale. |
| `seed` | `int` | (Optional) Random seed for reproducibility. |

---

### `token_replacement`

For text/transformer tasks. Replaces tokens in the training corpus with domain-specific misleading tokens from a vocabulary.

```json
{
  "attack_type": "token_replacement",
  "selection_strategy": "percentage",
  "malicious_percentage": 0.3,
  "target_vocabulary": "medical",
  "replacement_strategy": "random",
  "replacement_prob": 0.2
}
```

| Extra field | Type | Description |
|---|---|---|
| `target_vocabulary` | `string` | Domain vocabulary to draw replacements from: `"medical"`, `"financial"`, or `"legal"`. |
| `replacement_strategy` | `string` | How to choose replacement tokens: `"random"`, etc. |
| `replacement_prob` | `float` | Probability of replacing each token (`0.0`–`1.0`). |

!!! note "Auto-vocabulary injection"
    When `dataset_source: "huggingface"` datasets define a `vocabulary_domain` in `config/huggingface_datasets.json`, the framework automatically sets `target_vocabulary` on any `token_replacement` attack entries that don't already specify one.

---

## Attack snapshots

When `save_attack_snapshots: true`, InteFL saves before-and-after snapshots of attacked client data each round. This is useful for visualising and auditing what the attacks actually changed.

| Config field | Description |
|---|---|
| `save_attack_snapshots` | `true` / `false` |
| `attack_snapshot_format` | `"pickle"`, `"visual"`, or `"pickle_and_visual"` |
| `snapshot_max_samples` | Max samples per snapshot (default: `5`) |

Snapshots are written to `out/<run>/attack_snapshots/` and include an `index.html` for browsing results in a browser.
