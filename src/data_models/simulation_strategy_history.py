from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from flwr.common import EvaluateRes
    from flwr.server.client_proxy import ClientProxy

from src.attack_utils.poisoning import should_poison_this_round
from src.data_models.client_info import ClientInfo
from src.data_models.round_info import RoundsInfo
from src.data_models.simulation_strategy_config import StrategyConfig
from src.dataset_handlers.dataset_handler import DatasetHandler


@dataclass
class SimulationStrategyHistory:
    strategy_config: StrategyConfig
    dataset_handler: DatasetHandler
    rounds_history: RoundsInfo = field(init=False)
    _clients_dict: dict[int, ClientInfo] = field(default_factory=dict)
    _node_id_to_partition_id: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.rounds_history = RoundsInfo(simulation_strategy_config=self.strategy_config)

        num_clients = self.strategy_config.num_of_clients or 0
        num_rounds = self.strategy_config.num_of_rounds or 0
        for i in range(num_clients):
            self._clients_dict[i] = ClientInfo(
                client_id=i,
                num_of_rounds=num_rounds,
                is_malicious=False,
            )

    def get_all_clients(self) -> list[ClientInfo]:
        """Get list of all ClientInfo instances"""

        return list(self._clients_dict.values())

    def register_node_mapping(self, node_id: str, partition_id: int) -> None:
        """Register a mapping from Flower node_id to internal partition_id.

        In Flower 1.25+, ClientProxy.cid returns node IDs (large integers as strings)
        instead of sequential integers. This method maps those back to our partition IDs.

        Args:
            node_id: The Flower node ID (ClientProxy.cid)
            partition_id: Our internal sequential partition ID (0, 1, 2, ...)
        """
        self._node_id_to_partition_id[str(node_id)] = partition_id

    def get_partition_id(self, node_id: str | int) -> int:
        """Get the internal partition_id for a Flower node_id.

        If the node_id is already a valid partition_id (sequential integer),
        returns it directly for backward compatibility.

        Args:
            node_id: The Flower node ID (ClientProxy.cid) or partition_id

        Returns:
            The internal partition_id (0, 1, 2, ...)

        Raises:
            KeyError: If the node_id is not registered and not a valid partition_id
        """
        node_id_str = str(node_id)

        # Check if it's in our mapping (Flower 1.25+ node IDs)
        if node_id_str in self._node_id_to_partition_id:
            return self._node_id_to_partition_id[node_id_str]

        # For backward compatibility: if it's a small integer that matches a partition_id
        try:
            int_id = int(node_id)
            num_clients = self.strategy_config.num_of_clients or 0
            if 0 <= int_id < num_clients:
                return int_id
        except (ValueError, TypeError):
            pass

        raise KeyError(
            f"Unknown node_id: {node_id}. "
            f"Registered mappings: {len(self._node_id_to_partition_id)}. "
            f"Call register_node_mapping() first or ensure node_id is a valid partition_id."
        )

    def register_node_mappings_from_results(
        self, results: list[tuple[ClientProxy, EvaluateRes]]
    ) -> None:
        """Register node_id -> partition_id mappings from evaluate results.

        Flower 1.25+ returns node IDs instead of sequential partition IDs in
        ClientProxy.cid. This extracts partition_id from client metrics to
        restore the mapping.

        Args:
            results: List of (ClientProxy, EvaluateRes) tuples from aggregate_evaluate
        """
        for client_proxy, eval_res in results:
            metrics = getattr(eval_res, "metrics", None)
            if metrics and "partition_id" in metrics:
                partition_id = int(metrics["partition_id"])
                self.register_node_mapping(client_proxy.cid, partition_id)

    def insert_single_client_history_entry(
        self,
        client_id: int | str,
        current_round: int,
        removal_criterion: float | None = None,
        absolute_distance: float | None = None,
        loss: float | None = None,
        accuracy: float | None = None,
        aggregation_participation: int | None = None,
    ) -> None:
        """Insert history entry for a single client. Only those values provided will be updated.

        Args:
            client_id: Either a Flower node_id (str) or partition_id (int).
                       Will be automatically translated to partition_id if needed.
        """
        # Translate node_id to partition_id if necessary (Flower 1.25+ compatibility)
        partition_id = self.get_partition_id(client_id)
        updating_client: ClientInfo = self._clients_dict[partition_id]

        updating_client.add_history_entry(
            current_round,
            removal_criterion,
            absolute_distance,
            loss,
            accuracy,
            aggregation_participation,
        )

    def insert_round_history_entry(
        self,
        score_calculation_time_nanos: int | None = None,
        removal_threshold: float | None = None,
        loss_aggregated: float | None = None,
    ) -> None:
        """Append the round history info to the history. Only those values provided will be updated."""

        if score_calculation_time_nanos is not None:
            self.rounds_history.score_calculation_time_nanos_history.append(
                score_calculation_time_nanos
            )
        if removal_threshold is not None:
            self.rounds_history.removal_threshold_history.append(removal_threshold)
        if loss_aggregated is not None:
            self.rounds_history.aggregated_loss_history.append(loss_aggregated)

    def update_client_participation(self, current_round: int, removed_client_ids: set[int]) -> None:
        """Update history of client participation based on the IDs of removed clients at the given round."""

        for client_id in removed_client_ids:
            self.insert_single_client_history_entry(
                client_id=int(client_id),
                current_round=current_round,
                aggregation_participation=0,
            )

    def update_client_malicious_status(self, current_round: int) -> None:
        """
        Update client.is_malicious flag based on attack_schedule for the current round.

        Args:
            current_round: Current training round (1-indexed)
        """
        # Only update if attack_schedule is configured
        if not self.strategy_config.attack_schedule:
            return

        num_clients = self.strategy_config.num_of_clients or 0
        # Update each client's malicious status based on current round
        for client_id in range(num_clients):
            should_poison, _ = should_poison_this_round(
                current_round=current_round,
                client_id=client_id,
                attack_schedule=self.strategy_config.attack_schedule,
            )

            # Update the is_malicious flag
            self._clients_dict[client_id].is_malicious = should_poison

    def calculate_additional_rounds_data(self) -> None:
        """
        The primary data that is collected during the simulation is as follows:

        Per-client data ver rounds (stored in ClientInfo):
            loss_history,
            accuracy_history - achieved accuracy during the validation,
            removal_criterion_history - the calculated value based on which the removal is performed,
            absolute_distance_history (to cluster center) - the absolute distance to the center of the cluster of all models

        Per-round data  over rounds (stored in RoundsInfo):
            aggregated_loss_history - loss of all aggregated client models
            score_calculation_time_nanos_history - time that was used to calculate removal_criterion
            removal_threshold_history - removal threshold that was used for exclusion at each round

        The following derivative data is calculated here (for each round):

        average_accuracy_history - average accuracy of all benign clients that are not removed at a given round

        <to be continued>

        """

        num_rounds = self.strategy_config.num_of_rounds or 0
        for round_num in range(num_rounds):
            round_tp_count = 0
            round_tn_count = 0
            round_fp_count = 0
            round_fn_count = 0

            num_aggregated_clients = 0
            sum_aggregated_accuracies = 0.0

            round_client_accuracies: list[float] = []

            for client_info in self.get_all_clients():
                # Determine malicious status for this specific round using attack_schedule
                should_poison, _ = should_poison_this_round(
                    current_round=round_num + 1,  # round_num is 0-indexed
                    client_id=client_info.client_id,
                    attack_schedule=self.strategy_config.attack_schedule,
                )
                client_is_malicious = should_poison
                client_was_aggregated = (
                    client_info.aggregation_participation_history[round_num] == 1
                )

                if self.strategy_config.remove_clients:
                    # true positive: a good client was aggregated
                    if not client_is_malicious and client_was_aggregated:
                        round_tp_count += 1
                    # true negative: a malicious client was not aggregated
                    if client_is_malicious and not client_was_aggregated:
                        round_tn_count += 1
                    # false positive: a good client was not aggregated
                    if not client_is_malicious and not client_was_aggregated:
                        round_fp_count += 1
                    # false negative: a malicious client was aggregated
                    if client_is_malicious and client_was_aggregated:
                        round_fn_count += 1

                # sum of accuracies of aggregated clients
                if client_was_aggregated:
                    num_aggregated_clients += 1
                    accuracy = client_info.accuracy_history[round_num]
                    if accuracy is not None:
                        sum_aggregated_accuracies += accuracy
                        round_client_accuracies.append(accuracy)

            self.rounds_history.append_tp_tn_fp_fn(
                round_tp_count, round_tn_count, round_fp_count, round_fn_count
            )
            self.rounds_history.average_accuracy_history.append(
                sum_aggregated_accuracies / num_aggregated_clients
                if num_aggregated_clients > 0
                else 0.0
            )
            self.rounds_history.average_accuracy_std_history.append(
                float(np.std(round_client_accuracies)) if len(round_client_accuracies) > 1 else 0.0
            )

        if self.strategy_config.remove_clients:
            self.rounds_history.calculate_additional_metrics()
