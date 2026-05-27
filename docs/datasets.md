# :material-database-outline: Datasets

The `dataset_keyword` field in your config selects the dataset and automatically wires up the correct data loader, image transformer, and neural network architecture.

!!! tip "Quick start"

    Pick a keyword from the tables below, drop it into `"dataset_keyword"` in your config, and Phalanx handles the rest — partitioning, transforms, and model selection.

---

!!! info "Unified CNN architecture"

    All image datasets (except CIFAR-100) use the `MedMNISTCNN` architecture — a configurable CNN with dataset-specific input dimensions, channel counts, and layer widths. The model registry in `intellifl/network_models/__init__.py` maps each `dataset_keyword` to the correct constructor parameters. CIFAR-100 uses `DynamicCNN`, which is configured from HuggingFace dataset metadata.

## :material-image-outline: Image datasets

### :material-draw: FEMNIST

Federated version of the EMNIST handwritten character dataset (62 classes: 10 digits + 26 lowercase + 26 uppercase letters).

| Keyword | Partitioning | Classes | Network |
|---|---|---|---|
| `femnist_iid` | IID | 62 | `MedMNISTCNN` (28×28 grayscale) |
| `femnist_niid` | Non-IID (natural-id, partitioned by `writer_id`) | 62 | `MedMNISTCNN` (28×28 grayscale) |

### :material-grid: CIFAR family

32×32 RGB image classification, all downloaded automatically from HuggingFace Hub.

| Keyword | Classes | Network | HF path |
|---|---|---|---|
| `cifar100` | 100 (fine labels) | `DynamicCNN` | `uoft-cs/cifar100` |
| `cifar10` | 10 | `DynamicCNN` | `uoft-cs/cifar10` |
| `cinic10` | 10 (CIFAR-10 + downsampled ImageNet) | `DynamicCNN` | `flwrlabs/cinic10` |

### :material-hospital-box-outline: MedMNIST

A collection of standardised biomedical image classification benchmarks. All MedMNIST datasets use the `MedMNISTCNN` architecture with dataset-specific configurations.

| Keyword | Modality | Classes | Network |
|---|---|---|---|
| `bloodmnist` | Blood cell microscopy (RGB) | 8 | `MedMNISTCNN` |
| `breastmnist` | Ultrasound (grayscale) | 2 | `MedMNISTCNN` |
| `dermamnist` | Dermatoscopy (RGB) | 7 | `MedMNISTCNN` |
| `octmnist` | Retinal OCT (grayscale) | 4 | `MedMNISTCNN` |
| `organamnist` | Abdominal CT — axial (grayscale) | 11 | `MedMNISTCNN` |
| `organcmnist` | Abdominal CT — coronal (grayscale) | 11 | `MedMNISTCNN` |
| `organsmnist` | Abdominal CT — sagittal (grayscale) | 11 | `MedMNISTCNN` |
| `pathmnist` | Colon pathology (RGB) | 9 | `MedMNISTCNN` |
| `pneumoniamnist` | Chest X-ray (grayscale) | 2 | `MedMNISTCNN` |
| `retinamnist` | Fundus photography (RGB) | 5 | `MedMNISTCNN` |
| `tissuemnist` | Kidney cortex microscopy (grayscale) | 8 | `MedMNISTCNN` |

---

## :material-text-box-outline: Text datasets

Text datasets use a BERT-family transformer backbone (configured via `llm_model`).

### :material-stethoscope: MedQuAD

Medical question-answer pairs for masked language modelling.

| Keyword | Task | Vocabulary domain |
|---|---|---|
| `medquad` | MLM | medical |

### :fontawesome-solid-robot: HuggingFace text datasets

These are downloaded automatically from the HuggingFace Hub.

| Keyword | HF path | Task | Vocabulary domain |
|---|---|---|---|
| `financial_phrasebank` | `gtfintechlab/financial_phrasebank_sentences_allagree` | Classification | financial |
| `lexglue` | `coastalcph/lex_glue` (LEDGAR subset) | Classification | legal |
| `pubmed_classification_20k` | `ml4pubmed/pubmed-classification-20k` | Classification | medical |
| `medal` | `cyrilzakka/pubmed-medline` | MLM | medical |

!!! note "HuggingFace cache"
    Downloaded datasets are cached under `./cache/huggingface`. Set the `HF_HOME` environment variable to change the cache location.

---

## :material-call-split: Dataset partitioning

Each dataset is split into `num_of_clients` partitions, one per virtual client. The `training_subset_fraction` field controls what fraction of each partition is used for training (the rest is used for validation).

### :material-shuffle-variant: Partitioning strategies

HuggingFace and custom text datasets support configurable partitioning via the `partitioning_strategy` and `partitioning_params` config fields.

| Strategy | Description | Parameters |
|---|---|---|
| `iid` | Balanced, shuffled, even distribution across clients. | — |
| `dirichlet` | Heterogeneous (non-IID) distribution using a Dirichlet prior. | `alpha` (default `0.5`; lower = more heterogeneous, higher = more uniform) |
| `pathological` | Extreme non-IID — each client receives only K classes. | `num_classes_per_partition` (default `2`) |
| `natural_id` | One client per natural identifier (e.g. FEMNIST's `writer_id`). Auto-discovers the partition count from the column's unique values. | `partition_by` (column name; required) |

**Example:**

```json title="Dirichlet partitioning config"
{
  "dataset_keyword": "cifar10",
  "partitioning_strategy": "dirichlet",
  "partitioning_params": {
    "alpha": 0.5
  }
}
```

### :material-folder-outline: Dataset source location

The mapping between `dataset_keyword` and its local directory is defined in `config/dataset_keyword_to_dataset_dir.json`. HuggingFace datasets (`dataset_source: "huggingface"`) are downloaded automatically; local datasets must be placed in the corresponding directory first.

!!! info "Adding a new dataset"

    **HuggingFace-backed:** add an entry to `config/huggingface_datasets.json` with `modality`, `hf_dataset_path`, label / image columns, and shape (`num_classes`, `input_channels`, `input_height`, `input_width`). Register an `image_transformer` if the dataset needs custom normalization (see `intellifl/dataset_loaders/image_transformers/`). Add the keyword to `LOADER_REGISTRY` in `intellifl/dataset_loaders/__init__.py`.

    **Local files:** create a directory under `datasets/`, add an entry to `config/dataset_keyword_to_dataset_dir.json`, and implement a matching dataset handler in `intellifl/dataset_handlers/`.
