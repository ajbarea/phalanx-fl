from __future__ import annotations

from collections.abc import Callable
from typing import Any

import torch
from flwr_datasets import FederatedDataset
from flwr_datasets.partitioner import (
    DirichletPartitioner,
    IidPartitioner,
    NaturalIdPartitioner,
    PathologicalPartitioner,
)
from torch.utils.data import DataLoader, random_split
from torch.utils.data import Dataset as TorchDataset

from datasets import Dataset  # type: ignore[attr-defined]


class _TransformedImageDataset(TorchDataset):
    """Apply a torchvision-style transform to an inner HF dataset partition lazily.

    HF dataset partitions with ``set_format("torch")`` yield
    ``{"pixel_values": Tensor, "labels": int}``, but ``pixel_values`` is the
    raw image (PIL-converted, often uint8 [0, 255]). Training expects a
    normalized float32 tensor. Apply the transform per ``__getitem__``
    rather than materialising the whole transformed dataset to keep memory
    flat for 32×32 RGB datasets.
    """

    def __init__(self, inner: Any, transform: Callable[[Any], torch.Tensor]) -> None:
        self.inner = inner
        self.transform = transform

    def __len__(self) -> int:
        return len(self.inner)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        item = dict(self.inner[idx])
        item["pixel_values"] = self.transform(item["pixel_values"])
        return item


class FederatedDatasetLoader:
    """
    Load datasets from HuggingFace Hub using flwr-datasets library.

    Supports IID, Dirichlet, and Pathological partitioning strategies.
    """

    def __init__(
        self,
        dataset_name: str,
        num_of_clients: int,
        batch_size: int,
        training_subset_fraction: float,
        partitioning_strategy: str = "iid",
        partitioning_params: dict | None = None,
        label_column: str = "label",
        image_transform: Callable[[Any], torch.Tensor] | None = None,
        subset: str | None = None,
        image_column: str | None = None,
        partition_by: str | None = None,
    ) -> None:
        """
        Initialize FederatedDatasetLoader.

        Args:
            dataset_name: HuggingFace dataset name (e.g., "mnist", "cifar10")
            num_of_clients: Number of federated learning clients
            batch_size: Batch size for DataLoaders
            training_subset_fraction: Fraction of data for training (0.0-1.0)
            partitioning_strategy: "iid", "dirichlet", "pathological", or
                "natural_id" (the last splits on a non-label column such as
                FEMNIST's `writer_id`).
            partitioning_params: Strategy-specific parameters (e.g., {"alpha": 0.5})
            label_column: Name of the label column in the dataset (default: "label")
            image_transform: Optional torchvision-style transform applied per
                sample to ``pixel_values`` after partitioning. Used to normalize
                raw HF image tensors against per-dataset channel statistics
                (e.g. ``cifar10_image_transformer``). None = no transformation;
                callers downstream must handle raw uint8 tensors.
            subset: Optional HuggingFace dataset config name. Passed through to
                ``FederatedDataset(subset=...)``, which forwards it to
                ``load_dataset(name=...)``. Required for multi-config datasets
                like MedMNIST v2 (``albertvillanova/medmnist-v2`` + subset
                ``"pathmnist"`` / ``"dermamnist"`` / etc.) and lex_glue
                (``coastalcph/lex_glue`` + subset ``"ledgar"`` / ``"eurlex"``).
                None = use the dataset's default config (CIFAR-10, MNIST,
                FEMNIST all have no named config).
            image_column: Explicit name of the image column in the source
                dataset (e.g. ``"img"`` for CIFAR variants, ``"image"`` for
                MedMNIST). Renamed to ``"pixel_values"`` during column
                standardization. None falls back to the existing auto-detect
                over ("image", "img"); set explicitly when a dataset has
                both columns or when the auto-detect picks the wrong one.
            partition_by: Override the column the partitioner partitions on.
                Dirichlet / Pathological default to `label_column` (the
                standard label-skew shape); the `natural_id` strategy
                requires this to name a non-label column like FEMNIST's
                ``writer_id``. None falls back to `label_column` for the
                label-driven strategies; `natural_id` raises if both are
                None.
        """
        self.dataset_name = dataset_name
        self.num_of_clients = num_of_clients
        self.batch_size = batch_size
        self.training_subset_fraction = training_subset_fraction
        self.partitioning_strategy = partitioning_strategy
        self.partitioning_params = partitioning_params or {}
        self.label_column = label_column
        self.image_transform = image_transform
        self.subset = subset
        self.image_column = image_column
        self.partition_by = partition_by
        self.num_classes: int | None = None

    def load_datasets(self) -> tuple[list[DataLoader], list[DataLoader]]:
        """
        Load and partition dataset from HuggingFace Hub.

        Number of detected classes is stored on ``self.num_classes`` (None
        if not detectable from the dataset features).

        Returns:
            tuple: (trainloaders, valloaders)
                - trainloaders: List of PyTorch DataLoaders for training
                - valloaders: List of PyTorch DataLoaders for validation
        """
        # Create partitioner based on strategy
        partitioner = self._create_partitioner()

        # Load federated dataset from HuggingFace Hub. Forward `subset` as
        # an explicit kwarg when set; flwr-datasets accepts None but the
        # explicit `subset=None` default would still hit FederatedDataset's
        # kwarg-only signature, so we route through a small kwargs dict
        # rather than branching twice on the call site.
        fds_kwargs: dict[str, Any] = {
            "dataset": self.dataset_name,
            "partitioners": {"train": partitioner},
        }
        if self.subset is not None:
            fds_kwargs["subset"] = self.subset
        fds = FederatedDataset(**fds_kwargs)

        self.num_classes = self._detect_num_classes(fds)

        trainloaders = []
        valloaders = []

        for client_id in range(self.num_of_clients):
            partition = fds.load_partition(partition_id=client_id, split="train")

            partition = self._standardize_columns(partition)
            partition.set_format("torch")

            # Wrap with a per-access transform when one was supplied. The
            # wrapper keeps the dataset shape (pixel_values + labels) and
            # only intercepts pixel_values to apply normalization.
            wrapped: Any = partition
            if self.image_transform is not None:
                wrapped = _TransformedImageDataset(partition, self.image_transform)

            train_size = int(len(wrapped) * self.training_subset_fraction)
            val_size = len(wrapped) - train_size

            # Ensure at least 1 sample in validation if possible
            if val_size == 0 and len(wrapped) > 1:
                train_size -= 1
                val_size = 1

            # HuggingFace Dataset with format "torch" is compatible with random_split
            train_dataset, val_dataset = random_split(
                wrapped,  # pyright: ignore[reportArgumentType]
                [train_size, val_size],
                torch.Generator().manual_seed(42),
            )

            trainloaders.append(
                DataLoader(
                    train_dataset,
                    batch_size=self.batch_size,
                    shuffle=True,
                    num_workers=0,
                    pin_memory=False,
                )
            )
            valloaders.append(
                DataLoader(
                    val_dataset,
                    batch_size=self.batch_size,
                    num_workers=0,
                    pin_memory=False,
                )
            )

        return trainloaders, valloaders

    def _detect_num_classes(self, fds: FederatedDataset) -> int | None:
        """
        Detect number of classes from dataset features.

        Args:
            fds: FederatedDataset instance

        Returns:
            int: Number of classes, or None if not detected
        """
        try:
            # FederatedDataset doesn't expose the underlying dataset directly easily
            # Load a small sample partition to check features
            partition = fds.load_partition(partition_id=0, split="train")
            if hasattr(partition, "features") and self.label_column in partition.features:
                label_feature = partition.features[self.label_column]
                if hasattr(label_feature, "names"):
                    return len(label_feature.names)
        except Exception:
            pass
        return None

    def _create_partitioner(self):
        """
        Create partitioner based on strategy.

        Returns:
            Partitioner: flwr-datasets partitioner instance

        Raises:
            ValueError: If partitioning_strategy is unknown or natural_id is
                requested without a partition_by column.
        """
        # Dirichlet / Pathological default to label_column (label-skew shape);
        # natural_id requires partition_by to be set explicitly.
        partition_col = self.partition_by or self.label_column

        if self.partitioning_strategy == "iid":
            return IidPartitioner(num_partitions=self.num_of_clients)

        elif self.partitioning_strategy == "dirichlet":
            alpha = self.partitioning_params.get("alpha", 0.5)
            return DirichletPartitioner(
                num_partitions=self.num_of_clients,
                partition_by=partition_col,
                alpha=alpha,
            )

        elif self.partitioning_strategy == "pathological":
            num_classes = self.partitioning_params.get("num_classes_per_partition", 2)
            return PathologicalPartitioner(
                num_partitions=self.num_of_clients,
                partition_by=partition_col,
                num_classes_per_partition=num_classes,
            )

        elif self.partitioning_strategy == "natural_id":
            # NaturalIdPartitioner auto-discovers partitions from the
            # partition_by column's unique values (FEMNIST: ~3.5k writers).
            # `num_of_clients` then indexes into the discovered partition
            # list — load_partition(id=N) maps to the N-th natural id.
            if not self.partition_by:
                raise ValueError(
                    "natural_id strategy requires `partition_by` (e.g. 'writer_id' for FEMNIST)"
                )
            return NaturalIdPartitioner(partition_by=self.partition_by)

        else:
            raise ValueError(f"Unknown partitioning strategy: {self.partitioning_strategy}")

    def _standardize_columns(self, dataset: Dataset) -> Dataset:
        """
        Rename dataset columns to standard format and remove extra columns.

        Standard format matches transformers library conventions:
            - Images: "pixel_values"
            - Labels: "labels" (plural)
            - Text: "input_ids", "attention_mask", "labels"

        Args:
            dataset: HuggingFace dataset partition

        Returns:
            dataset: Dataset with standardized column names and only required columns
        """
        rename_mapping = {}

        # Detect and rename image column. Explicit `self.image_column` wins
        # over the auto-detect — caller-supplied takes priority over the
        # alias-list fallback the same way `self.label_column` does below.
        if (
            self.image_column
            and self.image_column in dataset.column_names
            and self.image_column != "pixel_values"
        ):
            rename_mapping[self.image_column] = "pixel_values"
        else:
            for col in ("image", "img"):
                if col in dataset.column_names and col != "pixel_values":
                    rename_mapping[col] = "pixel_values"
                    break

        # Detect and rename label column
        # Priority: self.label_column > common label columns
        label_col = None
        if self.label_column in dataset.column_names:
            label_col = self.label_column
        else:
            # Fallback: search for common label columns
            for col in ["label", "character", "fine_label"]:
                if col in dataset.column_names:
                    label_col = col
                    break

        if label_col and label_col != "labels":
            rename_mapping[label_col] = "labels"

        # Apply renaming if needed
        if rename_mapping:
            dataset = dataset.rename_columns(rename_mapping)

        # Remove extra columns - keep only standard ones
        # Image datasets: pixel_values + labels
        # Text datasets: input_ids + attention_mask + labels
        standard_columns = {"pixel_values", "labels", "input_ids", "attention_mask"}
        columns_to_remove = [col for col in dataset.column_names if col not in standard_columns]

        if columns_to_remove:
            dataset = dataset.remove_columns(columns_to_remove)

        return dataset
