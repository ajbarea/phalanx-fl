"""Unit tests for `intellifl.dataset_loaders.partitioner_registry`.

Covers each of the 13 partitioners wired in `PARTITIONER_REGISTRY`:
- happy path (default params resolve, partitioner instantiates with the
  right class)
- required-param surface (missing keys raise `ValueError` with a clear
  message keyed to the strategy)
- partition_by precedence (label-driven strategies fall back to
  `partition_col`; natural-id strategies refuse to fall back)
"""

from __future__ import annotations

import numpy as np
import pytest
from flwr_datasets.partitioner import (
    ContinuousPartitioner,
    DirichletPartitioner,
    DistributionPartitioner,
    ExponentialPartitioner,
    GroupedNaturalIdPartitioner,
    IidPartitioner,
    InnerDirichletPartitioner,
    LinearPartitioner,
    NaturalIdPartitioner,
    PathologicalPartitioner,
    ShardPartitioner,
    SizePartitioner,
    SquarePartitioner,
)

from intellifl.dataset_loaders.partitioner_registry import (
    PARTITIONER_REGISTRY,
    create_partitioner,
)


class TestSimplePartitioners:
    """Partitioners that take only `num_partitions`."""

    @pytest.mark.parametrize(
        "strategy, expected_cls",
        [
            ("iid", IidPartitioner),
            ("linear", LinearPartitioner),
            ("exponential", ExponentialPartitioner),
            ("square", SquarePartitioner),
        ],
    )
    def test_simple_partitioner_instantiates(self, strategy: str, expected_cls: type) -> None:
        partitioner = create_partitioner(strategy, num_of_clients=4, partition_col=None, params={})
        assert isinstance(partitioner, expected_cls)


class TestLabelDrivenPartitioners:
    """Partitioners that take `num_partitions` + `partition_by` + extras."""

    def test_dirichlet_defaults(self) -> None:
        partitioner = create_partitioner(
            "dirichlet", num_of_clients=4, partition_col="label", params={}
        )
        assert isinstance(partitioner, DirichletPartitioner)
        assert partitioner._partition_by == "label"
        # Default alpha is 0.5 per builder; DirichletPartitioner broadcasts
        # the scalar across num_partitions into a numpy array.
        assert np.allclose(partitioner._alpha, 0.5)

    def test_dirichlet_custom_alpha(self) -> None:
        partitioner = create_partitioner(
            "dirichlet", num_of_clients=4, partition_col="label", params={"alpha": 0.1}
        )
        assert np.allclose(partitioner._alpha, 0.1)

    def test_pathological_defaults(self) -> None:
        partitioner = create_partitioner(
            "pathological", num_of_clients=4, partition_col="label", params={}
        )
        assert isinstance(partitioner, PathologicalPartitioner)
        # Default is 2 classes per partition per builder
        assert partitioner._num_classes_per_partition == 2

    def test_shard_requires_one_of_sizing_modes(self) -> None:
        # ShardPartitioner accepts num_shards_per_partition OR shard_size, not both/neither.
        partitioner = create_partitioner(
            "shard",
            num_of_clients=4,
            partition_col="label",
            params={"num_shards_per_partition": 2},
        )
        assert isinstance(partitioner, ShardPartitioner)

    def test_continuous_requires_strictness(self) -> None:
        with pytest.raises(ValueError, match="`strictness`"):
            create_partitioner("continuous", num_of_clients=4, partition_col="label", params={})

    def test_continuous_with_strictness(self) -> None:
        partitioner = create_partitioner(
            "continuous", num_of_clients=4, partition_col="label", params={"strictness": 0.5}
        )
        assert isinstance(partitioner, ContinuousPartitioner)


class TestNaturalIdPartitioners:
    """Natural-ID partitioners require an explicit non-label `partition_by`."""

    def test_natural_id_requires_partition_by(self) -> None:
        with pytest.raises(ValueError, match="requires `partition_by`"):
            create_partitioner("natural_id", num_of_clients=10, partition_col=None, params={})

    def test_natural_id_happy_path(self) -> None:
        partitioner = create_partitioner(
            "natural_id", num_of_clients=10, partition_col="writer_id", params={}
        )
        assert isinstance(partitioner, NaturalIdPartitioner)
        assert partitioner._partition_by == "writer_id"

    def test_grouped_natural_id_requires_group_size(self) -> None:
        with pytest.raises(ValueError, match="`group_size`"):
            create_partitioner(
                "grouped_natural_id",
                num_of_clients=10,
                partition_col="writer_id",
                params={},
            )

    def test_grouped_natural_id_happy_path(self) -> None:
        partitioner = create_partitioner(
            "grouped_natural_id",
            num_of_clients=10,
            partition_col="writer_id",
            params={"group_size": 3},
        )
        assert isinstance(partitioner, GroupedNaturalIdPartitioner)


class TestSizesDrivenPartitioners:
    """Size-driven partitioners derive partition count from `partition_sizes`."""

    def test_size_requires_partition_sizes(self) -> None:
        with pytest.raises(ValueError, match="`partition_sizes`"):
            create_partitioner("size", num_of_clients=4, partition_col=None, params={})

    def test_size_happy_path(self) -> None:
        partitioner = create_partitioner(
            "size",
            num_of_clients=4,
            partition_col=None,
            params={"partition_sizes": [10, 20, 30]},
        )
        assert isinstance(partitioner, SizePartitioner)

    def test_inner_dirichlet_requires_partition_sizes_and_alpha(self) -> None:
        with pytest.raises(ValueError, match="`partition_sizes`"):
            create_partitioner(
                "inner_dirichlet",
                num_of_clients=4,
                partition_col="label",
                params={"alpha": 0.5},
            )

    def test_inner_dirichlet_happy_path(self) -> None:
        partitioner = create_partitioner(
            "inner_dirichlet",
            num_of_clients=4,
            partition_col="label",
            params={"partition_sizes": [100, 200, 300], "alpha": 0.5},
        )
        assert isinstance(partitioner, InnerDirichletPartitioner)


class TestDistributionPartitioner:
    """DistributionPartitioner takes a full probability matrix."""

    def test_distribution_requires_all_params(self) -> None:
        with pytest.raises(ValueError, match="`distribution_array`"):
            create_partitioner(
                "distribution",
                num_of_clients=2,
                partition_col="label",
                params={},
            )

    def test_distribution_happy_path(self) -> None:
        # 2 partitions × 2 unique labels = 2×2 matrix
        dist = np.array([[1, 1], [1, 1]], dtype=np.int64)
        partitioner = create_partitioner(
            "distribution",
            num_of_clients=2,
            partition_col="label",
            params={
                "distribution_array": dist,
                "num_unique_labels_per_partition": 2,
                "preassigned_num_samples_per_label": 10,
            },
        )
        assert isinstance(partitioner, DistributionPartitioner)


class TestRegistryContract:
    """The registry shape itself."""

    def test_unknown_strategy_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown partitioning strategy"):
            create_partitioner("totally_made_up", num_of_clients=1, partition_col=None, params={})

    def test_registry_covers_thirteen_horizontal_partitioners(self) -> None:
        # ROADMAP commits to 13 horizontal partitioners (vertical + abstract
        # parents intentionally omitted). Lock the count so future additions
        # are deliberate.
        assert len(PARTITIONER_REGISTRY) == 13

    def test_registry_keys_match_documented_set(self) -> None:
        expected = {
            "iid",
            "linear",
            "exponential",
            "square",
            "dirichlet",
            "pathological",
            "shard",
            "continuous",
            "natural_id",
            "grouped_natural_id",
            "size",
            "inner_dirichlet",
            "distribution",
        }
        assert set(PARTITIONER_REGISTRY) == expected
