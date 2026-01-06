from __future__ import annotations

import logging

import flwr as fl
from flwr.common import EvaluateRes, FitRes, Parameters, Scalar
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import weighted_loss_avg

from src.data_models.simulation_strategy_history import SimulationStrategyHistory
from src.utils.status_tracker import StatusTracker


class FedAvgStrategy(fl.server.strategy.FedAvg):
    """FedAvg strategy with round-level metrics tracking.

    Extends Flower's FedAvg to collect aggregated loss and accuracy metrics
    per round.
    """

    def __init__(
        self,
        strategy_history: SimulationStrategyHistory,
        status_tracker: StatusTracker | None = None,
        *args,
        **kwargs,
    ):
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
        failures: list[tuple[ClientProxy | FitRes, BaseException]],
    ) -> tuple[Parameters | None, dict[str, Scalar]]:
        """Aggregate fit results and track round number."""
        self.current_round = server_round

        # Update status tracker with current round progress
        if self.status_tracker:
            self.status_tracker.update_round(self.current_round)

        # Register node_id -> partition_id mappings (Flower 1.25+ compatibility)
        # FitRes.metrics contains partition_id set by FlowerClient
        for client_proxy, fit_res in results:
            metrics = getattr(fit_res, "metrics", None)
            if metrics and "partition_id" in metrics:
                partition_id = int(metrics["partition_id"])
                self.strategy_history.register_node_mapping(client_proxy.cid, partition_id)

        return super().aggregate_fit(server_round, results, failures)

    def aggregate_evaluate(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, EvaluateRes]],
        failures: list[tuple[ClientProxy | EvaluateRes, BaseException]],
    ) -> tuple[float | None, dict[str, Scalar]]:
        """Aggregate evaluation results and track round-level metrics.

        Collects per-client loss/accuracy and computes weighted averages.

        Args:
            server_round: Current round number from the Flower server.
            results: List of (ClientProxy, EvaluateRes) tuples from clients.
            failures: List of failed evaluation results or exceptions.

        Returns:
            Tuple of (weighted average loss, metrics dict with accuracy).
        """
        self.strategy_history.register_node_mappings_from_results(results)

        if not results:
            return None, {}

        # Collect per-client metrics
        total_examples = 0
        weighted_accuracy_sum = 0.0
        aggregate_loss_values = []

        for client_proxy, evaluate_res in results:
            node_id = client_proxy.cid  # Flower 1.25+: use node_id directly
            num_examples = evaluate_res.num_examples
            loss = evaluate_res.loss
            accuracy = float(evaluate_res.metrics.get("accuracy", 0.0))

            # Store per-client metrics
            self.strategy_history.insert_single_client_history_entry(
                client_id=node_id,  # Flower 1.25+: node_id translated via get_partition_id()
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
        average_accuracy = weighted_accuracy_sum / total_examples if total_examples > 0 else 0.0

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
