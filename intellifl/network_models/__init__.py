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
        "num_classes": 10,
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
    # ── 2-conv · 224×224 · RGB ──────────────────────────────────────────────
    "its": {
        "num_classes": 10,
        "input_channels": 3,
        "conv_channels": [6, 16],
        "fc_hidden": [64, 32],
        "input_height": 224,
        "input_width": 224,
    },
    # ── 3-conv · 224×224 · grayscale ────────────────────────────────────────
    "lung_photos": {
        "num_classes": 4,
        "input_channels": 1,
        "conv_channels": [16, 32, 64],
        "fc_hidden": [128, 64],
        "input_height": 224,
        "input_width": 224,
    },
    # ── 3-conv · 256×256 · RGB · custom dropout ─────────────────────────────
    "flair": {
        "num_classes": 2,
        "input_channels": 3,
        "conv_channels": [32, 64, 128],
        "fc_hidden": [512, 128],
        "input_height": 256,
        "input_width": 256,
        "dropout": (0.4, 0.3),
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
