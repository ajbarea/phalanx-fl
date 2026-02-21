"""Unit tests for weight-level poisoning attacks."""

from __future__ import annotations

import pytest

from intellifl.attack_utils.weight_poisoning import (
    WEIGHT_ATTACK_TYPES,
    apply_alternating_min_poisoning,
    apply_boosted_scaling,
    apply_byzantine_perturbation,
    apply_gradient_scaling,
    apply_inner_product_manipulation,
    apply_model_poisoning,
    apply_weight_poisoning,
    is_weight_attack,
)
from tests.common import np


class TestWeightAttackTypes:
    """Tests weight attack type constants and helpers."""

    def test_weight_attack_types_contains_expected_types(self):
        """Verifies WEIGHT_ATTACK_TYPES includes all expected attack types."""
        expected = {
            "model_poisoning",
            "gradient_scaling",
            "byzantine_perturbation",
            "boosted_scaling",
            "inner_product_manipulation",
            "alternating_min_poisoning",
        }
        assert expected == WEIGHT_ATTACK_TYPES

    def test_is_weight_attack_returns_true_for_weight_attacks(self):
        """Verifies is_weight_attack returns True for weight attack types."""
        for attack_type in WEIGHT_ATTACK_TYPES:
            assert is_weight_attack(attack_type) is True

    def test_is_weight_attack_returns_false_for_data_attacks(self):
        """Verifies is_weight_attack returns False for data poisoning types."""
        data_attacks = ["label_flipping", "gaussian_noise"]
        for attack_type in data_attacks:
            assert is_weight_attack(attack_type) is False

    def test_is_weight_attack_returns_false_for_unknown(self):
        """Verifies is_weight_attack returns False for unknown types."""
        assert is_weight_attack("unknown_attack") is False
        assert is_weight_attack("") is False


class TestModelPoisoning:
    """Tests model poisoning attack."""

    def test_model_poisoning_modifies_parameters(self):
        """Verifies model poisoning changes parameter values."""
        np.random.seed(42)
        params = [np.random.randn(10, 10), np.random.randn(5)]
        poisoned = apply_model_poisoning(params, poison_ratio=0.1, magnitude=5.0)

        assert len(poisoned) == len(params)
        for orig, pois in zip(params, poisoned, strict=False):
            assert orig.shape == pois.shape

        assert not np.allclose(params[0], poisoned[0])

    def test_model_poisoning_with_seed_is_deterministic(self):
        """Verifies model poisoning with seed produces consistent results."""
        params = [np.random.randn(100, 100)]

        poisoned1 = apply_model_poisoning(params, seed=42)
        poisoned2 = apply_model_poisoning(params, seed=42)

        assert np.allclose(poisoned1[0], poisoned2[0])

    def test_model_poisoning_different_seeds_differ(self):
        """Verifies different seeds produce different results."""
        params = [np.random.randn(100, 100)]

        poisoned1 = apply_model_poisoning(params, seed=42)
        poisoned2 = apply_model_poisoning(params, seed=123)

        assert not np.allclose(poisoned1[0], poisoned2[0])

    def test_model_poisoning_respects_poison_ratio(self):
        """Verifies poison_ratio controls fraction of modified weights."""
        np.random.seed(0)
        params = [np.random.randn(1000)]
        poison_ratio = 0.1

        poisoned = apply_model_poisoning(params, poison_ratio=poison_ratio, magnitude=5.0, seed=42)

        changed = np.sum(np.abs(poisoned[0] - params[0]) > 0.01)
        expected_changed = int(1000 * poison_ratio)

        assert abs(changed - expected_changed) <= 5

    def test_model_poisoning_magnitude_affects_values(self):
        """Verifies magnitude parameter affects poisoned value scale."""
        np.random.seed(0)
        params = [np.random.randn(100)]

        poisoned_small = apply_model_poisoning(params, magnitude=2.0, seed=42)
        poisoned_large = apply_model_poisoning(params, magnitude=10.0, seed=42)

        diff_small = np.max(np.abs(poisoned_small[0] - params[0]))
        diff_large = np.max(np.abs(poisoned_large[0] - params[0]))

        assert diff_large > diff_small


class TestGradientScaling:
    """Tests gradient scaling attack."""

    def test_gradient_scaling_scales_all_parameters(self):
        """Verifies gradient scaling multiplies all weights."""
        params = [np.ones((10, 10)), np.ones((5,))]
        scale_factor = 3.0

        scaled = apply_gradient_scaling(params, scale_factor=scale_factor)

        for orig, scal in zip(params, scaled, strict=False):
            assert np.allclose(scal, orig * scale_factor)

    def test_gradient_scaling_preserves_shapes(self):
        """Verifies gradient scaling preserves parameter shapes."""
        params = [np.random.randn(10, 20), np.random.randn(5, 5, 5)]

        scaled = apply_gradient_scaling(params, scale_factor=2.0)

        for orig, scal in zip(params, scaled, strict=False):
            assert orig.shape == scal.shape

    def test_gradient_scaling_with_zero_factor(self):
        """Verifies scale_factor=0 produces zero parameters."""
        params = [np.random.randn(10, 10)]

        scaled = apply_gradient_scaling(params, scale_factor=0.0)

        assert np.allclose(scaled[0], 0.0)

    def test_gradient_scaling_with_negative_factor(self):
        """Verifies negative scale_factor inverts signs."""
        params = [np.ones((10,))]

        scaled = apply_gradient_scaling(params, scale_factor=-2.0)  # type: ignore[arg-type]

        assert np.allclose(scaled[0], -2.0)


class TestByzantinePerturbation:
    """Tests Byzantine perturbation attack."""

    def test_byzantine_perturbation_adds_noise(self):
        """Verifies Byzantine perturbation adds noise to original values."""
        np.random.seed(0)
        params = [np.random.randn(10, 10), np.random.randn(5)]

        perturbed = apply_byzantine_perturbation(params, noise_scale=3.0, seed=42)

        for orig, pert in zip(params, perturbed, strict=False):
            assert orig.shape == pert.shape

        assert not np.allclose(perturbed[0], params[0])

    def test_byzantine_perturbation_with_seed_is_deterministic(self):
        """Verifies Byzantine perturbation with seed is reproducible."""
        np.random.seed(0)
        params = [np.random.randn(100, 100)]

        perturbed1 = apply_byzantine_perturbation(params, seed=42)
        perturbed2 = apply_byzantine_perturbation(params, seed=42)

        assert np.allclose(perturbed1[0], perturbed2[0])

    def test_byzantine_perturbation_scale_affects_magnitude(self):
        """Verifies noise_scale affects perturbation magnitude."""
        np.random.seed(0)
        params = [np.random.randn(1000)]

        perturbed_small = apply_byzantine_perturbation(params, noise_scale=1.0, seed=42)
        perturbed_large = apply_byzantine_perturbation(params, noise_scale=5.0, seed=42)

        diff_small = np.std(perturbed_small[0] - params[0])
        diff_large = np.std(perturbed_large[0] - params[0])

        assert diff_large > diff_small * 3


class TestApplyWeightPoisoning:
    """Tests the main apply_weight_poisoning dispatcher."""

    def test_apply_weight_poisoning_model_poisoning(self):
        """Verifies dispatcher handles model_poisoning correctly."""
        np.random.seed(0)
        params = [np.random.randn(10, 10)]
        configs = [{"attack_type": "model_poisoning", "poison_ratio": 0.1}]

        poisoned = apply_weight_poisoning(params, configs)

        assert not np.allclose(poisoned[0], params[0])

    def test_apply_weight_poisoning_gradient_scaling(self):
        """Verifies dispatcher handles gradient_scaling correctly."""
        params = [np.ones((10,))]
        configs = [{"attack_type": "gradient_scaling", "scale_factor": 5.0}]

        poisoned = apply_weight_poisoning(params, configs)  # type: ignore[arg-type]

        assert np.allclose(poisoned[0], 5.0)

    def test_apply_weight_poisoning_byzantine(self):
        """Verifies dispatcher handles byzantine_perturbation correctly."""
        np.random.seed(0)
        params = [np.random.randn(10)]
        configs = [{"attack_type": "byzantine_perturbation", "seed": 42}]

        poisoned = apply_weight_poisoning(params, configs)

        assert not np.allclose(poisoned[0], params[0])

    def test_apply_weight_poisoning_skips_data_attacks(self):
        """Verifies dispatcher ignores data poisoning attack types."""
        params = [np.ones((10,))]
        configs = [{"attack_type": "label_flipping"}]

        poisoned = apply_weight_poisoning(params, configs)  # type: ignore[arg-type]

        assert np.allclose(poisoned[0], params[0])

    def test_apply_weight_poisoning_multiple_attacks(self):
        """Verifies dispatcher applies multiple attacks sequentially."""
        params = [np.ones((10,))]
        configs = [
            {"attack_type": "gradient_scaling", "scale_factor": 2.0},
            {"attack_type": "gradient_scaling", "scale_factor": 3.0},
        ]

        poisoned = apply_weight_poisoning(params, configs)  # type: ignore[arg-type]

        assert np.allclose(poisoned[0], 6.0)

    def test_apply_weight_poisoning_empty_configs(self):
        """Verifies dispatcher handles empty config list."""
        params = [np.ones((10,))]

        poisoned = apply_weight_poisoning(params, [])  # type: ignore[arg-type]

        assert np.allclose(poisoned[0], params[0])

    def test_apply_weight_poisoning_uses_config_params(self):
        """Verifies dispatcher extracts parameters from config."""
        np.random.seed(0)
        params = [np.random.randn(100)]
        configs = [
            {
                "attack_type": "model_poisoning",
                "poison_ratio": 0.5,
                "magnitude": 5.0,
                "seed": 123,
            }
        ]

        poisoned = apply_weight_poisoning(params, configs)

        changed = np.sum(np.abs(poisoned[0] - params[0]) > 0.01)
        assert 40 <= changed <= 60


class TestEdgeCases:
    """Tests edge cases and error handling."""

    def test_empty_parameter_list(self):
        """Verifies attacks handle empty parameter lists."""
        params: list[np.ndarray] = []

        assert apply_model_poisoning(params) == []
        assert apply_gradient_scaling(params) == []
        assert apply_byzantine_perturbation(params) == []

    def test_single_element_parameters(self):
        """Verifies attacks handle single-element arrays."""
        params = [np.array([1.0])]

        poisoned = apply_model_poisoning(params, poison_ratio=1.0, magnitude=5.0)
        assert poisoned[0].shape == (1,)

    def test_preserves_dtype(self):
        """Verifies attacks preserve parameter dtype."""
        np.random.seed(0)
        params_f32 = [np.random.randn(10).astype(np.float32)]
        params_f64 = [np.random.randn(10).astype(np.float64)]

        poisoned_f32 = apply_byzantine_perturbation(params_f32, seed=42)
        poisoned_f64 = apply_byzantine_perturbation(params_f64, seed=42)

        assert poisoned_f32[0].dtype == np.float32
        assert poisoned_f64[0].dtype == np.float64

    def test_large_parameters(self):
        """Verifies attacks handle large parameter arrays."""
        params = [np.random.randn(1000, 1000)]

        poisoned = apply_model_poisoning(params, seed=42)

        assert poisoned[0].shape == (1000, 1000)


class TestBoostedScaling:
    """Tests boosted scaling attack (Baruch et al. 'A Little Is Enough')."""

    def test_boosted_scaling_counteracts_fedavg(self):
        """Verifies scale = n_total / n_malicious when boost_factor=1."""
        params = [np.ones((10,))]

        scaled = apply_boosted_scaling(params, n_total=10, n_malicious=1)

        assert np.allclose(scaled[0], 10.0)

    def test_boosted_scaling_with_multiple_malicious(self):
        """Verifies correct scaling with multiple colluding clients."""
        params = [np.ones((10,))]

        scaled = apply_boosted_scaling(params, n_total=10, n_malicious=2)

        assert np.allclose(scaled[0], 5.0)

    def test_boosted_scaling_with_boost_factor(self):
        """Verifies boost_factor multiplies the base scale."""
        params = [np.ones((10,))]

        scaled = apply_boosted_scaling(params, n_total=10, n_malicious=2, boost_factor=2.0)

        # scale = (10/2) * 2.0 = 10.0
        assert np.allclose(scaled[0], 10.0)

    def test_boosted_scaling_preserves_shapes(self):
        """Verifies boosted scaling preserves parameter shapes."""
        params = [np.random.randn(10, 20), np.random.randn(5, 5)]

        scaled = apply_boosted_scaling(params, n_total=5, n_malicious=1)

        for orig, scal in zip(params, scaled, strict=False):
            assert orig.shape == scal.shape

    def test_boosted_scaling_invalid_n_malicious(self):
        """Verifies ValueError for n_malicious < 1."""
        params = [np.ones((10,))]

        with pytest.raises(ValueError, match="n_malicious must be >= 1"):
            apply_boosted_scaling(params, n_total=10, n_malicious=0)

    def test_boosted_scaling_invalid_n_total(self):
        """Verifies ValueError when n_total < n_malicious."""
        params = [np.ones((10,))]

        with pytest.raises(ValueError, match="n_total.*must be >= n_malicious"):
            apply_boosted_scaling(params, n_total=2, n_malicious=5)

    def test_boosted_scaling_empty_params(self):
        """Verifies empty parameter list returns empty."""
        assert apply_boosted_scaling([], n_total=10, n_malicious=1) == []


class TestInnerProductManipulation:
    """Tests inner product manipulation attack."""

    def test_negative_direction_reverses_update(self):
        """Verifies 'negative' direction reverses learning at strength=1.0."""
        params = [np.ones((10,)) * 2.0]

        result = apply_inner_product_manipulation(
            params, perturbation_strength=1.0, target_direction="negative"
        )

        # result = param * (1 - 2*1.0) = param * -1
        assert np.allclose(result[0], -2.0)

    def test_negative_direction_partial_strength(self):
        """Verifies partial strength reduces update."""
        params = [np.ones((10,)) * 4.0]

        result = apply_inner_product_manipulation(
            params, perturbation_strength=0.5, target_direction="negative"
        )

        # result = param * (1 - 2*0.5) = param * 0 = 0
        assert np.allclose(result[0], 0.0)

    def test_zero_direction_pushes_toward_zero(self):
        """Verifies 'zero' direction shrinks parameters."""
        params = [np.ones((10,)) * 5.0]

        result = apply_inner_product_manipulation(
            params, perturbation_strength=0.5, target_direction="zero"
        )

        # result = param * (1 - 0.5) = 2.5
        assert np.allclose(result[0], 2.5)

    def test_zero_direction_full_strength(self):
        """Verifies 'zero' direction at full strength zeroes out params."""
        params = [np.random.randn(100)]

        result = apply_inner_product_manipulation(
            params, perturbation_strength=1.0, target_direction="zero"
        )

        assert np.allclose(result[0], 0.0)

    def test_random_direction_bounded_l2_norm(self):
        """Verifies 'random' perturbation has L2 norm proportional to strength * ||param||."""
        np.random.seed(0)
        params = [np.random.randn(1000)]
        strength = 0.3

        result = apply_inner_product_manipulation(
            params, perturbation_strength=strength, target_direction="random", seed=42
        )

        delta = result[0] - params[0]
        delta_norm = np.linalg.norm(delta)
        param_norm = np.linalg.norm(params[0])

        # delta_norm should be approximately strength * param_norm
        assert abs(delta_norm - strength * param_norm) / param_norm < 0.01

    def test_random_direction_is_deterministic_with_seed(self):
        """Verifies random direction produces same result with same seed."""
        params = [np.random.randn(100)]

        r1 = apply_inner_product_manipulation(params, target_direction="random", seed=42)
        r2 = apply_inner_product_manipulation(params, target_direction="random", seed=42)

        assert np.allclose(r1[0], r2[0])

    def test_unknown_direction_raises_error(self):
        """Verifies ValueError for unknown direction."""
        params = [np.ones((10,))]

        with pytest.raises(ValueError, match="Unknown target_direction"):
            apply_inner_product_manipulation(params, target_direction="invalid")

    def test_preserves_shapes(self):
        """Verifies all directions preserve parameter shapes."""
        params = [np.random.randn(10, 20), np.random.randn(5)]

        for direction in ("negative", "zero", "random"):
            result = apply_inner_product_manipulation(params, target_direction=direction, seed=42)
            for orig, res in zip(params, result, strict=False):
                assert orig.shape == res.shape

    def test_empty_params(self):
        """Verifies empty parameter list returns empty."""
        for direction in ("negative", "zero", "random"):
            assert apply_inner_product_manipulation([], target_direction=direction) == []


class TestByzantineClipNorm:
    """Tests the clip_norm enhancement on Byzantine perturbation."""

    def test_clip_norm_limits_perturbation(self):
        """Verifies clip_norm bounds the L2 norm of the perturbation."""
        np.random.seed(0)
        params = [np.random.randn(1000)]
        clip_norm = 1.0

        perturbed = apply_byzantine_perturbation(
            params, noise_scale=10.0, clip_norm=clip_norm, seed=42
        )

        delta = perturbed[0] - params[0]
        delta_l2 = np.linalg.norm(delta)

        assert delta_l2 <= clip_norm + 1e-6

    def test_clip_norm_none_does_not_clip(self):
        """Verifies default clip_norm=None allows large perturbations."""
        np.random.seed(0)
        params = [np.random.randn(1000)]

        perturbed = apply_byzantine_perturbation(params, noise_scale=10.0, clip_norm=None, seed=42)

        delta = perturbed[0] - params[0]
        delta_l2 = np.linalg.norm(delta)

        # Without clipping, large noise_scale should produce a large delta
        assert delta_l2 > 10.0

    def test_clip_norm_preserves_dtype(self):
        """Verifies clip_norm preserves float32 dtype."""
        params = [np.random.randn(100).astype(np.float32)]

        perturbed = apply_byzantine_perturbation(params, noise_scale=5.0, clip_norm=2.0, seed=42)

        assert perturbed[0].dtype == np.float32


class TestDispatchNewAttacks:
    """Tests dispatcher with new attack types."""

    def test_dispatch_boosted_scaling(self):
        """Verifies dispatcher correctly routes boosted_scaling."""
        params = [np.ones((10,))]
        configs = [{"attack_type": "boosted_scaling", "n_total": 10, "n_malicious": 2}]

        poisoned = apply_weight_poisoning(params, configs)

        assert np.allclose(poisoned[0], 5.0)

    def test_dispatch_inner_product_manipulation(self):
        """Verifies dispatcher correctly routes inner_product_manipulation."""
        params = [np.ones((10,)) * 4.0]
        configs = [
            {
                "attack_type": "inner_product_manipulation",
                "perturbation_strength": 0.5,
                "target_direction": "zero",
            }
        ]

        poisoned = apply_weight_poisoning(params, configs)

        assert np.allclose(poisoned[0], 2.0)

    def test_dispatch_strips_scheduling_keys(self):
        """Verifies dispatcher strips scheduling metadata before calling attack."""
        params = [np.ones((10,))]
        configs = [
            {
                "attack_type": "gradient_scaling",
                "scale_factor": 3.0,
                "start_round": 1,
                "end_round": 10,
                "selection_strategy": "specific",
                "malicious_client_ids": [0],
                "_selected_clients": [0],
                "percentage": 0.5,
            }
        ]

        poisoned = apply_weight_poisoning(params, configs)

        assert np.allclose(poisoned[0], 3.0)

    def test_dispatch_chained_new_attacks(self):
        """Verifies chaining boosted_scaling then inner_product_manipulation."""
        params = [np.ones((10,)) * 2.0]
        configs = [
            {"attack_type": "boosted_scaling", "n_total": 5, "n_malicious": 1},
            {
                "attack_type": "inner_product_manipulation",
                "perturbation_strength": 0.5,
                "target_direction": "zero",
            },
        ]

        poisoned = apply_weight_poisoning(params, configs)

        # boosted: 2.0 * 5 = 10.0, then zero(0.5): 10.0 * 0.5 = 5.0
        assert np.allclose(poisoned[0], 5.0)


class TestAlternatingMinPoisoning:
    """Tests for the optimization-based alternating-min poisoning attack."""

    def _make_params(self, shape=(50,), seed=0):
        rng = np.random.default_rng(seed)
        return [rng.standard_normal(shape)]

    # --- basic correctness ---

    def test_output_shapes_preserved(self):
        """Poisoned parameters have the same shapes as inputs."""
        params = [np.random.randn(10, 5), np.random.randn(3)]
        result = apply_alternating_min_poisoning(params, n_total=10, n_malicious=1)
        for orig, res in zip(params, result, strict=True):
            assert orig.shape == res.shape

    def test_output_dtypes_preserved(self):
        """Poisoned parameters preserve the original dtype."""
        params = [np.random.randn(20).astype(np.float32)]
        result = apply_alternating_min_poisoning(params, n_total=10, n_malicious=1)
        assert result[0].dtype == np.float32

    # --- trust-region / norm constraint ---

    def test_output_within_fedavg_trust_region(self):
        """Total update delta is bounded by tau = tau_factor * (n_total/n_malicious) * ||delta||.

        Bhagoji et al. (ICML 2019): the poisoned update must stay within the trust
        region to evade norm-based defences such as Krum and Bulyan.
        """
        params = self._make_params((200,))
        global_params = [p * 0.5 for p in params]  # global is half of local
        n_total, n_malicious = 10, 1
        tau_factor = 1.0

        result = apply_alternating_min_poisoning(
            params,
            global_parameters=global_params,
            n_total=n_total,
            n_malicious=n_malicious,
            tau_factor=tau_factor,
        )

        delta_honest = np.concatenate(
            [(p - g).flatten() for p, g in zip(params, global_params, strict=True)]
        )
        tau = tau_factor * (n_total / n_malicious) * np.linalg.norm(delta_honest)

        adv_delta = np.concatenate(
            [(r - g).flatten() for r, g in zip(result, global_params, strict=True)]
        )
        assert np.linalg.norm(adv_delta) <= tau * 1.001  # small tolerance for fp arithmetic

    def test_tau_factor_scales_trust_region(self):
        """Higher tau_factor produces a larger perturbation norm (Bagdasaryan et al., AISTATS 2020)."""
        params = self._make_params((100,))
        global_params = [np.zeros_like(p) for p in params]

        r1 = apply_alternating_min_poisoning(params, global_params, n_total=10, tau_factor=0.5)
        r2 = apply_alternating_min_poisoning(params, global_params, n_total=10, tau_factor=2.0)

        norm1 = np.linalg.norm(
            np.concatenate([(r - g).flatten() for r, g in zip(r1, global_params, strict=True)])
        )
        norm2 = np.linalg.norm(
            np.concatenate([(r - g).flatten() for r, g in zip(r2, global_params, strict=True)])
        )

        assert norm2 > norm1

    # --- adversarial direction ---

    def test_poisoned_update_opposes_honest_delta(self):
        """The adversarial delta points opposite to the honest delta (maximises divergence).

        Fang et al. (USENIX 2020): optimal attack under FedAvg is the antipodal
        point on the trust-region sphere.
        """
        params = self._make_params((500,))
        global_params = [np.zeros_like(p) for p in params]

        result = apply_alternating_min_poisoning(
            params,
            global_parameters=global_params,
            n_total=10,
            n_malicious=1,
            pgd_steps=50,
            pgd_step_size=0.05,
        )

        honest_flat = np.concatenate([p.flatten() for p in params])
        adv_flat = np.concatenate(
            [(r - g).flatten() for r, g in zip(result, global_params, strict=True)]
        )

        # Cosine similarity should be negative (opposite directions)
        cosine = np.dot(honest_flat, adv_flat) / (
            np.linalg.norm(honest_flat) * np.linalg.norm(adv_flat) + 1e-10
        )
        assert cosine < 0, f"Expected negative cosine similarity, got {cosine:.4f}"

    # --- no global parameters fallback ---

    def test_no_global_parameters_uses_zero_baseline(self):
        """When global_parameters is None the attack treats zeros as the baseline."""
        params = [np.ones((20,))]
        result_with_global = apply_alternating_min_poisoning(
            params,
            global_parameters=[np.zeros((20,))],
            n_total=10,
        )
        result_no_global = apply_alternating_min_poisoning(
            params,
            global_parameters=None,
            n_total=10,
        )
        np.testing.assert_allclose(result_with_global[0], result_no_global[0], rtol=1e-6)

    # --- multi-malicious scaling ---

    def test_multiple_malicious_clients_reduces_tau(self):
        """More colluding clients means each one needs a smaller individual tau.

        With n_malicious=1 the scale is n_total/1; with n_malicious=n_total/2
        the scale drops to 2, yielding a proportionally smaller trust region.
        """
        params = self._make_params((100,))
        global_params = [np.zeros_like(p) for p in params]

        r1 = apply_alternating_min_poisoning(params, global_params, n_total=10, n_malicious=1)
        r5 = apply_alternating_min_poisoning(params, global_params, n_total=10, n_malicious=5)

        norm1 = np.linalg.norm(
            np.concatenate([(r - g).flatten() for r, g in zip(r1, global_params, strict=True)])
        )
        norm5 = np.linalg.norm(
            np.concatenate([(r - g).flatten() for r, g in zip(r5, global_params, strict=True)])
        )

        assert norm1 > norm5

    # --- validation errors ---

    def test_raises_on_n_malicious_zero(self):
        """Verifies ValueError when n_malicious < 1."""
        with pytest.raises(ValueError, match="n_malicious must be"):
            apply_alternating_min_poisoning([np.ones(10)], n_total=5, n_malicious=0)

    def test_raises_on_n_total_less_than_n_malicious(self):
        """Verifies ValueError when n_total < n_malicious."""
        with pytest.raises(ValueError, match="n_total"):
            apply_alternating_min_poisoning([np.ones(10)], n_total=2, n_malicious=5)

    def test_raises_on_invalid_pgd_step_size(self):
        """Verifies ValueError when pgd_step_size is outside (0, 1]."""
        with pytest.raises(ValueError, match="pgd_step_size"):
            apply_alternating_min_poisoning([np.ones(10)], n_total=5, pgd_step_size=0.0)

    # --- dispatcher integration ---

    def test_dispatcher_routes_alternating_min_poisoning(self):
        """Verifies the weight_poisoning dispatcher correctly routes to the new attack."""
        params = [np.ones((20,))]
        configs = [
            {
                "attack_type": "alternating_min_poisoning",
                "n_total": 10,
                "n_malicious": 1,
                "pgd_steps": 5,
            }
        ]
        result = apply_weight_poisoning(params, configs)
        # Result should differ from the input (attack was applied)
        assert not np.allclose(result[0], params[0])
        assert result[0].shape == params[0].shape
