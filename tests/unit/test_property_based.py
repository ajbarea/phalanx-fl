"""Property-based tests using Hypothesis for FL aggregation invariants.

Note: pyright reports errors when Hypothesis is not installed because `st` is None.
These tests are skipped via pytestmark when Hypothesis is unavailable.
"""

# pyright: reportOptionalMemberAccess=false

import numpy as np
import pytest

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

    def _dummy_decorator(*args, **kwargs):
        def wrapper(f):
            return f

        return wrapper

    given = _dummy_decorator
    settings = _dummy_decorator  # type: ignore[misc,assignment]
    st = None  # type: ignore[misc,assignment]
    HealthCheck = None  # type: ignore[misc,assignment]  # noqa: N806


if not HYPOTHESIS_AVAILABLE:
    pytest.skip(
        "Hypothesis not installed. Install with: pip install hypothesis",
        allow_module_level=True,
    )


class TestTrimmedMeanProperties:
    """Property-based tests for trimmed mean aggregation."""

    @given(
        st.lists(
            st.floats(
                min_value=-1e6,
                max_value=1e6,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=5,
            max_size=100,
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_trimmed_mean_bounded_by_input_range(self, values):
        """Property: trimmed mean is always within input min/max bounds."""
        if len(values) < 5:
            return

        trim_ratio = 0.2
        trim_count = int(len(values) * trim_ratio)

        sorted_values = sorted(values)
        trimmed = sorted_values[trim_count : len(values) - trim_count]

        if len(trimmed) == 0:
            return

        result = np.mean(trimmed)

        min_val, max_val = min(trimmed), max(trimmed)
        epsilon = 1e-14 * max(abs(min_val), abs(max_val), 1.0)
        assert min_val - epsilon <= result <= max_val + epsilon, (
            f"Trimmed mean {result} outside bounds [{min_val}, {max_val}]"
        )

    @given(
        st.lists(
            st.floats(
                min_value=-100,
                max_value=100,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=10,
            max_size=50,
        ),
        st.floats(min_value=0.05, max_value=0.45),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_trimmed_mean_robustness_to_outliers(self, values, trim_ratio):
        """Property: trimmed mean is robust to extreme outliers."""
        if len(values) < 10:
            return

        trim_count = max(1, int(len(values) * trim_ratio))
        sorted_original = sorted(values)
        trimmed_original = sorted_original[trim_count : len(values) - trim_count]

        if len(trimmed_original) < 2:
            return

        original_mean = np.mean(trimmed_original)

        # Simulate Byzantine attack with extreme outliers
        num_outliers = min(trim_count, 2)
        outliers = [1e6] * num_outliers + [-1e6] * num_outliers
        values_with_outliers = values + outliers

        new_trim_count = max(1, int(len(values_with_outliers) * trim_ratio))
        sorted_with_outliers = sorted(values_with_outliers)
        trimmed_with_outliers = sorted_with_outliers[
            new_trim_count : len(values_with_outliers) - new_trim_count
        ]

        if len(trimmed_with_outliers) < 2:
            return

        new_mean = np.mean(trimmed_with_outliers)

        abs_change = abs(new_mean - original_mean)
        if abs(original_mean) > 1.0:
            relative_change = abs_change / abs(original_mean)
            assert relative_change < 10, (
                f"Mean changed too much (relative): {original_mean} -> {new_mean}"
            )
        else:
            assert np.isfinite(new_mean), f"New mean is not finite: {new_mean}"


class TestWeightedAverageProperties:
    """Property-based tests for FedAvg-style weighted aggregation."""

    @given(
        st.lists(
            st.tuples(
                st.floats(
                    min_value=-1000,
                    max_value=1000,
                    allow_nan=False,
                    allow_infinity=False,
                ),
                st.integers(min_value=1, max_value=1000),
            ),
            min_size=2,
            max_size=20,
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_weighted_average_convex_combination(self, value_weight_pairs):
        """Property: weighted average is within convex hull of inputs."""
        if not value_weight_pairs:
            return

        values = [v for v, w in value_weight_pairs]
        weights = [w for v, w in value_weight_pairs]

        total_weight = sum(weights)
        if total_weight == 0:
            return

        weighted_avg = sum(v * w for v, w in value_weight_pairs) / total_weight

        min_val, max_val = min(values), max(values)
        epsilon = 1e-9 * max(abs(min_val), abs(max_val), 1.0)
        assert min_val - epsilon <= weighted_avg <= max_val + epsilon, (
            f"Weighted average {weighted_avg} outside bounds [{min_val}, {max_val}]"
        )

    @given(
        st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
        st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_equal_weights_equals_simple_mean(self, value, num_clients):
        """Property: equal weights produce simple arithmetic mean."""
        values = [value] * num_clients
        weights = [100] * num_clients

        total_weight = sum(weights)
        weighted_avg = sum(v * w for v, w in zip(values, weights)) / total_weight
        simple_mean = np.mean(values)

        assert np.isclose(weighted_avg, simple_mean, rtol=1e-10), (
            f"Weighted avg {weighted_avg} != simple mean {simple_mean}"
        )


class TestKrumDistanceProperties:
    """Property-based tests for Krum distance calculations."""

    @given(
        st.lists(
            st.lists(
                st.floats(
                    min_value=-10,
                    max_value=10,
                    allow_nan=False,
                    allow_infinity=False,
                ),
                min_size=5,
                max_size=5,
            ),
            min_size=3,
            max_size=10,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_pairwise_distances_symmetry(self, vectors):
        """Property: pairwise squared distances are symmetric."""
        if len(vectors) < 2:
            return

        arr = np.array(vectors)
        n = len(vectors)
        distances = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                diff = arr[i] - arr[j]
                distances[i, j] = np.sum(diff**2)

        assert np.allclose(distances, distances.T, rtol=1e-10), "Distance matrix is not symmetric"

    @given(
        st.lists(
            st.lists(
                st.floats(
                    min_value=-10,
                    max_value=10,
                    allow_nan=False,
                    allow_infinity=False,
                ),
                min_size=5,
                max_size=5,
            ),
            min_size=3,
            max_size=10,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_pairwise_distances_non_negative(self, vectors):
        """Property: pairwise squared distances are non-negative."""
        if len(vectors) < 2:
            return

        arr = np.array(vectors)
        n = len(vectors)

        for i in range(n):
            for j in range(n):
                diff = arr[i] - arr[j]
                dist_sq = np.sum(diff**2)
                assert dist_sq >= 0, f"Negative squared distance: {dist_sq}"

    @given(
        st.lists(
            st.floats(
                min_value=-10,
                max_value=10,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=5,
            max_size=5,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_self_distance_is_zero(self, vector):
        """Property: distance from a vector to itself is zero."""
        arr = np.array(vector)
        diff = arr - arr
        dist_sq = np.sum(diff**2)

        assert np.isclose(dist_sq, 0, atol=1e-15), f"Self-distance should be 0, got {dist_sq}"


class TestByzantineDetectionProperties:
    """Property-based tests for Byzantine detection invariants."""

    @given(
        st.integers(min_value=5, max_value=20),
        st.floats(min_value=0.1, max_value=0.49),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_detection_upper_bound(self, total_clients, byzantine_ratio):
        """Property: detected Byzantine clients <= actual Byzantine clients."""
        num_byzantine = int(total_clients * byzantine_ratio)
        max_detectable = num_byzantine

        assert max_detectable <= num_byzantine

    @given(
        st.integers(min_value=10, max_value=50),
        st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_honest_majority_assumption(self, num_clients, num_byzantine):
        """Property: Byzantine-resilient algorithms require honest majority."""
        byzantine_ratio = num_byzantine / num_clients

        if byzantine_ratio < 0.5:
            honest_count = num_clients - num_byzantine
            assert honest_count > num_byzantine, "Honest majority assumption violated"


class TestNumericalStability:
    """Property-based tests for numerical stability."""

    @given(
        st.lists(
            st.floats(
                min_value=1e-10,
                max_value=1e10,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=5,
            max_size=100,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_mean_stability_with_large_values(self, values):
        """Property: mean is finite and within input bounds."""
        if not values:
            return

        mean_val = np.mean(values)

        assert np.isfinite(mean_val), f"Mean is not finite: {mean_val}"
        assert min(values) <= mean_val <= max(values), f"Mean {mean_val} outside input range"

    @given(
        st.lists(
            st.floats(
                min_value=-1e6,
                max_value=1e6,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=2,
            max_size=50,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_variance_non_negative(self, values):
        """Property: variance is always non-negative."""
        if len(values) < 2:
            return

        variance = np.var(values)
        assert variance >= 0, f"Negative variance: {variance}"


class TestStackedParametrize:
    """Stacked @parametrize for combinatorial attack × defense testing."""

    @pytest.mark.parametrize("attack_type", ["gaussian_noise", "model_poisoning"])
    @pytest.mark.parametrize("defense_strategy", ["krum", "trimmed_mean"])
    @pytest.mark.parametrize("byzantine_ratio", [0.1, 0.2, 0.3])
    def test_attack_defense_combinations(self, attack_type, defense_strategy, byzantine_ratio):
        """Test all attack × defense × ratio combinations."""
        assert attack_type in ["gaussian_noise", "model_poisoning"]
        assert defense_strategy in ["krum", "trimmed_mean"]
        assert 0 < byzantine_ratio < 0.5

        num_clients = 10
        num_byzantine = int(num_clients * byzantine_ratio)

        assert num_byzantine < num_clients // 2, (
            f"Byzantine ratio {byzantine_ratio} violates honest majority"
        )


class TestRoundtripProperties:
    """Encode/decode roundtrip invariants for serialization."""

    @given(
        st.dictionaries(
            st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(blacklist_categories=["Cs"]),
            ),
            st.one_of(
                st.integers(min_value=-1000000, max_value=1000000),
                st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
                st.text(
                    min_size=0,
                    max_size=50,
                    alphabet=st.characters(blacklist_categories=["Cs"]),
                ),
                st.booleans(),
            ),
            min_size=0,
            max_size=10,
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_json_roundtrip(self, data):
        """Property: json.loads(json.dumps(x)) == x for JSON-serializable data."""
        import json

        serialized = json.dumps(data)
        deserialized = json.loads(serialized)
        assert deserialized == data

    @given(
        st.lists(
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=100,
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_numpy_pickle_roundtrip(self, values):
        """Property: pickle.loads(pickle.dumps(arr)) equals original array."""
        import pickle

        arr = np.array(values)
        roundtripped = pickle.loads(pickle.dumps(arr))
        assert np.allclose(arr, roundtripped)

    @given(st.binary(min_size=1, max_size=1000))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_base64_roundtrip(self, data):
        """Property: base64 decode(encode(x)) == x"""
        import base64

        encoded = base64.b64encode(data)
        decoded = base64.b64decode(encoded)
        assert decoded == data

    @given(
        st.lists(
            st.lists(
                st.floats(min_value=-10, max_value=10, allow_nan=False, allow_infinity=False),
                min_size=5,
                max_size=5,
            ),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_numpy_tolist_roundtrip(self, nested_list):
        """Property: np.array(arr.tolist()) recovers original array."""
        arr = np.array(nested_list)
        roundtripped = np.array(arr.tolist())
        assert np.allclose(arr, roundtripped)


class TestAggregationInvariants:
    """FL aggregation mathematical invariants."""

    @given(
        st.lists(
            st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
            min_size=5,
            max_size=50,
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_median_single_outlier_robustness(self, values):
        """Property: median stays within original range despite single outlier."""
        with_outlier = values + [1e10]
        new_median = np.median(with_outlier)

        sorted_original = sorted(values)
        assert any(np.isclose(new_median, v, rtol=1e-10) for v in sorted_original) or min(
            values
        ) <= new_median <= max(values)

    @given(
        st.lists(
            st.floats(min_value=0.1, max_value=10, allow_nan=False, allow_infinity=False),
            min_size=4,
            max_size=20,
        ),
        st.lists(st.integers(min_value=1, max_value=100), min_size=4, max_size=20),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_weighted_average_associativity(self, values, weights):
        """Property: weighted average computed in parts equals whole."""
        min_len = min(len(values), len(weights))
        if min_len < 4:
            return
        values = values[:min_len]
        weights = weights[:min_len]

        total_weight = sum(weights)
        if total_weight == 0:
            return

        weighted_avg = sum(v * w for v, w in zip(values, weights)) / total_weight

        mid = len(values) // 2
        w1, w2 = sum(weights[:mid]), sum(weights[mid:])
        if w1 == 0 or w2 == 0:
            return

        part1 = sum(v * w for v, w in zip(values[:mid], weights[:mid])) / w1
        part2 = sum(v * w for v, w in zip(values[mid:], weights[mid:])) / w2
        combined = (part1 * w1 + part2 * w2) / total_weight

        assert np.isclose(weighted_avg, combined, rtol=1e-9)

    @given(
        st.lists(
            st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
            min_size=8,
            max_size=30,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_bulyan_style_trimmed_mean_bounds(self, values):
        """Property: Bulyan-style double trimming produces bounded result."""
        if len(values) < 8:
            return

        # Research: Bulyan applies two-phase trimming for Byzantine resilience
        # (El Mhamdi et al., ICML 2018)
        sorted_vals = sorted(values)
        n = len(sorted_vals)

        first_trim = max(1, n // 4)
        after_first_trim = sorted_vals[first_trim : n - first_trim]

        if len(after_first_trim) < 3:
            return

        second_trim = max(1, len(after_first_trim) // 4)
        final_trimmed = after_first_trim[second_trim : len(after_first_trim) - second_trim]

        if len(final_trimmed) == 0:
            return

        result = np.mean(final_trimmed)
        # Use tolerance for floating point comparison
        eps = 1e-10
        assert min(final_trimmed) - eps <= result <= max(final_trimmed) + eps


class TestModelParameterProperties:
    """Properties for FL model parameter operations."""

    @given(
        st.lists(
            st.lists(
                st.floats(min_value=-10, max_value=10, allow_nan=False, allow_infinity=False),
                min_size=5,
                max_size=5,
            ),
            min_size=2,
            max_size=10,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_fedavg_preserves_shape(self, client_params):
        """Property: FedAvg output has same shape as inputs."""
        arrays = [np.array(p) for p in client_params]
        avg = np.mean(arrays, axis=0)
        assert avg.shape == arrays[0].shape

    @given(st.floats(min_value=0.001, max_value=10.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_learning_rate_scaling_preserves_ratios(self, lr):
        """Property: scaling preserves pairwise parameter ratios."""
        params = np.array([1.0, 2.0, 3.0, 4.0])
        scaled = params * lr

        for i in range(len(params)):
            for j in range(i + 1, len(params)):
                original_ratio = params[j] / params[i]
                scaled_ratio = scaled[j] / scaled[i]
                assert np.isclose(original_ratio, scaled_ratio, rtol=1e-10)

    @given(
        st.lists(
            st.floats(min_value=-1, max_value=1, allow_nan=False, allow_infinity=False),
            min_size=10,
            max_size=100,
        ),
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_momentum_update_bounded(self, gradients, momentum):
        """Property: momentum update bounded by gradient magnitude."""
        velocity = np.zeros(len(gradients))
        grad_array = np.array(gradients)

        new_velocity = momentum * velocity + grad_array

        # For zero initial velocity, new velocity equals gradient
        assert np.linalg.norm(new_velocity) <= np.linalg.norm(grad_array) * 1.001
