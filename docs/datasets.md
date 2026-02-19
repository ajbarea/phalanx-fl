# Datasets

The `dataset_keyword` field in your config selects the dataset and automatically wires up the correct data loader, image transformer, and neural network architecture.

---

## Image datasets

### FEMNIST

Federated version of the EMNIST handwritten character dataset.

| Keyword | Partitioning | Network |
|---|---|---|
| `femnist_iid` | IID (reduced) | `FemnistReducedIIDNetwork` |
| `femnist_niid` | Non-IID (full) | `FemnistFullNIIDNetwork` |

### FLAIR

Federated Learning Annotated Image Recognition dataset (satellite imagery).

| Keyword | Network |
|---|---|
| `flair` | `FlairNetwork` |

### ITS (Intelligent Transportation Systems)

Traffic scene image classification.

| Keyword | Network |
|---|---|
| `its` | `ITSNetwork` |

### Lung Cancer Photos

Chest CT scan images for lung cancer classification.

| Keyword | Network |
|---|---|
| `lung_photos` | `LungCancerCNN` |

### MedMNIST

A collection of standardised biomedical image classification benchmarks.

| Keyword | Modality | Network |
|---|---|---|
| `bloodmnist` | Blood cell microscopy (RGB) | `BloodMNISTNetwork` |
| `breastmnist` | Ultrasound (grayscale) | `BreastMNISTNetwork` |
| `dermamnist` | Dermatoscopy (RGB) | `DermaMNISTNetwork` |
| `octmnist` | Retinal OCT (grayscale) | `OctMNISTNetwork` |
| `organamnist` | Abdominal CT — axial (grayscale) | `OrganAMNISTNetwork` |
| `organcmnist` | Abdominal CT — coronal (grayscale) | `OrganCMNISTNetwork` |
| `organsmnist` | Abdominal CT — sagittal (grayscale) | `OrganSMNISTNetwork` |
| `pathmnist` | Colon pathology (RGB) | `PathMNISTNetwork` |
| `pneumoniamnist` | Chest X-ray (grayscale) | `PneumoniamnistNetwork` |
| `retinamnist` | Fundus photography (RGB) | `RetinaMNISTNetwork` |
| `tissuemnist` | Kidney cortex microscopy (grayscale) | `TissueMNISTNetwork` |

---

## Text datasets

Text datasets use a BERT-family transformer backbone (configured via `llm_model`).

### MedQuAD

Medical question-answer pairs for masked language modelling.

| Keyword | Task | Vocabulary domain |
|---|---|---|
| `medquad` | MLM | medical |

### HuggingFace text datasets

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

## Dataset partitioning

Each dataset is split into `num_of_clients` partitions, one per virtual client. The `training_subset_fraction` field controls what fraction of each partition is used for training (the rest is used for validation).

### Dataset source location

The mapping between `dataset_keyword` and its local directory is defined in `config/dataset_keyword_to_dataset_dir.json`. HuggingFace datasets (`dataset_source: "huggingface"`) are downloaded automatically; local datasets must be placed in the corresponding directory first.
