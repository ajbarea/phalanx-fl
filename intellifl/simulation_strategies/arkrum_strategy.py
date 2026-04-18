"""
ArKrum: Parameter-free Krum for Robust Aggregation in Federated Learning.

Based on: "Secure and Private Federated Learning: Achieving Adversarial Resilience
through Robust Aggregation" (arXiv:2505.17226)

ArKrum improves upon Krum by:
1. Using median-based filtering to remove extreme outliers before f estimation
2. Applying SSE-based segmentation to automatically estimate Byzantine count (f)
3. Averaging top (n - f) updates closest to the selected update for stability
"""

from __future__ import annotations

import logging
import time

import numpy as np
from flwr.common import EvaluateRes, FitRes, Parameters, Scalar, parameters_to_ndarrays
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy import FedAvg
from flwr.server.strategy.aggregate import weighted_loss_avg

from intellifl.data_models.simulation_strategy_history import SimulationStrategyHistory
from intellifl.utils.status_tracker import StatusTracker


class ArKrumStrategy(FedAvg):
    """ArKrum: Parameter-free Krum for Robust Aggregation.

    ArKrum dynamically estimates the number of Byzantine clients (f) without
    requiring prior knowledge, using median-based filtering and SSE segmentation.
    It then averages the top updates closest to the selected Krum winner for
    improved stability in non-IID settings.

    Research Foundation:
    - Secure and Private Federated Learning (ArKrum):
      arXiv:2505.17226 (2025) introduced ArKrum as parameter-free extension
      of Krum, using median-based filtering to remove outliers before automatic
      Byzantine count estimation via SSE-based segmentation.

    - Byzantine-Robust FL (arXiv 2024):
      https://arxiv.org/abs/2402.12780
      Confirms importance of adaptive Byzantine detection, as fixed f assumptions
      become vulnerable when client subsampling varies or attacks are intermittent.

    - Centralized FL Security (SpringerLink 2022):
      https://link.springer.com/chapter/10.1007/978-3-032-03705-3_10
      Establishes need for dynamic threat assessment in long-running federations
      where Byzantine client count may change over time.

    - Theoretical Guarantees: ArKrum maintains Byzantine resilience under
      honest majority assumption (f < n/2) with automatic f estimation providing
      robustness to changing attack intensity.
    """

    def __init__(
        self,
        strategy_history: SimulationStrategyHistory,
        remove_clients: bool = False,
        begin_removing_from_round: int = 1,
        status_tracker: StatusTracker | None = None,
        *args,
        **kwargs,
    ):
        """Initialize the ArKrum strategy.

        Args:
            strategy_history: Storage for per-client and per-round metrics.
            remove_clients: Whether to enable permanent client removal based on scores (unused).
            begin_removing_from_round: First round when removal is permitted (unused).
            status_tracker: Optional progress reporting hook for UI or monitoring.
            *args: Forwarded to base FedAvg strategy.
            **kwargs: Forwarded to base FedAvg strategy.
        """
        super().__init__(*args, **kwargs)
        self.strategy_history = strategy_history
        self.status_tracker = status_tracker
        self.remove_clients = remove_clients
        self.begin_removing_from_round = begin_removing_from_round
        self.current_round = 0
        self.client_scores: dict[str, float] = {}

    def _median_filter_distances(self, sorted_distances: np.ndarray) -> np.ndarray:
        """Apply median-based filtering to remove extreme outliers before f estimation.

        Computes threshold tau = median + (median - min) and removes distances exceeding it.
        Assumes honest majority (f < n/2), guaranteeing median represents honest client behavior.
        Implements Algorithm 1 from ArKrum paper (arXiv:2505.17226).
        """
        if len(sorted_distances) <= 2:
            return sorted_distances

        mid = len(sorted_distances) // 2
        median = sorted_distances[mid]
        d_min = sorted_distances[0]

        delta_max = median - d_min
        tau = median + delta_max

        filtered = sorted_distances[sorted_distances <= tau]
        return filtered if len(filtered) > 0 else sorted_distances

    def _estimate_f_sse(self, filtered_distances: np.ndarray) -> int:
        """Estimate Byzantine count (f) using SSE elbow method for automatic segmentation.

        Finds change point in sorted distances indicating honest-to-Byzantine transition
        by minimizing within-subset variance (SSE). Enforces constraint 2 + 2f < n for
        honest majority. Returns f such that first (n - f) clients are considered honest.
        """
        n = len(filtered_distances)
        if n <= 3:
            return 0

        max_f = (n - 2) // 2
        best_f = 0
        min_sse = float("inf")

        for f_candidate in range(max_f + 1):
            k = n - f_candidate
            if k < 3:
                continue

            subset = filtered_distances[:k]
            sse = np.sum((subset - np.mean(subset)) ** 2)

            if sse < min_sse:
                min_sse = sse
                best_f = f_candidate

        return best_f

    def _compute_arkrum_scores(
        self, results: list[tuple[ClientProxy, FitRes]]
    ) -> tuple[list[float], list[int], np.ndarray]:
        """Compute ArKrum scores with automatic per-client Byzantine count estimation.

        For each client: (1) computes pairwise squared L2 distances, (2) applies median-based
        filtering to remove outliers, (3) estimates f via SSE segmentation, (4) computes Krum
        score as sum of distances to (n - f - 2) nearest neighbors. Returns scores, per-client
        f estimates, and distance matrix for later averaging of top updates.

        Side effects:
            - Populates distance matrix dist_matrix with symmetric pairwise squared distances

        Returns:
            Tuple of (scores, f_estimates, dist_matrix) where scores are Krum scores per client,
            f_estimates are per-client Byzantine counts, and dist_matrix is symmetric pairwise
            distance matrix.
        """
        param_data = [parameters_to_ndarrays(fit_res.parameters) for _, fit_res in results]
        flat_params = [np.concatenate([p.flatten() for p in params]) for params in param_data]
        num_clients = len(flat_params)

        dist_matrix = np.zeros((num_clients, num_clients))
        for i in range(num_clients):
            for j in range(i + 1, num_clients):
                dist_sq = np.sum((flat_params[i] - flat_params[j]) ** 2)
                dist_matrix[i, j] = dist_matrix[j, i] = dist_sq

        scores = []
        f_estimates = []

        for i in range(num_clients):
            distances_i = dist_matrix[i, :]
            sorted_distances = np.sort(distances_i)[1:]

            filtered_distances = self._median_filter_distances(sorted_distances)
            f_i = self._estimate_f_sse(filtered_distances)
            f_estimates.append(f_i)

            k_neighbors = max(1, num_clients - f_i - 2)
            score_i = float(np.sum(sorted_distances[:k_neighbors]))
            scores.append(score_i)

        return scores, f_estimates, dist_matrix

    def aggregate_fit(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, FitRes]],
        failures: list[tuple[ClientProxy, FitRes] | BaseException],
    ) -> tuple[Parameters | None, dict[str, Scalar]]:
        """Aggregate client updates using parameter-free ArKrum with automatic f estimation.

        Computes per-client ArKrum scores with dynamic Byzantine count estimation, selects
        client with minimum score as trusted center, then averages the (n - f_best) closest
        updates to that center. Provides robustness without requiring prior knowledge of
        Byzantine client count.

        Side effects:
            - Sets self.current_round to server_round
            - Updates self.client_scores with ArKrum scores
            - Registers client mappings via strategy_history
            - Logs selected client, scores, f estimates, and averaging decisions
            - Records score calculation time and per-client metrics to strategy_history

        Args:
            server_round: Current round number from the Flower server.
            results: List of (ClientProxy, FitRes) tuples from participating clients.
            failures: List of failed client results or exceptions (forwarded to base).

        Returns:
            Tuple of (aggregated_parameters, metrics_dict) from weighted average of
            (n - f_best) closest updates to the selected trusted client.
        """
        self.current_round = server_round
        if self.status_tracker:
            self.status_tracker.update_round(self.current_round)

        if not results:
            return super().aggregate_fit(server_round, results, failures)

        for client_proxy, fit_res in results:
            metrics = getattr(fit_res, "metrics", None)
            if metrics and "partition_id" in metrics:
                partition_id = int(metrics["partition_id"])
                self.strategy_history.register_node_mapping(client_proxy.cid, partition_id)

        num_clients = len(results)

        time_start = time.time_ns()
        arkrum_scores, f_estimates, dist_matrix = self._compute_arkrum_scores(results)
        time_end = time.time_ns()

        best_idx = int(np.argmin(arkrum_scores))
        best_f = f_estimates[best_idx]

        distances_to_best = dist_matrix[best_idx, :]
        m = max(1, num_clients - best_f)
        closest_indices = np.argsort(distances_to_best)[:m]
        selected_results = [results[i] for i in closest_indices]

        logging.info(
            f"Round {server_round}: ArKrum selected client {best_idx} "
            f"(score={arkrum_scores[best_idx]:.4f}, f={best_f}). "
            f"Averaging {m} closest updates."
        )

        self.strategy_history.insert_round_history_entry(
            score_calculation_time_nanos=time_end - time_start
        )

        closest_indices_set = set(closest_indices)
        for i, (proxy, _) in enumerate(results):
            cid = proxy.cid
            self.client_scores[cid] = arkrum_scores[i]
            self.strategy_history.insert_single_client_history_entry(
                current_round=self.current_round,
                client_id=cid,
                removal_criterion=arkrum_scores[i],
                absolute_distance=float(dist_matrix[best_idx, i]),
                aggregation_participation=1 if i in closest_indices_set else 0,
            )

        return super().aggregate_fit(server_round, selected_results, failures)

    def aggregate_evaluate(  # type: ignore[override]
        self,
        server_round: int,
        results: list[tuple[ClientProxy, EvaluateRes]],
        failures: list[tuple[ClientProxy | EvaluateRes, BaseException]],
    ) -> tuple[float | None, dict[str, Scalar]]:
        """Aggregate client evaluation results and record per-client metrics.

        Records per-client accuracy and loss metrics to strategy_history for
        post-simulation analysis and visualization. Computes weighted average
        loss across all participating clients.

        Side effects:
            - Registers client mappings via strategy_history
            - Records per-client accuracy and loss to strategy_history
            - Records round-level aggregated loss to strategy_history

        Args:
            server_round: Current round number from the Flower server.
            results: List of (ClientProxy, EvaluateRes) tuples from participating clients.
            failures: List of failed evaluation results or exceptions (unused).

        Returns:
            Tuple of (aggregated_loss, metrics_dict) where loss is weighted average
            across all clients, or None if no results. metrics_dict is empty.
        """
        self.strategy_history.register_node_mappings_from_results(results)

        for client_proxy, eval_res in results:
            cid = client_proxy.cid
            metrics = eval_res.metrics or {}
            self.strategy_history.insert_single_client_history_entry(
                client_id=cid,
                current_round=self.current_round,
                accuracy=float(metrics.get("accuracy", 0.0)),
            )

        if not results:
            return None, {}

        aggregate_value = []
        for client_proxy, eval_res in results:
            self.strategy_history.insert_single_client_history_entry(
                client_id=client_proxy.cid,
                current_round=self.current_round,
                loss=eval_res.loss,
            )
            aggregate_value.append((eval_res.num_examples, eval_res.loss))

        loss_aggregated = weighted_loss_avg(aggregate_value)
        self.strategy_history.insert_round_history_entry(loss_aggregated=loss_aggregated)

        return loss_aggregated, {}
