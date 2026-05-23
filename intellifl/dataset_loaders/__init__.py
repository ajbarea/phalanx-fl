"""Registry + factory for federated dataset loaders and their paired network models.

Maps each `dataset_keyword` (the JSON config string) to a builder callable that
constructs the right loader class AND the right network model in one go. The
dispatch table here replaces what used to be a 170-line `if/elif` chain in
`intellifl.federated_simulation._assign_dataset_loaders_and_network_model`,
plus three independent copies of the LLM-model-construction block (medquad,
HF text, medal).

Adding a new dataset = one entry in :data:`LOADER_REGISTRY` + one builder
function below. Loader classes themselves stay as separate files; the
consolidation is at the dispatch seam, not the per-loader implementation.

research(2026-05): registry + dispatch is the same pattern shipped in
`intellifl/network_models/__init__.py` and `intellifl/simulation_strategies/__init__.py`.
The dataset slice has the extra wrinkle that loader and network model are
selected together (CNN datasets pair with `build_cnn_model(keyword)`,
text datasets pair with the configured LLM, cifar100 pairs with
`DynamicCNN`) — so the factory returns the `(loader, model)` tuple rather
than just a loader.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from intellifl.dataset_loaders.federated_dataset_loader import FederatedDatasetLoader
from intellifl.dataset_loaders.huggingface_text_dataset_loader import (
    HuggingFaceTextDatasetLoader,
)
from intellifl.dataset_loaders.image_transformers.cifar10_image_transformer import (
    cifar10_image_transformer,
)
from intellifl.dataset_loaders.image_transformers.cifar100_image_transformer import (
    cifar100_image_transformer,
)
from intellifl.dataset_loaders.image_transformers.cinic10_image_transformer import (
    cinic10_image_transformer,
)
from intellifl.dataset_loaders.image_transformers.femnist_image_transformer import (
    femnist_image_transformer,
)
from intellifl.dataset_loaders.image_transformers.medmnist_2d_grayscale_image_transformer import (
    medmnist_2d_grayscale_image_transformer,
)
from intellifl.dataset_loaders.image_transformers.medmnist_2d_rgb_image_transformer import (
    medmnist_2d_rgb_image_transformer,
)
from intellifl.dataset_loaders.medquad_dataset_loader import MedQuADDatasetLoader
from intellifl.network_models import build_cnn_model
from intellifl.network_models.dynamic_cnn import DynamicCNN
from intellifl.network_models.transformer_models import load_model, load_model_with_lora

if TYPE_CHECKING:
    from intellifl.data_models.simulation_strategy_config import StrategyConfig


# --------------------------------------------------------------------------
# HuggingFace dataset config + image-transformer registry
# --------------------------------------------------------------------------


def get_hf_dataset_config(dataset_keyword: str) -> dict[str, Any]:
    """Read the per-keyword config block from `config/huggingface_datasets.json`."""
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "config", "huggingface_datasets.json"
    )
    with open(config_path, encoding="utf-8") as f:
        all_configs = json.load(f)
    return all_configs[dataset_keyword]


# Registry of image-transformer string keys -> transform objects.
# Keeps the JSON config declarative — transformer values are string keys
# resolved here on first use.
_IMAGE_TRANSFORMER_REGISTRY: dict[str, Any] = {}


def _build_image_transformer_registry() -> dict[str, Any]:
    """Lazily populate the image-transformer registry on first lookup."""
    if not _IMAGE_TRANSFORMER_REGISTRY:
        _IMAGE_TRANSFORMER_REGISTRY.update(
            {
                "cifar10_image_transformer": cifar10_image_transformer,
                "cifar100_image_transformer": cifar100_image_transformer,
                "cinic10_image_transformer": cinic10_image_transformer,
                "femnist_image_transformer": femnist_image_transformer,
                "medmnist_2d_grayscale_image_transformer": medmnist_2d_grayscale_image_transformer,
                "medmnist_2d_rgb_image_transformer": medmnist_2d_rgb_image_transformer,
            }
        )
    return _IMAGE_TRANSFORMER_REGISTRY


def resolve_image_transformer(name: str | None) -> Any:
    """Resolve an image-transformer JSON config key to its transform object."""
    if name is None:
        return None
    registry = _build_image_transformer_registry()
    if name not in registry:
        raise ValueError(
            f"Unknown image_transformer '{name}'. Available: {sorted(registry.keys())}"
        )
    return registry[name]


# --------------------------------------------------------------------------
# LLM-model construction (used by every text builder)
# --------------------------------------------------------------------------


def _build_llm_model(config: StrategyConfig) -> Any:
    """Construct the LLM (optionally with LoRA) according to the strategy config.

    Centralizes what used to be three near-identical blocks in
    `federated_simulation.py` (medquad, HF text, medal). All of them branch
    the same way on `llm_finetuning == "lora"` and read the same set of
    `llm_*` / `lora_*` fields off the config.
    """
    llm_model_name = cast(str, getattr(config, "llm_model", ""))
    if getattr(config, "llm_finetuning", None) == "lora":
        return load_model_with_lora(
            model_name=llm_model_name,
            lora_rank=cast(int, getattr(config, "lora_rank", 8)),
            lora_alpha=cast(int, getattr(config, "lora_alpha", 16)),
            lora_dropout=cast(float, getattr(config, "lora_dropout", 0.05)),
            lora_target_modules=cast(list, getattr(config, "lora_target_modules", None)),
        )
    return load_model(model_name=llm_model_name)


# --------------------------------------------------------------------------
# Per-keyword builders -> (loader, network_model)
# --------------------------------------------------------------------------

# Builder signature: (keyword, config, dataset_dir) -> (loader, model). The
# keyword is forwarded so a single builder can serve multiple registered
# aliases (e.g. CNN datasets, the three HF text variants).
LoaderBuilder = Callable[[str, "StrategyConfig", str], tuple[Any, Any]]


def _build_medquad(keyword: str, config: StrategyConfig, dataset_dir: str) -> tuple[Any, Any]:
    del keyword
    loader = MedQuADDatasetLoader(
        dataset_dir=dataset_dir,
        num_of_clients=cast(int, config.num_of_clients),
        training_subset_fraction=cast(float, config.training_subset_fraction),
        model_name=cast(str, getattr(config, "llm_model", "")),
        batch_size=cast(int, config.batch_size),
        chunk_size=cast(int, getattr(config, "llm_chunk_size", 512)),
        mlm_probability=cast(float, getattr(config, "mlm_probability", 0.15)),
        num_poisoned_clients=config.num_of_malicious_clients or 0,
        attack_schedule=config.attack_schedule,
    )
    return loader, _build_llm_model(config)


def _build_hf_text(keyword: str, config: StrategyConfig, dataset_dir: str) -> tuple[Any, Any]:
    hf_cfg = get_hf_dataset_config(keyword)
    loader = HuggingFaceTextDatasetLoader(
        hf_dataset_path=hf_cfg["hf_dataset_path"],
        hf_dataset_name=hf_cfg["hf_dataset_name"],
        tokenize_columns=hf_cfg.get("tokenize_columns"),
        remove_columns=hf_cfg.get("remove_columns"),
        dataset_dir=dataset_dir,
        num_of_clients=cast(int, config.num_of_clients),
        training_subset_fraction=cast(float, config.training_subset_fraction),
        model_name=cast(str, getattr(config, "llm_model", "")),
        batch_size=cast(int, config.batch_size),
        chunk_size=cast(int, getattr(config, "llm_chunk_size", 512)),
        mlm_probability=cast(float, getattr(config, "mlm_probability", 0.15)),
        num_poisoned_clients=config.num_of_malicious_clients or 0,
        attack_schedule=config.attack_schedule,
    )
    return loader, _build_llm_model(config)


def _build_medal(keyword: str, config: StrategyConfig, dataset_dir: str) -> tuple[Any, Any]:
    # The medal dataset uses a hard-coded HF path + remove_columns set rather
    # than a JSON config entry, because it's a one-off corpus and the columns
    # to drop don't match any other HF text path's shape.
    del keyword
    max_samples = getattr(config, "max_dataset_samples", None)
    loader = HuggingFaceTextDatasetLoader(
        hf_dataset_path="cyrilzakka/pubmed-medline",
        hf_dataset_name=None,
        tokenize_columns=["content"],
        remove_columns=[
            "id",
            "title",
            "authors",
            "journal",
            "content",
            "source_url",
            "publication_types",
            "pubmed_id",
            "split",
        ],
        dataset_dir=dataset_dir,
        num_of_clients=cast(int, config.num_of_clients),
        training_subset_fraction=cast(float, config.training_subset_fraction),
        model_name=cast(str, getattr(config, "llm_model", "")),
        batch_size=cast(int, config.batch_size),
        chunk_size=cast(int, getattr(config, "llm_chunk_size", 512)),
        mlm_probability=cast(float, getattr(config, "mlm_probability", 0.15)),
        attack_schedule=config.attack_schedule,
        max_samples=max_samples,
    )
    return loader, _build_llm_model(config)


def _build_federated_dataset_loader(keyword: str, config: StrategyConfig) -> FederatedDatasetLoader:
    """Common FederatedDatasetLoader construction for every HF-image family.

    Reads the JSON entry for ``keyword``, resolves the image transformer,
    applies the partitioning precedence (config > JSON default > Dirichlet
    alpha=0.5 fallback — the alpha=0.5 default carries over from the legacy
    pre-Phase-2E loader's hardcoded label-skew shape), and forwards
    ``partition_by`` from JSON so FEMNIST-style natural_id wiring works
    without per-builder branching.
    """
    hf_cfg = get_hf_dataset_config(keyword)
    transformer = resolve_image_transformer(hf_cfg.get("image_transformer"))
    # Precedence: config > JSON per-dataset default > "dirichlet" alpha=0.5
    # fallback. The JSON default lets FEMNIST entries declare iid /
    # natural_id without polluting the StrategyConfig surface.
    config_partitioning_strategy = getattr(config, "partitioning_strategy", None)
    if config_partitioning_strategy is not None:
        partitioning_strategy = config_partitioning_strategy
        partitioning_params: dict[str, Any] = getattr(config, "partitioning_params", None) or {}
    elif hf_cfg.get("partitioning_strategy") is not None:
        partitioning_strategy = hf_cfg["partitioning_strategy"]
        partitioning_params = hf_cfg.get("partitioning_params") or {}
    else:
        partitioning_strategy = "dirichlet"
        partitioning_params = {"alpha": 0.5}
    return FederatedDatasetLoader(
        dataset_name=hf_cfg["hf_dataset_path"],
        subset=hf_cfg.get("hf_dataset_name"),
        num_of_clients=cast(int, config.num_of_clients),
        batch_size=cast(int, config.batch_size),
        training_subset_fraction=cast(float, config.training_subset_fraction),
        partitioning_strategy=partitioning_strategy,
        partitioning_params=partitioning_params,
        label_column=hf_cfg.get("label_column", "label"),
        image_transform=transformer,
        image_column=hf_cfg.get("image_column"),
        partition_by=hf_cfg.get("partition_by"),
    )


def _build_hf_image_cnn(keyword: str, config: StrategyConfig, dataset_dir: str) -> tuple[Any, Any]:
    """HF-backed CIFAR-family CNN builder — JSON-driven loader + DynamicCNN."""
    del dataset_dir
    hf_cfg = get_hf_dataset_config(keyword)
    loader = _build_federated_dataset_loader(keyword, config)
    model = DynamicCNN(
        num_classes=hf_cfg["num_classes"],
        input_channels=hf_cfg.get("input_channels", 3),
        input_height=hf_cfg.get("input_height", 32),
        input_width=hf_cfg.get("input_width", 32),
    )
    return loader, model


def _build_hf_medmnist_cnn(
    keyword: str, config: StrategyConfig, dataset_dir: str
) -> tuple[Any, Any]:
    """HF-backed MedMNIST CNN builder — JSON-driven loader + per-keyword MedMNISTCNN.

    Pulls from ``albertvillanova/medmnist-v2`` + per-variant subset via
    ``FederatedDatasetLoader``, which partitions in-loader. The model side
    keeps the existing ``build_cnn_model(keyword)`` dispatch — each MedMNIST
    variant retains its registered ``MedMNISTCNN`` conv/fc shape from
    ``intellifl.network_models._CNN_REGISTRY``.

    Partitioning behavior change: the OLD path used externally pre-
    partitioned files (Dirichlet-shaped, baked into the S3 tarball);
    the NEW path partitions Dirichlet alpha=0.5 in-loader. The shape
    matches but the seed differs, so per-client sample assignment will
    drift from prior baselines. Acceptable — the CIFAR-family migration
    (#27) made the same trade.
    """
    del dataset_dir
    loader = _build_federated_dataset_loader(keyword, config)
    model = build_cnn_model(keyword)
    return loader, model


# --------------------------------------------------------------------------
# Registry + factory
# --------------------------------------------------------------------------

_HF_TEXT_KEYWORDS = ("financial_phrasebank", "lexglue", "pubmed_classification_20k")
_HF_IMAGE_CNN_KEYWORDS = ("cifar100", "cifar10", "cinic10")
# MedMNIST + FEMNIST share `_build_hf_medmnist_cnn`: HF loader paired with
# the per-keyword `MedMNISTCNN` architecture registered in
# `intellifl.network_models._CNN_REGISTRY`. The keyword's `partitioning_strategy`
# default is read from the JSON entry — FEMNIST iid declares `"iid"`,
# FEMNIST niid declares `"natural_id"` + `partition_by="writer_id"`,
# MedMNIST entries leave it absent (the builder falls back to
# Dirichlet alpha=0.5).
_HF_MEDMNIST_CNN_KEYWORDS = (
    "pneumoniamnist",
    "bloodmnist",
    "breastmnist",
    "pathmnist",
    "dermamnist",
    "octmnist",
    "retinamnist",
    "tissuemnist",
    "organamnist",
    "organcmnist",
    "organsmnist",
    "femnist_iid",
    "femnist_niid",
)


LOADER_REGISTRY: dict[str, LoaderBuilder] = {
    # Text datasets
    "medquad": _build_medquad,
    **dict.fromkeys(_HF_TEXT_KEYWORDS, _build_hf_text),
    "medal": _build_medal,
    # HF-backed CIFAR family — `FederatedDatasetLoader` + `DynamicCNN`,
    # entirely shaped from the JSON entry.
    **dict.fromkeys(_HF_IMAGE_CNN_KEYWORDS, _build_hf_image_cnn),
    # HF-backed MedMNIST family — `FederatedDatasetLoader` reading
    # `albertvillanova/medmnist-v2` + per-variant subset, paired with the
    # registered per-keyword `MedMNISTCNN` architecture.
    **dict.fromkeys(_HF_MEDMNIST_CNN_KEYWORDS, _build_hf_medmnist_cnn),
}


def build_dataset_loader_and_model(
    keyword: str | None,
    config: StrategyConfig,
    dataset_dir: str,
) -> tuple[Any, Any]:
    """Construct the configured dataset loader + network model pair.

    Returns ``(loader, network_model)``. The pair is bound: CNN datasets get
    a ``build_cnn_model(keyword)`` network; text datasets get an LLM via
    :func:`_build_llm_model`; cifar100 gets a :class:`DynamicCNN` shaped by
    the HF config.

    Assumes ``config.num_of_clients``, ``config.batch_size``, and
    ``config.training_subset_fraction`` have all been set by the caller —
    raises AssertionError otherwise. These fields are `int | None` /
    `float | None` on the config type for partial-construction reasons, but
    every loader constructor below requires them.

    If ``keyword`` is missing from :data:`LOADER_REGISTRY`, logs an error and
    exits with status 1 — preserving the prior `sys.exit(-1)` behavior. The
    ``None`` case lands here too.
    """
    if keyword is None or keyword not in LOADER_REGISTRY:
        logging.error(
            f"You are parsing a strategy for dataset: {keyword}. "
            f"Check that you assign a correct dataset_loader at the code above."
        )
        sys.exit(-1)
    assert config.num_of_clients is not None, "num_of_clients must be set"
    assert config.batch_size is not None, "batch_size must be set"
    assert config.training_subset_fraction is not None, "training_subset_fraction must be set"
    return LOADER_REGISTRY[keyword](keyword, config, dataset_dir)


__all__ = [
    "LOADER_REGISTRY",
    "LoaderBuilder",
    "build_dataset_loader_and_model",
    "get_hf_dataset_config",
    "resolve_image_transformer",
]
