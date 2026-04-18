from __future__ import annotations

from intellifl.data_models.client_info import ClientInfo
from intellifl.data_models.round_info import RoundsInfo
from intellifl.data_models.simulation_strategy_config import StrategyConfig
from intellifl.data_models.simulation_strategy_history import SimulationStrategyHistory
from intellifl.dataset_handlers.dataset_handler import DatasetHandler
from tests.common import Mock, pytest


class TestSimulationStrategyHistory:
    """Tests for SimulationStrategyHistory data model."""

    def test_init_basic(self):
        """Verifies basic initialization stores config and creates required attributes."""
        mock_dataset_handler = Mock(spec=DatasetHandler)

        config = StrategyConfig(
            aggregation_strategy_keyword="trust",
            num_of_rounds=3,
            num_of_clients=5,
            remove_clients=True,
        )

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        assert history.strategy_config == config
        assert history.dataset_handler == mock_dataset_handler
        assert isinstance(history.rounds_history, RoundsInfo)
        assert isinstance(history._clients_dict, dict)

    def test_post_init_rounds_history_creation(self):
        """Verifies __post_init__ creates RoundsInfo with correct config."""
        mock_dataset_handler = Mock(spec=DatasetHandler)

        config = StrategyConfig(
            aggregation_strategy_keyword="pid", num_of_rounds=4, num_of_clients=6
        )

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        assert isinstance(history.rounds_history, RoundsInfo)
        assert history.rounds_history is not None
        assert history.rounds_history.simulation_strategy_config == config

    def test_post_init_clients_dict_creation(self):
        """Verifies __post_init__ creates client dictionary with correct ClientInfo instances."""
        mock_dataset_handler = Mock(spec=DatasetHandler)

        config = StrategyConfig(num_of_rounds=3, num_of_clients=4)

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        assert len(history._clients_dict) == 4

        for i in range(4):
            assert i in history._clients_dict
            client = history._clients_dict[i]
            assert isinstance(client, ClientInfo)
            assert client.client_id == i
            assert client.num_of_rounds == 3

    def test_post_init_malicious_client_marking(self):
        """Verifies clients start benign and are marked malicious via attack_schedule."""
        mock_dataset_handler = Mock(spec=DatasetHandler)
        mock_dataset_handler.poisoned_client_ids = []

        config = StrategyConfig(
            num_of_rounds=2,
            num_of_clients=5,
            attack_schedule=[
                {
                    "start_round": 1,
                    "end_round": 2,
                    "attack_type": "label_flipping",
                    "selection_strategy": "specific",
                    "malicious_client_ids": [1, 3],
                }
            ],
        )

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        for client in history.get_all_clients():
            assert client.is_malicious is False

        history.update_client_malicious_status(current_round=1)

        assert history._clients_dict[0].is_malicious is False
        assert history._clients_dict[1].is_malicious is True
        assert history._clients_dict[2].is_malicious is False
        assert history._clients_dict[3].is_malicious is True
        assert history._clients_dict[4].is_malicious is False

    def test_get_all_clients(self):
        """Verifies get_all_clients returns all ClientInfo instances."""
        mock_dataset_handler = Mock(spec=DatasetHandler)

        config = StrategyConfig(num_of_rounds=2, num_of_clients=3)

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        all_clients = history.get_all_clients()

        assert len(all_clients) == 3
        assert all(isinstance(client, ClientInfo) for client in all_clients)

        client_ids = {client.client_id for client in all_clients}
        assert client_ids == {0, 1, 2}

    def test_insert_single_client_history_entry_basic(self):
        """Verifies insert_single_client_history_entry stores all provided metrics."""
        mock_dataset_handler = Mock(spec=DatasetHandler)

        config = StrategyConfig(num_of_rounds=3, num_of_clients=2)

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        history.insert_single_client_history_entry(
            client_id=0,
            current_round=1,
            removal_criterion=0.5,
            absolute_distance=0.3,
            loss=0.2,
            accuracy=0.85,
            aggregation_participation=1,
        )

        client = history._clients_dict[0]
        assert client.removal_criterion_history[0] == 0.5
        assert client.absolute_distance_history[0] == 0.3
        assert client.loss_history[0] == 0.2
        assert client.accuracy_history[0] == 0.85
        assert client.aggregation_participation_history[0] == 1

    def test_insert_single_client_history_entry_partial_data(self):
        """Verifies insert_single_client_history_entry handles partial metric updates."""
        mock_dataset_handler = Mock(spec=DatasetHandler)

        config = StrategyConfig(num_of_rounds=2, num_of_clients=2)

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        history.insert_single_client_history_entry(
            client_id=1, current_round=2, loss=0.4, accuracy=0.75
        )

        client = history._clients_dict[1]
        assert client.loss_history[1] == 0.4
        assert client.accuracy_history[1] == 0.75
        assert client.removal_criterion_history[1] is None
        assert client.absolute_distance_history[1] is None
        assert client.aggregation_participation_history[1] == 0

    def test_insert_round_history_entry_basic(self):
        """Verifies insert_round_history_entry stores all provided round metrics."""
        mock_dataset_handler = Mock(spec=DatasetHandler)

        config = StrategyConfig(num_of_rounds=2, num_of_clients=2)

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        history.insert_round_history_entry(
            score_calculation_time_nanos=1500000,
            removal_threshold=0.6,
            loss_aggregated=0.25,
        )

        rounds_info = history.rounds_history
        assert rounds_info is not None
        assert rounds_info.score_calculation_time_nanos_history == [1500000]
        assert rounds_info.removal_threshold_history == [0.6]
        assert rounds_info.aggregated_loss_history == [0.25]

    def test_insert_round_history_entry_partial_data(self):
        """Verifies insert_round_history_entry handles partial round metrics."""
        mock_dataset_handler = Mock(spec=DatasetHandler)

        config = StrategyConfig(num_of_rounds=2, num_of_clients=2)

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        history.insert_round_history_entry(
            score_calculation_time_nanos=2000000, loss_aggregated=0.35
        )

        rounds_info = history.rounds_history
        assert rounds_info is not None
        assert rounds_info.score_calculation_time_nanos_history == [2000000]
        assert rounds_info.aggregated_loss_history == [0.35]
        assert len(rounds_info.removal_threshold_history) == 0

    def test_update_client_participation(self):
        """Verifies update_client_participation marks removed clients with zero participation."""
        mock_dataset_handler = Mock(spec=DatasetHandler)

        config = StrategyConfig(num_of_rounds=3, num_of_clients=5)

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        # Pre-mark all clients as participated for round 2 (simulates aggregation).
        # update_client_participation only overrides removed clients back to 0;
        # inclusion is recorded separately by strategies via aggregation_participation=1.
        for cid in range(5):
            history.insert_single_client_history_entry(
                client_id=cid, current_round=2, aggregation_participation=1
            )

        removed_client_ids = {1, 3}
        history.update_client_participation(current_round=2, removed_client_ids=removed_client_ids)

        assert history._clients_dict[1].aggregation_participation_history[1] == 0
        assert history._clients_dict[3].aggregation_participation_history[1] == 0

        assert history._clients_dict[0].aggregation_participation_history[1] == 1
        assert history._clients_dict[2].aggregation_participation_history[1] == 1
        assert history._clients_dict[4].aggregation_participation_history[1] == 1

    def test_calculate_additional_rounds_data_basic_scenario(self):
        """Verifies calculate_additional_rounds_data computes TP/TN/FP/FN and average accuracy."""
        mock_dataset_handler = Mock(spec=DatasetHandler)
        mock_dataset_handler.poisoned_client_ids = []

        config = StrategyConfig(
            num_of_rounds=2,
            num_of_clients=4,
            remove_clients=True,
            attack_schedule=[
                {
                    "start_round": 1,
                    "end_round": 2,
                    "attack_type": "label_flipping",
                    "selection_strategy": "specific",
                    "malicious_client_ids": [1, 3],
                }
            ],
        )

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        history.update_client_malicious_status(current_round=1)

        history.insert_single_client_history_entry(0, 1, accuracy=0.8, aggregation_participation=1)
        history.insert_single_client_history_entry(1, 1, accuracy=0.6, aggregation_participation=0)
        history.insert_single_client_history_entry(2, 1, accuracy=0.9, aggregation_participation=1)
        history.insert_single_client_history_entry(3, 1, accuracy=0.7, aggregation_participation=1)

        history.insert_single_client_history_entry(0, 2, accuracy=0.85, aggregation_participation=1)
        history.insert_single_client_history_entry(1, 2, accuracy=0.65, aggregation_participation=0)
        history.insert_single_client_history_entry(2, 2, accuracy=0.95, aggregation_participation=0)
        history.insert_single_client_history_entry(3, 2, accuracy=0.75, aggregation_participation=0)

        history.calculate_additional_rounds_data()

        rounds_info = history.rounds_history
        assert rounds_info is not None

        assert rounds_info.tp_history == [2, 1]
        assert rounds_info.tn_history == [1, 2]
        assert rounds_info.fp_history == [0, 1]
        assert rounds_info.fn_history == [1, 0]

        assert rounds_info.average_accuracy_history == pytest.approx([0.8, 0.85], rel=1e-3)

    def test_calculate_additional_rounds_data_no_removal(self):
        """Verifies calculate_additional_rounds_data works when remove_clients is disabled."""
        mock_dataset_handler = Mock(spec=DatasetHandler)
        mock_dataset_handler.poisoned_client_ids = []

        config = StrategyConfig(num_of_rounds=2, num_of_clients=3, remove_clients=False)

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        history.insert_single_client_history_entry(0, 1, accuracy=0.8, aggregation_participation=1)
        history.insert_single_client_history_entry(1, 1, accuracy=0.6, aggregation_participation=1)
        history.insert_single_client_history_entry(2, 1, accuracy=0.9, aggregation_participation=1)

        history.insert_single_client_history_entry(0, 2, accuracy=0.85, aggregation_participation=1)
        history.insert_single_client_history_entry(1, 2, accuracy=0.65, aggregation_participation=1)
        history.insert_single_client_history_entry(2, 2, accuracy=0.95, aggregation_participation=1)

        history.calculate_additional_rounds_data()

        rounds_info = history.rounds_history
        assert rounds_info is not None

        assert len(rounds_info.tp_history) == 2
        assert len(rounds_info.tn_history) == 2
        assert len(rounds_info.fp_history) == 2
        assert len(rounds_info.fn_history) == 2

        assert rounds_info.average_accuracy_history == pytest.approx(
            [0.7666666666666666, 0.8166666666666667], rel=1e-3
        )

    def test_calculate_additional_rounds_data_calls_additional_metrics(self):
        """Verifies calculate_additional_rounds_data invokes calculate_additional_metrics."""
        mock_dataset_handler = Mock(spec=DatasetHandler)
        mock_dataset_handler.poisoned_client_ids = []

        config = StrategyConfig(num_of_rounds=1, num_of_clients=2, remove_clients=True)

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        history.insert_single_client_history_entry(0, 1, accuracy=0.8, aggregation_participation=1)
        history.insert_single_client_history_entry(1, 1, accuracy=0.9, aggregation_participation=1)

        assert history.rounds_history is not None
        original_method = history.rounds_history.calculate_additional_metrics
        history.rounds_history.calculate_additional_metrics = Mock()  # type: ignore[method-assign]

        history.calculate_additional_rounds_data()

        history.rounds_history.calculate_additional_metrics.assert_called_once()

        history.rounds_history.calculate_additional_metrics = original_method  # type: ignore[method-assign]

    def test_data_consistency_across_operations(self):
        """Verifies data integrity when combining multiple history operations."""
        mock_dataset_handler = Mock(spec=DatasetHandler)
        mock_dataset_handler.poisoned_client_ids = []

        config = StrategyConfig(
            num_of_rounds=1,
            num_of_clients=3,
            remove_clients=True,
        )

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        history.insert_single_client_history_entry(
            0, 1, loss=0.3, accuracy=0.8, aggregation_participation=1
        )
        history.insert_single_client_history_entry(
            1, 1, loss=0.25, accuracy=0.85, aggregation_participation=1
        )
        history.insert_single_client_history_entry(
            2, 1, loss=0.4, accuracy=0.7, aggregation_participation=0
        )

        history.insert_round_history_entry(
            score_calculation_time_nanos=1000000,
            removal_threshold=0.5,
            loss_aggregated=0.275,
        )

        history.update_client_participation(1, {2})

        history.calculate_additional_rounds_data()

        assert len(history._clients_dict) == 3
        assert history._clients_dict[0].loss_history[0] == 0.3
        assert history._clients_dict[1].accuracy_history[0] == 0.85
        assert history._clients_dict[2].aggregation_participation_history[0] == 0

        assert history.rounds_history is not None
        assert history.rounds_history.score_calculation_time_nanos_history == [1000000]
        assert history.rounds_history.removal_threshold_history == [0.5]
        assert history.rounds_history.aggregated_loss_history == [0.275]

        assert history.rounds_history.average_accuracy_history[0] == pytest.approx(0.825, rel=1e-3)

    def test_edge_case_no_clients(self):
        """Verifies initialization handles zero clients."""
        mock_dataset_handler = Mock(spec=DatasetHandler)

        config = StrategyConfig(num_of_rounds=1, num_of_clients=0)

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        assert len(history._clients_dict) == 0
        assert len(history.get_all_clients()) == 0

    def test_edge_case_all_clients_malicious(self):
        """Verifies all clients can be marked malicious via attack_schedule."""
        mock_dataset_handler = Mock(spec=DatasetHandler)
        mock_dataset_handler.poisoned_client_ids = []

        config = StrategyConfig(
            num_of_rounds=1,
            num_of_clients=3,
            attack_schedule=[
                {
                    "start_round": 1,
                    "end_round": 1,
                    "attack_type": "label_flipping",
                    "selection_strategy": "specific",
                    "malicious_client_ids": [0, 1, 2],
                }
            ],
        )

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        history.update_client_malicious_status(current_round=1)

        for client in history.get_all_clients():
            assert client.is_malicious is True

    def test_edge_case_single_round_single_client(self):
        """Verifies functionality with minimal configuration of one round and one client."""
        mock_dataset_handler = Mock(spec=DatasetHandler)
        mock_dataset_handler.poisoned_client_ids = []

        config = StrategyConfig(num_of_rounds=1, num_of_clients=1, remove_clients=True)

        history = SimulationStrategyHistory(
            strategy_config=config,
            dataset_handler=mock_dataset_handler,
        )

        history.insert_single_client_history_entry(0, 1, accuracy=0.9, aggregation_participation=1)
        history.calculate_additional_rounds_data()

        assert len(history._clients_dict) == 1
        assert history.rounds_history is not None
        assert history.rounds_history.average_accuracy_history[0] == 0.9

    def test_calculate_additional_rounds_data_with_attack_schedule(self):
        """Verifies TP/TN/FP/FN metrics for dynamic attack schedules across rounds."""
        mock_dataset_handler = Mock(spec=DatasetHandler)
        mock_dataset_handler.poisoned_client_ids = []

        config = StrategyConfig(
            num_of_rounds=5,
            num_of_clients=3,
            remove_clients=True,
            attack_schedule=[
                {
                    "start_round": 2,
                    "end_round": 3,
                    "attack_type": "label_flipping",
                    "selection_strategy": "specific",
                    "malicious_client_ids": [0, 1],
                }
            ],
        )

        history = SimulationStrategyHistory(
            strategy_config=config, dataset_handler=mock_dataset_handler
        )

        for round_num in range(1, 6):
            for client_id in range(3):
                history.insert_single_client_history_entry(
                    client_id, round_num, accuracy=0.8, aggregation_participation=1
                )

        history.calculate_additional_rounds_data()

        rounds_info = history.rounds_history

        assert rounds_info.tp_history[0] == 3
        assert rounds_info.tn_history[0] == 0
        assert rounds_info.fp_history[0] == 0
        assert rounds_info.fn_history[0] == 0

        assert rounds_info.tp_history[1] == 1
        assert rounds_info.tn_history[1] == 0
        assert rounds_info.fp_history[1] == 0
        assert rounds_info.fn_history[1] == 2

        assert rounds_info.tp_history[2] == 1
        assert rounds_info.tn_history[2] == 0
        assert rounds_info.fp_history[2] == 0
        assert rounds_info.fn_history[2] == 2

        assert rounds_info.tp_history[3] == 3
        assert rounds_info.tn_history[3] == 0
        assert rounds_info.fp_history[3] == 0
        assert rounds_info.fn_history[3] == 0

        assert rounds_info.tp_history[4] == 3
        assert rounds_info.tn_history[4] == 0
        assert rounds_info.fp_history[4] == 0
        assert rounds_info.fn_history[4] == 0
