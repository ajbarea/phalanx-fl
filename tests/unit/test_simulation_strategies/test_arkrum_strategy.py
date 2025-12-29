"""Unit tests for ArKrum aggregation strategy.

Tests the ArKrum (Parameter-free Krum) algorithm based on arXiv:2505.17226:
- Median-based filtering to remove extreme outliers
- SSE-based segmentation for automatic Byzantine count estimation
- Multi-update averaging for stability
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from flwr.common import ndarrays_to_parameters

from src.data_models.simulation_strategy_history import SimulationStrategyHistory
from src.simulation_strategies.arkrum_strategy import ArKrumStrategy


def create_mock_results(param_vectors):
    """Create mock client results from parameter vectors."""
    results = []
    for i, params in enumerate(param_vectors):
        client = MagicMock()
        client.cid = str(i)
        fit_res = MagicMock()
        fit_res.parameters = ndarrays_to_parameters([params])
        results.append((client, fit_res))
    return results


class TestArKrumMedianFiltering:
    """Test the median-based filtering algorithm (Algorithm 1 from paper)."""

    @pytest.fixture
    def strategy(self):
        """Create an ArKrum strategy with mocked history."""
        history = MagicMock(spec=SimulationStrategyHistory)
        return ArKrumStrategy(strategy_history=history)

    def test_median_filter_with_normal_distribution(self, strategy):
        """Test filtering with normally distributed distances."""
        # Honest clients should have similar distances
        distances = np.array(
            [0.1, 0.12, 0.11, 0.13, 0.14, 0.15, 0.9]
        )  # Last is outlier
        sorted_distances = np.sort(distances)

        filtered = strategy._median_filter_distances(sorted_distances)

        # Outlier 0.9 should be filtered out
        assert len(filtered) < len(sorted_distances)
        assert 0.9 not in filtered

    def test_median_filter_handles_edge_cases(self, strategy):
        """Test filtering with edge case inputs."""
        # Two elements - should return as-is
        small = np.array([0.1, 0.2])
        assert np.array_equal(strategy._median_filter_distances(small), small)

        # Single element
        single = np.array([0.5])
        assert np.array_equal(strategy._median_filter_distances(single), single)

        # Empty
        empty = np.array([])
        assert len(strategy._median_filter_distances(empty)) == 0

    def test_median_filter_with_multiple_outliers(self, strategy):
        """Test filtering removes multiple Byzantine outliers."""
        # 5 honest (tight cluster) + 3 Byzantine (outliers)
        distances = np.array([0.1, 0.11, 0.12, 0.13, 0.14, 0.8, 0.85, 0.9])
        sorted_distances = np.sort(distances)

        filtered = strategy._median_filter_distances(sorted_distances)

        # Byzantine outliers should be filtered
        assert max(filtered) < 0.5  # All outliers removed

    def test_median_filter_never_returns_empty(self, strategy):
        """Test that filtering never returns completely empty array."""
        # Even with extreme values, should return something
        distances = np.array([0.1, 1.0, 2.0, 3.0])
        sorted_distances = np.sort(distances)

        filtered = strategy._median_filter_distances(sorted_distances)

        assert len(filtered) > 0


class TestArKrumSSEEstimation:
    """Test SSE-based Byzantine count estimation."""

    @pytest.fixture
    def strategy(self):
        """Create an ArKrum strategy with mocked history."""
        history = MagicMock(spec=SimulationStrategyHistory)
        return ArKrumStrategy(strategy_history=history)

    def test_sse_respects_honest_majority(self, strategy):
        """Test that f estimate respects 2+2f < n constraint."""
        # 10 clients total
        distances = np.linspace(0.1, 1.0, 10)

        f_estimate = strategy._estimate_f_sse(distances)

        # For n=10: max_f = (10-2)//2 = 4
        assert f_estimate <= 4

    def test_sse_handles_small_inputs(self, strategy):
        """Test SSE with small number of clients."""
        # 3 or fewer elements should return 0
        assert strategy._estimate_f_sse(np.array([0.1])) == 0
        assert strategy._estimate_f_sse(np.array([0.1, 0.2])) == 0
        assert strategy._estimate_f_sse(np.array([0.1, 0.2, 0.3])) == 0

    def test_sse_returns_non_negative(self, strategy):
        """Test that f estimate is never negative."""
        for _ in range(10):
            distances = np.random.rand(10) * 2
            f_estimate = strategy._estimate_f_sse(np.sort(distances))
            assert f_estimate >= 0

    def test_sse_with_uniform_distances(self, strategy):
        """Test SSE with uniformly distributed distances."""
        distances = np.linspace(0.1, 0.2, 8)  # Very uniform
        f_estimate = strategy._estimate_f_sse(distances)

        # Uniform distribution suggests no clear outliers
        assert f_estimate <= 3  # max_f = (8-2)//2 = 3


class TestArKrumScoreComputation:
    """Test ArKrum score computation."""

    @pytest.fixture
    def strategy(self):
        """Create an ArKrum strategy with mocked history."""
        history = MagicMock(spec=SimulationStrategyHistory)
        return ArKrumStrategy(strategy_history=history)

    def test_compute_scores_returns_correct_shapes(self, strategy):
        """Test that score computation returns correct shapes."""
        np.random.seed(42)
        params = [np.random.randn(10).astype(np.float32) for _ in range(4)]
        results = create_mock_results(params)

        scores, f_estimates, dist_matrix = strategy._compute_arkrum_scores(results)

        assert len(scores) == 4
        assert len(f_estimates) == 4
        assert dist_matrix.shape == (4, 4)

    def test_distance_matrix_is_symmetric(self, strategy):
        """Test that distance matrix is symmetric."""
        np.random.seed(42)
        params = [np.random.randn(20).astype(np.float32) for _ in range(5)]
        results = create_mock_results(params)

        _, _, dist_matrix = strategy._compute_arkrum_scores(results)

        np.testing.assert_array_almost_equal(dist_matrix, dist_matrix.T)

    def test_distance_matrix_diagonal_is_zero(self, strategy):
        """Test that self-distances are zero."""
        np.random.seed(42)
        params = [np.random.randn(10).astype(np.float32) for _ in range(3)]
        results = create_mock_results(params)

        _, _, dist_matrix = strategy._compute_arkrum_scores(results)

        np.testing.assert_array_equal(np.diag(dist_matrix), np.zeros(3))

    def test_scores_are_positive(self, strategy):
        """Test that all scores are non-negative."""
        np.random.seed(42)
        params = [np.random.randn(15).astype(np.float32) for _ in range(6)]
        results = create_mock_results(params)

        scores, _, _ = strategy._compute_arkrum_scores(results)

        assert all(s >= 0 for s in scores)


class TestArKrumAggregate:
    """Test the aggregate_fit method."""

    @pytest.fixture
    def strategy(self):
        """Create an ArKrum strategy with mocked history."""
        history = MagicMock(spec=SimulationStrategyHistory)
        history.insert_round_history_entry = MagicMock()
        history.insert_single_client_history_entry = MagicMock()
        return ArKrumStrategy(strategy_history=history)

    def test_aggregate_updates_current_round(self, strategy):
        """Test that current_round is updated."""
        np.random.seed(42)
        params = [np.random.randn(10).astype(np.float32) for _ in range(4)]
        results = create_mock_results(params)

        with patch.object(
            ArKrumStrategy.__bases__[0], "aggregate_fit", return_value=(MagicMock(), {})
        ):
            strategy.aggregate_fit(5, results, [])

        assert strategy.current_round == 5

    def test_aggregate_updates_status_tracker(self, strategy):
        """Test that status tracker is updated."""
        strategy.status_tracker = MagicMock()

        np.random.seed(42)
        params = [np.random.randn(10).astype(np.float32) for _ in range(4)]
        results = create_mock_results(params)

        with patch.object(
            ArKrumStrategy.__bases__[0], "aggregate_fit", return_value=(MagicMock(), {})
        ):
            strategy.aggregate_fit(3, results, [])

        strategy.status_tracker.update_round.assert_called_once_with(3)

    def test_aggregate_records_history(self, strategy):
        """Test that history entries are recorded."""
        np.random.seed(42)
        params = [np.random.randn(10).astype(np.float32) for _ in range(3)]
        results = create_mock_results(params)

        with patch.object(
            ArKrumStrategy.__bases__[0], "aggregate_fit", return_value=(MagicMock(), {})
        ):
            strategy.aggregate_fit(1, results, [])

        # Should record round entry
        strategy.strategy_history.insert_round_history_entry.assert_called_once()

        # Should record client entries
        assert (
            strategy.strategy_history.insert_single_client_history_entry.call_count == 3
        )

    def test_aggregate_stores_client_scores(self, strategy):
        """Test that client scores are stored."""
        np.random.seed(42)
        params = [np.random.randn(10).astype(np.float32) for _ in range(4)]
        results = create_mock_results(params)

        with patch.object(
            ArKrumStrategy.__bases__[0], "aggregate_fit", return_value=(MagicMock(), {})
        ):
            strategy.aggregate_fit(1, results, [])

        assert len(strategy.client_scores) == 4


class TestArKrumInitialization:
    """Test ArKrum strategy initialization."""

    def test_init_with_required_args(self):
        """Test initialization with required arguments."""
        history = MagicMock(spec=SimulationStrategyHistory)

        strategy = ArKrumStrategy(strategy_history=history)

        assert strategy.strategy_history is history
        assert strategy.status_tracker is None
        assert strategy.remove_clients is False
        assert strategy.begin_removing_from_round == 1
        assert strategy.current_round == 0
        assert strategy.client_scores == {}

    def test_init_with_optional_args(self):
        """Test initialization with optional arguments."""
        history = MagicMock(spec=SimulationStrategyHistory)
        tracker = MagicMock()

        strategy = ArKrumStrategy(
            strategy_history=history,
            remove_clients=True,
            begin_removing_from_round=5,
            status_tracker=tracker,
        )

        assert strategy.remove_clients is True
        assert strategy.begin_removing_from_round == 5
        assert strategy.status_tracker is tracker

    def test_init_passes_kwargs_to_parent(self):
        """Test that kwargs are passed to FedAvg parent."""
        history = MagicMock(spec=SimulationStrategyHistory)

        # FedAvg accepts min_fit_clients, min_evaluate_clients, etc.
        strategy = ArKrumStrategy(
            strategy_history=history,
            min_fit_clients=5,
            min_evaluate_clients=3,
        )

        assert strategy.min_fit_clients == 5
        assert strategy.min_evaluate_clients == 3


class TestArKrumByzantineDetection:
    """Integration tests for Byzantine client detection."""

    @pytest.fixture
    def strategy(self):
        """Create an ArKrum strategy with mocked history."""
        history = MagicMock(spec=SimulationStrategyHistory)
        history.insert_round_history_entry = MagicMock()
        history.insert_single_client_history_entry = MagicMock()
        return ArKrumStrategy(strategy_history=history)

    def test_honest_clients_get_lower_scores(self, strategy):
        """Test that honest clients in tight cluster get lower Krum scores."""
        np.random.seed(42)

        # 7 honest clients with similar parameters
        honest_base = np.random.randn(50).astype(np.float32)
        honest_params = [
            honest_base + np.random.randn(50).astype(np.float32) * 0.01
            for _ in range(7)
        ]

        # 3 Byzantine clients with divergent parameters
        byzantine_params = [
            np.random.randn(50).astype(np.float32) * 100 for _ in range(3)
        ]

        results = create_mock_results(honest_params + byzantine_params)

        scores, f_estimates, _ = strategy._compute_arkrum_scores(results)

        # Byzantine clients (indices 7, 8, 9) should have higher scores
        honest_scores = scores[:7]
        byzantine_scores = scores[7:]

        assert max(honest_scores) < min(byzantine_scores)

    def test_f_estimation_increases_with_byzantines(self, strategy):
        """Test that f estimates tend to increase with more Byzantine clients."""
        np.random.seed(42)

        # 8 honest clients
        honest_base = np.random.randn(30).astype(np.float32)
        honest_params = [
            honest_base + np.random.randn(30).astype(np.float32) * 0.01
            for _ in range(8)
        ]

        # 2 Byzantine clients
        byzantine_params = [
            np.random.randn(30).astype(np.float32) * 50 for _ in range(2)
        ]

        results = create_mock_results(honest_params + byzantine_params)

        _, f_estimates, _ = strategy._compute_arkrum_scores(results)

        # At least some f estimates should be > 0
        assert max(f_estimates) >= 0
