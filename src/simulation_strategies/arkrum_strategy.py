"""
ArKrum: Parameter-free Krum for Robust Aggregation in Federated Learning.

Based on: "Secure and Private Federated Learning: Achieving Adversarial Resilience
through Robust Aggregation" (arXiv:2505.17226)

ArKrum improves upon Krum by:
1. Using median-based filtering to remove extreme outliers before f estimation
2. Applying SSE-based segmentation to automatically estimate Byzantine count (f)
3. Averaging top (n - f) updates closest to the selected update for stability
"""

import logging
import time
from typing import Optional, Union

import numpy as np
from flwr.common import FitRes, Parameters, Scalar, parameters_to_ndarrays
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy import FedAvg

from src.data_models.simulation_strategy_history import SimulationStrategyHistory
from src.utils.status_tracker import StatusTracker


class ArKrumStrategy(FedAvg):
    """
    ArKrum: Parameter-free Krum for Robust Aggregation.

    ArKrum dynamically estimates the number of Byzantine clients (f) without
    requiring prior knowledge, using median-based filtering and SSE segmentation.
    It then averages the top updates closest to the selected Krum winner for
    improved stability in non-IID settings.

    Reference: arXiv:2505.17226
    """

    def __init__(
        self,
        strategy_history: SimulationStrategyHistory,
        remove_clients: bool = False,
        begin_removing_from_round: int = 1,
        status_tracker: Optional[StatusTracker] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.strategy_history = strategy_history
        self.status_tracker = status_tracker
        self.remove_clients = remove_clients
        self.begin_removing_from_round = begin_removing_from_round
        self.current_round = 0
        self.client_scores: dict[str, float] = {}

    def _median_filter_distances(self, sorted_distances: np.ndarray) -> np.ndarray:
        """
        Apply median-based filtering to remove extreme outliers.

        Algorithm 1 from the paper:
        1. Calculate median at position mid = floor(n/2)
        2. Determine delta_max = median - d_i1 (distance from median to smallest)
        3. Set threshold tau = median + delta_max
        4. Remove all distances exceeding tau

        Rationale: Assuming honest majority (< 50% Byzantine), the median
        is guaranteed to be from an honest client.
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
        """
        Estimate number of Byzantine clients using SSE-based segmentation.

        Uses the elbow method on Sum of Squared Errors to find the
        change point that indicates transition from honest to Byzantine
        client distances.

        Constraint: 2 + 2f < n (honest majority assumption)
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
        """
        Compute Krum scores using ArKrum parameter-free approach.

        Steps:
        1. Compute pairwise squared Euclidean distances
        2. For each client, apply median filtering, estimate f, calculate score
        3. Return all scores and per-client f estimates
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
        failures: list[Union[tuple[ClientProxy, FitRes], BaseException]],
    ) -> tuple[Optional[Parameters], dict[str, Scalar]]:
        """
        Aggregate client updates using ArKrum.

        ArKrum Algorithm:
        1. Compute pairwise distances and per-client Krum scores
        2. Select the update with minimum Krum score (u_i*)
        3. Average the top (n - f_i*) updates closest to the selected update
        4. Return the averaged parameters
        """
        self.current_round = server_round
        if self.status_tracker:
            self.status_tracker.update_round(self.current_round)

        if not results:
            return super().aggregate_fit(server_round, results, failures)

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

        for i, (proxy, _) in enumerate(results):
            cid = proxy.cid
            self.client_scores[cid] = arkrum_scores[i]
            self.strategy_history.insert_single_client_history_entry(
                current_round=self.current_round,
                client_id=int(cid),
                removal_criterion=arkrum_scores[i],
                absolute_distance=float(dist_matrix[best_idx, i]),
            )

        return super().aggregate_fit(server_round, selected_results, failures)
