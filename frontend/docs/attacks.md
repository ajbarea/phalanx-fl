# Attack Configuration

Attacks are defined in `attack_schedule` array within a simulation strategy.

## Schema

```json
{
  "simulation_strategies": [
    {
      "strategy_name": "my_experiment",
      "attack_schedule": [
        {
          "start_round": 2,
          "end_round": 5,
          "attack_type": "model_poisoning",
          "selection_strategy": "specific",
          "malicious_client_ids": [0, 1]
        }
      ]
    }
  ]
}
```

## Selection Strategies

| Strategy     | Required Fields                     | Description               |
| :----------- | :---------------------------------- | :------------------------ |
| `specific`   | `malicious_client_ids: [0, 1, ...]` | Target exact client IDs   |
| `random`     | `malicious_client_count: N`         | Randomly select N clients |
| `percentage` | `malicious_percentage: 0.3`         | Select % of total clients |

Optional: `random_seed` for reproducible random/percentage selection.

## Attack Types

### Data Poisoning (applied during training)

| Type                | Parameters                                                          |
| :------------------ | :------------------------------------------------------------------ |
| `label_flipping`    | `num_classes`                                                       |
| `gaussian_noise`    | `mean`, `std`, `attack_ratio` OR `target_noise_snr`, `attack_ratio` |
| `token_replacement` | `target_vocabulary`, `replacement_strategy`, `replacement_prob`     |

### Weight Poisoning (applied after training)

| Type                     | Parameters                  |
| :----------------------- | :-------------------------- |
| `model_poisoning`        | `poison_ratio`, `magnitude` |
| `gradient_scaling`       | `scale_factor`              |
| `byzantine_perturbation` | `noise_scale`               |

Optional: `seed` for reproducible weight attacks.

## Examples

### Label Flipping

```json
{
  "attack_schedule": [
    {
      "start_round": 1,
      "end_round": 10,
      "attack_type": "label_flipping",
      "num_classes": 10,
      "selection_strategy": "specific",
      "malicious_client_ids": [0, 2]
    }
  ]
}
```

### Model Poisoning (Weight Attack)

```json
{
  "attack_schedule": [
    {
      "start_round": 2,
      "end_round": 4,
      "attack_type": "model_poisoning",
      "poison_ratio": 0.1,
      "magnitude": 5.0,
      "selection_strategy": "specific",
      "malicious_client_ids": [0]
    }
  ]
}
```

### Percentage-Based Selection

```json
{
  "attack_schedule": [
    {
      "start_round": 1,
      "end_round": 20,
      "attack_type": "gaussian_noise",
      "mean": 0.0,
      "std": 0.5,
      "attack_ratio": 1.0,
      "selection_strategy": "percentage",
      "malicious_percentage": 0.3,
      "random_seed": 42
    }
  ]
}
```

### Multi-Phase Schedule

```json
{
  "attack_schedule": [
    {
      "start_round": 1,
      "end_round": 5,
      "attack_type": "label_flipping",
      "num_classes": 10,
      "selection_strategy": "specific",
      "malicious_client_ids": [0]
    },
    {
      "start_round": 6,
      "end_round": 10,
      "attack_type": "model_poisoning",
      "poison_ratio": 0.1,
      "magnitude": 5.0,
      "selection_strategy": "specific",
      "malicious_client_ids": [0]
    }
  ]
}
```
