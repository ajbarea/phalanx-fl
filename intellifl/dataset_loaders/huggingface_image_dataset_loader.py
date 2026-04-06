from __future__ import annotations

import logging
from typing import Any

from flwr_datasets.partitioner import DirichletPartitioner
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

from datasets import Dataset as HFDataset  # type: ignore[attr-defined]
from datasets import load_dataset  # type: ignore[attr-defined]


class HuggingFaceImageDataset(Dataset):  # type: ignore[type-arg]
    """PyTorch Dataset wrapper for HuggingFace image datasets with transforms."""

    def __init__(
        self,
        hf_dataset: Any,
        transform: transforms.Compose | None = None,
        image_column: str = "image",
        label_column: str = "label",
    ) -> None:
        self.hf_dataset = hf_dataset
        self.transform = transform
        self.image_column = image_column
        self.label_column = label_column

    def __len__(self) -> int:
        return len(self.hf_dataset)

    def __getitem__(self, idx: int) -> tuple[Any, Any]:
        item = self.hf_dataset[idx]
        image = item[self.image_column]
        label = item[self.label_column]

        if not isinstance(image, Image.Image):
            image = Image.fromarray(image)

        if self.transform:
            image = self.transform(image)

        return image, label


class HuggingFaceImageDatasetLoader:
    """
    Unified dataset loader for HuggingFace image classification datasets.

    Examples:
        MedMNIST BreastMNIST: hf_dataset_path="randall-lab/medmnist",
                             hf_dataset_name="breastmnist"
        CIFAR-10: hf_dataset_path="cifar10",
                 hf_dataset_name=None
    """

    def __init__(
        self,
        hf_dataset_path: str,
        hf_dataset_name: str | None = None,
        transformer: transforms.Compose | None = None,
        dataset_dir: str | None = None,  # Not used, kept for compatibility
        num_of_clients: int = 10,
        batch_size: int = 32,
        training_subset_fraction: float = 0.8,
        max_samples: int | None = None,  # Limit dataset size
        image_column: str = "image",
        label_column: str = "label",
    ) -> None:
        self.hf_dataset_path = hf_dataset_path
        self.hf_dataset_name = hf_dataset_name
        self.transformer = transformer
        self.num_of_clients = num_of_clients
        self.batch_size = batch_size
        self.training_subset_fraction = training_subset_fraction
        self.max_samples = max_samples
        self.image_column = image_column
        self.label_column = label_column

        if self.transformer is None:
            self.transformer = transforms.Compose(
                [
                    transforms.Resize((28, 28)),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.5], std=[0.5]),
                ]
            )

    def _partition_iid(self, full_dataset: Any) -> list[Any]:
        """Partition dataset uniformly across clients (IID distribution)."""
        client_size = len(full_dataset) // self.num_of_clients
        client_partitions: list[Any] = []

        for client_id in range(self.num_of_clients):
            start_idx = client_id * client_size
            end_idx = (
                start_idx + client_size
                if client_id < self.num_of_clients - 1
                else len(full_dataset)
            )
            client_partitions.append(full_dataset.select(range(start_idx, end_idx)))

        return client_partitions

    def _partition_label_skew_dirichlet(self, full_dataset: Any, alpha: float = 0.5) -> list[Any]:
        """
        Partition dataset using Dirichlet distribution (Non-IID).

        Uses Flower's DirichletPartitioner based on the paper
        "Bayesian Nonparametric Federated Learning of Neural Networks"
        (https://arxiv.org/abs/1905.12022).

        Lower alpha = more heterogeneous (typical: 0.1-1.0).

        Args:
            full_dataset: HuggingFace Dataset with "label" column
            alpha: Dirichlet concentration parameter

        Returns:
            List of dataset partitions, one per client
        """
        partitioner = DirichletPartitioner(
            num_partitions=self.num_of_clients,
            partition_by=self.label_column,
            alpha=alpha,
            min_partition_size=1,
            self_balancing=True,
            seed=42,
        )

        # Assign dataset to partitioner
        partitioner.dataset = full_dataset

        # Load partitions for each client
        return [partitioner.load_partition(i) for i in range(self.num_of_clients)]

    def load_datasets(self):
        """Loads dataset from HuggingFace Hub and partitions into clients."""
        trainloaders = []
        valloaders = []

        if self.hf_dataset_name:
            dataset = load_dataset(
                self.hf_dataset_path, self.hf_dataset_name, trust_remote_code=True
            )
        else:
            dataset = load_dataset(self.hf_dataset_path, trust_remote_code=True)

        full_dataset: HFDataset = dataset["train"]

        # Limit dataset size for memory optimization
        if self.max_samples is not None and len(full_dataset) > self.max_samples:
            original_size = len(full_dataset)
            full_dataset = full_dataset.shuffle(seed=42)
            full_dataset = full_dataset.select(range(self.max_samples))
            logging.info(
                f"Dataset optimization: Limited from {original_size:,} to {self.max_samples:,} samples "
                f"({(self.max_samples / original_size) * 100:.1f}%) for faster processing"
            )

        # Use Non-IID for labeled datasets, IID for unlabeled
        if self.label_column in full_dataset.column_names:
            client_partitions = self._partition_label_skew_dirichlet(full_dataset, alpha=0.5)
        else:
            # Only shuffle if not already shuffled above
            if self.max_samples is None or len(dataset["train"]) <= self.max_samples:
                full_dataset = full_dataset.shuffle(seed=42)
            client_partitions = self._partition_iid(full_dataset)

        for client_id in range(self.num_of_clients):
            client_dataset = client_partitions[client_id]

            split_dataset = client_dataset.train_test_split(
                test_size=(1 - self.training_subset_fraction), seed=42
            )

            train_dataset = HuggingFaceImageDataset(
                split_dataset["train"],
                transform=self.transformer,
                image_column=self.image_column,
                label_column=self.label_column,
            )
            val_dataset = HuggingFaceImageDataset(
                split_dataset["test"],
                transform=self.transformer,
                image_column=self.image_column,
                label_column=self.label_column,
            )

            trainloader = DataLoader(
                train_dataset,
                batch_size=self.batch_size,
                shuffle=True,
                num_workers=0,
                pin_memory=False,
            )
            valloader = DataLoader(
                val_dataset,
                batch_size=self.batch_size,
                shuffle=False,
                num_workers=0,
                pin_memory=False,
            )

            trainloaders.append(trainloader)
            valloaders.append(valloader)

        return trainloaders, valloaders
