"""Centralized warning suppression configuration."""

from __future__ import annotations

import logging
import os
import warnings
from typing import Any

logger = logging.getLogger(__name__)

WARNING_FILTERS: dict[str, dict[str, Any]] = {
    "ray_accel_env_var": {
        "env_vars": {"RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO": "0"},
        "description": "Suppress Ray CUDA_VISIBLE_DEVICES FutureWarning",
    },
    "numpy_runtime": {
        "filter_kwargs": {
            "action": "ignore",
            "category": RuntimeWarning,
            "module": r"numpy\..*",
        },
        "description": "Suppress NumPy overflow/divide warnings in FL aggregation",
    },
    "threadpoolctl": {
        "filter_kwargs": {
            "action": "ignore",
            "category": RuntimeWarning,
            "module": r"threadpoolctl.*",
        },
        "env_vars": {"PYTHONWARNINGS": "ignore::RuntimeWarning:threadpoolctl"},
        "description": "Suppress threadpoolctl DLL enumeration warnings on Windows",
    },
    "torch_pytree": {
        "filter_kwargs": {
            "action": "ignore",
            "category": UserWarning,
            "message": r".*pytree.*",
        },
        "description": "Suppress PyTorch pytree registration warnings",
    },
    "torch_weights_only": {
        "filter_kwargs": {
            "action": "ignore",
            "category": FutureWarning,
            "message": r".*weights_only.*",
        },
        "description": "Suppress torch.load weights_only FutureWarning",
    },
    "transformers_tf_warning": {
        "filter_kwargs": {
            "action": "ignore",
            "category": UserWarning,
            "message": r".*TensorFlow.*",
        },
        "description": "Suppress TensorFlow not installed warnings",
    },
    "flwr_deprecation": {
        "filter_kwargs": {
            "action": "ignore",
            "category": DeprecationWarning,
            "module": r"flwr\..*",
        },
        "description": "Suppress Flower deprecation warnings",
    },
    "pending_deprecation": {
        "filter_kwargs": {
            "action": "ignore",
            "category": PendingDeprecationWarning,
        },
        "description": "Suppress PendingDeprecationWarning globally",
    },
}


def apply_env_vars(filter_keys: list[str] | None = None) -> None:
    """Apply environment variables for warning suppression."""
    keys = filter_keys or list(WARNING_FILTERS.keys())

    for key in keys:
        if key not in WARNING_FILTERS:
            logger.warning(f"Unknown warning filter key: {key}")
            continue

        config = WARNING_FILTERS[key]
        env_vars = config.get("env_vars", {})

        for var_name, var_value in env_vars.items():
            os.environ.setdefault(var_name, var_value)


def apply_filter(key: str) -> None:
    """Apply a single warning filter by key."""
    if key not in WARNING_FILTERS:
        logger.warning(f"Unknown warning filter key: {key}")
        return

    config = WARNING_FILTERS[key]
    filter_kwargs = config.get("filter_kwargs")

    if filter_kwargs:
        warnings.filterwarnings(**filter_kwargs)


def configure_warnings(
    exclude: list[str] | None = None,
    include_only: list[str] | None = None,
    verbose: bool = False,
) -> None:
    """Apply warning suppressions from the central registry."""
    exclude = exclude or []

    if include_only is not None:
        keys_to_apply = [k for k in include_only if k in WARNING_FILTERS]
    else:
        keys_to_apply = [k for k in WARNING_FILTERS if k not in exclude]

    apply_env_vars(keys_to_apply)

    for key in keys_to_apply:
        config = WARNING_FILTERS[key]
        filter_kwargs = config.get("filter_kwargs")

        if filter_kwargs:
            if verbose:
                logger.info(f"Applying warning filter: {key}")
            warnings.filterwarnings(**filter_kwargs)

    if verbose:
        logger.info(f"Applied {len(keys_to_apply)} warning filters")


def list_filters() -> None:
    """Print all available warning filters with descriptions."""
    print("\n=== Available Warning Filters ===\n")
    for key, config in WARNING_FILTERS.items():
        print(f"[{key}]")
        print(f"  Description: {config['description']}")
        if "filter_kwargs" in config:
            print(f"  Filter: {config['filter_kwargs']}")
        if "env_vars" in config:
            print(f"  Env vars: {config['env_vars']}")
        print()
