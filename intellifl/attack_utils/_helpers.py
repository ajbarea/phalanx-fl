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


def extract_individual_attack_types(
    attack_config: dict | list[dict],
) -> list[tuple[str, dict]]:
    """Return one ``(attack_type, sub_config)`` pair per attack in a config.

    Singles wrap into a one-element list; composites unfold so callers can
    iterate per-attack without re-implementing the dict-vs-list branch.

    Used by ``save_visual_snapshot`` to emit each composite member's
    specialized visualization (``label_flipping_visual.png``,
    ``backdoor_trigger_visual.png``, …) alongside the composite synopsis
    plate, instead of dropping per-type visuals because the joined
    ``attack_type`` string ("label_flipping_gaussian_noise") didn't match
    any of the single-attack equality branches.
    """
    if isinstance(attack_config, list):
        return [
            (cfg.get("attack_type") or cfg.get("type", "unknown"), cfg) for cfg in attack_config
        ]
    return [
        (
            attack_config.get("attack_type") or attack_config.get("type", "unknown"),
            attack_config,
        )
    ]


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
