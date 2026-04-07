from __future__ import annotations

import logging
from typing import Any

import flwr as fl
import numpy as np
from flwr.common import (
    EvaluateRes,
    Parameters,
    Scalar,
    ndarrays_to_parameters,
    parameters_to_ndarrays,
)
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import weighted_loss_avg
from flwr.server.strategy.fedavg import FedAvg

from intellifl.data_models.simulation_strategy_history import SimulationStrategyHistory
from intellifl.utils.status_tracker import StatusTracker


class TrimmedMeanBasedRemovalStrategy(FedAvg):
    """Trimmed mean aggregation strategy with client removal.

    Computes coordinate-wise trimmed mean to exclude extreme parameter values,
    tracking trim frequency as removal criterion. Trimmed mean operates
    independently on each parameter dimension, offering Byzantine robustness
    without requiring full gradient comparisons.

    Research Foundation:
    - Byzantine-Robust Stochastic Gradient Descent (Trimmed Mean):
      Coordinate-wise trimming provides dimension-independent Byzantine filtering,
      with breakdown point determined by trim_ratio parameter.

    - Byzantine-Robust FL (arXiv 2024):
      https://arxiv.org/abs/2402.12780
      Confirms trimmed mean as effective statistical outlier filter for
      Byzantine attacks targeting specific model parameters.

    - Centralized FL Security (SpringerLink 2022):
      https://link.springer.com/chapter/10.1007/978-3-032-03705-3_10
      Lists trimmed mean (mean-around-median) as standard robust aggregation,
      effective against weight perturbation attacks.

    - Statistical Robustness: Trimming top/bottom percentiles per coordinate
      provides natural protection against gradient scaling and sign-flipping attacks.
    """

    def __init__(
        self,
        remove_clients: bool,
        begin_removing_from_round: int,
        strategy_history: SimulationStrategyHistory,
        status_tracker: StatusTracker | None = None,
        trim_ratio: float = 0.1,
        *args,
        **kwargs,
    ):
        """Initialize the trimmed mean-based removal strategy.

        Args:
            remove_clients: Whether to enable permanent client removal based on trim frequency.
            begin_removing_from_round: First round when removal is permitted (warmup period).
            strategy_history: Storage for per-client and per-round metrics.
            status_tracker: Optional progress reporting hook for UI or monitoring.
            trim_ratio: Fraction of extreme values to trim from each end (0.1 = 10% top/bottom).
            *args: Forwarded to base FedAvg strategy.
            **kwargs: Forwarded to base FedAvg strategy.
        """
        super().__init__(*args, **kwargs)
        self.remove_clients = remove_clients
        self.begin_removing_from_round = begin_removing_from_round
        self.trim_ratio = trim_ratio
        self.current_round = 0
        self.client_scores: dict[Any, float] = {}

        self.strategy_history = strategy_history
        self.status_tracker = status_tracker

    def aggregate_fit(  # type: ignore[override]
        self, server_round: int, results: list[tuple], failures: list[BaseException]
    ) -> tuple[Parameters | None, dict[str, Scalar]]:
        """Aggregate client updates using coordinate-wise trimmed mean filtering.

        For each parameter coordinate, sorts client values and trims the top and bottom
        trim_ratio fraction before averaging. Tracks per-client trim frequency (fraction
        of parameters where client was trimmed) as Byzantine detection criterion. Provides
        dimension-independent robustness against gradient scaling and sign-flipping attacks.

        Side effects:
            - Increments self.current_round
            - Updates self.client_scores with trim frequencies
            - Registers client mappings via strategy_history
            - Records per-client trim frequency metrics to strategy_history
            - Updates strategy_history with client participation
            - Logs clients with trimmed parameters

        Args:
            server_round: Current round number from the Flower server.
            results: List of (ClientProxy, FitRes) tuples from participating clients.
            failures: List of failed client results or exceptions (unused).

        Returns:
            Tuple of (aggregated_parameters, metrics_dict) where parameters are the
            coordinate-wise trimmed mean, or None if no results. metrics_dict is empty.
        """
        self.current_round += 1

        # Update status tracker with current round progress
        if self.status_tracker:
            self.status_tracker.update_round(self.current_round)

        if self.strategy_history:
            self.strategy_history.update_client_malicious_status(server_round)

        if not results:
            return None, {}

        for client_proxy, fit_res in results:
            metrics = getattr(fit_res, "metrics", None)
            if metrics and "partition_id" in metrics:
                partition_id = int(metrics["partition_id"])
                self.strategy_history.register_node_mapping(client_proxy.cid, partition_id)

        participating_clients = [client.cid for client, _ in results]
        weights_results = [
            (
                parameters_to_ndarrays(fit_res.parameters),
                fit_res.num_examples,
                client.cid,
            )
            for client, fit_res in results
        ]

        num_clients = len(weights_results)
        num_trim = int(self.trim_ratio * num_clients)

        if num_trim == 0:
            aggregated_weights = self._average_weights([w for w, _, _ in weights_results])

            for cid in participating_clients:
                self.client_scores[cid] = 0.0
                self.strategy_history.insert_single_client_history_entry(
                    current_round=self.current_round,
                    client_id=cid,
                    removal_criterion=0.0,
                )

            self.strategy_history.update_client_participation(
                current_round=self.current_round, removed_client_ids=set()
            )
            return ndarrays_to_parameters(aggregated_weights), {}

        weights_by_layer = list(zip(*[w for w, _, _ in weights_results], strict=False))
        aggregated = []
        trimmed_clients: set[str] = set()
        client_trim_counts = {cid: 0 for _, _, cid in weights_results}
        total_parameters = 0

        for layer_weights in weights_by_layer:
            stacked = np.stack(layer_weights)
            trimmed_layer = []
            num_params_in_layer = int(np.prod(stacked.shape[1:])) if len(stacked.shape) > 1 else 1
            total_parameters += num_params_in_layer

            for i in range(num_params_in_layer):
                values = (
                    stacked if len(stacked.shape) == 1 else stacked.reshape((num_clients, -1))[:, i]
                )
                sorted_indices = np.argsort(values)
                trimmed_indices = sorted_indices[num_trim:-num_trim]
                trimmed_values = values[trimmed_indices]
                trimmed_layer.append(np.mean(trimmed_values))

                removed_this_dim = {weights_results[j][2] for j in sorted_indices[:num_trim]}.union(
                    weights_results[j][2] for j in sorted_indices[-num_trim:]
                )
                trimmed_clients.update(removed_this_dim)

                for cid in removed_this_dim:
                    client_trim_counts[cid] += 1

            aggregated.append(np.array(trimmed_layer).reshape(stacked.shape[1:]))

        for cid in participating_clients:
            trim_frequency = float(
                client_trim_counts[cid] / total_parameters if total_parameters > 0 else 0.0
            )
            self.client_scores[cid] = trim_frequency
            self.strategy_history.insert_single_client_history_entry(
                current_round=self.current_round,
                client_id=cid,
                removal_criterion=trim_frequency,
            )

        self.strategy_history.update_client_participation(
            current_round=self.current_round, removed_client_ids=set()
        )

        logging.info(f"clients with trimmed parameters this round: {trimmed_clients}")

        return ndarrays_to_parameters(aggregated), {}

    def configure_fit(
        self, server_round: int, parameters: Parameters, client_manager
    ) -> list[tuple[ClientProxy, fl.common.FitIns]]:
        """Configure client selection for the next training round.

        During warmup (rounds up to begin_removing_from_round), all clients participate.
        After warmup, permanently removes the client with highest trim frequency (most
        often trimmed across parameter coordinates). Maintains local removed set for
        this round's participation tracking.

        Side effects:
            - Updates currently_removed_client_ids local set (if remove_clients enabled)
            - Does NOT persist removals across rounds (stateless removal)

        Args:
            server_round: Current round number from the Flower server.
            parameters: Current global model parameters to distribute.
            client_manager: Flower client manager for accessing clients.

        Returns:
            List of (ClientProxy, FitIns) tuples for selected clients, excluding removed clients.
        """
        currently_removed_client_ids = set()
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
            currently_removed_client_ids.add(client_id)

        selected_client_ids = sorted(client_scores, key=lambda x: client_scores[x], reverse=True)
        fit_ins = fl.common.FitIns(parameters, {"server_round": server_round})

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

        Computes weighted average loss from all participating clients. Unlike removal-based
        strategies, trimmed mean does not maintain persistent removed_client_ids, so all
        clients contribute to loss aggregation. Records per-client accuracy and loss for
        historical analysis.

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
            results available, otherwise weighted average loss from all clients.
            metrics_dict is currently empty.
        """
        self.strategy_history.register_node_mappings_from_results(results)

        logging.info("\n" + "-" * 50 + f"AGGREGATION ROUND {server_round}" + "-" * 50)

        for client_result in results:
            cid = client_result[0].cid
            accuracy_matrix = client_result[1].metrics

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
            client_id = client_metadata.cid

            self.strategy_history.insert_single_client_history_entry(
                client_id=client_id,
                current_round=self.current_round,
                loss=evaluate_res.loss,
            )

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
            f"Aggregated loss: {loss_aggregated} "
        )

        return loss_aggregated, metrics_aggregated

    def _average_weights(self, weights: list[list[np.ndarray]]) -> list[np.ndarray]:
        """Compute simple arithmetic mean of parameter layers across clients."""
        avg_weights = []
        for layers in zip(*weights, strict=False):
            stacked = np.stack(layers, axis=0)
            avg_weights.append(np.mean(stacked, axis=0))
        return avg_weights
