from __future__ import annotations

import logging
import time
from typing import Any

import flwr as fl
import numpy as np
import torch
from flwr.common import EvaluateRes, FitRes, Parameters, Scalar
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import weighted_loss_avg
from flwr.server.strategy.fedavg import FedAvg
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

from src.simulation_strategies.termination_policies import (
    TerminationHandler,
    TerminationPolicy,
)


class RFABasedRemovalStrategy(FedAvg):
    """Geometric median-based Byzantine-resilient aggregation with deviation-based removal.

    Extends FedAvg by computing geometric median of client parameters instead of weighted
    average, providing natural robustness to outlier updates. Removes one client per round
    with highest deviation from the computed median. Geometric median generalizes univariate
    median to multivariate spaces, achieving breakdown point of approximately 50% Byzantine
    clients without explicit thresholding or statistical assumptions.

    Research Foundation:
    - Robust Federated Averaging (Original RFA):
      Geometric median-based aggregation naturally filters extreme gradient
      magnifications without explicit detection mechanisms.

    - Byzantine-Robust FL (arXiv 2024):
      https://arxiv.org/abs/2402.12780
      Confirms geometric median as effective Byzantine-robust aggregator,
      especially with adaptive client removal.

    - Centralized FL Security (SpringerLink 2022):
      https://link.springer.com/chapter/10.1007/978-3-032-03705-3_10
      Lists geometric median as standard robust aggregation method alongside
      Krum, trimmed mean, and coordinate-wise median.

    - Statistical Robustness: Geometric median generalizes median to multivariate
      spaces, providing breakdown point of ~50% Byzantine clients.
    """

    def __init__(
        self,
        remove_clients: bool,
        begin_removing_from_round: int,
        weighted_median_factor: float = 1.0,
        termination_policy: str = "graceful",
        min_clients_ratio: float = 0.3,
        num_of_clients: int | None = None,
        *args,
        **kwargs,
    ):
        """Initialize the RFA-based removal strategy.

        Args:
            remove_clients: Whether to enable permanent client removal based on deviation.
            begin_removing_from_round: First round when removal is permitted (warmup period).
            weighted_median_factor: Scaling factor applied to geometric median (typically 1.0).
            termination_policy: Behavior when clients exhausted ("graceful", "strict", "adaptive").
            min_clients_ratio: Minimum fraction of clients required (for adaptive termination).
            num_of_clients: Total client count for termination calculations.
            *args: Forwarded to base FedAvg strategy.
            **kwargs: Forwarded to base FedAvg strategy (strategy_history, status_tracker extracted).
        """
        self.strategy_history = kwargs.pop("strategy_history", None)
        self.status_tracker = kwargs.pop("status_tracker", None)
        kwargs.pop("num_of_malicious_clients", None)  # RFA doesn't use this parameter
        super().__init__(*args, **kwargs)
        self.remove_clients = remove_clients
        self.begin_removing_from_round = begin_removing_from_round
        self.weighted_median_factor = weighted_median_factor
        self.current_round = 0
        self.removed_client_ids: set[Any] = set()
        self.client_scores: dict[Any, float] = {}
        self.num_of_clients = num_of_clients or kwargs.get("min_available_clients", 1)

        # Initialize termination handler for client removal edge cases
        # Research: Byzantine-robust FL requires careful handling of minimum federation size
        # https://arxiv.org/abs/2402.12780
        self.termination_handler = TerminationHandler(
            policy=TerminationPolicy(termination_policy),
            min_clients_threshold=kwargs.get("min_fit_clients", 1),
            min_clients_ratio=min_clients_ratio,
            logger=logging.getLogger(f"rfa_strategy_{id(self)}"),
        )

    def aggregate_fit(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, FitRes]],
        failures: list[tuple[ClientProxy, FitRes] | BaseException],
    ) -> tuple[Parameters | None, dict[str, Scalar]]:
        """Aggregate client updates using geometric median and track deviation-based scores.

        Computes geometric median via iteratively reweighted least squares, measures client
        deviations from this robust center point, performs K-means clustering for additional
        distance metrics, checks termination conditions, and aggregates parameters from
        non-removed clients. Uses deviation as removal criterion for Byzantine detection.

        Side effects:
            - Increments self.current_round
            - Updates self.client_scores with deviation values
            - May trigger termination via TerminationHandler
            - Logs deviation and normalized distance metrics for each client
            - Records score calculation time and per-client metrics to strategy_history

        Args:
            server_round: Current round number from the Flower server.
            results: List of (ClientProxy, FitRes) tuples from participating clients.
            failures: List of failed client results or exceptions (unused).

        Returns:
            Tuple of (aggregated_parameters, metrics_dict) where parameters may be None
            if all clients are removed or termination is triggered, and metrics_dict
            contains either standard aggregation metrics or a termination signal.
        """
        if not results:
            return super().aggregate_fit(server_round, results, failures)

        self.current_round += 1

        # Update status tracker with current round progress
        if self.status_tracker:
            self.status_tracker.update_round(self.current_round)

        if self.strategy_history:
            self.strategy_history.update_client_malicious_status(server_round)

        for client_proxy, fit_res in results:
            metrics = getattr(fit_res, "metrics", None)
            if metrics and "partition_id" in metrics:
                partition_id = int(metrics["partition_id"])
                self.strategy_history.register_node_mapping(client_proxy.cid, partition_id)

        aggregate_clients = []
        for result in results:
            client_id = result[0].cid
            if client_id not in self.removed_client_ids:
                aggregate_clients.append(result)

        if not aggregate_clients:
            return super().aggregate_fit(server_round, [], failures)

        # Check termination condition based on configured policy
        should_stop, reason = self.termination_handler.should_terminate(
            available_clients=len(aggregate_clients),
            total_clients=self.num_of_clients,
            round_num=server_round,
            removed_count=len(self.removed_client_ids),
        )

        if should_stop:
            logging.critical(f"TERMINATION: {reason}")
            # Return special termination signal in metrics
            return None, {
                "termination": True,
                "reason": reason,
                "round": server_round,
                "removed_clients": str(list(self.removed_client_ids)),
                "available_clients": len(aggregate_clients),
                **self.termination_handler.get_termination_summary(),
            }

        param_data = [
            fl.common.parameters_to_ndarrays(fit_res.parameters) for _, fit_res in aggregate_clients
        ]
        stacked_params = np.stack(
            [np.concatenate([p.flatten() for p in params]) for params in param_data]
        )

        time_start_calc = time.time_ns()
        geometric_median = self._geometric_median(stacked_params)
        weighted_geometric_median = geometric_median * self.weighted_median_factor
        time_end_calc = time.time_ns()

        self.strategy_history.insert_round_history_entry(
            score_calculation_time_nanos=time_end_calc - time_start_calc
        )

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

        for i, (client_proxy, _) in enumerate(aggregate_clients):
            client_id = client_proxy.cid
            deviation = float(np.linalg.norm(stacked_params[i] - weighted_geometric_median))
            self.client_scores[client_id] = deviation

            logging.info(
                f"Aggregation round: {server_round} Client ID: {client_id} Deviation: {deviation} Normalized Distance: {normalized_distances[i][0]}"
            )

            self.strategy_history.insert_single_client_history_entry(
                current_round=self.current_round,
                client_id=client_id,
                removal_criterion=deviation,
                absolute_distance=float(distances[i][0]),
            )

        aggregated_parameters_list = []
        start_idx = 0
        for param in param_data[0]:
            param_size = param.size
            aggregated_param = np.reshape(
                weighted_geometric_median[start_idx : start_idx + param_size],
                param.shape,
            )
            aggregated_parameters_list.append(aggregated_param)
            start_idx += param_size
        aggregated_parameters = fl.common.ndarrays_to_parameters(aggregated_parameters_list)
        aggregated_metrics: dict[str, Any] = {}

        return aggregated_parameters, aggregated_metrics

    def _geometric_median(
        self, points: np.ndarray, max_iter: int = 1000, tol: float = 1e-5
    ) -> np.ndarray:
        """Compute geometric median via Weierstrass iteratively reweighted least squares.

        Converges to L1-optimal center point minimizing sum of Euclidean distances
        to all client parameter vectors. Provides natural Byzantine robustness without
        explicit thresholding. Terminates on convergence (delta < tol) or max_iter.
        """
        median = np.mean(points, axis=0)
        for _ in range(max_iter):
            distances = np.linalg.norm(points - median, axis=1)
            non_zero_distances = distances[distances != 0]
            if len(non_zero_distances) == 0:
                return median
            weights = 1 / np.maximum(distances, tol)
            new_median = np.average(points, axis=0, weights=weights)
            if np.linalg.norm(new_median - median) < tol:
                return new_median
            median = new_median
        return median

    def configure_fit(
        self, server_round: int, parameters: Parameters, client_manager
    ) -> list[tuple[ClientProxy, fl.common.FitIns]]:
        """Configure client selection for the next training round.

        During warmup (rounds before begin_removing_from_round), all clients participate.
        After warmup, permanently removes the client with highest deviation from geometric
        median each round. Maintains removed_client_ids set and updates strategy_history
        with participation status.

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

        # Warmup period: no removal before begin_removing_from_round
        if (
            self.begin_removing_from_round is not None
            and self.current_round < self.begin_removing_from_round
        ):
            fit_ins = fl.common.FitIns(parameters, {"server_round": server_round})
            return [(client, fit_ins) for client in available_clients.values()]

        client_scores = {
            client_id: self.client_scores.get(client_id, 0) for client_id in available_clients
        }

        if self.remove_clients:
            client_id = max(client_scores, key=lambda x: client_scores[x])
            logging.info(f"Removing client with highest deviation: {client_id}")
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
            non-removed clients available, otherwise weighted average loss from
            non-removed clients only. metrics_dict is currently empty.
        """
        self.strategy_history.register_node_mappings_from_results(results)

        logging.info("\n" + "-" * 50 + f"AGGREGATION ROUND {server_round}" + "-" * 50)

        for client_result in results:
            cid = client_result[0].cid
            accuracy_matrix = client_result[1].metrics

            self.strategy_history.insert_single_client_history_entry(
                client_id=cid,
                current_round=self.current_round,
                accuracy=accuracy_matrix.get("accuracy"),
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

            if client_id not in self.removed_client_ids:
                aggregate_value.append((evaluate_res.num_examples, evaluate_res.loss))
                number_of_clients_in_loss_calc += 1

        if not aggregate_value:
            logging.warning(
                f"Round {server_round}: No clients available for evaluation "
                f"(all {len(results)} clients removed). Returning None for loss."
            )
            return None, {}

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
