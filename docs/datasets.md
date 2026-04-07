# :material-database-outline: Datasets

The `dataset_keyword` field in your config selects the dataset and automatically wires up the correct data loader, image transformer, and neural network architecture.

!!! tip "Quick start"

    Pick a keyword from the tables below, drop it into `"dataset_keyword"` in your config, and InteFL handles the rest — partitioning, transforms, and model selection.

---

!!! info "Unified CNN architecture"

    All image datasets (except CIFAR-100) use the `MedMNISTCNN` architecture — a configurable CNN with dataset-specific input dimensions, channel counts, and layer widths. The model registry in `intellifl/network_models/__init__.py` maps each `dataset_keyword` to the correct constructor parameters. CIFAR-100 uses `DynamicCNN`, which is configured from HuggingFace dataset metadata.

## :material-image-outline: Image datasets

### :material-draw: FEMNIST

Federated version of the EMNIST handwritten character dataset.

| Keyword | Partitioning | Classes | Network |
|---|---|---|---|
| `femnist_iid` | IID (reduced) | 10 | `MedMNISTCNN` (28×28 grayscale) |
| `femnist_niid` | Non-IID (full) | 62 | `MedMNISTCNN` (28×28 grayscale) |

### :material-satellite-variant: FLAIR

Federated Learning Annotated Image Recognition dataset (satellite imagery).

| Keyword | Classes | Network |
|---|---|---|
| `flair` | 2 | `MedMNISTCNN` (256×256 RGB) |

### :material-car-connected: ITS (Intelligent Transportation Systems)

Traffic scene image classification.

| Keyword | Classes | Network |
|---|---|---|
| `its` | 10 | `MedMNISTCNN` (224×224 RGB) |

### :material-grid: CIFAR-100

100 classes of 32×32 RGB images (fine-grained classification). Downloaded automatically from HuggingFace Hub (`uoft-cs/cifar100`).

| Keyword | Classes | Network | Source |
|---|---|---|---|
| `cifar100` | 100 (fine labels) | `DynamicCNN` | HuggingFace Hub |

### :material-lungs: Lung Cancer Photos

Chest CT scan images for lung cancer classification.

| Keyword | Classes | Network |
|---|---|---|
| `lung_photos` | 4 | `MedMNISTCNN` (224×224 grayscale) |

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

**Example:**

```json title="Dirichlet partitioning config"
{
  "dataset_keyword": "uoft-cs/cifar10",
  "partitioning_strategy": "dirichlet",
  "partitioning_params": {
    "alpha": 0.5
  }
}
```

### :material-folder-outline: Dataset source location

The mapping between `dataset_keyword` and its local directory is defined in `config/dataset_keyword_to_dataset_dir.json`. HuggingFace datasets (`dataset_source: "huggingface"`) are downloaded automatically; local datasets must be placed in the corresponding directory first.

!!! info "Adding a new dataset"

    To add a custom dataset, create a directory under `datasets/`, add an entry to `config/dataset_keyword_to_dataset_dir.json`, and implement a matching dataset handler in `intellifl/dataset_handlers/`.
