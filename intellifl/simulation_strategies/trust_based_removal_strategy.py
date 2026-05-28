from __future__ import annotations

import gc
import logging
import math as m
from typing import Any

import flwr as fl
import numpy as np
import torch
from flwr.common import EvaluateRes, FitRes, Parameters, Scalar
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import weighted_loss_avg
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

from intellifl.data_models.simulation_strategy_history import SimulationStrategyHistory
from intellifl.output_handlers.directory_handler import DirectoryHandler
from intellifl.simulation_strategies.termination_policies import (
    TerminationHandler,
    TerminationPolicy,
)
from intellifl.utils.status_tracker import StatusTracker


class TrustBasedRemovalStrategy(fl.server.strategy.FedAvg):
    """Trust and reputation-based Byzantine-resilient aggregation with two-phase removal.

    Extends Flower's FedAvg by maintaining historical reputation and trust scores for
    each client. Uses beta-weighted exponential smoothing to track behavior over time,
    with distance from federation centroid as the primary signal. Employs two-phase
    removal: first round removes single lowest-trust client, subsequent rounds use
    threshold-based batch removal for aggressive filtering.

    Research Foundation:
    - Byzantine Client Detection (ACM 2024):
      https://dl.acm.org/doi/10.1145/3708036.3708276
      Privacy-preserving Byzantine detection via reputation systems and statistical filtering.

    - Trust Management in FL: Beta reputation models provide probabilistic trust
      assessment based on historical behavior patterns.

    - Byzantine-Robust FL (arXiv 2024):
      https://arxiv.org/abs/2402.12780
      Historical tracking counters adaptive attacks that change behavior over time.

    - Centralized FL Security (SpringerLink 2022):
      https://link.springer.com/chapter/10.1007/978-3-032-03705-3_10
      Trust-based filtering established as robust aggregation standard.
    """

    def __init__(
        self,
        remove_clients: bool,
        beta_value: float,
        trust_threshold: float,
        begin_removing_from_round: int,
        strategy_history: SimulationStrategyHistory,
        status_tracker: StatusTracker | None = None,
        termination_policy: str = "graceful",
        min_clients_ratio: float = 0.3,
        num_of_clients: int | None = None,
        *args,
        **kwargs,
    ):
        """Initialize the trust-based removal strategy.

        Args:
            remove_clients: Whether to enable permanent client removal based on trust scores.
            beta_value: Exponential smoothing factor for trust/reputation updates (0-1).
            trust_threshold: Minimum trust score required for participation after warmup.
            begin_removing_from_round: First round when removal is permitted (warmup period).
            strategy_history: Storage for per-client and per-round metrics.
            status_tracker: Optional progress reporting hook for UI or monitoring.
            termination_policy: Behavior when clients exhausted ("graceful", "strict", "adaptive").
            min_clients_ratio: Minimum fraction of clients required (for adaptive termination).
            num_of_clients: Total client count for termination calculations.
            *args: Forwarded to base FedAvg strategy.
            **kwargs: Forwarded to base FedAvg strategy.
        """
        super().__init__(*args, **kwargs)

        self.client_reputations: dict[Any, float] = {}
        self.current_round = 0
        self.client_trusts: dict[Any, float] = {}
        self.removed_client_ids: set[Any] = set()

        self.remove_clients = remove_clients
        self.beta_value = beta_value
        self.trust_threshold = trust_threshold
        self.begin_removing_from_round = begin_removing_from_round
        self.num_of_clients = num_of_clients or kwargs.get("min_available_clients", 1)

        self.strategy_history = strategy_history
        self.status_tracker = status_tracker

        self.termination_handler = TerminationHandler(
            policy=TerminationPolicy(termination_policy),
            min_clients_threshold=kwargs.get("min_fit_clients", 1),
            min_clients_ratio=min_clients_ratio,
            logger=logging.getLogger(f"trust_strategy_{id(self)}"),
            output_dir=DirectoryHandler.dirname,
        )

    def calculate_reputation(self, client_id, truth_value):
        """Calculate reputation from normalized distance (truth value).

        First round initializes to current distance; subsequent rounds apply
        exponential smoothing with round-dependent penalty for low performers.
        """
        if self.current_round == 1:
            return truth_value
        else:
            prev_reputation = self.client_reputations.get(client_id, 0)
            return self.update_reputation(prev_reputation, truth_value, self.current_round)

    def update_reputation(self, prev_reputation, truth_value, current_round):
        """Update reputation using exponential decay with performance-dependent penalties.

        Applies beta-weighted smoothing: high performers get linear updates, low
        performers (<0.5) incur exponential penalties. Bounded to [0, 1].
        """
        if truth_value >= 0.5:
            updated_reputation = (prev_reputation + truth_value) - (prev_reputation / current_round)
        else:
            temp = -(1 - (truth_value * (prev_reputation / current_round)))
            updated_reputation = (prev_reputation + truth_value) - np.exp(temp)
        updated_reputation = (
            self.beta_value * updated_reputation + (1 - self.beta_value) * prev_reputation
        )

        if updated_reputation > 1.0:
            return 1.0
        elif updated_reputation < 0.0:
            return 0.0

        return updated_reputation[0]

    def calculate_trust(self, client_id, reputation, d):
        """Calculate trust score from reputation and distance.

        First round initializes to zero; subsequent rounds apply geometric combination.
        """
        if self.current_round == 1:
            prev_trust: float = 0.0
        else:
            prev_trust = self.client_trusts.get(client_id, 0.0)
        return self.update_trust(prev_trust, reputation, d)

    def update_trust(self, prev_trust, reputation, d):
        """Update trust using geometric distance metric with beta smoothing.

        Computes trust as L2 norm difference between (reputation, distance) and (1-reputation, 1-distance).
        Applies exponential smoothing and bounds to [0, 1].
        """
        if hasattr(d, "item"):
            d = d.item()
        if hasattr(reputation, "item"):
            reputation = reputation.item()
        if hasattr(prev_trust, "item"):
            prev_trust = prev_trust.item()

        trust = m.sqrt(m.pow(reputation, 2) + m.pow(d, 2)) - m.sqrt(
            m.pow(1 - reputation, 2) + m.pow(1 - d, 2)
        )
        trust = self.beta_value * trust + (1 - self.beta_value) * prev_trust

        if trust > 1.0:
            trust = 1.0
        if trust < 0.0:
            trust = 0.0
        return trust

    def aggregate_fit(
        self,
        server_round: int,
        results: list[tuple[fl.server.client_proxy.ClientProxy, fl.common.FitRes]],
        failures: list[tuple[ClientProxy, FitRes] | BaseException],
    ) -> tuple[Parameters | None, dict[str, Scalar]]:
        """Aggregate client updates and update reputation/trust scores for Byzantine detection.

        Computes K-means centroid, measures normalized distances, updates reputation and trust
        scores using geometric distance metrics, checks termination conditions, and aggregates
        parameters from non-removed clients.

        Side effects:
            - Increments self.current_round
            - Updates self.client_reputations and self.client_trusts
            - May trigger termination via TerminationHandler
            - Logs reputation, trust, and distance metrics for each client
            - Records metrics to strategy_history including removal threshold

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
            return None, {}

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

        aggregated_parameters, aggregated_metrics = super().aggregate_fit(
            server_round, aggregate_clients, failures
        )

        if aggregated_parameters is None:
            return None, {}

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

        for i, (client_proxy, _) in enumerate(results):
            client_id = client_proxy.cid
            truth_value = 1 - normalized_distances[i]

            new_reputation = self.calculate_reputation(client_id, truth_value)
            new_trust = self.calculate_trust(client_id, new_reputation, truth_value)

            self.client_reputations[client_id] = new_reputation
            self.client_trusts[client_id] = new_trust

            is_participating = 1 if client_id not in self.removed_client_ids else 0

            self.strategy_history.insert_single_client_history_entry(
                current_round=self.current_round,
                client_id=client_id,
                removal_criterion=float(new_trust.item())
                if hasattr(new_trust, "item")
                else float(new_trust),
                absolute_distance=float(distances[i][0].item())
                if hasattr(distances[i][0], "item")
                else float(distances[i][0]),
                aggregation_participation=is_participating,
            )

            logging.info(
                f"Aggregation round: {server_round} "
                f"Client ID: {client_id} "
                f"Reputation: {new_reputation} "
                f"Trust: {new_trust} "
                f"Normalized Distance: {normalized_distances[i][0]} "
            )

        self.strategy_history.insert_round_history_entry(removal_threshold=self.trust_threshold)

        gc.collect()

        return aggregated_parameters, aggregated_metrics

    def configure_fit(self, server_round, parameters, client_manager):
        """Configure client selection for the next training round.

        During warmup, all clients participate. After warmup, removes clients
        with trust scores below the threshold.

        Args:
            server_round: Current round number from the Flower server.
            parameters: Current global model parameters to distribute.
            client_manager: Flower client manager for accessing clients.

        Returns:
            List of (ClientProxy, FitIns) tuples for selected clients.
        """
        available_clients = client_manager.all()

        # Warmup period: no removal before begin_removing_from_round
        if self.current_round < self.begin_removing_from_round:
            fit_ins = fl.common.FitIns(parameters, {"server_round": server_round})
            return [(client, fit_ins) for client in available_clients.values()]

        client_trusts = {
            client_id: self.client_trusts.get(client_id, 0) for client_id in available_clients
        }

        if self.remove_clients:
            if self.current_round == self.begin_removing_from_round:
                client_id = min(client_trusts, key=lambda x: client_trusts[x])
                logging.info(f"Removing client with lowest TRUST: {client_id}")
                self.removed_client_ids.add(client_id)
            else:
                for client_id, trust in client_trusts.items():
                    if trust < self.trust_threshold and client_id not in self.removed_client_ids:
                        logging.info(f"Removing client with TRUST less than Threshold: {client_id}")
                        self.removed_client_ids.add(client_id)

            logging.info(f"removed clients are : {self.removed_client_ids}")

        sorted_client_ids = sorted(client_trusts, key=lambda x: client_trusts[x], reverse=True)
        selected_client_ids = sorted_client_ids
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
        """Aggregate client evaluation results and record metrics.

        Records per-client accuracy and loss to strategy_history. Computes
        weighted average loss from non-removed clients only.

        Args:
            server_round: Current round number from the Flower server.
            results: List of (ClientProxy, EvaluateRes) tuples from clients.
            failures: List of failed evaluation results or exceptions.

        Returns:
            Tuple of (aggregated loss, metrics dict).
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
            f"Aggregated loss: {loss_aggregated} "
        )

        return loss_aggregated, metrics_aggregated
