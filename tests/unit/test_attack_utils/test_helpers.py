"""Tests for `intellifl.attack_utils._helpers`."""

from __future__ import annotations

from intellifl.attack_utils._helpers import (
    extract_attack_param,
    extract_attack_type,
    extract_individual_attack_types,
)


class TestExtractAttackType:
    def test_single_dict_attack_type_key(self) -> None:
        assert extract_attack_type({"attack_type": "label_flipping"}) == "label_flipping"

    def test_single_dict_type_key_fallback(self) -> None:
        assert extract_attack_type({"type": "gaussian_noise"}) == "gaussian_noise"

    def test_single_dict_missing_keys(self) -> None:
        assert extract_attack_type({}) == "unknown"

    def test_composite_joins_with_underscore(self) -> None:
        config = [{"attack_type": "label_flipping"}, {"attack_type": "gaussian_noise"}]
        assert extract_attack_type(config) == "label_flipping_gaussian_noise"

    def test_empty_list_returns_unknown(self) -> None:
        assert extract_attack_type([]) == "unknown"


class TestExtractIndividualAttackTypes:
    def test_single_dict_wraps_to_one_pair(self) -> None:
        cfg = {"attack_type": "label_flipping", "intensity": 0.5}
        result = extract_individual_attack_types(cfg)
        assert result == [("label_flipping", cfg)]

    def test_single_dict_type_fallback_key(self) -> None:
        cfg = {"type": "backdoor_trigger"}
        assert extract_individual_attack_types(cfg) == [("backdoor_trigger", cfg)]

    def test_composite_splits_per_attack_preserving_sub_config(self) -> None:
        sub1 = {"attack_type": "label_flipping", "flip_ratio": 0.3}
        sub2 = {"attack_type": "gaussian_noise", "std_dev": 0.1}
        result = extract_individual_attack_types([sub1, sub2])
        assert result == [("label_flipping", sub1), ("gaussian_noise", sub2)]

    def test_composite_unknown_when_keys_missing(self) -> None:
        result = extract_individual_attack_types([{}, {"attack_type": "gaussian_noise"}])
        assert result[0][0] == "unknown"
        assert result[1][0] == "gaussian_noise"

    def test_empty_list_returns_empty(self) -> None:
        assert extract_individual_attack_types([]) == []


class TestExtractAttackParam:
    def test_returns_first_matching_param(self) -> None:
        cfg = {"flip_ratio": 0.3, "intensity": 0.5}
        assert extract_attack_param(cfg, "intensity", "flip_ratio") == 0.5

    def test_uses_default_when_missing(self) -> None:
        assert extract_attack_param({}, "intensity", default="?") == "?"

    def test_composite_reads_first_entry(self) -> None:
        cfg = [{"flip_ratio": 0.5}, {"std_dev": 0.1}]
        assert extract_attack_param(cfg, "flip_ratio") == 0.5
