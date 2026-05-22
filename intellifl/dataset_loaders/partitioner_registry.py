"""Registry + factory for `flwr_datasets.partitioner` classes.

Maps a string key (the JSON / `StrategyConfig.partitioning_strategy` value)
to a builder that instantiates the right partitioner from `flwr_datasets`,
threading `num_partitions`, `partition_by`, and a per-strategy
`partitioning_params` dict into the class's constructor.

Adding a new partitioner = one entry in :data:`PARTITIONER_REGISTRY` +
one builder function below. Each builder documents the params it reads
out of `params` so the surface is auditable from this file alone.

research(2026-05): registry shape mirrors
`intellifl.dataset_loaders.LOADER_REGISTRY` (the dataset-loader builder
registry) and `intellifl.simulation_strategies.STRATEGY_REGISTRY`. The
partitioner-side registry was the third copy of the if/elif chain —
`FederatedDatasetLoader._create_partitioner()` and the orphaned legacy
loaders (`huggingface_image_dataset_loader.py`,
`huggingface_text_dataset_loader.py`, `text_classification_loader.py`)
all duplicated the same iid/dirichlet/pathological dispatch. Once Phase
2E deletes the legacy loaders, this registry is the single source of
truth across the codebase.

Source: https://flower.ai/docs/datasets/ref-api/flwr_datasets.partitioner.html
(flwr-datasets v0.6.0; 13 horizontal partitioners wired, 2 vertical
ones deliberately omitted — see :data:`OUT_OF_SCOPE_PARTITIONERS`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

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
    Partitioner,
    PathologicalPartitioner,
    ShardPartitioner,
    SizePartitioner,
    SquarePartitioner,
)

# Builder signature: (num_of_clients, partition_col, params) -> Partitioner.
# `partition_col` resolves to `self.partition_by or self.label_column` in
# the calling loader; the partitioner-specific builder decides whether
# that value is required, optional, or ignored.
PartitionerFactory = Callable[[int, str | None, dict[str, Any]], Partitioner]


def _require(params: dict[str, Any], key: str, strategy: str) -> Any:
    """Raise a uniform error when a partitioner needs a JSON-supplied param."""
    if key not in params:
        raise ValueError(
            f"partitioning_strategy={strategy!r} requires `{key}` in partitioning_params"
        )
    return params[key]


def _require_partition_col(partition_col: str | None, strategy: str) -> str:
    if not partition_col:
        raise ValueError(
            f"partitioning_strategy={strategy!r} requires `partition_by` "
            f"(no label_column fallback for this strategy)"
        )
    return partition_col


# --------------------------------------------------------------------------
# Simple (num_partitions only)
# --------------------------------------------------------------------------


def _build_iid(
    num_partitions: int, partition_col: str | None, params: dict[str, Any]
) -> Partitioner:
    del partition_col, params
    return IidPartitioner(num_partitions=num_partitions)


def _build_linear(
    num_partitions: int, partition_col: str | None, params: dict[str, Any]
) -> Partitioner:
    del partition_col, params
    return LinearPartitioner(num_partitions=num_partitions)


def _build_exponential(
    num_partitions: int, partition_col: str | None, params: dict[str, Any]
) -> Partitioner:
    del partition_col, params
    return ExponentialPartitioner(num_partitions=num_partitions)


def _build_square(
    num_partitions: int, partition_col: str | None, params: dict[str, Any]
) -> Partitioner:
    del partition_col, params
    return SquarePartitioner(num_partitions=num_partitions)


# --------------------------------------------------------------------------
# Label-driven (num_partitions + partition_by + extras)
# --------------------------------------------------------------------------


def _build_dirichlet(
    num_partitions: int, partition_col: str | None, params: dict[str, Any]
) -> Partitioner:
    return DirichletPartitioner(
        num_partitions=num_partitions,
        partition_by=_require_partition_col(partition_col, "dirichlet"),
        alpha=params.get("alpha", 0.5),
        min_partition_size=params.get("min_partition_size", 10),
        self_balancing=params.get("self_balancing", False),
        shuffle=params.get("shuffle", True),
        seed=params.get("seed", 42),
    )


def _build_pathological(
    num_partitions: int, partition_col: str | None, params: dict[str, Any]
) -> Partitioner:
    return PathologicalPartitioner(
        num_partitions=num_partitions,
        partition_by=_require_partition_col(partition_col, "pathological"),
        num_classes_per_partition=params.get("num_classes_per_partition", 2),
        class_assignment_mode=params.get("class_assignment_mode", "random"),
        shuffle=params.get("shuffle", True),
        seed=params.get("seed", 42),
    )


def _build_shard(
    num_partitions: int, partition_col: str | None, params: dict[str, Any]
) -> Partitioner:
    # ShardPartitioner exposes two sizing modes — `num_shards_per_partition`
    # (McMahan-style fixed count) OR `shard_size` (fixed size, count derived
    # from dataset length). flwr_datasets accepts either as long as exactly
    # one is set, so pass both through and let the partitioner raise.
    return ShardPartitioner(
        num_partitions=num_partitions,
        partition_by=_require_partition_col(partition_col, "shard"),
        num_shards_per_partition=params.get("num_shards_per_partition"),
        shard_size=params.get("shard_size"),
        keep_incomplete_shard=params.get("keep_incomplete_shard", False),
        shuffle=params.get("shuffle", True),
        seed=params.get("seed", 42),
    )


def _build_continuous(
    num_partitions: int, partition_col: str | None, params: dict[str, Any]
) -> Partitioner:
    return ContinuousPartitioner(
        num_partitions=num_partitions,
        partition_by=_require_partition_col(partition_col, "continuous"),
        strictness=_require(params, "strictness", "continuous"),
        shuffle=params.get("shuffle", True),
        seed=params.get("seed", 42),
    )


# --------------------------------------------------------------------------
# Natural-ID driven (partition_by; num_partitions ignored)
# --------------------------------------------------------------------------


def _build_natural_id(
    num_partitions: int, partition_col: str | None, params: dict[str, Any]
) -> Partitioner:
    # NaturalIdPartitioner derives partitions from the column's unique values
    # — `num_partitions` is ignored. Caller's `num_of_clients` then indexes
    # into the discovered partition list (FEMNIST: ~3.5k writers).
    del num_partitions, params
    return NaturalIdPartitioner(
        partition_by=_require_partition_col(partition_col, "natural_id"),
    )


def _build_grouped_natural_id(
    num_partitions: int, partition_col: str | None, params: dict[str, Any]
) -> Partitioner:
    del num_partitions
    return GroupedNaturalIdPartitioner(
        partition_by=_require_partition_col(partition_col, "grouped_natural_id"),
        group_size=_require(params, "group_size", "grouped_natural_id"),
        mode=params.get("mode", "allow-smaller"),
        sort_unique_ids=params.get("sort_unique_ids", False),
    )


# --------------------------------------------------------------------------
# Sizes-driven (no num_partitions kwarg — partition count comes from `partition_sizes`)
# --------------------------------------------------------------------------


def _build_size(
    num_partitions: int, partition_col: str | None, params: dict[str, Any]
) -> Partitioner:
    del num_partitions, partition_col
    return SizePartitioner(
        partition_sizes=_require(params, "partition_sizes", "size"),
    )


def _build_inner_dirichlet(
    num_partitions: int, partition_col: str | None, params: dict[str, Any]
) -> Partitioner:
    del num_partitions
    return InnerDirichletPartitioner(
        partition_sizes=_require(params, "partition_sizes", "inner_dirichlet"),
        partition_by=_require_partition_col(partition_col, "inner_dirichlet"),
        alpha=_require(params, "alpha", "inner_dirichlet"),
        shuffle=params.get("shuffle", True),
        seed=params.get("seed", 42),
    )


# --------------------------------------------------------------------------
# Distribution-driven (full probability matrix)
# --------------------------------------------------------------------------


def _build_distribution(
    num_partitions: int, partition_col: str | None, params: dict[str, Any]
) -> Partitioner:
    return DistributionPartitioner(
        distribution_array=_require(params, "distribution_array", "distribution"),
        num_partitions=num_partitions,
        num_unique_labels_per_partition=_require(
            params, "num_unique_labels_per_partition", "distribution"
        ),
        partition_by=_require_partition_col(partition_col, "distribution"),
        preassigned_num_samples_per_label=_require(
            params, "preassigned_num_samples_per_label", "distribution"
        ),
        rescale=params.get("rescale", True),
        shuffle=params.get("shuffle", True),
        seed=params.get("seed", 42),
    )


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


PARTITIONER_REGISTRY: dict[str, PartitionerFactory] = {
    "iid": _build_iid,
    "linear": _build_linear,
    "exponential": _build_exponential,
    "square": _build_square,
    "dirichlet": _build_dirichlet,
    "pathological": _build_pathological,
    "shard": _build_shard,
    "continuous": _build_continuous,
    "natural_id": _build_natural_id,
    "grouped_natural_id": _build_grouped_natural_id,
    "size": _build_size,
    "inner_dirichlet": _build_inner_dirichlet,
    "distribution": _build_distribution,
}


OUT_OF_SCOPE_PARTITIONERS = {
    # Vertical (feature-split FL) — different paradigm, intentionally not
    # surfaced through the horizontal partitioning_strategy key.
    "vertical_even",
    "vertical_size",
    # IdToSizeFncPartitioner is an abstract-ish parent class for the
    # arithmetic-progression partitioners (Linear / Exponential / Square)
    # — surfacing it on its own would force callers to pass a function,
    # which isn't representable in JSON. Skipped.
    "id_to_size_fnc",
}


def create_partitioner(
    strategy: str,
    num_of_clients: int,
    partition_col: str | None,
    params: dict[str, Any] | None,
) -> Partitioner:
    """Construct the configured `flwr_datasets` partitioner.

    Args:
        strategy: Registry key (e.g. ``"dirichlet"``, ``"natural_id"``).
        num_of_clients: Forwarded as ``num_partitions`` for partitioners
            that take it; ignored by natural-id / size-driven variants.
        partition_col: The resolved column to partition on — caller threads
            ``self.partition_by or self.label_column`` here. Required by
            label-driven and natural-id strategies; ignored otherwise.
        params: Strategy-specific parameters (e.g. ``{"alpha": 0.5}``).
            Defaults applied per-builder when keys are absent; missing
            *required* keys raise :class:`ValueError`.

    Raises:
        ValueError: If ``strategy`` is unknown or a required param is
            missing.
    """
    if strategy not in PARTITIONER_REGISTRY:
        known = sorted(PARTITIONER_REGISTRY)
        raise ValueError(f"Unknown partitioning strategy: {strategy!r}. Known: {known}")
    return PARTITIONER_REGISTRY[strategy](num_of_clients, partition_col, params or {})


__all__ = [
    "OUT_OF_SCOPE_PARTITIONERS",
    "PARTITIONER_REGISTRY",
    "PartitionerFactory",
    "create_partitioner",
]
