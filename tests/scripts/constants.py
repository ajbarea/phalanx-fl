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
    # Quick tests (~60-70s)
    "gradient_scaling_only_test.json",
    "byzantine_perturbation_only_test.json",
    "femnist_bulyan_vs_byzantine.json",
    "femnist_mkrum_vs_byzantine.json",
    "femnist_krum_vs_modelpoisoning.json",
    "femnist_bulyan_vs_gradscaling.json",
    "femnist_bulyan_vs_modelpoisoning.json",
    "weight_poisoning_quick_test.json",
    "femnist_rfa_vs_modelpoisoning.json",
    "multi_client_weight_attack_test.json",
    # Baselines and scenarios (~80-90s)
    "femnist_pidstdscore_baseline.json",
    "femnist_trust_baseline.json",
    "femnist_pidstd_baseline.json",
    "femnist_pidscaled_baseline.json",
    "femnist_pid_baseline.json",
    "femnist_rfa_baseline.json",
    "round_boundary_test.json",
    "breastmnist_krum_vs_labelflip20.json",
    "femnist_bulyan_baseline.json",
    "femnist_mkrum_baseline.json",
    "femnist_krum_baseline.json",
    "femnist_trimmean_baseline.json",
    # Heavier scenarios (~105-117s)
    "femnist_krum_vs_labelflip20.json",
    "femnist_rfa_vs_labelflip20.json",
    "femnist_pidstdscore_vs_labelflip20.json",
    "femnist_mkrum_vs_labelflip20.json",
    "femnist_pidstd_vs_labelflip20.json",
    "femnist_krum_vs_labelflip50.json",
    "femnist_trust_vs_labelflip20.json",
    "femnist_krum_multi_overlapping.json",
]

# Derived config categories for selective testing
BASELINE_CONFIGS = [c for c in FAST_CONFIGS if "baseline" in c]
ATTACK_CONFIGS = [c for c in FAST_CONFIGS if "vs_" in c or "multi_" in c]

# Version for baseline format compatibility checking
BASELINE_FORMAT_VERSION = "1.0"
