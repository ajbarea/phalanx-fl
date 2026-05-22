"""
Tests for FederatedDatasetLoader.
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, Mock, patch

import pytest
from flwr_datasets.partitioner import (
    DirichletPartitioner,
    IidPartitioner,
    NaturalIdPartitioner,
    PathologicalPartitioner,
)
from torch.utils.data import DataLoader

from intellifl.dataset_loaders.federated_dataset_loader import FederatedDatasetLoader


class TestFederatedDatasetLoaderInit:
    """Test FederatedDatasetLoader initialization."""

    def test_basic_initialization(self):
        """Should initialize with required parameters."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=10,
            batch_size=32,
            training_subset_fraction=0.8,
        )
        assert loader.dataset_name == "mnist"
        assert loader.num_of_clients == 10
        assert loader.batch_size == 32
        assert loader.training_subset_fraction == 0.8
        assert loader.partitioning_strategy == "iid"
        assert loader.partitioning_params == {}
        # num_classes is initialized as None and set after load_datasets()
        assert loader.num_classes is None

    def test_initialization_with_partitioning_params(self):
        """Should initialize with custom partitioning parameters."""
        params = {"alpha": 0.5}
        loader = FederatedDatasetLoader(
            dataset_name="cifar10",
            num_of_clients=5,
            batch_size=64,
            training_subset_fraction=0.9,
            partitioning_strategy="dirichlet",
            partitioning_params=params,
        )
        assert loader.partitioning_strategy == "dirichlet"
        assert loader.partitioning_params == params

    def test_initialization_with_none_params(self):
        """Should handle None partitioning_params."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=10,
            batch_size=32,
            training_subset_fraction=0.8,
            partitioning_params=None,
        )
        assert loader.partitioning_params == {}


class TestCreatePartitioner:
    """Test partitioner creation."""

    def test_create_iid_partitioner(self):
        """Should create IidPartitioner for 'iid' strategy."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=10,
            batch_size=32,
            training_subset_fraction=0.8,
            partitioning_strategy="iid",
        )
        partitioner = loader._create_partitioner()
        assert isinstance(partitioner, IidPartitioner)
        assert partitioner.num_partitions == 10

    def test_create_dirichlet_partitioner(self):
        """Should create DirichletPartitioner with alpha parameter."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=10,
            batch_size=32,
            training_subset_fraction=0.8,
            partitioning_strategy="dirichlet",
            partitioning_params={"alpha": 0.3},
        )
        partitioner = loader._create_partitioner()
        assert isinstance(partitioner, DirichletPartitioner)
        assert partitioner._num_partitions == 10
        # _alpha can be an array, so check if all values are 0.3
        import numpy as np

        assert np.all(partitioner._alpha == 0.3)

    def test_create_dirichlet_partitioner_default_alpha(self):
        """Should use default alpha if not provided."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=10,
            batch_size=32,
            training_subset_fraction=0.8,
            partitioning_strategy="dirichlet",
        )
        partitioner = loader._create_partitioner()
        assert isinstance(partitioner, DirichletPartitioner)
        # _alpha can be an array, so check if all values are 0.5
        import numpy as np

        assert np.all(partitioner._alpha == 0.5)

    def test_create_pathological_partitioner(self):
        """Should create PathologicalPartitioner with num_classes parameter."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=10,
            batch_size=32,
            training_subset_fraction=0.8,
            partitioning_strategy="pathological",
            partitioning_params={"num_classes_per_partition": 3},
        )
        partitioner = loader._create_partitioner()
        assert isinstance(partitioner, PathologicalPartitioner)
        assert partitioner._num_partitions == 10
        assert partitioner._num_classes_per_partition == 3

    def test_create_pathological_partitioner_default_classes(self):
        """Should use default num_classes if not provided."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=10,
            batch_size=32,
            training_subset_fraction=0.8,
            partitioning_strategy="pathological",
        )
        partitioner = loader._create_partitioner()
        assert isinstance(partitioner, PathologicalPartitioner)
        assert partitioner._num_classes_per_partition == 2

    def test_unknown_partitioning_strategy_raises_error(self):
        """Should raise ValueError for unknown strategy."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=10,
            batch_size=32,
            training_subset_fraction=0.8,
            partitioning_strategy="unknown_strategy",
        )
        with pytest.raises(ValueError, match="Unknown partitioning strategy"):
            loader._create_partitioner()


class TestLoadDatasets:
    """Test dataset loading and partitioning."""

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    def test_load_datasets_creates_correct_number_of_loaders(self, mock_federated_dataset):
        """Should create trainloaders and valloaders for each client."""
        # Setup mock partition
        mock_partition = MagicMock()
        mock_partition.__len__ = Mock(return_value=100)
        mock_partition.set_format = Mock()

        # Setup mock FederatedDataset
        mock_fds = MagicMock()
        mock_fds.load_partition = Mock(return_value=mock_partition)
        mock_federated_dataset.return_value = mock_fds

        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=5,
            batch_size=32,
            training_subset_fraction=0.8,
        )

        trainloaders, valloaders = loader.load_datasets()

        assert len(trainloaders) == 5
        assert len(valloaders) == 5
        assert all(isinstance(tl, DataLoader) for tl in trainloaders)
        assert all(isinstance(vl, DataLoader) for vl in valloaders)
        # num_classes is exposed on the instance, not in the return tuple
        assert hasattr(loader, "num_classes")

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    def test_load_datasets_uses_correct_partitioner(self, mock_federated_dataset):
        """Should pass partitioner to FederatedDataset."""
        mock_partition = MagicMock()
        mock_partition.__len__ = Mock(return_value=100)
        mock_partition.set_format = Mock()

        mock_fds = MagicMock()
        mock_fds.load_partition = Mock(return_value=mock_partition)
        mock_federated_dataset.return_value = mock_fds

        loader = FederatedDatasetLoader(
            dataset_name="cifar10",
            num_of_clients=3,
            batch_size=64,
            training_subset_fraction=0.75,
            partitioning_strategy="dirichlet",
            partitioning_params={"alpha": 0.1},
        )

        loader.load_datasets()

        # Verify FederatedDataset was called with correct arguments
        mock_federated_dataset.assert_called_once()
        call_kwargs = mock_federated_dataset.call_args[1]
        assert call_kwargs["dataset"] == "cifar10"
        assert "train" in call_kwargs["partitioners"]
        assert isinstance(call_kwargs["partitioners"]["train"], DirichletPartitioner)

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    def test_load_datasets_loads_correct_partitions(self, mock_federated_dataset):
        """Should load partition for each client ID."""
        mock_partition = MagicMock()
        mock_partition.__len__ = Mock(return_value=100)
        mock_partition.set_format = Mock()

        mock_fds = MagicMock()
        mock_fds.load_partition = Mock(return_value=mock_partition)
        mock_federated_dataset.return_value = mock_fds

        num_clients = 4
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=num_clients,
            batch_size=32,
            training_subset_fraction=0.8,
        )

        loader.load_datasets()

        # Verify load_partition was called for each client + 1 time for _detect_num_classes
        assert mock_fds.load_partition.call_count == num_clients + 1
        for i in range(num_clients):
            mock_fds.load_partition.assert_any_call(partition_id=i, split="train")

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    @patch("intellifl.dataset_loaders.federated_dataset_loader.random_split")
    def test_load_datasets_splits_data_correctly(self, mock_random_split, mock_federated_dataset):
        """Should split data according to training_subset_fraction."""
        mock_partition = MagicMock()
        mock_partition.__len__ = Mock(return_value=100)
        mock_partition.set_format = Mock()

        mock_fds = MagicMock()
        mock_fds.load_partition = Mock(return_value=mock_partition)
        mock_federated_dataset.return_value = mock_fds

        # Mock train/val datasets with proper __len__ for DataLoader
        mock_train = MagicMock()
        mock_train.__len__ = Mock(return_value=80)
        mock_val = MagicMock()
        mock_val.__len__ = Mock(return_value=20)
        mock_random_split.return_value = [mock_train, mock_val]

        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=2,
            batch_size=32,
            training_subset_fraction=0.8,
        )

        loader.load_datasets()

        # Verify split was called with correct sizes (80% train, 20% val)
        mock_random_split.assert_called()
        call_args = mock_random_split.call_args[0]
        assert call_args[1] == [80, 20]  # 80% of 100, 20% of 100

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    @patch("intellifl.dataset_loaders.federated_dataset_loader.random_split")
    def test_load_datasets_ensures_validation_sample(
        self, mock_random_split, mock_federated_dataset
    ):
        """Should ensure at least 1 validation sample when possible."""
        mock_partition = MagicMock()
        mock_partition.__len__ = Mock(return_value=10)
        mock_partition.set_format = Mock()

        mock_fds = MagicMock()
        mock_fds.load_partition = Mock(return_value=mock_partition)
        mock_federated_dataset.return_value = mock_fds

        # Mock train/val datasets with proper __len__ for DataLoader
        mock_train = MagicMock()
        mock_train.__len__ = Mock(return_value=9)
        mock_val = MagicMock()
        mock_val.__len__ = Mock(return_value=1)
        mock_random_split.return_value = [mock_train, mock_val]

        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=1,
            batch_size=32,
            training_subset_fraction=1.0,  # 100% would leave 0 for validation
        )

        loader.load_datasets()

        # Should adjust to ensure 1 validation sample
        call_args = mock_random_split.call_args[0]
        assert call_args[1] == [9, 1]  # 9 train, 1 val

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    @patch("intellifl.dataset_loaders.federated_dataset_loader.random_split")
    @patch("intellifl.dataset_loaders.federated_dataset_loader.DataLoader")
    def test_load_datasets_handles_single_sample_partition(
        self, mock_dataloader, mock_random_split, mock_federated_dataset
    ):
        """Should handle partition with only 1 sample."""
        mock_partition = MagicMock()
        mock_partition.__len__ = Mock(return_value=1)
        mock_partition.set_format = Mock()

        mock_fds = MagicMock()
        mock_fds.load_partition = Mock(return_value=mock_partition)
        mock_federated_dataset.return_value = mock_fds

        # Mock train/val datasets
        mock_train = MagicMock()
        mock_val = MagicMock()
        mock_random_split.return_value = [mock_train, mock_val]

        # Mock DataLoader to avoid issues with empty datasets
        mock_dataloader.return_value = MagicMock()

        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=1,
            batch_size=32,
            training_subset_fraction=0.8,
        )

        loader.load_datasets()

        # With 1 sample and 0.8 fraction, int(1 * 0.8) = 0 train, 1 val
        call_args = mock_random_split.call_args[0]
        assert call_args[1] == [0, 1]

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    def test_load_datasets_sets_format_to_torch(self, mock_federated_dataset):
        """Should set partition format to 'torch'."""
        mock_partition = MagicMock()
        mock_partition.__len__ = Mock(return_value=100)
        mock_partition.set_format = Mock()

        mock_fds = MagicMock()
        mock_fds.load_partition = Mock(return_value=mock_partition)
        mock_federated_dataset.return_value = mock_fds

        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=2,
            batch_size=32,
            training_subset_fraction=0.8,
        )

        loader.load_datasets()

        # Verify set_format was called with "torch"
        assert mock_partition.set_format.call_count == 2
        mock_partition.set_format.assert_called_with("torch")

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    @patch("intellifl.dataset_loaders.federated_dataset_loader.DataLoader")
    def test_load_datasets_creates_dataloaders_with_correct_batch_size(
        self, mock_dataloader, mock_federated_dataset
    ):
        """Should create DataLoaders with specified batch size."""
        mock_partition = MagicMock()
        mock_partition.__len__ = Mock(return_value=100)
        mock_partition.set_format = Mock()

        mock_fds = MagicMock()
        mock_fds.load_partition = Mock(return_value=mock_partition)
        mock_federated_dataset.return_value = mock_fds

        mock_dataloader.return_value = MagicMock()

        batch_size = 64
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=1,
            batch_size=batch_size,
            training_subset_fraction=0.8,
        )

        loader.load_datasets()

        # Verify DataLoader was called with correct batch_size
        calls = mock_dataloader.call_args_list
        for call in calls:
            assert call[1]["batch_size"] == batch_size

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    @patch("intellifl.dataset_loaders.federated_dataset_loader.DataLoader")
    def test_load_datasets_shuffles_training_data(self, mock_dataloader, mock_federated_dataset):
        """Should shuffle training data but not validation data."""
        mock_partition = MagicMock()
        mock_partition.__len__ = Mock(return_value=100)
        mock_partition.set_format = Mock()

        mock_fds = MagicMock()
        mock_fds.load_partition = Mock(return_value=mock_partition)
        mock_federated_dataset.return_value = mock_fds

        mock_dataloader.return_value = MagicMock()

        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=1,
            batch_size=32,
            training_subset_fraction=0.8,
        )

        loader.load_datasets()

        # Check that shuffle=True for train, shuffle not set (False) for val
        calls = mock_dataloader.call_args_list
        # First call should be trainloader with shuffle=True
        assert calls[0][1].get("shuffle") is True
        # Second call should be valloader without shuffle or shuffle=False
        assert calls[1][1].get("shuffle", False) is False


class TestIntegration:
    """Integration tests with real partitioners (no mocking)."""

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    def test_end_to_end_iid_loading(self, mock_federated_dataset):
        """Test complete flow with IID partitioner."""
        mock_partition = MagicMock()
        mock_partition.__len__ = Mock(return_value=100)
        mock_partition.set_format = Mock()

        mock_fds = MagicMock()
        mock_fds.load_partition = Mock(return_value=mock_partition)
        mock_federated_dataset.return_value = mock_fds

        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=3,
            batch_size=16,
            training_subset_fraction=0.7,
            partitioning_strategy="iid",
        )

        trainloaders, valloaders = loader.load_datasets()

        assert len(trainloaders) == 3
        assert len(valloaders) == 3

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    def test_end_to_end_dirichlet_loading(self, mock_federated_dataset):
        """Test complete flow with Dirichlet partitioner."""
        mock_partition = MagicMock()
        mock_partition.__len__ = Mock(return_value=100)
        mock_partition.set_format = Mock()

        mock_fds = MagicMock()
        mock_fds.load_partition = Mock(return_value=mock_partition)
        mock_federated_dataset.return_value = mock_fds

        loader = FederatedDatasetLoader(
            dataset_name="cifar10",
            num_of_clients=5,
            batch_size=32,
            training_subset_fraction=0.8,
            partitioning_strategy="dirichlet",
            partitioning_params={"alpha": 0.1},
        )

        trainloaders, valloaders = loader.load_datasets()

        assert len(trainloaders) == 5
        assert len(valloaders) == 5

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    def test_end_to_end_pathological_loading(self, mock_federated_dataset):
        """Test complete flow with Pathological partitioner."""
        mock_partition = MagicMock()
        mock_partition.__len__ = Mock(return_value=100)
        mock_partition.set_format = Mock()

        mock_fds = MagicMock()
        mock_fds.load_partition = Mock(return_value=mock_partition)
        mock_federated_dataset.return_value = mock_fds

        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=4,
            batch_size=64,
            training_subset_fraction=0.9,
            partitioning_strategy="pathological",
            partitioning_params={"num_classes_per_partition": 3},
        )

        trainloaders, valloaders = loader.load_datasets()

        assert len(trainloaders) == 4
        assert len(valloaders) == 4


class TestStandardizeColumns:
    """Test column standardization functionality."""

    def test_standardize_image_column(self):
        """Should rename 'image' column to 'pixel_values'."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=1,
            batch_size=32,
            training_subset_fraction=0.8,
        )

        mock_dataset = MagicMock()
        mock_dataset.column_names = ["image", "label"]
        mock_dataset.rename_columns = Mock(return_value=mock_dataset)

        loader._standardize_columns(mock_dataset)

        mock_dataset.rename_columns.assert_called_once_with(
            {"image": "pixel_values", "label": "labels"}
        )

    def test_standardize_img_column(self):
        """Should rename 'img' column to 'pixel_values'."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=1,
            batch_size=32,
            training_subset_fraction=0.8,
        )

        mock_dataset = MagicMock()
        mock_dataset.column_names = ["img", "label"]
        mock_dataset.rename_columns = Mock(return_value=mock_dataset)

        loader._standardize_columns(mock_dataset)

        mock_dataset.rename_columns.assert_called_once_with(
            {"img": "pixel_values", "label": "labels"}
        )

    def test_standardize_character_column(self):
        """Should rename 'character' column to 'labels' (FEMNIST)."""
        loader = FederatedDatasetLoader(
            dataset_name="flwrlabs/femnist",
            num_of_clients=1,
            batch_size=32,
            training_subset_fraction=0.8,
            label_column="character",
        )

        mock_dataset = MagicMock()
        mock_dataset.column_names = ["image", "character"]
        mock_dataset.rename_columns = Mock(return_value=mock_dataset)

        loader._standardize_columns(mock_dataset)

        mock_dataset.rename_columns.assert_called_once_with(
            {"image": "pixel_values", "character": "labels"}
        )

    def test_standardize_label_column_singular(self):
        """Should rename 'label' (singular) to 'labels' (plural)."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=1,
            batch_size=32,
            training_subset_fraction=0.8,
        )

        mock_dataset = MagicMock()
        mock_dataset.column_names = ["image", "label"]
        mock_dataset.rename_columns = Mock(return_value=mock_dataset)

        loader._standardize_columns(mock_dataset)

        mock_dataset.rename_columns.assert_called_once_with(
            {"image": "pixel_values", "label": "labels"}
        )

    def test_no_rename_if_already_standard(self):
        """Should not rename if columns are already standardized."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=1,
            batch_size=32,
            training_subset_fraction=0.8,
        )

        mock_dataset = MagicMock()
        mock_dataset.column_names = ["pixel_values", "labels"]
        mock_dataset.rename_columns = Mock(return_value=mock_dataset)

        loader._standardize_columns(mock_dataset)

        mock_dataset.rename_columns.assert_not_called()

    def test_standardize_fine_label_column(self):
        """Should rename 'fine_label' to 'labels'."""
        loader = FederatedDatasetLoader(
            dataset_name="cifar10",
            num_of_clients=1,
            batch_size=32,
            training_subset_fraction=0.8,
        )

        mock_dataset = MagicMock()
        mock_dataset.column_names = ["img", "fine_label"]
        mock_dataset.rename_columns = Mock(return_value=mock_dataset)

        loader._standardize_columns(mock_dataset)

        mock_dataset.rename_columns.assert_called_once_with(
            {"img": "pixel_values", "fine_label": "labels"}
        )

    def test_respects_label_column_parameter(self):
        """Should prioritize label_column parameter for renaming."""
        loader = FederatedDatasetLoader(
            dataset_name="custom_dataset",
            num_of_clients=1,
            batch_size=32,
            training_subset_fraction=0.8,
            label_column="custom_label",
        )

        mock_dataset = MagicMock()
        mock_dataset.column_names = ["image", "custom_label", "label"]
        mock_dataset.rename_columns = Mock(return_value=mock_dataset)

        loader._standardize_columns(mock_dataset)

        mock_dataset.rename_columns.assert_called_once_with(
            {"image": "pixel_values", "custom_label": "labels"}
        )

    def test_only_renames_image_if_label_already_standardized(self):
        """Should only rename image column if labels is already standardized."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=1,
            batch_size=32,
            training_subset_fraction=0.8,
        )

        mock_dataset = MagicMock()
        mock_dataset.column_names = ["image", "labels"]
        mock_dataset.rename_columns = Mock(return_value=mock_dataset)

        loader._standardize_columns(mock_dataset)

        mock_dataset.rename_columns.assert_called_once_with({"image": "pixel_values"})

    def test_only_renames_label_if_image_already_standardized(self):
        """Should only rename label column if pixel_values is already standardized."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=1,
            batch_size=32,
            training_subset_fraction=0.8,
        )

        mock_dataset = MagicMock()
        mock_dataset.column_names = ["pixel_values", "label"]
        mock_dataset.rename_columns = Mock(return_value=mock_dataset)

        loader._standardize_columns(mock_dataset)

        mock_dataset.rename_columns.assert_called_once_with({"label": "labels"})


class TestTransformedImageDatasetWrapper:
    """Phase 2A: `image_transform` applies a torchvision-style transform per access."""

    def test_image_transform_default_is_none(self):
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=2,
            batch_size=8,
            training_subset_fraction=0.8,
        )
        assert loader.image_transform is None

    def test_image_transform_stored_when_provided(self):
        import torch

        transform = torch.nn.Identity()  # any callable
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=2,
            batch_size=8,
            training_subset_fraction=0.8,
            image_transform=transform,
        )
        assert loader.image_transform is transform

    def test_wrapper_invokes_transform_on_pixel_values(self):
        import torch

        from intellifl.dataset_loaders.federated_dataset_loader import (
            _TransformedImageDataset,
        )

        sentinel = torch.tensor([[1.0, 2.0], [3.0, 4.0]])

        class InnerStub:
            def __init__(self) -> None:
                self.calls = 0

            def __len__(self) -> int:
                return 2

            def __getitem__(self, idx: int) -> dict:
                self.calls += 1
                return {"pixel_values": torch.zeros((2, 2)), "labels": idx}

        def transform(_x: torch.Tensor) -> torch.Tensor:
            return sentinel

        inner = InnerStub()
        wrapped = _TransformedImageDataset(inner, transform)

        assert len(wrapped) == 2
        item = wrapped[0]
        assert torch.equal(item["pixel_values"], sentinel)
        assert item["labels"] == 0
        # `__getitem__` was invoked exactly once on the inner dataset.
        assert inner.calls == 1

    def test_wrapper_preserves_labels(self):
        """Transform applies only to pixel_values; labels pass through."""
        import torch

        from intellifl.dataset_loaders.federated_dataset_loader import (
            _TransformedImageDataset,
        )

        class InnerStub:
            def __getitem__(self, idx: int) -> dict:
                return {"pixel_values": torch.tensor([float(idx)]), "labels": idx + 100}

            def __len__(self) -> int:
                return 3

        def double(t: torch.Tensor) -> torch.Tensor:
            return t * 2

        wrapped = _TransformedImageDataset(InnerStub(), double)
        for i in range(3):
            item = wrapped[i]
            assert item["labels"] == i + 100
            assert item["pixel_values"].item() == float(i) * 2

    def test_wrapper_does_not_mutate_inner_item(self):
        """`dict(self.inner[idx])` copies — the inner partition is read-only."""
        import torch

        from intellifl.dataset_loaders.federated_dataset_loader import (
            _TransformedImageDataset,
        )

        original = {"pixel_values": torch.tensor([1.0, 2.0]), "labels": 7}

        class InnerStub:
            def __getitem__(self, _idx: int) -> dict:
                return original

            def __len__(self) -> int:
                return 1

        def zero(_t: torch.Tensor) -> torch.Tensor:
            return torch.zeros_like(_t)

        wrapped = _TransformedImageDataset(InnerStub(), zero)
        item = wrapped[0]
        # Returned dict has the transformed value...
        assert torch.equal(item["pixel_values"], torch.zeros(2))
        # ...but the inner item we'd hand back next iteration is untouched.
        assert torch.equal(original["pixel_values"], torch.tensor([1.0, 2.0]))


class TestSubsetParam:
    """Phase 2A: `subset` forwards to FederatedDataset for multi-config HF datasets."""

    def test_subset_default_is_none(self):
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=2,
            batch_size=8,
            training_subset_fraction=0.8,
        )
        assert loader.subset is None

    def test_subset_stored_when_provided(self):
        loader = FederatedDatasetLoader(
            dataset_name="albertvillanova/medmnist-v2",
            num_of_clients=2,
            batch_size=8,
            training_subset_fraction=0.8,
            subset="pathmnist",
        )
        assert loader.subset == "pathmnist"

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    def test_subset_omitted_from_federated_dataset_call_when_none(self, mock_fds_cls):
        """No `subset` kwarg should be passed when the loader has subset=None.

        Ensures the bare-minimum FederatedDataset signature still works for
        single-config datasets (CIFAR-10, MNIST, FEMNIST).
        """
        mock_fds = MagicMock()
        mock_partition = MagicMock()
        mock_partition.column_names = ["pixel_values", "labels"]
        mock_partition.features = {}
        mock_partition.__len__ = Mock(return_value=10)
        mock_fds.load_partition.return_value = mock_partition
        mock_fds_cls.return_value = mock_fds

        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=1,
            batch_size=8,
            training_subset_fraction=0.8,
        )
        # Implementation details past FederatedDataset call are unrelated;
        # only the constructor kwargs matter for this test.
        with contextlib.suppress(Exception):
            loader.load_datasets()

        kwargs = mock_fds_cls.call_args.kwargs
        assert "subset" not in kwargs, f"subset should be omitted when None, got {kwargs}"

    @patch("intellifl.dataset_loaders.federated_dataset_loader.FederatedDataset")
    def test_subset_forwarded_to_federated_dataset_when_set(self, mock_fds_cls):
        """When subset is set, it must reach the FederatedDataset constructor."""
        mock_fds = MagicMock()
        mock_partition = MagicMock()
        mock_partition.column_names = ["pixel_values", "labels"]
        mock_partition.features = {}
        mock_partition.__len__ = Mock(return_value=10)
        mock_fds.load_partition.return_value = mock_partition
        mock_fds_cls.return_value = mock_fds

        loader = FederatedDatasetLoader(
            dataset_name="albertvillanova/medmnist-v2",
            num_of_clients=1,
            batch_size=8,
            training_subset_fraction=0.8,
            subset="pathmnist",
        )
        with contextlib.suppress(Exception):
            loader.load_datasets()

        kwargs = mock_fds_cls.call_args.kwargs
        assert kwargs.get("subset") == "pathmnist"


class TestImageColumnParam:
    """Phase 2A: `image_column` overrides the auto-detect in _standardize_columns."""

    def test_image_column_default_is_none(self):
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=2,
            batch_size=8,
            training_subset_fraction=0.8,
        )
        assert loader.image_column is None

    def test_image_column_stored_when_provided(self):
        loader = FederatedDatasetLoader(
            dataset_name="uoft-cs/cifar10",
            num_of_clients=2,
            batch_size=8,
            training_subset_fraction=0.8,
            image_column="img",
        )
        assert loader.image_column == "img"

    def test_explicit_image_column_wins_over_auto_detect(self):
        """When both 'image' and 'img' exist, explicit picks the named one."""
        loader = FederatedDatasetLoader(
            dataset_name="some/multi-image-dataset",
            num_of_clients=2,
            batch_size=8,
            training_subset_fraction=0.8,
            image_column="img",
        )
        mock_dataset = MagicMock()
        mock_dataset.column_names = ["image", "img", "labels"]
        mock_dataset.rename_columns = Mock(return_value=mock_dataset)
        mock_dataset.remove_columns = Mock(return_value=mock_dataset)

        loader._standardize_columns(mock_dataset)

        mock_dataset.rename_columns.assert_called_once_with({"img": "pixel_values"})

    def test_auto_detect_still_runs_when_image_column_is_none(self):
        """Default behavior preserved: with image_column=None, auto-detect picks
        the first matching alias ('image' before 'img')."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=2,
            batch_size=8,
            training_subset_fraction=0.8,
        )
        mock_dataset = MagicMock()
        mock_dataset.column_names = ["image", "labels"]
        mock_dataset.rename_columns = Mock(return_value=mock_dataset)
        mock_dataset.remove_columns = Mock(return_value=mock_dataset)

        loader._standardize_columns(mock_dataset)

        mock_dataset.rename_columns.assert_called_once_with({"image": "pixel_values"})

    def test_image_column_falls_back_when_named_column_missing(self):
        """If image_column names a column the dataset doesn't have, fall back to auto-detect."""
        loader = FederatedDatasetLoader(
            dataset_name="some/dataset",
            num_of_clients=2,
            batch_size=8,
            training_subset_fraction=0.8,
            image_column="picture",
        )
        mock_dataset = MagicMock()
        mock_dataset.column_names = ["image", "labels"]
        mock_dataset.rename_columns = Mock(return_value=mock_dataset)
        mock_dataset.remove_columns = Mock(return_value=mock_dataset)

        loader._standardize_columns(mock_dataset)

        mock_dataset.rename_columns.assert_called_once_with({"image": "pixel_values"})


class TestPartitionByParam:
    """Phase 2A: `partition_by` overrides the column the partitioner partitions on.

    Dirichlet / Pathological default to `label_column`; the new `natural_id`
    strategy needs an explicit non-label column (FEMNIST's `writer_id`).
    """

    def test_partition_by_default_is_none(self):
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=2,
            batch_size=8,
            training_subset_fraction=0.8,
        )
        assert loader.partition_by is None

    def test_partition_by_stored_when_provided(self):
        loader = FederatedDatasetLoader(
            dataset_name="flwrlabs/femnist",
            num_of_clients=10,
            batch_size=32,
            training_subset_fraction=0.8,
            partition_by="writer_id",
        )
        assert loader.partition_by == "writer_id"

    def test_dirichlet_uses_partition_by_when_set(self):
        """Dirichlet's partition_by should follow the explicit override, not label_column."""
        loader = FederatedDatasetLoader(
            dataset_name="some/dataset",
            num_of_clients=4,
            batch_size=8,
            training_subset_fraction=0.8,
            partitioning_strategy="dirichlet",
            partitioning_params={"alpha": 0.3},
            label_column="label",
            partition_by="writer_id",
        )
        partitioner = loader._create_partitioner()
        assert isinstance(partitioner, DirichletPartitioner)
        assert partitioner._partition_by == "writer_id"

    def test_dirichlet_falls_back_to_label_column_when_partition_by_none(self):
        """Default behavior preserved when partition_by is None."""
        loader = FederatedDatasetLoader(
            dataset_name="mnist",
            num_of_clients=4,
            batch_size=8,
            training_subset_fraction=0.8,
            partitioning_strategy="dirichlet",
            label_column="label",
        )
        partitioner = loader._create_partitioner()
        assert partitioner._partition_by == "label"

    def test_natural_id_strategy_creates_natural_id_partitioner(self):
        """`natural_id` strategy is the femnist_niid path."""
        loader = FederatedDatasetLoader(
            dataset_name="flwrlabs/femnist",
            num_of_clients=10,
            batch_size=32,
            training_subset_fraction=0.8,
            partitioning_strategy="natural_id",
            partition_by="writer_id",
        )
        partitioner = loader._create_partitioner()
        assert isinstance(partitioner, NaturalIdPartitioner)
        assert partitioner._partition_by == "writer_id"

    def test_natural_id_strategy_raises_without_partition_by(self):
        """natural_id requires partition_by — the failure should be explicit."""
        loader = FederatedDatasetLoader(
            dataset_name="flwrlabs/femnist",
            num_of_clients=10,
            batch_size=32,
            training_subset_fraction=0.8,
            partitioning_strategy="natural_id",
        )
        with pytest.raises(ValueError, match="requires `partition_by`"):
            loader._create_partitioner()
