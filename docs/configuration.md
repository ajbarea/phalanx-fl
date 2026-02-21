# :material-cog-outline: Configuration

Simulations are controlled entirely by a single JSON file. The file has two top-level keys:

```json title="Config structure"
{
  "shared_settings": { ... },
  "simulation_strategies": [
    { ... },
    { ... }
  ]
}
```

!!! tip "Shared settings + per-strategy overrides"

    `shared_settings` provides defaults for every strategy. Each entry in `simulation_strategies` can override any field. This makes it easy to sweep a single parameter across multiple runs in one file.

---

## :material-test-tube: Example

```json title="example_strategy_config.json"
{
  "shared_settings": {
    "aggregation_strategy_keyword": "pid_standardized",
    "dataset_keyword": "femnist_iid",
    "num_of_rounds": 10,
    "num_of_clients": 5,
    "num_of_malicious_clients": 2,
    "training_device": "cpu",
    "cpus_per_client": 1,
    "gpus_per_client": 0.0,
    "batch_size": 20,
    "num_of_client_epochs": 1,
    "save_plots": true,
    "save_csv": true,
    "Kp": 1, "Ki": 0.05, "Kd": 0.05
  },
  "simulation_strategies": [
    { "num_std_dev": 2.33 },
    { "num_std_dev": 3.0 }
  ]
}
```

This runs two strategies back-to-back, differing only in `num_std_dev`.

---

## :material-format-list-bulleted: Field reference

### :material-play-circle: Core simulation

| Field | Type | Default | Description |
|---|---|---|---|
| `display_name` | `string` | `null` | Optional human-readable label shown in the UI. |
| `dataset_keyword` | `string` | — | Which dataset to use. See [Datasets](datasets.md). |
| `aggregation_strategy_keyword` | `string` | — | Which strategy. See [Strategies](strategies.md). |
| `num_of_rounds` | `int` | — | Total FL rounds to run. |
| `num_of_clients` | `int` | — | Total virtual clients. |
| `num_of_malicious_clients` | `int` | `0` | How many clients are treated as potentially malicious. |
| `training_device` | `string` | — | `"cpu"`, `"cuda"`, or `"gpu"` (alias for `cuda`). |
| `cpus_per_client` | `float` | — | CPU cores allocated to each Ray worker. |
| `gpus_per_client` | `float` | — | GPU fraction allocated to each Ray worker (`0.0`–`1.0`). |
| `model_keyword` | `string` | `null` | Override the default network model for a dataset. |
| `model_type` | `string` | `"cnn"` | `"cnn"` or `"transformer"`. |
| `use_llm` | `bool` | `false` | Enable transformer-based training path. |

### :material-brain: Training

| Field | Type | Default | Description |
|---|---|---|---|
| `num_of_client_epochs` | `int` | — | Local training epochs per round per client. |
| `batch_size` | `int` | — | Mini-batch size for local training. |
| `learning_rate` | `float` | `null` | Override default learning rate. |
| `training_subset_fraction` | `float` | — | Fraction of each client's data used for training (`0.0`–`1.0`). |

### :material-account-group: Client selection

| Field | Type | Default | Description |
|---|---|---|---|
| `min_fit_clients` | `int` | — | Minimum clients that must participate in training each round. |
| `min_evaluate_clients` | `int` | — | Minimum clients for evaluation each round. |
| `min_available_clients` | `int` | — | Minimum clients that must be available before a round starts. |
| `evaluate_metrics_aggregation_fn` | `string` | `null` | Set to `"weighted_average"` to aggregate evaluation metrics. |

### :material-bug-outline: Attack schedule

See the [Attacks](attacks.md) page for full documentation.

| Field | Type | Default | Description |
|---|---|---|---|
| `attack_schedule` | `array` | `[]` | List of attack entries. Required in config (use `[]` for no attacks). |

### :material-account-remove: Client removal

| Field | Type | Default | Description |
|---|---|---|---|
| `remove_clients` | `bool` | `false` | Enable permanent removal of detected malicious clients. |
| `begin_removing_from_round` | `int` | `null` | Only start removing from this round onwards. |
| `termination_policy` | `string` | `"graceful"` | `"strict"`, `"graceful"`, or `"adaptive"`. Controls behaviour when too many clients have been removed. |
| `min_clients_ratio` | `float` | `0.3` | For `"adaptive"` policy: stop removing if fewer than this fraction of clients remain. |

### :material-content-save-outline: Output

| Field | Type | Default | Description |
|---|---|---|---|
| `save_csv` | `bool` | — | Save per-round metrics to CSV. |
| `save_plots` | `bool` | — | Save matplotlib figures to PDF. |
| `show_plots` | `bool` | — | Display plots interactively (not suitable for headless/server runs). |
| `preserve_dataset` | `bool` | — | Keep partitioned dataset files after the simulation. |
| `save_attack_snapshots` | `bool` | `false` | Save before/after data snapshots for attacked clients. |
| `attack_snapshot_format` | `string` | `"pickle"` | `"pickle"`, `"visual"`, or `"pickle_and_visual"`. |
| `snapshot_max_samples` | `int` | `5` | Max samples included in each snapshot. |

### :material-tune-variant: Strategy-specific parameters

#### Trust-based

| Field | Type | Description |
|---|---|---|
| `trust_threshold` | `float` | Clients below this trust score are considered malicious. |
| `beta_value` | `float` | EMA decay for updating trust scores. |

#### PID-based

| Field | Type | Description |
|---|---|---|
| `Kp` | `float` | Proportional gain. |
| `Ki` | `float` | Integral gain. |
| `Kd` | `float` | Derivative gain. |
| `num_std_dev` | `float` | Threshold (in std devs) for flagging outlier clients. |

#### Krum / Multi-Krum / Bulyan

| Field | Type | Description |
|---|---|---|
| `num_krum_selections` | `int` | Number of clients selected by Krum per round. |

#### Trimmed Mean

| Field | Type | Description |
|---|---|---|
| `trim_ratio` | `float` | Fraction of extreme updates trimmed from each end. |

### :fontawesome-solid-robot: HuggingFace / custom text datasets

| Field | Type | Default | Description |
|---|---|---|---|
| `hf_dataset_name` | `string` | `null` | HuggingFace dataset path to load dynamically (e.g. `"ylecun/mnist"`). |
| `partitioning_strategy` | `string` | `null` | Partitioning method: `"iid"`, `"dirichlet"`, or `"pathological"`. See [Datasets](datasets.md#partitioning-strategies). |
| `partitioning_params` | `object` | `null` | Parameters for the chosen strategy (e.g. `{"alpha": 0.5}` for dirichlet, `{"num_classes_per_partition": 2}` for pathological). |
| `text_column` | `string` | `null` | Name of the text/input column in the dataset. |
| `label_column` | `string` | `null` | Name of the label column in the dataset. |

### :material-robot-outline: LLM / transformer options

| Field | Type | Default | Description |
|---|---|---|---|
| `llm_model` | `string` | — | HuggingFace model ID, e.g. `"microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext"`. |
| `llm_task` | `string` | — | `"mlm"` (masked language modelling) or `"classification"`. |
| `llm_chunk_size` | `int` | `512` | Token sequence length. |
| `max_seq_length` | `int` | `null` | Maximum sequence length for the tokeniser (overrides `llm_chunk_size` when set). |
| `mlm_probability` | `float` | `0.15` | Fraction of tokens masked during MLM. |
| `llm_finetuning` | `string` | `null` | `"lora"` to use LoRA adapters instead of full fine-tuning. |
| `use_lora` | `bool` | `false` | Alternative boolean flag to enable LoRA (equivalent to `llm_finetuning: "lora"`). |
| `lora_rank` | `int` | `8` | LoRA rank `r`. |
