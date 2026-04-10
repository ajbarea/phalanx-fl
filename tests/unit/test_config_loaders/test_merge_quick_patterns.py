"""Test that frontend quick patterns survive the config merge + validation pipeline.

Simulates the full data flow:
  Frontend initialConfig → buildMultiSimConfig() strips 4 keys → JSON file →
  ConfigLoader._merge_usecase_configs() → validate_strategy_config()

Run:  python -m pytest tests/unit/test_config_loaders/test_merge_quick_patterns.py -v
"""

from __future__ import annotations

import json

import pytest

from intellifl.config_loaders.config_loader import ConfigLoader

INITIAL_CONFIG = {
    "display_name": "",
    "num_of_rounds": 4,
    "num_of_clients": 7,
    "num_of_malicious_clients": 1,
    "attack_ratio": 1.0,
    "dataset_keyword": "femnist_iid",
    "model_type": "cnn",
    "use_llm": False,
    "attack_type": "gaussian_noise",
    "gaussian_noise_mean": 0,
    "gaussian_noise_std": 75,
    "num_std_dev": 2,
    "attack_schedule": [],
    "aggregation_strategy_keyword": "pid",
    "remove_clients": True,
    "begin_removing_from_round": 2,
    "trust_threshold": 0.15,
    "beta_value": 0.75,
    "Kp": 1,
    "Ki": 0.05,
    "Kd": 0.05,
    "num_krum_selections": 3,
    "num_of_clusters": 1,
    "training_device": "cpu",
    "cpus_per_client": 1,
    "gpus_per_client": 0,
    "num_of_client_epochs": 1,
    "batch_size": 20,
    "training_subset_fraction": 0.9,
    "min_fit_clients": 7,
    "min_evaluate_clients": 7,
    "min_available_clients": 7,
    "evaluate_metrics_aggregation_fn": "weighted_average",
    "show_plots": False,
    "save_plots": True,
    "save_csv": True,
    "save_attack_snapshots": False,
    "attack_snapshot_format": "pickle_and_visual",
    "snapshot_max_samples": 6,
    "preserve_dataset": True,
    "strict_mode": True,
}

_STRIPPED_FROM_SHARED = {
    "aggregation_strategy_keyword",
    "num_of_malicious_clients",
    "num_krum_selections",
    "remove_clients",
}


def build_shared_settings(shared_config: dict) -> dict:
    """Mirror of frontend buildMultiSimConfig() — strips per-strategy keys."""
    return {k: v for k, v in shared_config.items() if k not in _STRIPPED_FROM_SHARED}


def strip_frontend_keys(strategy: dict) -> dict:
    """Strip keys the frontend uses but the backend doesn't (id, name).
    Also strip None values (model_dump(exclude_none=True) equivalent)."""
    skip = {"id", "name"}
    return {k: v for k, v in strategy.items() if k not in skip and v is not None}


def build_config_dict(shared_config: dict, strategy_variations: list[dict]) -> dict:
    """Build the JSON config dict as the frontend + API would produce it."""
    shared = build_shared_settings(shared_config)
    strategies = [strip_frontend_keys(s) for s in strategy_variations]
    return {"shared_settings": shared, "simulation_strategies": strategies}


def merge_via_file(config_dict: dict, tmp_path) -> list[dict]:
    """Write config to temp file, run through ConfigLoader merge + validation."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_dict, indent=2))
    return ConfigLoader._merge_usecase_configs(str(config_file))


STRATEGY_DEFAULTS: dict[str, dict[str, object]] = {
    "trust": {"trust_threshold": 0.15, "beta_value": 0.75, "begin_removing_from_round": 2},
    "pid": {"Kp": 1.0, "Ki": 0.05, "Kd": 0.05, "num_std_dev": 2.0, "begin_removing_from_round": 2},
    "krum": {"num_krum_selections": 1},
    "multi-krum": {"num_krum_selections": 3},
    "bulyan": {"num_krum_selections": 3, "begin_removing_from_round": 2},
    "trimmed_mean": {"trim_ratio": 0.1, "begin_removing_from_round": 2},
    "rfa": {"begin_removing_from_round": 2},
    "fedavg": {},
}


def gen_sweep_malicious(base_strategy="pid", num_clients=7, num_rounds=4):
    max_mal = min(5, num_clients - 1)
    end_round = max(1, num_rounds)
    strategy_defaults = STRATEGY_DEFAULTS.get(base_strategy, {})

    def build_schedule(mal_count):
        if mal_count > 0:
            return [
                {
                    "start_round": 1,
                    "end_round": end_round,
                    "attack_type": "gaussian_noise",
                    "selection_strategy": "random",
                    "malicious_client_count": mal_count,
                    "target_noise_snr": 10,
                    "attack_ratio": 1.0,
                }
            ]
        return []

    return [
        {
            **strategy_defaults,
            "name": f"{base_strategy}_mal_{i}",
            "aggregation_strategy_keyword": base_strategy,
            "num_of_malicious_clients": i,
            "remove_clients": False,
            "attack_type": "gaussian_noise",
            "attack_schedule": build_schedule(i),
            "preserve_dataset": False,
        }
        for i in range(max_mal + 1)
    ]


def gen_compare_strategies(num_clients=7):
    max_k = num_clients
    return [
        {
            "name": "fedavg_baseline",
            "aggregation_strategy_keyword": "fedavg",
            "num_of_malicious_clients": 0,
            "remove_clients": False,
        },
        {
            "name": "krum_baseline",
            "aggregation_strategy_keyword": "krum",
            "num_of_malicious_clients": 0,
            "num_krum_selections": 1,
            "remove_clients": False,
        },
        {
            "name": "multi_krum_baseline",
            "aggregation_strategy_keyword": "multi-krum",
            "num_of_malicious_clients": 0,
            "num_krum_selections": min(4, max_k),
            "remove_clients": False,
        },
        {
            "name": "bulyan_baseline",
            "aggregation_strategy_keyword": "bulyan",
            "num_of_malicious_clients": 0,
            "num_krum_selections": min(4, max_k),
            "remove_clients": False,
        },
        {
            "name": "trimmed_mean_baseline",
            "aggregation_strategy_keyword": "trimmed_mean",
            "num_of_malicious_clients": 0,
            "trim_ratio": 0.1,
            "remove_clients": False,
        },
        {
            "name": "rfa_baseline",
            "aggregation_strategy_keyword": "rfa",
            "num_of_malicious_clients": 0,
            "remove_clients": False,
        },
        {
            "name": "trust_baseline",
            "aggregation_strategy_keyword": "trust",
            "num_of_malicious_clients": 0,
            "trust_threshold": 0.15,
            "beta_value": 0.75,
            "remove_clients": False,
        },
        {
            "name": "pid_baseline",
            "aggregation_strategy_keyword": "pid",
            "num_of_malicious_clients": 0,
            "Kp": 1.0,
            "Ki": 0.05,
            "Kd": 0.05,
            "num_std_dev": 2.0,
            "remove_clients": False,
        },
    ]


def gen_defense_comparison(num_clients=7):
    malicious = 1
    max_k = num_clients - malicious
    return [
        {
            "name": "fedavg_1mal",
            "aggregation_strategy_keyword": "fedavg",
            "num_of_malicious_clients": malicious,
            "remove_clients": False,
        },
        {
            "name": "krum_1mal",
            "aggregation_strategy_keyword": "krum",
            "num_of_malicious_clients": malicious,
            "num_krum_selections": 1,
            "remove_clients": True,
            "strict_mode": False,
            "begin_removing_from_round": 2,
        },
        {
            "name": "multi_krum_1mal",
            "aggregation_strategy_keyword": "multi-krum",
            "num_of_malicious_clients": malicious,
            "num_krum_selections": min(3, max_k),
            "remove_clients": True,
            "strict_mode": False,
            "begin_removing_from_round": 2,
        },
        {
            "name": "bulyan_1mal",
            "aggregation_strategy_keyword": "bulyan",
            "num_of_malicious_clients": malicious,
            "num_krum_selections": min(3, max_k),
            "remove_clients": True,
            "strict_mode": False,
            "begin_removing_from_round": 2,
        },
        {
            "name": "trimmed_mean_1mal",
            "aggregation_strategy_keyword": "trimmed_mean",
            "num_of_malicious_clients": malicious,
            "trim_ratio": 0.1,
            "remove_clients": True,
            "strict_mode": False,
            "begin_removing_from_round": 2,
        },
        {
            "name": "rfa_1mal",
            "aggregation_strategy_keyword": "rfa",
            "num_of_malicious_clients": malicious,
            "remove_clients": True,
            "strict_mode": False,
            "begin_removing_from_round": 2,
        },
        {
            "name": "trust_1mal",
            "aggregation_strategy_keyword": "trust",
            "num_of_malicious_clients": malicious,
            "trust_threshold": 0.15,
            "beta_value": 0.75,
            "remove_clients": True,
            "strict_mode": False,
            "begin_removing_from_round": 2,
        },
        {
            "name": "pid_1mal",
            "aggregation_strategy_keyword": "pid",
            "num_of_malicious_clients": malicious,
            "Kp": 1.0,
            "Ki": 0.05,
            "Kd": 0.05,
            "num_std_dev": 2.0,
            "remove_clients": True,
            "strict_mode": False,
            "begin_removing_from_round": 2,
        },
    ]


def gen_sweep_krum_selections(num_clients=7):
    max_k = min(5, num_clients)
    return [
        {
            "name": f"multi_krum_k{k}",
            "aggregation_strategy_keyword": "multi-krum",
            "num_of_malicious_clients": 0,
            "num_krum_selections": k,
            "remove_clients": False,
        }
        for k in range(1, max_k + 1)
    ]


def gen_byzantine_robustness(num_clients=7):
    constraints = {
        "krum": {"max_mal": (num_clients - 2) // 2},
        "multi-krum": {"max_mal": (num_clients - 2) // 2},
        "bulyan": {"max_mal": (num_clients - 3) // 4},
        "trimmed_mean": {"max_mal": num_clients // 2 - 1},
    }
    variations = []
    for strategy, c in constraints.items():
        max_mal = max(0, c["max_mal"])
        for mal in range(max_mal + 1):
            honest = num_clients - mal
            valid_k = max(1, min(3, honest))
            v = {
                "name": f"{strategy.replace('-', '_')}_mal{mal}",
                "aggregation_strategy_keyword": strategy,
                "num_of_malicious_clients": mal,
                "remove_clients": mal > 0,
            }
            if strategy != "trimmed_mean":
                v["num_krum_selections"] = valid_k
            else:
                v["trim_ratio"] = 0.1
            if mal > 0:
                v["strict_mode"] = False
                v["begin_removing_from_round"] = 2
            variations.append(v)
    return variations


PATTERNS = {
    "sweepMalicious_pid": lambda: gen_sweep_malicious("pid", 7, 4),
    "compareStrategies": lambda: gen_compare_strategies(7),
    "defenseComparison": lambda: gen_defense_comparison(7),
    "sweepKrumSelections": lambda: gen_sweep_krum_selections(7),
    "byzantineRobustness": lambda: gen_byzantine_robustness(7),
}


class TestQuickPatternsMergeAndValidate:
    """Each quick pattern should merge with default shared config and pass validation."""

    @pytest.mark.parametrize("pattern_name", PATTERNS.keys())
    def test_pattern_passes_full_pipeline(self, pattern_name, tmp_path):
        strategies = PATTERNS[pattern_name]()
        config = build_config_dict(INITIAL_CONFIG, strategies)
        merged = merge_via_file(config, tmp_path)

        assert len(merged) == len(strategies), (
            f"Expected {len(strategies)} strategies, got {len(merged)}"
        )

    @pytest.mark.parametrize("pattern_name", PATTERNS.keys())
    def test_strategy_values_survive_merge(self, pattern_name, tmp_path):
        """Strategy-specific values must not be clobbered by shared_settings."""
        strategies = PATTERNS[pattern_name]()
        config = build_config_dict(INITIAL_CONFIG, strategies)
        merged = merge_via_file(config, tmp_path)

        for i, (original, result) in enumerate(zip(strategies, merged, strict=True)):
            cleaned = strip_frontend_keys(original)
            for key, expected in cleaned.items():
                actual = result.get(key)
                if key == "attack_schedule" and isinstance(expected, list):
                    assert isinstance(actual, list), f"Strategy[{i}] attack_schedule missing"
                    for j, (exp_entry, act_entry) in enumerate(zip(expected, actual, strict=True)):
                        for ek, ev in exp_entry.items():
                            assert act_entry.get(ek) == ev, (
                                f"Strategy[{i}] attack_schedule[{j}].{ek}: "
                                f"{act_entry.get(ek)!r} != {ev!r}"
                            )
                    continue
                assert actual == expected, (
                    f"Strategy[{i}] ({original.get('name', '?')}): "
                    f"'{key}' = {actual!r}, expected {expected!r}. "
                    f"Shared had: {config['shared_settings'].get(key, '<absent>')}"
                )


class TestMergeOrderConflicts:
    """Verify that strategy values win over shared when both define the same key."""

    def test_strict_mode_false_overrides_shared_true(self, tmp_path):
        """strict_mode=false in strategy must survive shared's strict_mode=true."""
        strategies = gen_defense_comparison(7)
        config = build_config_dict(INITIAL_CONFIG, strategies)

        assert config["shared_settings"]["strict_mode"] is True

        merged = merge_via_file(config, tmp_path)

        for i, (orig, result) in enumerate(zip(strategies, merged, strict=True)):
            if orig.get("strict_mode") is False:
                assert result["strict_mode"] is False, (
                    f"Strategy[{i}] ({orig.get('name')}): strict_mode was clobbered to True"
                )

    def test_attack_schedule_not_clobbered_by_shared_empty(self, tmp_path):
        """Strategy attack_schedule must not be replaced by shared's empty []."""
        strategies = gen_sweep_malicious("pid", 7, 4)
        config = build_config_dict(INITIAL_CONFIG, strategies)

        assert config["shared_settings"]["attack_schedule"] == []

        merged = merge_via_file(config, tmp_path)

        for i, (orig, result) in enumerate(zip(strategies, merged, strict=True)):
            cleaned = strip_frontend_keys(orig)
            if cleaned.get("attack_schedule"):
                assert len(result["attack_schedule"]) > 0, (
                    f"Strategy[{i}] ({orig.get('name')}): attack_schedule clobbered to []"
                )

    def test_preserve_dataset_false_overrides_shared_true(self, tmp_path):
        """preserve_dataset=false in strategy must win over shared's true."""
        strategies = gen_sweep_malicious("pid", 7, 4)
        config = build_config_dict(INITIAL_CONFIG, strategies)

        assert config["shared_settings"]["preserve_dataset"] is True

        merged = merge_via_file(config, tmp_path)

        for i, (orig, result) in enumerate(zip(strategies, merged, strict=True)):
            if "preserve_dataset" in strip_frontend_keys(orig):
                assert result["preserve_dataset"] is False, (
                    f"Strategy[{i}] ({orig.get('name')}): preserve_dataset clobbered to True"
                )


class TestSweepMaliciousBaseStrategies:
    """Expose missing strategy-specific params when sweepMalicious uses non-default bases."""

    def test_sweep_with_fedavg_base(self, tmp_path):
        """fedavg needs no extra params — should pass."""
        strategies = gen_sweep_malicious("fedavg", 7, 4)
        config = build_config_dict(INITIAL_CONFIG, strategies)
        merged = merge_via_file(config, tmp_path)
        assert len(merged) == len(strategies)

    def test_sweep_with_pid_base(self, tmp_path):
        """PID params (Kp, Ki, Kd, num_std_dev) are in shared (not stripped) — should pass."""
        strategies = gen_sweep_malicious("pid", 7, 4)
        config = build_config_dict(INITIAL_CONFIG, strategies)
        merged = merge_via_file(config, tmp_path)
        assert len(merged) == len(strategies)

    def test_sweep_with_rfa_base(self, tmp_path):
        """RFA needs no extra params — should pass."""
        strategies = gen_sweep_malicious("rfa", 7, 4)
        config = build_config_dict(INITIAL_CONFIG, strategies)
        merged = merge_via_file(config, tmp_path)
        assert len(merged) == len(strategies)

    def test_sweep_with_trust_base(self, tmp_path):
        """Trust params are in shared (not stripped) — should pass."""
        strategies = gen_sweep_malicious("trust", 7, 4)
        config = build_config_dict(INITIAL_CONFIG, strategies)
        merged = merge_via_file(config, tmp_path)
        assert len(merged) == len(strategies)

    def test_sweep_with_krum_base(self, tmp_path):
        """FIXED: strategy defaults now include num_krum_selections for krum.
        Uses 13 clients so the full sweep (0-5) satisfies n > 2f + 2."""
        many_clients = {
            **INITIAL_CONFIG,
            "num_of_clients": 13,
            "min_fit_clients": 13,
            "min_evaluate_clients": 13,
            "min_available_clients": 13,
        }
        strategies = gen_sweep_malicious("krum", 13, 4)
        config = build_config_dict(many_clients, strategies)
        merged = merge_via_file(config, tmp_path)
        assert len(merged) == len(strategies)
        for m in merged:
            assert m["aggregation_strategy_keyword"] == "krum"
            assert "num_krum_selections" in m

    def test_sweep_with_krum_base_rejects_byzantine_violation(self, tmp_path):
        """Krum correctly rejects configs that violate n > 2f + 2.
        With 7 clients the sweep hits f=3 where 7 > 8 fails."""
        strategies = gen_sweep_malicious("krum", 7, 4)
        config = build_config_dict(INITIAL_CONFIG, strategies)
        with pytest.raises(Exception, match="Krum aggregation requires n > 2f"):
            merge_via_file(config, tmp_path)

    def test_sweep_with_multi_krum_base(self, tmp_path):
        """FIXED: strategy defaults now include num_krum_selections for multi-krum.
        Uses 13 clients so the full sweep satisfies n > 2f + 2."""
        many_clients = {
            **INITIAL_CONFIG,
            "num_of_clients": 13,
            "min_fit_clients": 13,
            "min_evaluate_clients": 13,
            "min_available_clients": 13,
        }
        strategies = gen_sweep_malicious("multi-krum", 13, 4)
        config = build_config_dict(many_clients, strategies)
        merged = merge_via_file(config, tmp_path)
        assert len(merged) == len(strategies)
        for m in merged:
            assert m["aggregation_strategy_keyword"] == "multi-krum"
            assert "num_krum_selections" in m

    def test_sweep_with_multi_krum_base_rejects_byzantine_violation(self, tmp_path):
        """Multi-krum correctly rejects configs that violate n > 2f + 2."""
        strategies = gen_sweep_malicious("multi-krum", 7, 4)
        config = build_config_dict(INITIAL_CONFIG, strategies)
        with pytest.raises(Exception, match="Krum aggregation requires n > 2f"):
            merge_via_file(config, tmp_path)

    def test_sweep_with_bulyan_base(self, tmp_path):
        """FIXED: strategy defaults now include num_krum_selections for bulyan."""
        strategies = gen_sweep_malicious("bulyan", 7, 4)
        config = build_config_dict(INITIAL_CONFIG, strategies)
        merged = merge_via_file(config, tmp_path)
        assert len(merged) == len(strategies)
        for m in merged:
            assert m["aggregation_strategy_keyword"] == "bulyan"
            assert "num_krum_selections" in m

    def test_sweep_with_trimmed_mean_base(self, tmp_path):
        """FIXED: strategy defaults now include trim_ratio for trimmed_mean."""
        strategies = gen_sweep_malicious("trimmed_mean", 7, 4)
        config = build_config_dict(INITIAL_CONFIG, strategies)
        merged = merge_via_file(config, tmp_path)
        assert len(merged) == len(strategies)
        for m in merged:
            assert m["aggregation_strategy_keyword"] == "trimmed_mean"
            assert "trim_ratio" in m


class TestConfigLoaderErrorHandling:
    """Verify ConfigLoader raises exceptions instead of calling sys.exit."""

    def test_merge_invalid_json_raises(self, tmp_path):
        config_file = tmp_path / "bad.json"
        config_file.write_text("{ not valid json !!!")

        with pytest.raises(json.JSONDecodeError):
            ConfigLoader._merge_usecase_configs(str(config_file))

    def test_merge_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            ConfigLoader._merge_usecase_configs("totally_nonexistent_file.json")

    def test_set_config_invalid_json_raises(self, tmp_path):
        config_file = tmp_path / "bad_dataset.json"
        config_file.write_text("not json at all")

        with pytest.raises(json.JSONDecodeError):
            ConfigLoader._set_config(str(config_file))

    def test_set_config_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            ConfigLoader._set_config("totally_nonexistent_dataset.json")


class TestMergeDirection:
    """Test the raw merge behavior: strategy values must override shared values."""

    def test_strategy_overrides_shared_on_conflict(self, tmp_path):
        """When both shared and strategy define a key, strategy wins."""
        config = {
            "shared_settings": {
                "num_of_rounds": 10,
                "num_of_clients": 5,
                "strict_mode": True,
                "preserve_dataset": True,
                "begin_removing_from_round": 5,
                "dataset_keyword": "femnist_iid",
                "model_type": "cnn",
                "use_llm": False,
                "remove_clients": False,
                "show_plots": False,
                "save_plots": True,
                "save_csv": True,
                "training_subset_fraction": 0.9,
                "training_device": "cpu",
                "cpus_per_client": 1,
                "gpus_per_client": 0.0,
                "min_fit_clients": 5,
                "min_evaluate_clients": 5,
                "min_available_clients": 5,
                "evaluate_metrics_aggregation_fn": "weighted_average",
                "num_of_client_epochs": 1,
                "batch_size": 20,
                "attack_schedule": [],
            },
            "simulation_strategies": [
                {
                    "aggregation_strategy_keyword": "rfa",
                    "strict_mode": False,
                    "preserve_dataset": False,
                    "begin_removing_from_round": 2,
                    "attack_schedule": [
                        {
                            "start_round": 1,
                            "end_round": 10,
                            "attack_type": "gaussian_noise",
                            "selection_strategy": "random",
                            "malicious_client_count": 1,
                            "target_noise_snr": 10,
                            "attack_ratio": 1.0,
                        }
                    ],
                }
            ],
        }

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config, indent=2))
        merged = ConfigLoader._merge_usecase_configs(str(config_file))

        s = merged[0]
        assert s["strict_mode"] is False, (
            "Strategy's strict_mode=False should override shared's True"
        )
        assert s["preserve_dataset"] is False, "Strategy's preserve_dataset=False should override"
        assert s["begin_removing_from_round"] == 2, "Strategy's value should override shared's 5"
        assert len(s["attack_schedule"]) == 1, "Strategy's schedule should override shared's []"

    def test_shared_fills_in_missing_strategy_keys(self, tmp_path):
        """Keys only in shared should be added to the strategy."""
        config = {
            "shared_settings": {
                "num_of_rounds": 10,
                "num_of_clients": 5,
                "dataset_keyword": "femnist_iid",
                "model_type": "cnn",
                "use_llm": False,
                "remove_clients": False,
                "show_plots": False,
                "save_plots": True,
                "save_csv": True,
                "preserve_dataset": False,
                "training_subset_fraction": 0.9,
                "training_device": "cpu",
                "cpus_per_client": 1,
                "gpus_per_client": 0.0,
                "min_fit_clients": 5,
                "min_evaluate_clients": 5,
                "min_available_clients": 5,
                "evaluate_metrics_aggregation_fn": "weighted_average",
                "num_of_client_epochs": 1,
                "batch_size": 20,
            },
            "simulation_strategies": [
                {
                    "aggregation_strategy_keyword": "rfa",
                    "attack_schedule": [],
                }
            ],
        }

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config, indent=2))
        merged = ConfigLoader._merge_usecase_configs(str(config_file))

        s = merged[0]
        assert s["num_of_rounds"] == 10, "Shared key should be present in merged strategy"
        assert s["num_of_clients"] == 5
        assert s["dataset_keyword"] == "femnist_iid"
        assert s["aggregation_strategy_keyword"] == "rfa", "Strategy key should be preserved"
