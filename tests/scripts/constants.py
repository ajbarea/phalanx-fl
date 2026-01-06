"""Shared test constants across CI scripts.

This module centralizes configuration lists used by:
- ci_smoke_test.py
- mock_simulation_runner.py
- record_baselines.py

When adding new fast configs, update only this file.
"""

from __future__ import annotations

# Configs under 2 minutes runtime for smoke tests and baseline recording
# Sorted by runtime (fastest first) based on timing database
FAST_CONFIGS = [
    # Quick tests (~45-50s)
    "weight_poisoning_quick_test.json",
    "byzantine_perturbation_only_test.json",
    "gradient_scaling_only_test.json",
    "femnist_bulyan_vs_gradscaling.json",
    "femnist_bulyan_vs_byzantine.json",
    "femnist_krum_vs_modelpoisoning.json",
    "femnist_rfa_vs_modelpoisoning.json",
    "femnist_mkrum_vs_byzantine.json",
    "femnist_bulyan_vs_modelpoisoning.json",
    # Baselines (~55-70s)
    "femnist_mkrum_baseline.json",
    "femnist_krum_baseline.json",
    "femnist_pidscaled_baseline.json",
    "multi_client_weight_attack_test.json",
    "femnist_rfa_baseline.json",
    "femnist_pid_baseline.json",
    "femnist_pidstd_baseline.json",
    "femnist_pidstdscore_baseline.json",
    "femnist_trust_baseline.json",
    "femnist_bulyan_baseline.json",
    "round_boundary_test.json",
    "femnist_trimmean_baseline.json",
    # Attack scenarios (~75-120s)
    "breastmnist_krum_vs_labelflip20.json",
    "femnist_krum_vs_labelflip20.json",
    "femnist_krum_multi_overlapping.json",
    "femnist_pidstd_vs_labelflip20.json",
    "femnist_rfa_vs_labelflip20.json",
    "femnist_pidstdscore_vs_labelflip20.json",
    "femnist_trust_vs_labelflip20.json",
    "femnist_mkrum_vs_labelflip20.json",
    "femnist_bulyan_vs_labelflip50.json",
    "femnist_mkrum_vs_labelflip50.json",
    "femnist_mkrum_multi_concurrent.json",
    "femnist_mkrum_multi_showcase.json",
    "femnist_mkrum_vs_gaussnoise25.json",
    "femnist_krum_vs_labelflip50.json",
]

# Derived config categories for selective testing
BASELINE_CONFIGS = [c for c in FAST_CONFIGS if "baseline" in c]
ATTACK_CONFIGS = [c for c in FAST_CONFIGS if "vs_" in c or "multi_" in c]

# Version for baseline format compatibility checking
BASELINE_FORMAT_VERSION = "1.0"
