"""
Network model registry and factory for the FL execution framework.

All dataset → model mappings live here as data (not code).
Use build_cnn_model(dataset_keyword) to instantiate the correct architecture.

DynamicCNN (for HuggingFace image datasets such as CIFAR-100) is constructed
directly in federated_simulation.py using values from the HF dataset config,
so it is not in this registry.
"""

from __future__ import annotations

from typing import Any

from intellifl.network_models.cnn_models import MedMNISTCNN
from intellifl.network_models.dynamic_cnn import DynamicCNN

# ---------------------------------------------------------------------------
# Dataset → MedMNISTCNN constructor kwargs
# ---------------------------------------------------------------------------
# input_height / input_width default to 28 (all standard MedMNIST datasets).
# High-resolution datasets override explicitly.
# dropout defaults to (0.3, 0.2); only FLAIR uses a different schedule.
# ---------------------------------------------------------------------------
_CNN_REGISTRY: dict[str, dict[str, Any]] = {
    # ── 2-conv · 28×28 · grayscale ──────────────────────────────────────────
    "breastmnist": {
        "num_classes": 2,
        "input_channels": 1,
        "conv_channels": [6, 16],
        "fc_hidden": [64, 32],
    },
    "femnist_iid": {
        # 62 classes (10 digits + 26 lowercase + 26 uppercase) matches the
        # canonical LEAF FEMNIST baseline + the `flwrlabs/femnist` HF
        # mirror. Pre-2026-05-23 this carried `num_classes=10` reflecting
        # an AJ-side digits-only preprocessing of the local-files tarball;
        # Phase 2B migration to `FederatedDatasetLoader` adopts the
        # community-standard 62-class baseline (no external paper used
        # the 10-class digit subset, so no published comparison regresses).
        "num_classes": 62,
        "input_channels": 1,
        "conv_channels": [6, 16],
        "fc_hidden": [64, 32],
    },
    "femnist_niid": {
        "num_classes": 62,
        "input_channels": 1,
        "conv_channels": [6, 16],
        "fc_hidden": [64, 32],
    },
    "pneumoniamnist": {
        "num_classes": 2,
        "input_channels": 1,
        "conv_channels": [6, 16],
        "fc_hidden": [64, 32],
    },
    "octmnist": {
        "num_classes": 4,
        "input_channels": 1,
        "conv_channels": [16, 32],
        "fc_hidden": [128, 64],
    },
    "organamnist": {
        "num_classes": 11,
        "input_channels": 1,
        "conv_channels": [16, 32],
        "fc_hidden": [128, 64],
    },
    "organcmnist": {
        "num_classes": 11,
        "input_channels": 1,
        "conv_channels": [16, 32],
        "fc_hidden": [128, 64],
    },
    "organsmnist": {
        "num_classes": 11,
        "input_channels": 1,
        "conv_channels": [16, 32],
        "fc_hidden": [128, 64],
    },
    "tissuemnist": {
        "num_classes": 8,
        "input_channels": 1,
        "conv_channels": [16, 32],
        "fc_hidden": [128, 64],
    },
    # ── 2-conv · 28×28 · RGB ────────────────────────────────────────────────
    "bloodmnist": {
        "num_classes": 8,
        "input_channels": 3,
        "conv_channels": [16, 32],
        "fc_hidden": [128, 64],
    },
    "pathmnist": {
        "num_classes": 9,
        "input_channels": 3,
        "conv_channels": [16, 32],
        "fc_hidden": [128, 64],
    },
    "dermamnist": {
        "num_classes": 7,
        "input_channels": 3,
        "conv_channels": [16, 32],
        "fc_hidden": [128, 64],
    },
    "retinamnist": {
        "num_classes": 5,
        "input_channels": 3,
        "conv_channels": [16, 32],
        "fc_hidden": [128, 64],
    },
}


def build_cnn_model(dataset_keyword: str) -> MedMNISTCNN:
    """
    Return a new MedMNISTCNN configured for the given dataset keyword.

    Raises KeyError for unknown keywords — fail fast rather than returning None.
    """
    if dataset_keyword not in _CNN_REGISTRY:
        known = sorted(_CNN_REGISTRY)
        raise KeyError(f"No CNN model registered for '{dataset_keyword}'. Known datasets: {known}")
    return MedMNISTCNN(**_CNN_REGISTRY[dataset_keyword])


__all__ = ["MedMNISTCNN", "DynamicCNN", "build_cnn_model"]
