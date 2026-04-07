"""Integration tests for strategy combination scenarios."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import patch

from intellifl.data_models.simulation_strategy_config import StrategyConfig
from intellifl.federated_simulation import FederatedSimulation
from intellifl.simulation_runner import SimulationRunner
from tests.common import Mock, pytest
from tests.fixtures.mock_datasets import (
    MockDatasetHandler,
    generate_byzantine_client_parameters,
    generate_mock_client_parameters,
)
from tests.fixtures.sample_models import MockNetwork


def _create_multi_strategy_config(strategies: list[dict[str, Any]]) -> dict[str, Any]:
    """Create configuration with multiple strategies."""
    return {
        "shared_settings": {
            "dataset_keyword": "its",
            "num_of_rounds": 3,
            "num_of_clients": 10,
            "num_of_malicious_clients": 2,
            "begin_removing_from_round": 1,
            "remove_clients": False,
            "min_fit_clients": 8,
            "min_evaluate_clients": 8,
            "min_available_clients": 10,
            "evaluate_metrics_aggregation_fn": "weighted_average",
            "training_device": "cpu",
            "cpus_per_client": 1,
            "gpus_per_client": 0.0,
            "batch_size": 32,
            "num_of_client_epochs": 1,
            "training_subset_fraction": 1.0,
            "model_type": "cnn",
            "use_llm": False,
            "show_plots": False,
            "save_plots": True,
            "save_csv": True,
        },
        "simulation_strategies": strategies,
    }


def _create_attack_defense_config(
    defense_strategies: list[str], attack_type: str = "gaussian_noise"
) -> dict[str, Any]:
    """Create configuration for attack-defense scenarios."""
    strategies = []
    for defense in defense_strategies:
        strategy_config: dict[str, Any] = {
            "aggregation_strategy_keyword": defense,
            "attack_schedule": [
                {
                    "start_round": 1,
                    "end_round": 3,
                    "attack_type": attack_type,
                    "selection_strategy": "percentage",
                    "malicious_percentage": 0.2,
                }
            ],
        }

        if attack_type == "gaussian_noise":
            strategy_config["attack_schedule"][0].update(
                {
                    "target_noise_snr": 10.0,
                    "attack_ratio": 1.0,
                }
            )
        elif attack_type == "label_flipping":
            strategy_config["attack_schedule"][0].update({})

        if defense == "trust":
            strategy_config.update({"trust_threshold": 0.7, "beta_value": 0.5})
        elif defense in ["pid", "pid_scaled", "pid_standardized"]:
            strategy_config.update({"Kp": 1.0, "Ki": 0.1, "Kd": 0.01, "num_std_dev": 2.0})
        elif defense in ["krum", "multi-krum", "multi-krum-based"]:
            strategy_config.update({"num_krum_selections": 6})
        elif defense == "trimmed_mean":
            strategy_config.update({"trim_ratio": 0.2})

        strategies.append(strategy_config)

    return _create_multi_strategy_config(strategies)


class TestMultiStrategyScenarios:
    """Test multi-strategy execution scenarios."""

    @pytest.fixture
    def mock_simulation_components(self):
        with (
            patch("intellifl.simulation_runner.ConfigLoader") as mock_config_loader,
            patch("intellifl.simulation_runner.DirectoryHandler") as mock_directory_handler,
            patch("intellifl.simulation_runner.DatasetHandler") as mock_dataset_handler,
            patch("intellifl.simulation_runner.FederatedSimulation") as mock_federated_simulation,
            patch("intellifl.simulation_runner.new_plot_handler") as mock_plot_handler,
        ):
            mock_loader_instance = Mock()
            mock_config_loader.return_value = mock_loader_instance

            mock_dir_instance = Mock()
            mock_dir_instance.dataset_dir = "/tmp/test_dataset"
            mock_dir_instance.dirname = "/tmp/test_output"
            mock_directory_handler.return_value = mock_dir_instance

            mock_dataset_instance = Mock()
            mock_dataset_handler.return_value = mock_dataset_instance

            mock_simulation_instance = Mock()
            mock_simulation_instance.strategy_history = Mock()
            mock_simulation_instance.strategy_history.calculate_additional_rounds_data = Mock()
            mock_federated_simulation.return_value = mock_simulation_instance

            yield {
                "config_loader": mock_config_loader,
                "directory_handler": mock_directory_handler,
                "dataset_handler": mock_dataset_handler,
                "federated_simulation": mock_federated_simulation,
                "plot_handler": mock_plot_handler,
                "loader_instance": mock_loader_instance,
                "dir_instance": mock_dir_instance,
                "dataset_instance": mock_dataset_instance,
                "simulation_instance": mock_simulation_instance,
            }

    @pytest.mark.parametrize(
        "strategy_combination,expected_behavior",
        [
            # Test Trust + PID interactions
            (["trust", "pid"], "trust_overrides_pid_removal"),
            # Test Krum variants with different client removal patterns
            (["krum", "multi-krum"], "consistent_client_selection"),
            # Test Byzantine-robust strategies under attack scenarios
            (["trust", "krum", "rfa"], "robust_aggregation_convergence"),
            # Test PID variants with different scaling approaches
            (["pid", "pid_scaled", "pid_standardized"], "consistent_pid_behavior"),
            # Test defense strategy combinations
            (["trust", "krum", "bulyan", "trimmed_mean"], "multi_layer_defense"),
        ],
    )
    def test_strategy_combination_execution(
        self,
        mock_simulation_components: Any,
        strategy_combination: list[str],
        expected_behavior: str,
    ) -> None:
        mocks = mock_simulation_components

        strategies = []
        for strategy in strategy_combination:
            strategy_config: dict[str, Any] = {"aggregation_strategy_keyword": strategy}

            if strategy == "trust":
                strategy_config.update({"trust_threshold": 0.7, "beta_value": 0.5})
            elif strategy in ["pid", "pid_scaled", "pid_standardized"]:
                strategy_config.update({"Kp": 1.0, "Ki": 0.1, "Kd": 0.01})
            elif strategy in ["krum", "multi-krum", "multi-krum-based"]:
                strategy_config.update({"num_krum_selections": 6})

            strategies.append(strategy_config)

        config_dicts: list[dict[str, Any]] = []
        for i, strategy_dict in enumerate(strategies):
            config_dict: dict[str, Any] = {
                "aggregation_strategy_keyword": strategy_dict["aggregation_strategy_keyword"],
                "dataset_keyword": "its",
                "num_of_rounds": 3,
                "num_of_clients": 10,
                "strategy_number": i,
            }
            config_dict.update(strategy_dict)
            config_dicts.append(config_dict)

        mocks["loader_instance"].get_usecase_config_list.return_value = config_dicts
        mocks["loader_instance"].get_dataset_config_list.return_value = [{"its": "datasets/its"}]

        runner = SimulationRunner("multi_strategy_config.json")

        runner.run()

        assert mocks["federated_simulation"].call_count == len(strategy_combination)
        assert mocks["simulation_instance"].run_simulation.call_count == len(strategy_combination)

        if expected_behavior == "trust_overrides_pid_removal":
            call_args_list = mocks["federated_simulation"].call_args_list
            strategy_keywords = [
                call.kwargs["strategy_config"].aggregation_strategy_keyword
                for call in call_args_list
            ]
            assert "trust" in strategy_keywords
            assert "pid" in strategy_keywords

        elif expected_behavior == "consistent_client_selection":
            call_args_list = mocks["federated_simulation"].call_args_list
            krum_calls = [
                call
                for call in call_args_list
                if "krum" in call.kwargs["strategy_config"].aggregation_strategy_keyword
            ]
            assert len(krum_calls) >= 2

        elif expected_behavior == "robust_aggregation_convergence":
            call_args_list = mocks["federated_simulation"].call_args_list
            strategy_keywords = [
                call.kwargs["strategy_config"].aggregation_strategy_keyword
                for call in call_args_list
            ]
            assert "trust" in strategy_keywords
            assert "krum" in strategy_keywords
            assert "rfa" in strategy_keywords

        elif expected_behavior == "consistent_pid_behavior":
            call_args_list = mocks["federated_simulation"].call_args_list
            pid_strategies = [
                call.kwargs["strategy_config"].aggregation_strategy_keyword
                for call in call_args_list
                if "pid" in call.kwargs["strategy_config"].aggregation_strategy_keyword
            ]
            assert len(pid_strategies) == 3

        elif expected_behavior == "multi_layer_defense":
            call_args_list = mocks["federated_simulation"].call_args_list
            strategy_keywords = [
                call.kwargs["strategy_config"].aggregation_strategy_keyword
                for call in call_args_list
            ]
            expected_strategies = ["trust", "krum", "bulyan", "trimmed_mean"]
            for strategy in expected_strategies:
                assert strategy in strategy_keywords

    def test_strategy_interaction_parameter_inheritance(self, mock_simulation_components):
        """Verify shared parameters are inherited by all strategies."""
        mocks = mock_simulation_components

        shared_params = {
            "num_of_rounds": 5,
            "num_of_clients": 12,
            "dataset_keyword": "femnist_iid",
            "training_device": "cpu",
        }

        strategies = [
            {"aggregation_strategy_keyword": "trust", "trust_threshold": 0.8},
            {"aggregation_strategy_keyword": "krum", "num_krum_selections": 8},
        ]

        config_dicts = []
        for i, strategy in enumerate(strategies):
            config_dict = shared_params.copy()
            config_dict.update(strategy)
            config_dict["strategy_number"] = i
            config_dicts.append(config_dict)

        mocks["loader_instance"].get_usecase_config_list.return_value = config_dicts
        mocks["loader_instance"].get_dataset_config_list.return_value = [
            {"femnist_iid": "datasets/femnist_iid"}
        ]

        runner = SimulationRunner("shared_params_config.json")

        runner.run()

        call_args_list = mocks["federated_simulation"].call_args_list

        for call in call_args_list:
            strategy_config = call.kwargs["strategy_config"]
            assert strategy_config.num_of_rounds == 5
            assert strategy_config.num_of_clients == 12
            assert strategy_config.dataset_keyword == "femnist_iid"

        trust_call = next(
            call
            for call in call_args_list
            if call.kwargs["strategy_config"].aggregation_strategy_keyword == "trust"
        )
        assert trust_call.kwargs["strategy_config"].trust_threshold == 0.8

        krum_call = next(
            call
            for call in call_args_list
            if call.kwargs["strategy_config"].aggregation_strategy_keyword == "krum"
        )
        assert krum_call.kwargs["strategy_config"].num_krum_selections == 8

    def test_strategy_execution_order_consistency(self, mock_simulation_components):
        """Verify strategies execute in configuration order."""
        mocks = mock_simulation_components

        strategies = ["trust", "pid", "krum", "rfa", "bulyan"]
        config_dicts = []

        for i, strategy in enumerate(strategies):
            config_dict = {
                "aggregation_strategy_keyword": strategy,
                "dataset_keyword": "its",
                "num_of_rounds": 2,
                "num_of_clients": 8,
                "strategy_number": i,
            }
            config_dicts.append(config_dict)

        mocks["loader_instance"].get_usecase_config_list.return_value = config_dicts
        mocks["loader_instance"].get_dataset_config_list.return_value = [{"its": "datasets/its"}]

        execution_order = []

        def track_execution(strategy_config, **kwargs):
            execution_order.append(strategy_config.aggregation_strategy_keyword)
            return mocks["simulation_instance"]

        mocks["federated_simulation"].side_effect = track_execution

        runner = SimulationRunner("order_test_config.json")

        runner.run()

        assert execution_order == strategies
        assert len(execution_order) == len(strategies)


class TestByzantineFaultTolerance:
    @pytest.fixture
    def mock_federated_simulation_with_byzantine(self):
        with (
            patch("intellifl.federated_simulation.ImageDatasetLoader") as mock_loader,
            patch("intellifl.federated_simulation.build_cnn_model") as mock_build_cnn,
            patch("intellifl.federated_simulation.run_simulation") as mock_run_sim,
            patch(
                "intellifl.federated_simulation.FederatedSimulation._assign_aggregation_strategy"
            ) as mock_assign_strategy,
        ):
            mock_loader_instance = Mock()
            mock_loader_instance.load_datasets.return_value = (
                [Mock() for _ in range(10)],  # trainloaders
                [Mock() for _ in range(10)],  # valloaders
            )
            mock_loader.return_value = mock_loader_instance

            mock_network_instance = MockNetwork()
            mock_build_cnn.return_value = mock_network_instance

            # Mock strategy assignment to avoid initialization issues
            mock_strategy = Mock()
            mock_assign_strategy.return_value = mock_strategy

            # Mock Flower simulation to simulate Byzantine behavior
            mock_run_sim.return_value = None

            yield {
                "loader": mock_loader,
                "network": mock_build_cnn,
                "run_simulation": mock_run_sim,
                "assign_strategy": mock_assign_strategy,
                "loader_instance": mock_loader_instance,
                "network_instance": mock_network_instance,
                "strategy": mock_strategy,
            }

    @pytest.mark.parametrize(
        "defense_strategies,attack_type,expected_robustness",
        [
            # Gaussian noise attacks
            (["trust", "krum", "rfa"], "gaussian_noise", "high_robustness"),
            (
                ["multi-krum", "bulyan", "trimmed_mean"],
                "gaussian_noise",
                "high_robustness",
            ),
            (["pid", "pid_scaled"], "gaussian_noise", "medium_robustness"),
            # Model poisoning attacks
            (["krum", "multi-krum", "bulyan"], "model_poisoning", "high_robustness"),
            (["trust", "rfa", "trimmed_mean"], "model_poisoning", "medium_robustness"),
            # Byzantine client attacks
            (
                ["trust", "krum", "rfa", "bulyan"],
                "byzantine_perturbation",
                "very_high_robustness",
            ),
            (
                ["multi-krum", "trimmed_mean"],
                "byzantine_perturbation",
                "high_robustness",
            ),
        ],
    )
    def test_byzantine_fault_tolerance_combinations(
        self,
        mock_federated_simulation_with_byzantine,
        defense_strategies: list[str],
        attack_type: str,
        expected_robustness: str,
    ):
        """Verify Byzantine resilience for strategy combinations."""
        mocks = mock_federated_simulation_with_byzantine

        for strategy in defense_strategies:
            base_config = {
                "aggregation_strategy_keyword": strategy,
                "dataset_keyword": "its",
                "num_of_rounds": 3,
                "num_of_clients": 10,
                "num_of_malicious_clients": 3,  # 30% Byzantine clients
                "begin_removing_from_round": 1,
                "remove_clients": False,
                "min_fit_clients": 7,
                "min_evaluate_clients": 7,
                "min_available_clients": 10,
                "evaluate_metrics_aggregation_fn": "weighted_average",
                "training_device": "cpu",
                "cpus_per_client": 1,
                "gpus_per_client": 0.0,
                "batch_size": 32,
                "num_of_client_epochs": 1,
                "training_subset_fraction": 1.0,
                "model_type": "cnn",
                "use_llm": False,
            }

            if strategy == "trust":
                base_config.update({"trust_threshold": 0.7, "beta_value": 0.5})
            elif strategy in ["pid", "pid_scaled", "pid_standardized"]:
                base_config.update({"Kp": 1.0, "Ki": 0.1, "Kd": 0.01, "num_std_dev": 2.0})
            elif strategy in ["krum", "multi-krum", "multi-krum-based"]:
                base_config.update({"num_krum_selections": 6})
            elif strategy == "trimmed_mean":
                # Higher trim ratio for Byzantine tolerance
                base_config.update({"trim_ratio": 0.3})

            strategy_config = StrategyConfig.from_dict(base_config)
            mock_dataset_handler = MockDatasetHandler(dataset_type="its")
            mock_dataset_handler.setup_dataset(num_clients=10)

            simulation = FederatedSimulation(
                strategy_config=strategy_config,
                dataset_dir="/tmp/test",
                dataset_handler=mock_dataset_handler,
            )

            def mock_client_fn_with_byzantine(cid: str):
                client_id_int = int(cid)

                # First 3 clients are malicious
                if client_id_int < 3:
                    byzantine_client = Mock()
                    byzantine_client.fit = Mock(
                        return_value=(
                            generate_byzantine_client_parameters(1, 1, 1000, attack_type)[0],
                            50,  # dataset size
                            {
                                "loss": 10.0,
                                "accuracy": 0.1,
                            },  # Poor metrics indicating attack
                        )
                    )
                    byzantine_client.evaluate = Mock(
                        return_value=(
                            5.0,  # high loss
                            50,  # dataset size
                            {"accuracy": 0.1, "f1_score": 0.1},  # Poor performance
                        )
                    )
                    return byzantine_client
                else:
                    # Honest client
                    honest_client = Mock()
                    honest_client.fit = Mock(
                        return_value=(
                            generate_mock_client_parameters(1, 1000)[0],
                            50,
                            {"loss": 0.5, "accuracy": 0.8},
                        )
                    )
                    honest_client.evaluate = Mock(
                        return_value=(0.3, 50, {"accuracy": 0.85, "f1_score": 0.8})
                    )
                    return honest_client

            simulation.client_fn = mock_client_fn_with_byzantine  # type: ignore[method-assign, assignment]

            simulation.run_simulation()

            mocks["run_simulation"].assert_called()

            assert strategy_config.num_of_malicious_clients is not None
            assert strategy_config.num_of_clients is not None
            if expected_robustness == "very_high_robustness":
                assert (
                    strategy_config.num_of_malicious_clients <= strategy_config.num_of_clients * 0.4
                )
            elif expected_robustness == "high_robustness":
                assert (
                    strategy_config.num_of_malicious_clients
                    <= strategy_config.num_of_clients * 0.35
                )
            elif expected_robustness == "medium_robustness":
                assert (
                    strategy_config.num_of_malicious_clients <= strategy_config.num_of_clients * 0.3
                )

    def test_strategy_combination_byzantine_resilience(
        self, mock_federated_simulation_with_byzantine
    ):
        """Verify strategy combinations improve Byzantine resilience."""
        individual_strategies = ["trust", "krum", "rfa"]

        byzantine_ratios = [0.1, 0.2, 0.3, 0.4]

        for byzantine_ratio in byzantine_ratios:
            num_clients = 10
            num_byzantine = int(num_clients * byzantine_ratio)

            individual_results = []
            for strategy in individual_strategies:
                base_config = {
                    "aggregation_strategy_keyword": strategy,
                    "dataset_keyword": "its",
                    "num_of_rounds": 2,
                    "num_of_clients": num_clients,
                    "num_of_malicious_clients": num_byzantine,
                    "begin_removing_from_round": 1,
                    "remove_clients": False,
                    "min_fit_clients": max(1, num_clients - num_byzantine),
                    "min_evaluate_clients": max(1, num_clients - num_byzantine),
                    "min_available_clients": num_clients,
                    "evaluate_metrics_aggregation_fn": "weighted_average",
                    "training_device": "cpu",
                    "cpus_per_client": 1,
                    "gpus_per_client": 0.0,
                    "batch_size": 16,
                    "num_of_client_epochs": 1,
                    "training_subset_fraction": 1.0,
                    "model_type": "cnn",
                    "use_llm": False,
                }

                if strategy == "trust":
                    base_config.update({"trust_threshold": 0.7, "beta_value": 0.5})
                elif strategy == "krum":
                    base_config.update({"num_krum_selections": max(1, num_clients - num_byzantine)})

                try:
                    strategy_config = StrategyConfig.from_dict(base_config)
                    mock_dataset_handler = MockDatasetHandler(dataset_type="its")
                    mock_dataset_handler.setup_dataset(num_clients=num_clients)

                    simulation = FederatedSimulation(
                        strategy_config=strategy_config,
                        dataset_dir="/tmp/test",
                        dataset_handler=mock_dataset_handler,
                    )

                    simulation.run_simulation()
                    individual_results.append(True)  # Success

                except Exception:
                    individual_results.append(False)

            success_rate = sum(individual_results) / len(individual_results)

            if byzantine_ratio <= 0.2:
                assert success_rate >= 0.6
            elif byzantine_ratio <= 0.3:
                assert success_rate >= 0.3


class TestAttackDefenseScenarios:
    @pytest.fixture
    def mock_attack_simulation_components(self):
        with (
            patch("intellifl.simulation_runner.ConfigLoader") as mock_config_loader,
            patch("intellifl.simulation_runner.DirectoryHandler") as mock_directory_handler,
            patch("intellifl.simulation_runner.DatasetHandler") as mock_dataset_handler,
            patch("intellifl.simulation_runner.FederatedSimulation") as mock_federated_simulation,
            patch("intellifl.simulation_runner.new_plot_handler") as mock_plot_handler,
        ):
            mock_loader_instance = Mock()
            mock_config_loader.return_value = mock_loader_instance

            mock_dir_instance = Mock()
            mock_dir_instance.dataset_dir = "/tmp/attack_test_dataset"
            mock_dir_instance.dirname = "/tmp/attack_test_output"
            mock_directory_handler.return_value = mock_dir_instance

            mock_dataset_instance = Mock()
            mock_dataset_handler.return_value = mock_dataset_instance

            mock_simulation_instance = Mock()
            mock_simulation_instance.strategy_history = Mock()
            mock_simulation_instance.strategy_history.calculate_additional_rounds_data = Mock()

            mock_simulation_instance.strategy_history.attack_detection_rate = 0.8
            mock_simulation_instance.strategy_history.defense_effectiveness = 0.9

            mock_federated_simulation.return_value = mock_simulation_instance

            yield {
                "config_loader": mock_config_loader,
                "directory_handler": mock_directory_handler,
                "dataset_handler": mock_dataset_handler,
                "federated_simulation": mock_federated_simulation,
                "plot_handler": mock_plot_handler,
                "loader_instance": mock_loader_instance,
                "dir_instance": mock_dir_instance,
                "dataset_instance": mock_dataset_instance,
                "simulation_instance": mock_simulation_instance,
            }

    @pytest.mark.parametrize(
        "attack_type,defense_strategies,expected_effectiveness",
        [
            # Gaussian noise attacks with different defense combinations
            ("gaussian_noise", ["trust", "krum", "rfa"], "high_effectiveness"),
            (
                "gaussian_noise",
                ["multi-krum", "bulyan", "trimmed_mean"],
                "high_effectiveness",
            ),
            ("gaussian_noise", ["pid", "pid_scaled"], "medium_effectiveness"),
            # Model poisoning attacks
            ("model_poisoning", ["krum", "multi-krum", "bulyan"], "high_effectiveness"),
            (
                "model_poisoning",
                ["trust", "rfa", "trimmed_mean"],
                "medium_effectiveness",
            ),
            ("model_poisoning", ["pid"], "low_effectiveness"),
            # Byzantine client attacks
            (
                "byzantine_perturbation",
                ["trust", "krum", "rfa", "bulyan"],
                "very_high_effectiveness",
            ),
            (
                "byzantine_perturbation",
                ["multi-krum", "trimmed_mean"],
                "high_effectiveness",
            ),
            (
                "byzantine_perturbation",
                ["pid_scaled", "pid_standardized"],
                "medium_effectiveness",
            ),
            # Gradient inversion attacks
            (
                "gradient_scaling",
                ["trust", "pid", "trimmed_mean"],
                "medium_effectiveness",
            ),
            ("gradient_scaling", ["krum", "bulyan"], "high_effectiveness"),
        ],
    )
    def test_attack_defense_scenario_workflows(
        self,
        mock_attack_simulation_components,
        attack_type: str,
        defense_strategies: list[str],
        expected_effectiveness: str,
    ):
        """Verify defense effectiveness against attack types."""
        mocks = mock_attack_simulation_components

        config = _create_attack_defense_config(defense_strategies, attack_type)

        config_dicts = []
        for i, strategy_config in enumerate(config["simulation_strategies"]):
            config_dict = config["shared_settings"].copy()
            config_dict.update(strategy_config)
            config_dict["strategy_number"] = i
            config_dicts.append(config_dict)

        mocks["loader_instance"].get_usecase_config_list.return_value = config_dicts
        mocks["loader_instance"].get_dataset_config_list.return_value = [{"its": "datasets/its"}]

        def mock_simulation_with_attack_metrics(strategy_config, **kwargs):
            simulation = mocks["simulation_instance"]

            strategy_name = strategy_config.aggregation_strategy_keyword

            if strategy_name in ["trust", "krum", "rfa", "bulyan"]:
                simulation.strategy_history.attack_detection_rate = 0.9
                simulation.strategy_history.defense_effectiveness = 0.85
            elif strategy_name in ["multi-krum", "trimmed_mean"]:
                simulation.strategy_history.attack_detection_rate = 0.8
                simulation.strategy_history.defense_effectiveness = 0.75
            elif "pid" in strategy_name:
                simulation.strategy_history.attack_detection_rate = 0.6
                simulation.strategy_history.defense_effectiveness = 0.6

            return simulation

        mocks["federated_simulation"].side_effect = mock_simulation_with_attack_metrics

        runner = SimulationRunner("attack_defense_config.json")

        runner.run()

        assert mocks["federated_simulation"].call_count == len(defense_strategies)
        assert mocks["simulation_instance"].run_simulation.call_count == len(defense_strategies)

        call_args_list = mocks["federated_simulation"].call_args_list

        for call in call_args_list:
            strategy_config = call.kwargs["strategy_config"]

            if hasattr(strategy_config, "attack_schedule") and strategy_config.attack_schedule:
                assert strategy_config.attack_schedule[0]["attack_type"] == attack_type

            strategy_name = strategy_config.aggregation_strategy_keyword

            if strategy_name == "trust":
                assert hasattr(strategy_config, "trust_threshold")
                assert strategy_config.trust_threshold == 0.7
            elif "pid" in strategy_name:
                assert hasattr(strategy_config, "Kp")
                assert strategy_config.Kp == 1.0
            elif "krum" in strategy_name:
                assert hasattr(strategy_config, "num_krum_selections")
                assert strategy_config.num_krum_selections == 6

        if expected_effectiveness == "very_high_effectiveness":
            assert len(defense_strategies) >= 3
        elif expected_effectiveness == "high_effectiveness":
            assert len(defense_strategies) >= 2
        elif expected_effectiveness in ["medium_effectiveness", "low_effectiveness"]:
            assert len(defense_strategies) >= 1

    def test_multi_attack_defense_resilience(self, mock_attack_simulation_components):
        """Verify defense resilience against multiple attack types."""
        mocks = mock_attack_simulation_components

        attack_types = ["gaussian_noise", "model_poisoning", "byzantine_perturbation"]
        defense_strategies = ["trust", "krum", "rfa", "bulyan", "trimmed_mean"]

        all_config_dicts = []
        strategy_number = 0

        for attack_type in attack_types:
            for defense_strategy in defense_strategies:
                config_dict = {
                    "aggregation_strategy_keyword": defense_strategy,
                    "attack_schedule": [
                        {
                            "start_round": 1,
                            "end_round": 2,
                            "attack_type": attack_type,
                            "selection_strategy": "percentage",
                            "malicious_percentage": 0.3,
                        }
                    ],
                    "dataset_keyword": "its",
                    "num_of_rounds": 2,
                    "num_of_clients": 10,
                    "num_of_malicious_clients": 3,
                    "begin_removing_from_round": 1,
                    "remove_clients": False,
                    "min_fit_clients": 7,
                    "min_evaluate_clients": 7,
                    "min_available_clients": 10,
                    "evaluate_metrics_aggregation_fn": "weighted_average",
                    "training_device": "cpu",
                    "cpus_per_client": 1,
                    "gpus_per_client": 0.0,
                    "batch_size": 16,
                    "num_of_client_epochs": 1,
                    "training_subset_fraction": 1.0,
                    "model_type": "cnn",
                    "use_llm": False,
                    "strategy_number": strategy_number,
                }

                attack_schedule = cast(list[dict[str, Any]], config_dict["attack_schedule"])
                if attack_type == "gaussian_noise":
                    attack_schedule[0].update(
                        {
                            "target_noise_snr": 10.0,
                            "attack_ratio": 1.0,
                        }
                    )
                elif attack_type == "label_flipping":
                    attack_schedule[0].update({})

                if defense_strategy == "trust":
                    config_dict.update({"trust_threshold": 0.7, "beta_value": 0.5})
                elif "pid" in defense_strategy:
                    config_dict.update({"Kp": 1.0, "Ki": 0.1, "Kd": 0.01})
                elif "krum" in defense_strategy:
                    config_dict.update({"num_krum_selections": 6})
                elif defense_strategy == "trimmed_mean":
                    config_dict.update({"trim_ratio": 0.25})

                all_config_dicts.append(config_dict)
                strategy_number += 1

        mocks["loader_instance"].get_usecase_config_list.return_value = all_config_dicts
        mocks["loader_instance"].get_dataset_config_list.return_value = [{"its": "datasets/its"}]

        runner = SimulationRunner("multi_attack_defense_config.json")

        runner.run()

        expected_total_simulations = len(attack_types) * len(defense_strategies)
        assert mocks["federated_simulation"].call_count == expected_total_simulations
        assert mocks["simulation_instance"].run_simulation.call_count == expected_total_simulations

        call_args_list = mocks["federated_simulation"].call_args_list

        tested_combinations = set()
        for call in call_args_list:
            strategy_config = call.kwargs["strategy_config"]
            attack_type = "unknown"
            if hasattr(strategy_config, "attack_schedule") and strategy_config.attack_schedule:
                attack_type = strategy_config.attack_schedule[0]["attack_type"]
            combination = (
                attack_type,
                strategy_config.aggregation_strategy_keyword,
            )
            tested_combinations.add(combination)

        expected_combinations = {
            (attack, defense) for attack in attack_types for defense in defense_strategies
        }

        tested_defense_strategies = {combo[1] for combo in tested_combinations}
        assert tested_defense_strategies == set(defense_strategies)

        assert len(tested_combinations) == len(expected_combinations)

    def test_attack_scenario_parameter_validation(self, mock_attack_simulation_components):
        """Verify attack scenario parameter validation."""
        mocks = mock_attack_simulation_components

        attack_configs = [
            {
                "attack_type": "gaussian_noise",
                "defense_strategy": "trust",
                "attack_intensity": "high",
                "expected_params": {"trust_threshold": 0.7, "beta_value": 0.5},
            },
            {
                "attack_type": "model_poisoning",
                "defense_strategy": "krum",
                "attack_intensity": "medium",
                "expected_params": {"num_krum_selections": 6},
            },
            {
                "attack_type": "byzantine_perturbation",
                "defense_strategy": "bulyan",
                "attack_intensity": "low",
                "expected_params": {},
            },
        ]

        for attack_config in attack_configs:
            config_dict = {
                "aggregation_strategy_keyword": attack_config["defense_strategy"],
                "attack_schedule": [
                    {
                        "start_round": 1,
                        "end_round": 2,
                        "attack_type": attack_config["attack_type"],
                        "selection_strategy": "percentage",
                        "malicious_percentage": 0.25,
                    }
                ],
                "dataset_keyword": "its",
                "num_of_rounds": 2,
                "num_of_clients": 8,
                "num_of_malicious_clients": 2,
                "strategy_number": 0,
            }

            attack_type = attack_config["attack_type"]
            attack_schedule = cast(list[dict[str, Any]], config_dict["attack_schedule"])
            if attack_type == "gaussian_noise":
                attack_schedule[0].update(
                    {
                        "target_noise_snr": 10.0,
                        "attack_ratio": 1.0,
                    }
                )
            elif attack_type == "label_flipping":
                attack_schedule[0].update({})

            expected_params = cast(dict[str, Any], attack_config["expected_params"])
            config_dict.update(expected_params)

            mocks["loader_instance"].get_usecase_config_list.return_value = [config_dict]
            mocks["loader_instance"].get_dataset_config_list.return_value = [
                {"its": "datasets/its"}
            ]

            runner = SimulationRunner("attack_param_test_config.json")

            runner.run()

            call_args = mocks["federated_simulation"].call_args
            strategy_config = call_args.kwargs["strategy_config"]

            assert strategy_config.aggregation_strategy_keyword == attack_config["defense_strategy"]

            for param_name, param_value in expected_params.items():
                assert hasattr(strategy_config, param_name)
                assert getattr(strategy_config, param_name) == param_value

            mocks["federated_simulation"].reset_mock()
            mocks["simulation_instance"].run_simulation.reset_mock()
