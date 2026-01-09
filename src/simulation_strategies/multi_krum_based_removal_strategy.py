from __future__ import annotations

import logging
import os
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

from src.data_models.simulation_strategy_history import SimulationStrategyHistory
from src.output_handlers.directory_handler import DirectoryHandler
from src.utils.status_tracker import StatusTracker


class MultiKrumBasedRemovalStrategy(Krum):
    """Multi-Krum aggregation with permanent client removal.

    Uses Multi-Krum scoring to identify malicious clients and permanently
    removes them from future rounds once the removal limit is reached.
    Combines Byzantine-resilient aggregation with adaptive client filtering
    for long-term federation health.

    Research Foundation:
    - Machine Learning with Adversaries: Byzantine Tolerant Gradient Descent:
      Multi-Krum scoring provides distance-based Byzantine detection,
      with permanent removal enabling progressive federation hardening
      against persistent attackers.

    - Byzantine-Robust FL (arXiv 2024):
      https://arxiv.org/abs/2402.12780
      Confirms that adaptive client removal based on historical scores
      improves long-term Byzantine resilience, especially against
      adaptive attacks that change behavior over time.

    - Centralized FL Security (SpringerLink 2022):
      https://link.springer.com/chapter/10.1007/978-3-032-03705-3_10
      Establishes permanent removal as effective strategy for persistent
      Byzantine clients in long-running federations.

    - Federated Unlearning (arXiv 2025):
      https://arxiv.org/html/2508.02485
      Client removal aligns with federated unlearning principles,
      ensuring removed malicious clients cannot influence future rounds.
    """

    def __init__(
        self,
        remove_clients: bool,
        num_of_malicious_clients: int,
        num_krum_selections: int,
        begin_removing_from_round: int,
        strategy_history: SimulationStrategyHistory,
        status_tracker: StatusTracker | None = None,
        *args,
        **kwargs,
    ):
        """Initialize the Multi-Krum with permanent removal strategy.

        Args:
            remove_clients: Whether to enable permanent client removal based on scores.
            num_of_malicious_clients: Expected number of Byzantine clients (used for f parameter).
            num_krum_selections: Number of top clients (lowest scores) to aggregate.
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
        self.num_of_malicious_clients = num_of_malicious_clients
        self.num_krum_selections = num_krum_selections
        self.begin_removing_from_round = begin_removing_from_round
        self.current_round = 0
        self.logger = logging.getLogger(f"multi_krum_removal_{id(self)}")
        self.logger.setLevel(logging.INFO)
        out_dir = DirectoryHandler.dirname
        assert out_dir is not None
        os.makedirs(out_dir, exist_ok=True)
        file_handler = logging.FileHandler(f"{out_dir}/output.log")
        console_handler = logging.StreamHandler()
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.propagate = False
        self.strategy_history = strategy_history
        self.status_tracker = status_tracker

    def _calculate_multi_krum_scores(
        self, results: list[tuple[ClientProxy, FitRes]], distances: np.ndarray
    ) -> list[float]:
        """Calculate Multi-Krum scores using sum of distances to closest neighbors.

        Computes pairwise L2 distances, then for each client sums distances to its
        (num_krum_selections - 2) closest neighbors. Lower scores indicate higher trust.

        Side effects:
            - Modifies distances matrix in-place with computed pairwise L2 norms

        Args:
            results: List of (ClientProxy, FitRes) tuples containing client parameters.
            distances: Preallocated square matrix for storing symmetric pairwise distances.

        Returns:
            List of Multi-Krum scores (one per client), where lower values indicate higher trust.
        """
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
            score = np.sum(sorted_distances[: self.num_krum_selections - 2])
            scores.append(score)

        return scores

    def aggregate_fit(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, FitRes]],
        failures: list[tuple[ClientProxy, FitRes] | BaseException],
    ) -> tuple[Parameters | None, dict[str, Scalar]]:
        """Aggregate client updates using Multi-Krum with permanent removal tracking.

        Computes Multi-Krum scores for all clients, performs K-means clustering for distance
        metrics, selects num_krum_selections clients with lowest scores, and aggregates their
        parameters. Tracks scores for subsequent permanent removal decisions in configure_fit.

        Side effects:
            - Increments self.current_round
            - Updates self.client_scores with Multi-Krum scores
            - Registers client mappings via strategy_history
            - Logs Multi-Krum scores and normalized distances for each client
            - Records score calculation time and per-client metrics to strategy_history

        Args:
            server_round: Current round number from the Flower server.
            results: List of (ClientProxy, FitRes) tuples from participating clients.
            failures: List of failed client results or exceptions (forwarded to base).

        Returns:
            Tuple of (aggregated_parameters, metrics_dict) from weighted average of
            selected clients' parameters.
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
        kmeans = KMeans(n_clusters=1, init="k-means++").fit(X)
        distances = kmeans.transform(X)

        scaler = MinMaxScaler()
        scaler.fit(distances)
        normalized_distances = scaler.transform(distances)

        distances = np.zeros((len(results), len(results)))
        time_start_calc = time.time_ns()

        multi_krum_scores = self._calculate_multi_krum_scores(results, distances)

        selected_indices = np.argsort(multi_krum_scores)[: self.num_krum_selections]
        selected_clients = [results[i] for i in selected_indices]
        aggregated_parameters, aggregated_metrics = super().aggregate_fit(
            server_round, selected_clients, failures
        )

        time_end_calc = time.time_ns()

        self.strategy_history.insert_round_history_entry(
            score_calculation_time_nanos=time_end_calc - time_start_calc
        )

        for i, (client_proxy, _) in enumerate(results):
            client_id = client_proxy.cid
            score = float(multi_krum_scores[i])
            self.client_scores[client_id] = score

            self.strategy_history.insert_single_client_history_entry(
                current_round=self.current_round,
                client_id=client_id,
                removal_criterion=float(score),
                absolute_distance=float(distances[i][0]),
            )

            self.logger.info(
                f"Aggregation round: {server_round} Client ID: {client_id} Multi-Krum Score: {score} Normalized Distance: {normalized_distances[i][0]}"
            )

        return aggregated_parameters, aggregated_metrics

    def configure_fit(
        self, server_round: int, parameters: Parameters, client_manager
    ) -> list[tuple[ClientProxy, fl.common.FitIns]]:
        """Configure client selection with progressive permanent removal.

        During warmup (rounds up to begin_removing_from_round), all clients participate.
        After warmup, permanently removes one client with highest Multi-Krum score per round
        until (total_clients - num_krum_selections) clients are removed. Stops removal when
        limit reached to maintain minimum viable federation size.

        Side effects:
            - Adds one client_id to self.removed_client_ids per round (if conditions met)
            - Sets self.remove_clients = False when removal limit reached
            - Updates strategy_history.update_client_participation()
            - Logs removal decisions, limits, and current removed set

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

        total_clients = len(client_scores)
        if (
            self.remove_clients
            and len(self.removed_client_ids) < total_clients - self.num_krum_selections
        ):
            eligible_clients = {
                cid: score
                for cid, score in client_scores.items()
                if cid not in self.removed_client_ids
            }
            if eligible_clients:
                client_id_to_remove = max(eligible_clients, key=lambda x: eligible_clients[x])
                self.logger.info(
                    f"Removing client with highest Multi-Krum score: {client_id_to_remove}"
                )
                self.removed_client_ids.add(client_id_to_remove)

        if len(self.removed_client_ids) >= total_clients - self.num_krum_selections:
            self.logger.info(
                f"Removal limit reached: {total_clients - self.num_krum_selections} clients removed."
            )
            self.remove_clients = False  # Stop further removal

        self.logger.info(f"removed clients are : {self.removed_client_ids}")

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

        Computes weighted average loss from non-removed clients only, ensuring permanently
        removed clients do not influence global model quality assessment. Records per-client
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

        self.logger.info("\n" + "-" * 50 + f"AGGREGATION ROUND {server_round}" + "-" * 50)

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

        self.logger.info(
            f"Round: {server_round} "
            f"Number of aggregated clients: {number_of_clients_in_loss_calc} "
            f"Aggregated loss: {loss_aggregated}"
        )
        return loss_aggregated, metrics_aggregated
