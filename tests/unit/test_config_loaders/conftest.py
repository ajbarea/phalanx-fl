"""Shared fixtures for config validation tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def base_valid_config():
    """Base configuration with all common required fields."""
    return {
        "remove_clients": True,
        "dataset_keyword": "femnist_iid",
        "dataset_source": "local",
        "model_type": "cnn",
        "use_llm": False,
        "num_of_rounds": 5,
        "num_of_clients": 10,
        "num_of_malicious_clients": 2,
        "attack_type": "label_flipping",
        "show_plots": False,
        "save_plots": True,
        "save_csv": True,
        "preserve_dataset": False,
        "training_subset_fraction": 0.8,
        "training_device": "cpu",
        "cpus_per_client": 1,
        "gpus_per_client": 0.0,
        "min_fit_clients": 8,
        "min_evaluate_clients": 8,
        "min_available_clients": 10,
        "evaluate_metrics_aggregation_fn": "weighted_average",
        "num_of_client_epochs": 3,
        "batch_size": 32,
    }
