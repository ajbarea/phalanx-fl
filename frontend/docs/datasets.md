# Dataset Loading

## Supported Datasets

### Local Pre-partitioned (Keywords)

Use these keywords for optimized local datasets:

| Keyword                | Description                        | Type  |
| :--------------------- | :--------------------------------- | :---- |
| `femnist_iid`          | Federated EMNIST (IID)             | Image |
| `femnist_niid`         | Federated EMNIST (Non-IID)         | Image |
| `bloodmnist`           | Blood cell microscopy              | Image |
| `pathmnist`            | Colon pathology                    | Image |
| `dermamnist`           | Dermatoscope images                | Image |
| `octmnist`             | Retinal OCT scans                  | Image |
| `pneumoniamnist`       | Chest X-ray                        | Image |
| `retinamnist`          | Fundus images                      | Image |
| `breastmnist`          | Breast ultrasound                  | Image |
| `tissuemnist`          | Kidney cortex                      | Image |
| `organamnist`          | Abdominal CT (axial)               | Image |
| `organcmnist`          | Abdominal CT (coronal)             | Image |
| `organsmnist`          | Abdominal CT (sagittal)            | Image |
| `its`                  | Intelligent Transportation Systems | Image |
| `lung_photos`          | Lung imagery                       | Image |
| `flair`                | FLAIR dataset                      | Image |
| `medquad`              | Medical Question Answering         | Text  |
| `medal`                | Pubmed-Medline (HuggingFace)       | Text  |
| `financial_phrasebank` | Financial sentiment (HuggingFace)  | Text  |
| `lexglue`              | Legal NLP benchmark (HuggingFace)  | Text  |

### HuggingFace Datasets

Enter the full `username/dataset` string. Popular options:

| Dataset                | Description             |
| :--------------------- | :---------------------- |
| `ylecun/mnist`         | Handwritten digits      |
| `fashion_mnist`        | Clothing items          |
| `uoft-cs/cifar10`      | 10 classes, 32x32 RGB   |
| `uoft-cs/cifar100`     | 100 classes, 32x32 RGB  |
| `flwrlabs/femnist`     | Federated handwriting   |
| `flwrlabs/shakespeare` | Federated text          |
| `imdb`                 | Movie reviews sentiment |

## Partitioning Strategies

Configure how data is split among clients.

| Strategy       | Description                    | Parameters                               |
| :------------- | :----------------------------- | :--------------------------------------- |
| `iid`          | Balanced, random distribution. | `max_samples` (optional)                 |
| `dirichlet`    | Heterogeneous (Non-IID).       | `alpha` (0.1 = distinct, 10.0 = uniform) |
| `pathological` | Extreme separation.            | `num_classes_per_partition`              |

### Configuration Example

```json
{
  "dataset_keyword": "uoft-cs/cifar10",
  "partitioning_strategy": "dirichlet",
  "partitioning_params": {
    "alpha": 0.5
  }
}
```
