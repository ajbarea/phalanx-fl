"""Shared helper functions for attack configuration extraction."""

from __future__ import annotations

from typing import Any


def extract_attack_type(attack_config: dict | list[dict]) -> str:
    """Extract attack type string from config, joining multiple with underscore."""
    if isinstance(attack_config, list):
        if attack_config:
            attack_types = [
                cfg.get("attack_type") or cfg.get("type", "unknown") for cfg in attack_config
            ]
            return "_".join(attack_types)
        else:
            return "unknown"
    else:
        return attack_config.get("attack_type") or attack_config.get("type", "unknown")


def extract_attack_param(
    attack_config: dict | list[dict], *attack_parameters: str, default: Any = "?"
) -> Any:
    """Extract first matching parameter from attack config."""
    config = (
        attack_config[0] if isinstance(attack_config, list) and attack_config else attack_config
    )

    if isinstance(config, dict):
        for attack_parameter in attack_parameters:
            if attack_parameter in config:
                return config[attack_parameter]

    return default
