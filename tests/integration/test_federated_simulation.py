"""
Integration tests for FederatedSimulation class.

Tests end-to-end simulation workflows, component integration, and
cross-system interactions with mocked external dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from flwr.common import Context
from flwr.common.record import RecordDict

from intellifl.data_models.simulation_strategy_config import StrategyConfig
from intellifl.federated_simulation import FederatedSimulation
from tests.common import Mock, np, pytest
from tests.fixtures.mock_datasets import MockDatasetHandler
from tests.fixtures.sample_models import MockNetwork

NDArray = np.ndarray


def _get_base_strategy_config_dict() -> dict[str, Any]:
    """Return a base strategy configuration dictionary for testing."""
    return {
        "aggregation_strategy_keyword": "trust",
        "dataset_keyword": "its",
        "num_of_rounds": 3,
        "num_of_clients": 5,
        "num_of_malicious_clients": 1,
        "trust_threshold": 0.7,
        "beta_value": 0.5,
        "begin_removing_from_round": 1,
        "remove_clients": False,
        "min_fit_clients": 3,
        "min_evaluate_clients": 3,
        "min_available_clients": 5,
        "evaluate_metrics_aggregation_fn": "weighted_average",
        "training_device": "cpu",
        "cpus_per_client": 1,
        "gpus_per_client": 0.0,
        "batch_size": 32,
        "num_of_client_epochs": 1,
        "training_subset_fraction": 1.0,
        "model_type": "cnn",
        "use_llm": False,
        "llm_finetuning": None,
    }


def _create_mock_context(partition_id: int, num_partitions: int = 5) -> Context:
    """Create a mock Flower Context object for testing.

    Args:
        partition_id: The client partition index (0, 1, 2, ...)
        num_partitions: Total number of partitions/clients

    Returns:
        A Context object with the partition-id set in node_config
    """
    return Context(
        run_id=1,
        node_id=partition_id + 1000000,  # Simulate large node_id
        node_config={"partition-id": partition_id, "num-partitions": num_partitions},
        state=RecordDict(),
        run_config={},
    )


def _create_simulation_with_mocks(
    strategy_config: StrategyConfig,
    dataset_dir: str,
    dataset_handler: MockDatasetHandler,
    network_name: str = "ITSNetwork",
) -> FederatedSimulation:
    """Create a FederatedSimulation instance with mocked dependencies for testing."""
    with (
        patch("intellifl.federated_simulation.ImageDatasetLoader") as mock_loader,
        patch("intellifl.federated_simulation.build_cnn_model") as mock_build_cnn,
    ):
        mock_loader_instance = Mock()
        mock_loader_instance.load_datasets.return_value = (
            [Mock() for _ in range(strategy_config.num_of_clients or 0)],
            [Mock() for _ in range(strategy_config.num_of_clients or 0)],
        )
        mock_loader.return_value = mock_loader_instance

        mock_network_instance = MockNetwork()
        mock_build_cnn.return_value = mock_network_instance

        return FederatedSimulation(
            strategy_config=strategy_config,
            dataset_dir=dataset_dir,
            dataset_handler=dataset_handler,
        )


class TestFederatedSimulationIntegration:
    """Test suite for FederatedSimulation end-to-end workflows."""

    @pytest.fixture
    def mock_dataset_handler(self) -> MockDatasetHandler:
        """Mock dataset handler."""
        handler = MockDatasetHandler(dataset_type="its")
        handler.setup_dataset(num_clients=5)
        return handler

    @pytest.fixture
    def temp_dataset_dir(self, tmp_path: Path) -> str:
        """Temporary dataset directory."""
        dataset_dir = tmp_path / "datasets" / "its"
        dataset_dir.mkdir(parents=True)
        return str(dataset_dir)

    @patch("intellifl.federated_simulation.run_simulation")
    def test_complete_simulation_workflow_with_trust_strategy(
        self,
        mock_run_simulation: Mock,
        temp_dataset_dir: str,
        mock_dataset_handler: MockDatasetHandler,
    ) -> None:
        """Test complete simulation workflow from initialization to execution with trust strategy."""
        strategy_config = StrategyConfig.from_dict(_get_base_strategy_config_dict())
        simulation = _create_simulation_with_mocks(
            strategy_config, temp_dataset_dir, mock_dataset_handler
        )

        # Mock successful simulation completion
        mock_run_simulation.return_value = Mock()

        # Execute the simulation
        simulation.run_simulation()

        # Verify all components are properly integrated
        # Research: Flower 1.13+ run_simulation uses server_app, client_app, num_supernodes
        # https://flower.ai/docs/framework/how-to-run-simulations.html
        mock_run_simulation.assert_called_once()
        call_args = mock_run_simulation.call_args

        # Verify the new API parameters
        assert "server_app" in call_args.kwargs
        assert "client_app" in call_args.kwargs
        assert call_args.kwargs["num_supernodes"] == 5
        assert "backend_config" in call_args.kwargs
        assert call_args.kwargs["backend_config"]["client_resources"]["num_cpus"] == 1

        # Test client creation works across the workflow
        with patch("intellifl.federated_simulation.FlowerClient") as mock_flower_client:
            mock_client_instance = Mock()
            mock_client_instance.to_client.return_value = Mock()
            mock_flower_client.return_value = mock_client_instance

            # Test all clients can be created
            assert strategy_config.num_of_clients is not None
            for client_id in range(strategy_config.num_of_clients):
                context = _create_mock_context(client_id, strategy_config.num_of_clients)
                client = simulation.client_fn(context)
                assert client is not None

    @patch("intellifl.federated_simulation.run_simulation")
    def test_simulation_workflow_with_multiple_strategies(
        self,
        mock_run_simulation: Mock,
        temp_dataset_dir: str,
        mock_dataset_handler: MockDatasetHandler,
    ) -> None:
        """Test simulation workflow works with different aggregation strategies."""
        strategies_to_test: list[tuple[str, dict[str, Any]]] = [
            ("trust", {"trust_threshold": 0.7, "beta_value": 0.5}),
            ("pid", {"Kp": 1.0, "Ki": 0.1, "Kd": 0.01, "num_std_dev": 2.0}),
            ("krum", {"num_krum_selections": 3}),
        ]

        for strategy_name, extra_params in strategies_to_test:
            config_dict = _get_base_strategy_config_dict()
            config_dict["aggregation_strategy_keyword"] = strategy_name
            for key, value in extra_params.items():
                config_dict[key] = value
            strategy_config = StrategyConfig.from_dict(config_dict)

            simulation = _create_simulation_with_mocks(
                strategy_config, temp_dataset_dir, mock_dataset_handler
            )

            # Mock successful simulation
            mock_run_simulation.return_value = Mock()

            # Execute simulation
            simulation.run_simulation()

            # Verify strategy-specific integration
            assert simulation._aggregation_strategy is not None
            assert simulation.strategy_config.aggregation_strategy_keyword == strategy_name

    def test_cross_component_integration_dataset_network_strategy(
        self, temp_dataset_dir: str, mock_dataset_handler: MockDatasetHandler
    ) -> None:
        """Test integration between dataset loaders, networks, and strategies across different configurations."""
        dataset_network_combinations = [
            ("its", "ITSNetwork"),
            ("femnist_iid", "FemnistReducedIIDNetwork"),
            ("pneumoniamnist", "PneumoniamnistNetwork"),
        ]

        for dataset_type, expected_network in dataset_network_combinations:
            config_dict = _get_base_strategy_config_dict()
            config_dict["dataset_keyword"] = dataset_type
            strategy_config = StrategyConfig.from_dict(config_dict)

            simulation = _create_simulation_with_mocks(
                strategy_config,
                temp_dataset_dir,
                mock_dataset_handler,
                expected_network,
            )

            # Verify cross-component integration
            assert simulation._network_model is not None
            assert simulation._aggregation_strategy is not None
            assert simulation._trainloaders is not None
            assert simulation._valloaders is not None
            assert simulation.strategy_history is not None

            # Verify consistent client count across components
            assert len(simulation._trainloaders) == strategy_config.num_of_clients
            assert len(simulation._valloaders) == strategy_config.num_of_clients

    @patch("intellifl.federated_simulation.run_simulation")
    def test_simulation_handles_flower_exceptions(
        self,
        mock_run_simulation: Mock,
        temp_dataset_dir: str,
        mock_dataset_handler: MockDatasetHandler,
    ) -> None:
        """Test that simulation properly handles Flower simulation exceptions."""
        strategy_config = StrategyConfig.from_dict(_get_base_strategy_config_dict())
        simulation = _create_simulation_with_mocks(
            strategy_config, temp_dataset_dir, mock_dataset_handler
        )

        # Mock Flower to raise an exception
        mock_run_simulation.side_effect = RuntimeError("Flower simulation failed")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Flower simulation failed"):
            simulation.run_simulation()

    def test_end_to_end_client_workflow_integration(
        self, temp_dataset_dir: str, mock_dataset_handler: MockDatasetHandler
    ) -> None:
        """Test end-to-end client creation and execution workflow."""
        strategy_config = StrategyConfig.from_dict(_get_base_strategy_config_dict())
        simulation = _create_simulation_with_mocks(
            strategy_config, temp_dataset_dir, mock_dataset_handler
        )

        with patch("intellifl.federated_simulation.FlowerClient") as mock_flower_client:
            mock_client_instance = Mock()
            mock_client_instance.to_client.return_value = Mock()
            mock_flower_client.return_value = mock_client_instance

            # Test that client creation integrates with all system components
            assert strategy_config.num_of_clients is not None
            for client_id in range(strategy_config.num_of_clients):
                context = _create_mock_context(client_id, strategy_config.num_of_clients)
                _client = simulation.client_fn(context)

                # Verify client was created with proper integration
                call_args = mock_flower_client.call_args
                assert call_args.kwargs["client_id"] == client_id
                assert call_args.kwargs["net"] is simulation._network_model
                if simulation._trainloaders is not None:
                    assert call_args.kwargs["trainloader"] == simulation._trainloaders[client_id]
                if simulation._valloaders is not None:
                    assert call_args.kwargs["valloader"] == simulation._valloaders[client_id]
                assert call_args.kwargs["training_device"] == strategy_config.training_device
                assert (
                    call_args.kwargs["num_of_client_epochs"] == strategy_config.num_of_client_epochs
                )

    def test_simulation_error_recovery_integration(
        self, temp_dataset_dir: str, mock_dataset_handler: MockDatasetHandler
    ) -> None:
        """Test simulation handles errors gracefully across integrated components."""
        # Test unsupported dataset error propagation
        config_dict = _get_base_strategy_config_dict()
        config_dict["dataset_keyword"] = "unsupported_dataset"
        strategy_config = StrategyConfig.from_dict(config_dict)

        with pytest.raises(SystemExit) as exc_info:
            _create_simulation_with_mocks(strategy_config, temp_dataset_dir, mock_dataset_handler)
        assert exc_info.value.code == -1

        # Test unsupported strategy error propagation
        config_dict = _get_base_strategy_config_dict()
        config_dict["aggregation_strategy_keyword"] = "unsupported_strategy"
        strategy_config = StrategyConfig.from_dict(config_dict)

        with pytest.raises(NotImplementedError, match="not implemented"):
            _create_simulation_with_mocks(strategy_config, temp_dataset_dir, mock_dataset_handler)

    def test_strategy_history_integration_workflow(
        self, temp_dataset_dir: str, mock_dataset_handler: MockDatasetHandler
    ) -> None:
        """Test that strategy history is properly integrated throughout the workflow."""
        strategy_config = StrategyConfig.from_dict(_get_base_strategy_config_dict())
        simulation = _create_simulation_with_mocks(
            strategy_config, temp_dataset_dir, mock_dataset_handler
        )

        # Verify strategy history integration
        assert simulation.strategy_history is not None
        assert simulation.strategy_history.strategy_config == strategy_config
        assert simulation.strategy_history.dataset_handler == mock_dataset_handler
        assert simulation.strategy_history.rounds_history is not None

        # Verify strategy history maintains consistency across simulation lifecycle
        original_history = simulation.strategy_history

        # After potential simulation operations, history should remain consistent
        assert simulation.strategy_history is original_history
        assert simulation.strategy_history.strategy_config == strategy_config
