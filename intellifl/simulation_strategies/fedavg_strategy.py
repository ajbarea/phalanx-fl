from __future__ import annotations

import logging

import flwr as fl
from flwr.common import EvaluateRes, FitRes, Parameters, Scalar
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import weighted_loss_avg

from intellifl.data_models.simulation_strategy_history import SimulationStrategyHistory
from intellifl.utils.status_tracker import StatusTracker


class FedAvgStrategy(fl.server.strategy.FedAvg):
    """FedAvg strategy with round-level metrics tracking.

    Extends Flower's FedAvg strategy by recording per-client and aggregated
    loss and accuracy metrics for each training round. This enables detailed
    post-round analysis while preserving standard FedAvg behavior.

    FedAvg performs weighted averaging of client model parameters and serves
    as the canonical baseline for federated learning research.

    Research Foundation:
    - Communication-Efficient Learning of Deep Networks (McMahan et al., 2017):
      https://arxiv.org/abs/1602.05629
    - Byzantine-Robust FL (arXiv 2024):
      https://arxiv.org/abs/2402.12780
    - Centralized FL Security (SpringerLink 2022):
      https://link.springer.com/chapter/10.1007/978-3-032-03705-3_10
    """

    def __init__(
        self,
        strategy_history: SimulationStrategyHistory,
        status_tracker: StatusTracker | None = None,
        *args,
        **kwargs,
    ):
        """Initialize the FedAvg strategy with metric tracking support.

        Args:
            strategy_history: Storage for per-client and per-round metrics.
            status_tracker: Optional progress reporting hook for UI or monitoring.
            *args: Forwarded to base FedAvg strategy.
            **kwargs: Forwarded to base FedAvg strategy.
        """
        super().__init__(*args, **kwargs)
        self.strategy_history = strategy_history
        self.status_tracker = status_tracker
        self.current_round = 0
        self.logger = logging.getLogger(f"fedavg_strategy_{id(self)}")
        self.logger.setLevel(logging.INFO)

    def aggregate_fit(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, FitRes]],
        failures: list[tuple[ClientProxy, FitRes] | BaseException],
    ) -> tuple[Parameters | None, dict[str, Scalar]]:
        """Aggregate client updates using weighted average and track round state.

        Computes weighted average of client parameters based on dataset size, providing
        the canonical FedAvg baseline. Registers node mappings and updates round tracking
        before delegating to base FedAvg implementation.

        Side effects:
            - Sets self.current_round to server_round
            - Updates status_tracker with current round (if provided)
            - Registers client mappings via strategy_history

        Args:
            server_round: Current round number from the Flower server.
            results: List of (ClientProxy, FitRes) tuples from participating clients.
            failures: List of failed client results or exceptions (forwarded to base).

        Returns:
            Tuple of (aggregated_parameters, metrics_dict) from base FedAvg weighted averaging.
        """
        self.current_round = server_round

        # Update status tracker with current round progress
        if self.status_tracker:
            self.status_tracker.update_round(self.current_round)

        for client_proxy, fit_res in results:
            metrics = getattr(fit_res, "metrics", None)
            if metrics and "partition_id" in metrics:
                partition_id = int(metrics["partition_id"])
                self.strategy_history.register_node_mapping(client_proxy.cid, partition_id)

            # Record that this client participated in the aggregation
            self.strategy_history.insert_single_client_history_entry(
                client_id=client_proxy.cid,
                current_round=self.current_round,
                aggregation_participation=1,
            )

        return super().aggregate_fit(server_round, results, failures)

    def aggregate_evaluate(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, EvaluateRes]],
        failures: list[tuple[ClientProxy, EvaluateRes] | BaseException],
    ) -> tuple[float | None, dict[str, Scalar]]:
        """Aggregate client evaluation results and compute weighted average metrics.

        Computes weighted average loss and accuracy across all clients based on dataset
        size. Records per-client and round-level metrics for historical analysis and
        comparison with Byzantine-resilient strategies.

        Side effects:
            - Registers client mappings via strategy_history
            - Records per-client loss and accuracy to strategy_history
            - Appends aggregated_loss and average_accuracy to strategy_history round lists
            - Logs per-client metrics (debug level) and round summary (info level)

        Args:
            server_round: Current round number from the Flower server.
            results: List of (ClientProxy, EvaluateRes) tuples from participating clients.
            failures: List of failed evaluation results or exceptions (unused).

        Returns:
            Tuple of (aggregated_loss, metrics_dict) where loss is None if no
            results available, otherwise weighted average loss. metrics_dict contains
            weighted average accuracy.
        """
        self.strategy_history.register_node_mappings_from_results(results)

        if not results:
            return None, {}

        # Collect per-client metrics
        total_examples = 0
        weighted_accuracy_sum = 0.0
        aggregate_loss_values = []

        for client_proxy, evaluate_res in results:
            node_id = client_proxy.cid
            num_examples = evaluate_res.num_examples
            loss = evaluate_res.loss
            accuracy = float(evaluate_res.metrics.get("accuracy", 0.0))

            # Store per-client metrics
            self.strategy_history.insert_single_client_history_entry(
                client_id=node_id,
                current_round=self.current_round,
                loss=loss,
                accuracy=accuracy,
            )

            # Accumulate for aggregation
            aggregate_loss_values.append((num_examples, loss))
            weighted_accuracy_sum += accuracy * num_examples
            total_examples += num_examples

            self.logger.debug(
                f"Round {server_round} - Client {node_id}: "
                f"loss={loss:.4f}, accuracy={accuracy:.4f}, examples={num_examples}"
            )

        # Calculate aggregated metrics
        loss_aggregated = weighted_loss_avg(aggregate_loss_values)
        average_accuracy = 0.0
        if total_examples > 0:
            average_accuracy = weighted_accuracy_sum / total_examples

        # Store round-level metrics
        self.strategy_history.rounds_history.aggregated_loss_history.append(loss_aggregated)
        self.strategy_history.rounds_history.average_accuracy_history.append(average_accuracy)

        self.logger.info(
            f"Round {server_round}: "
            f"Aggregated loss={loss_aggregated:.4f}, "
            f"Average accuracy={average_accuracy:.4f} "
            f"({len(results)} clients)"
        )

        metrics_aggregated: dict[str, Scalar] = {"accuracy": average_accuracy}

        return loss_aggregated, metrics_aggregated
