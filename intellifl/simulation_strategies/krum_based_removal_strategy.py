from __future__ import annotations

import gc
import logging
import time
from typing import Any

import flwr as fl
import numpy as np
import torch
from flwr.common import EvaluateRes, FitRes, Parameters, Scalar
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import weighted_loss_avg
from flwr.server.strategy.krum import Krum
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

from intellifl.data_models.simulation_strategy_history import SimulationStrategyHistory
from intellifl.utils.status_tracker import StatusTracker


class KrumBasedRemovalStrategy(Krum):
    """Krum-based Byzantine-resilient aggregation with client removal.

    Implements a Krum-inspired aggregation strategy that scores client updates
    based on pairwise parameter distances and selects the most trusted client
    for aggregation each round. Optionally removes high-scoring clients over
    time to mitigate persistent Byzantine behavior.

    This strategy extends Flower's Krum implementation with round tracking,
    client removal, and detailed metric logging for experimental analysis.

    Research Foundation:
    - Machine Learning with Adversaries: Byzantine Tolerant Gradient Descent (Krum):
      Krum achieves Byzantine resilience by distance-based neighbor proximity,
      with theoretical guarantees for f < n/2 - 2 Byzantine clients.

    - Byzantine-Robust FL (arXiv 2024):
      https://arxiv.org/abs/2402.12780
      Confirms Krum as effective distance-based Byzantine defense, especially
      when combined with adaptive client removal.

    - Centralized FL Security (SpringerLink 2022):
      https://link.springer.com/chapter/10.1007/978-3-032-03705-3_10
      Lists Krum as standard robust aggregation with distance-based filtering.
    """

    def __init__(
        self,
        remove_clients: bool,
        num_malicious_clients: int,
        num_krum_selections: int,
        begin_removing_from_round: int,
        strategy_history: SimulationStrategyHistory,
        status_tracker: StatusTracker | None = None,
        *args,
        **kwargs,
    ):
        """Initialize the Krum-based removal strategy.

        Args:
            remove_clients: Whether to enable permanent client removal based on Krum scores.
            num_malicious_clients: Expected number of Byzantine clients (used for f parameter).
            num_krum_selections: Number of closest neighbors considered in Krum score calculation.
            begin_removing_from_round: First round when removal is permitted (warmup period).
            strategy_history: Storage for per-client and per-round metrics.
            status_tracker: Optional progress reporting hook for UI or monitoring.
            *args: Forwarded to base Krum strategy.
            **kwargs: Forwarded to base Krum strategy.
        """
        super().__init__(*args, **kwargs)
        self.client_scores: dict[Any, float] = {}
        self.removed_client_ids: set[Any] = set()
        self.remove_clients = remove_clients
        self.num_malicious_clients = num_malicious_clients
        self.begin_removing_from_round = begin_removing_from_round
        self.current_round = 0
        self.num_krum_selections = num_krum_selections

        self.strategy_history = strategy_history
        self.status_tracker = status_tracker

    def _calculate_krum_scores(
        self, results: list[tuple[ClientProxy, FitRes]], distances: np.ndarray
    ) -> list[float]:
        """Calculate Krum scores using sum of distances to (n - f - 2) nearest neighbors.

        Computes pairwise L2 distances between all client parameter vectors, then for each
        client sums distances to its closest neighbors (excluding self and f furthest clients).
        Lower scores indicate higher trust (proximity to honest cluster).

        Side effects:
            - Modifies distances matrix in-place with computed pairwise L2 norms

        Args:
            results: List of (ClientProxy, FitRes) tuples containing client parameters.
            distances: Preallocated square matrix for storing symmetric pairwise distances.

        Returns:
            List of Krum scores (one per client), where lower values indicate higher trust.

        Raises:
            ValueError: If num_malicious_clients is None (must be set in config).
        """
        if self.num_malicious_clients is None:
            raise ValueError(
                "num_of_malicious_clients must be set in config for Krum-based strategies. "
                "Calculate from attack_schedule (e.g., 20% of 10 clients = 2)"
            )
        raw_param_data = [
            fl.common.parameters_to_ndarrays(fit_res.parameters) for _, fit_res in results
        ]
        flat_params = [np.concatenate([p.flatten() for p in params]) for params in raw_param_data]
        num_clients = len(flat_params)

        for i in range(num_clients):
            for j in range(i + 1, num_clients):
                distances[i, j] = np.linalg.norm(flat_params[i] - flat_params[j])  # type: ignore[operator]
                distances[j, i] = distances[i, j]

        scores = []
        for i in range(num_clients):
            sorted_distances = np.sort(distances[i])
            # Sum distances to (n - f - 2) nearest neighbors
            num_neighbors = num_clients - self.num_malicious_clients - 2
            score = np.sum(sorted_distances[:num_neighbors])
            scores.append(score)
        return scores

    def aggregate_fit(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, FitRes]],
        failures: list[tuple[ClientProxy, FitRes] | BaseException],
    ) -> tuple[Parameters | None, dict[str, Scalar]]:
        """Aggregate client updates by selecting single lowest-Krum-score client.

        Computes Krum scores for all clients based on pairwise parameter distances,
        performs K-means clustering for additional distance metrics, selects the
        most trusted client (minimum Krum score), and aggregates using only that
        client's parameters. Records timing and per-client metrics for analysis.

        Side effects:
            - Increments self.current_round
            - Updates self.client_scores with Krum scores
            - Registers client mappings via strategy_history
            - Logs Krum scores, normalized distances, and selected client
            - Records score calculation time and per-client metrics to strategy_history

        Args:
            server_round: Current round number from the Flower server.
            results: List of (ClientProxy, FitRes) tuples from participating clients.
            failures: List of failed client results or exceptions (forwarded to base).

        Returns:
            Tuple of (aggregated_parameters, metrics_dict) from the single selected
            client's parameters, or base FedAvg behavior if no results.
        """
        self.current_round += 1

        # Update status tracker with current round progress
        if self.status_tracker:
            self.status_tracker.update_round(self.current_round)

        if self.strategy_history:
            self.strategy_history.update_client_malicious_status(server_round)

        if not results:
            return super().aggregate_fit(server_round, results, failures)

        for client_proxy, fit_res in results:
            metrics = getattr(fit_res, "metrics", None)
            if metrics and "partition_id" in metrics:
                partition_id = int(metrics["partition_id"])
                self.strategy_history.register_node_mapping(client_proxy.cid, partition_id)

        clustering_param_data = []
        for client_proxy, fit_res in results:
            client_params = fl.common.parameters_to_ndarrays(fit_res.parameters)
            params_tensor_list = [torch.Tensor(arr) for arr in client_params]
            flattened_param_list = [param.flatten() for param in params_tensor_list]
            param_tensor = torch.cat(flattened_param_list)
            clustering_param_data.append(param_tensor)

        X = np.array(clustering_param_data)
        del clustering_param_data  # No longer needed after X created
        kmeans = KMeans(n_clusters=1, init="k-means++").fit(X)
        distances = kmeans.transform(X)
        del kmeans, X  # No longer needed after distances computed

        scaler = MinMaxScaler()
        scaler.fit(distances)
        normalized_distances = scaler.transform(distances)
        del scaler  # No longer needed after normalized_distances computed

        distances = np.zeros((len(results), len(results)))

        time_start_calc = time.time_ns()

        krum_scores = self._calculate_krum_scores(results, distances)
        del distances  # No longer needed after krum_scores computed
        time_end_calc = time.time_ns()

        self.strategy_history.insert_round_history_entry(
            score_calculation_time_nanos=time_end_calc - time_start_calc
        )

        for i, (client_proxy, _) in enumerate(results):
            client_id = client_proxy.cid
            score = float(krum_scores[i])
            self.client_scores[client_id] = score

            self.strategy_history.insert_single_client_history_entry(
                current_round=self.current_round,
                client_id=client_id,
                removal_criterion=float(score),
                absolute_distance=float(normalized_distances[i][0]),
            )

            logging.info(
                f"Aggregation round: {server_round} Client ID: {client_id} Krum Score: {score} Normalized Distance: {normalized_distances[i][0]}"
            )

        min_krum_score_index = np.argmin(krum_scores)
        min_krum_client = results[min_krum_score_index]
        selected_client_id = min_krum_client[0].cid
        logging.info(
            f"Selected client for aggregation: {selected_client_id} with Krum Score: {krum_scores[min_krum_score_index]}"
        )

        selected_clients = [min_krum_client]
        aggregated_parameters, aggregated_metrics = super().aggregate_fit(
            server_round, selected_clients, failures
        )

        del krum_scores, normalized_distances  # Cleanup remaining intermediates
        gc.collect()

        return aggregated_parameters, aggregated_metrics

    def configure_fit(
        self, server_round: int, parameters: Parameters, client_manager
    ) -> list[tuple[ClientProxy, fl.common.FitIns]]:
        """Configure client selection for the next training round.

        During warmup (rounds up to begin_removing_from_round), all clients participate.
        After warmup, permanently removes the client with highest Krum score each round.
        Maintains removed_client_ids set and updates strategy_history with participation.

        Side effects:
            - Adds client_id to self.removed_client_ids (if remove_clients enabled)
            - Updates strategy_history.update_client_participation()
            - Logs removal decisions and current removed set

        Args:
            server_round: Current round number from the Flower server.
            parameters: Current global model parameters to distribute.
            client_manager: Flower client manager for accessing clients.

        Returns:
            List of (ClientProxy, FitIns) tuples for selected clients, excluding removed clients.
        """
        available_clients = client_manager.all()

        if (
            self.begin_removing_from_round is not None
            and self.current_round <= self.begin_removing_from_round
        ):
            fit_ins = fl.common.FitIns(parameters, {"server_round": server_round})
            return [(client, fit_ins) for client in available_clients.values()]

        client_scores = {
            client_id: self.client_scores.get(client_id, 0) for client_id in available_clients
        }

        if self.remove_clients:
            client_id = max(client_scores, key=lambda x: client_scores[x])
            logging.info(f"Removing client with highest Krum score: {client_id}")
            self.removed_client_ids.add(client_id)

        logging.info(f"removed clients are : {self.removed_client_ids}")

        selected_client_ids = sorted(client_scores, key=lambda x: client_scores[x], reverse=True)
        fit_ins = fl.common.FitIns(parameters, {"server_round": server_round})

        self.strategy_history.update_client_participation(
            current_round=self.current_round, removed_client_ids=self.removed_client_ids
        )

        return [
            (available_clients[cid], fit_ins)
            for cid in selected_client_ids
            if cid in available_clients
        ]

    def aggregate_evaluate(  # type: ignore[override]
        self,
        server_round: int,
        results: list[tuple[ClientProxy, EvaluateRes]],
        failures: list[tuple[ClientProxy | EvaluateRes, BaseException]],
    ) -> tuple[float | None, dict[str, Scalar]]:
        """Aggregate client evaluation results and record per-client metrics.

        Computes weighted average loss from non-removed clients only, ensuring removed
        clients do not influence global model quality assessment. Records per-client
        accuracy and loss for historical analysis and Byzantine behavior tracking.

        Side effects:
            - Registers client mappings via strategy_history
            - Records per-client accuracy and loss to strategy_history
            - Records round-level aggregated loss to strategy_history
            - Logs aggregation round header, per-client metrics, and summary statistics

        Args:
            server_round: Current round number from the Flower server.
            results: List of (ClientProxy, EvaluateRes) tuples from participating clients.
            failures: List of failed evaluation results or exceptions (unused).

        Returns:
            Tuple of (aggregated_loss, metrics_dict) where loss is None if no
            results available, otherwise weighted average loss from non-removed
            clients only. metrics_dict is currently empty.
        """
        self.strategy_history.register_node_mappings_from_results(results)

        logging.info("\n" + "-" * 50 + f"AGGREGATION ROUND {server_round}" + "-" * 50)

        for client_result in results:
            cid = client_result[0].cid
            accuracy_matrix = client_result[1].metrics
            accuracy_matrix["cid"] = cid

            self.strategy_history.insert_single_client_history_entry(
                client_id=cid,
                current_round=self.current_round,
                accuracy=float(accuracy_matrix.get("accuracy", 0.0)),
            )

        if not results:
            return None, {}

        aggregate_value = []
        number_of_clients_in_loss_calc = 0

        for client_metadata, evaluate_res in results:
            self.strategy_history.insert_single_client_history_entry(
                client_id=client_metadata.cid,
                current_round=self.current_round,
                loss=evaluate_res.loss,
            )

            if client_metadata.cid not in self.removed_client_ids:
                aggregate_value.append((evaluate_res.num_examples, evaluate_res.loss))
                number_of_clients_in_loss_calc += 1

        loss_aggregated = weighted_loss_avg(aggregate_value)

        self.strategy_history.insert_round_history_entry(loss_aggregated=loss_aggregated)

        for result in results:
            logging.debug(f"Client ID: {result[0].cid}")
            logging.debug(f"Metrics: {result[1].metrics}")
            logging.debug(f"Loss: {result[1].loss}")

        metrics_aggregated: dict[str, Any] = {}

        logging.info(
            f"Round: {server_round} "
            f"Number of aggregated clients: {number_of_clients_in_loss_calc} "
            f"Aggregated loss: {loss_aggregated}"
        )
        return loss_aggregated, metrics_aggregated
