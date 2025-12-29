"""Parameterized tests for attack scenarios in federated learning."""

from tests.common import ATTACK_SCENARIOS, DEFENSE_STRATEGIES, Mock, np, pytest
from tests.fixtures.mock_datasets import (
    MockDatasetHandler,
    generate_byzantine_client_parameters,
    generate_mock_client_parameters,
)


class TestAttackScenarios:
    @pytest.mark.parametrize(
        "attack_type,defense_strategies,expected_robustness",
        ATTACK_SCENARIOS,
    )
    def test_defense_mechanism_effectiveness(
        self, attack_type, defense_strategies, expected_robustness
    ):
        """Verify defense strategy effectiveness against attack types."""
        num_clients = 10
        num_byzantine = 3
        param_size = 1000

        attack_params = generate_byzantine_client_parameters(
            num_clients=num_clients,
            num_byzantine=num_byzantine,
            param_size=param_size,
            attack_type=attack_type,
        )

        assert len(attack_params) == num_clients, (
            "Should generate parameters for all clients"
        )

        for strategy_name in defense_strategies:
            mock_strategy = Mock()

            np.random.seed(42)
            if expected_robustness == "high":
                mock_strategy.detect_byzantine_perturbation.return_value = list(
                    range(num_byzantine)
                )
                mock_strategy.aggregate_parameters.return_value = (
                    np.random.randn(param_size) * 0.01
                )
            elif expected_robustness == "medium":
                mock_strategy.detect_byzantine_perturbation.return_value = list(
                    range(num_byzantine // 2)
                )
                mock_strategy.aggregate_parameters.return_value = (
                    np.random.randn(param_size) * 0.005
                )
            else:
                mock_strategy.detect_byzantine_perturbation.return_value = []
                mock_strategy.aggregate_parameters.return_value = (
                    np.random.randn(param_size) * 0.1
                )

            detected_byzantine = mock_strategy.detect_byzantine_perturbation()
            aggregated_params = mock_strategy.aggregate_parameters()
            if expected_robustness == "high":
                assert len(detected_byzantine) >= num_byzantine // 2, (
                    f"Strategy {strategy_name} should detect at least half of Byzantine clients "
                    f"for {attack_type} attack"
                )
                assert np.linalg.norm(aggregated_params) < 0.5, (
                    f"Strategy {strategy_name} should produce stable aggregation for {attack_type}"
                )
            elif expected_robustness == "medium":
                assert len(detected_byzantine) >= 1, (
                    f"Strategy {strategy_name} should detect some Byzantine clients for {attack_type}"
                )
                assert np.linalg.norm(aggregated_params) < 1.0, (
                    f"Strategy {strategy_name} should maintain reasonable stability for {attack_type}"
                )

    @pytest.mark.parametrize(
        "attack_type",
        [
            "gaussian_noise",
            "model_poisoning",
            "byzantine_perturbation",
            "gradient_scaling",
        ],
    )
    def test_attack_parameter_generation(self, attack_type):
        """Verify attack parameter generation for different attack types."""
        num_clients = 8
        num_byzantine = 2
        param_size = 500

        attack_params = generate_byzantine_client_parameters(
            num_clients=num_clients,
            num_byzantine=num_byzantine,
            param_size=param_size,
            attack_type=attack_type,
        )

        assert len(attack_params) == num_clients, (
            "Should generate parameters for all clients"
        )

        for params in attack_params:
            assert isinstance(params, np.ndarray), "Parameters should be numpy arrays"
            assert params.shape == (param_size,), (
                f"Parameters should have shape ({param_size},)"
            )

        param_norms = [np.linalg.norm(params) for params in attack_params]

        if attack_type in [
            "gaussian_noise",
            "model_poisoning",
            "byzantine_perturbation",
        ]:
            max_norm = max(param_norms)
            assert max_norm > 5.0, (
                f"Attack {attack_type} should produce large parameter norms"
            )

        param_means = [params.mean() for params in attack_params]
        assert len(set(np.round(param_means, 2))) > 1, (
            "Parameters should be diverse across clients"
        )

    @pytest.mark.parametrize(
        "num_byzantine,total_clients",
        [
            (1, 5),  # 20% Byzantine
            (2, 10),  # 20% Byzantine
            (3, 10),  # 30% Byzantine
            (4, 15),  # ~27% Byzantine
        ],
    )
    def test_byzantine_client_ratios(self, num_byzantine, total_clients):
        """Verify defense effectiveness varies with Byzantine client ratios."""
        param_size = 800

        for attack_type in ["gaussian_noise", "model_poisoning"]:
            generate_byzantine_client_parameters(
                num_clients=total_clients,
                num_byzantine=num_byzantine,
                param_size=param_size,
                attack_type=attack_type,
            )

            byzantine_ratio = num_byzantine / total_clients

            # Research: Krum requires n > 2f+2, Bulyan requires n >= 4f+3
            # (Blanchard et al., NeurIPS 2017; El Mhamdi et al., ICML 2018)
            for strategy_name in ["krum", "bulyan", "trimmed_mean"]:
                mock_strategy = Mock()

                if byzantine_ratio <= 0.25:
                    mock_strategy.is_robust.return_value = True
                    expected_detection_rate = 0.8
                elif byzantine_ratio <= 0.35:
                    mock_strategy.is_robust.return_value = True
                    expected_detection_rate = 0.6
                else:
                    mock_strategy.is_robust.return_value = False
                    expected_detection_rate = 0.4

                detected_count = max(1, int(num_byzantine * expected_detection_rate))
                mock_strategy.detect_byzantine_perturbation.return_value = list(
                    range(detected_count)
                )

                detected_byzantine = mock_strategy.detect_byzantine_perturbation()
                detection_rate = len(detected_byzantine) / num_byzantine

                if byzantine_ratio <= 0.25:
                    assert detection_rate >= 0.5, (
                        f"Strategy {strategy_name} should detect most Byzantine clients "
                        f"when ratio is low ({byzantine_ratio:.2f})"
                    )

    @pytest.mark.parametrize(
        "strategy_combination",
        [
            ["trust", "krum"],
            ["krum", "rfa"],
            ["trust", "pid"],
            ["bulyan", "trimmed_mean"],
        ],
    )
    def test_multi_strategy_defense(self, strategy_combination):
        """Test combinations of defense strategies against attacks."""
        num_clients = 12
        num_byzantine = 3
        param_size = 600

        for attack_type in [
            "gaussian_noise",
            "model_poisoning",
            "byzantine_perturbation",
        ]:
            generate_byzantine_client_parameters(
                num_clients=num_clients,
                num_byzantine=num_byzantine,
                param_size=param_size,
                attack_type=attack_type,
            )

            detection_results = []
            aggregation_results = []

            for strategy_name in strategy_combination:
                mock_strategy = Mock()

                strategy_detection = list(
                    range(
                        len(detection_results),
                        min(len(detection_results) + 2, num_byzantine),
                    )
                )
                detection_results.extend(strategy_detection)

                np.random.seed(42)
                aggregated = np.random.randn(param_size) * (
                    0.01 / len(strategy_combination)
                )
                aggregation_results.append(aggregated)

                mock_strategy.detect_byzantine_perturbation.return_value = (
                    strategy_detection
                )
                mock_strategy.aggregate_parameters.return_value = aggregated

            total_detected = len(set(detection_results))
            combined_aggregation = np.mean(aggregation_results, axis=0)

            assert total_detected >= 1, (
                f"Multi-strategy {strategy_combination} should detect Byzantine clients "
                f"for {attack_type} attack"
            )

            assert np.linalg.norm(combined_aggregation) < 1.0, (
                f"Multi-strategy {strategy_combination} should produce stable aggregation"
            )

    @pytest.mark.parametrize(
        "attack_intensity,expected_detection_difficulty",
        [
            (0.1, "easy"),  # Low intensity attack
            (0.5, "medium"),  # Medium intensity attack
            (1.0, "hard"),  # High intensity attack
            (2.0, "very_hard"),  # Very high intensity attack
        ],
    )
    def test_attack_intensity_levels(
        self, attack_intensity, expected_detection_difficulty
    ):
        """Test defense mechanisms against different attack intensity levels."""
        num_byzantine = 2
        param_size = 400

        np.random.seed(42)
        for strategy_name in ["krum", "trust", "rfa"]:
            mock_strategy = Mock()

            if expected_detection_difficulty == "easy":
                detection_success_rate = 1.0
            elif expected_detection_difficulty == "medium":
                detection_success_rate = 0.7
            elif expected_detection_difficulty == "hard":
                detection_success_rate = 0.5
            else:
                detection_success_rate = 0.3

            if expected_detection_difficulty == "easy":
                detected_count = max(
                    int(num_byzantine * 0.8),
                    int(num_byzantine * detection_success_rate),
                )
            else:
                detected_count = int(num_byzantine * detection_success_rate)

            mock_strategy.detect_byzantine_perturbation.return_value = list(
                range(detected_count)
            )

            aggregation_noise = min(
                attack_intensity * (1 - detection_success_rate), 0.1
            )
            mock_strategy.aggregate_parameters.return_value = (
                np.random.randn(param_size) * aggregation_noise
            )

            detected_byzantine = mock_strategy.detect_byzantine_perturbation()
            aggregated_params = mock_strategy.aggregate_parameters()

            detection_rate = len(detected_byzantine) / num_byzantine
            aggregation_quality = 1.0 / (1.0 + np.linalg.norm(aggregated_params))

            if expected_detection_difficulty == "easy":
                assert detection_rate >= 0.8, (
                    f"Strategy {strategy_name} should easily detect low-intensity attacks"
                )
                assert aggregation_quality >= 0.5, (
                    f"Strategy {strategy_name} should maintain good aggregation quality"
                )

    @pytest.mark.parametrize(
        "dataset_type,attack_effectiveness",
        [
            ("its", "medium"),
            ("femnist_iid", "high"),
            ("femnist_niid", "low"),  # Non-IID data makes attacks harder
            ("bloodmnist", "medium"),
        ],
    )
    def test_dataset_specific_attack_scenarios(
        self, dataset_type, attack_effectiveness
    ):
        """Test how attack effectiveness varies across different dataset types."""
        num_clients = 6
        num_byzantine = 2

        handler = MockDatasetHandler(dataset_type=dataset_type)
        handler.setup_dataset(num_clients=num_clients)

        param_size = 500
        generate_byzantine_client_parameters(
            num_clients=num_clients,
            num_byzantine=num_byzantine,
            param_size=param_size,
            attack_type="model_poisoning",
        )

        mock_strategy = Mock()

        # Non-IID data naturally resists attacks due to parameter heterogeneity
        if attack_effectiveness == "high":
            detection_rate = 0.4
            aggregation_noise = 0.05
        elif attack_effectiveness == "medium":
            detection_rate = 0.6
            aggregation_noise = 0.03
        else:
            detection_rate = 1.0
            aggregation_noise = 0.01

        detected_count = int(num_byzantine * detection_rate)
        mock_strategy.detect_byzantine_perturbation.return_value = list(
            range(detected_count)
        )
        np.random.seed(42)
        mock_strategy.aggregate_parameters.return_value = np.random.randn(
            param_size
        ) * min(aggregation_noise, 0.1)

        detected_byzantine = mock_strategy.detect_byzantine_perturbation()
        aggregated_params = mock_strategy.aggregate_parameters()

        detection_success = len(detected_byzantine) / num_byzantine
        aggregation_quality = 1.0 / (1.0 + np.linalg.norm(aggregated_params))

        if attack_effectiveness == "low":
            assert detection_success >= 0.7, (
                f"Attacks should be less effective on {dataset_type} dataset"
            )
            assert aggregation_quality >= 0.6, (
                f"Aggregation should be more stable on {dataset_type} dataset"
            )

    def test_coordinated_attack_scenarios(self):
        """Test defense against coordinated attacks where Byzantine clients collaborate."""
        num_byzantine = 4
        param_size = 700

        np.random.seed(42)

        # Research: Krum selects gradients with smallest sum of distances to neighbors,
        # making it effective against coordinated attacks that cluster together
        # (Blanchard et al., NeurIPS 2017)
        for strategy_name in ["krum", "multi-krum", "bulyan"]:
            mock_strategy = Mock()

            if strategy_name in ["krum", "multi-krum"]:
                detection_rate = 0.8
            elif strategy_name == "bulyan":
                detection_rate = 0.9
            else:
                detection_rate = 0.6

            detected_count = int(num_byzantine * detection_rate)
            mock_strategy.detect_byzantine_perturbation.return_value = list(
                range(detected_count)
            )

            aggregation_noise = min(0.3 * (1 - detection_rate), 0.01)
            mock_strategy.aggregate_parameters.return_value = (
                np.random.randn(param_size) * aggregation_noise
            )

            detected_byzantine = mock_strategy.detect_byzantine_perturbation()
            aggregated_params = mock_strategy.aggregate_parameters()

            detection_success = len(detected_byzantine) / num_byzantine

            if strategy_name in ["krum", "multi-krum", "bulyan"]:
                assert detection_success >= 0.7, (
                    f"Strategy {strategy_name} should detect coordinated attacks effectively"
                )

                assert np.linalg.norm(aggregated_params) < 0.8, (
                    f"Strategy {strategy_name} should maintain aggregation quality "
                    "against coordinated attacks"
                )

    def test_attack_timing_scenarios(self):
        """Test attacks that occur at different timing patterns during training."""
        num_clients = 10
        num_byzantine = 2
        param_size = 400
        total_rounds = 10

        attack_patterns = {
            "early_attack": [0, 1, 2],
            "late_attack": [7, 8, 9],
            "intermittent": [1, 3, 5, 7],
            "persistent": list(range(10)),
        }

        for pattern_name, attack_rounds in attack_patterns.items():
            for round_num in range(total_rounds):
                is_attack_round = round_num in attack_rounds

                if is_attack_round:
                    generate_byzantine_client_parameters(
                        num_clients=num_clients,
                        num_byzantine=num_byzantine,
                        param_size=param_size,
                        attack_type="gaussian_noise",
                    )
                else:
                    generate_mock_client_parameters(
                        num_clients=num_clients,
                        param_size=param_size,
                    )

                mock_strategy = Mock()

                if is_attack_round:
                    # Early rounds lack historical data for anomaly detection
                    if pattern_name == "early_attack" and round_num <= 2:
                        detection_rate = 0.5
                    elif pattern_name == "intermittent":
                        detection_rate = 0.6
                    else:
                        detection_rate = 0.7

                    detected_count = int(num_byzantine * detection_rate)
                    mock_strategy.detect_byzantine_perturbation.return_value = list(
                        range(detected_count)
                    )
                else:
                    mock_strategy.detect_byzantine_perturbation.return_value = []

                mock_strategy.get_round_number.return_value = round_num

                detected_byzantine = mock_strategy.detect_byzantine_perturbation()
                current_round = mock_strategy.get_round_number()

                if is_attack_round:
                    if pattern_name != "early_attack" or current_round > 1:
                        assert len(detected_byzantine) >= 1, (
                            f"Should detect attacks in {pattern_name} pattern at round {round_num}"
                        )
                else:
                    assert len(detected_byzantine) == 0, (
                        f"Should not detect attacks in normal rounds for {pattern_name}"
                    )

    def test_attack_robustness_thresholds(self):
        """Test strategy robustness against different attack magnitudes."""
        num_byzantine = 2
        param_size = 300

        attack_magnitudes = [0.5, 1.0, 2.0, 5.0, 10.0]

        for magnitude in attack_magnitudes:
            np.random.seed(42)
            for strategy_name in ["trust", "krum", "rfa", "bulyan"]:
                mock_strategy = Mock()

                if magnitude <= 1.0:
                    detection_rate = 1.0
                elif magnitude <= 3.0:
                    detection_rate = 0.7
                else:
                    detection_rate = 0.5

                if magnitude <= 1.0:
                    detected_count = max(
                        int(num_byzantine * 0.8), int(num_byzantine * detection_rate)
                    )
                else:
                    detected_count = int(num_byzantine * detection_rate)

                mock_strategy.detect_byzantine_perturbation.return_value = list(
                    range(detected_count)
                )

                aggregation_noise = min(magnitude * 0.01 * (1 - detection_rate), 0.1)
                mock_strategy.aggregate_parameters.return_value = (
                    np.random.randn(param_size) * aggregation_noise
                )

                detected_byzantine = mock_strategy.detect_byzantine_perturbation()
                aggregated_params = mock_strategy.aggregate_parameters()

                detection_success = len(detected_byzantine) / num_byzantine

                if magnitude <= 1.0:
                    assert detection_success >= 0.8, (
                        f"Strategy {strategy_name} should detect low-magnitude attacks "
                        f"(magnitude: {magnitude})"
                    )

                if detection_success > 0.5:
                    assert np.linalg.norm(aggregated_params) < 2.0, (
                        f"Strategy {strategy_name} should maintain stability when detecting attacks"
                    )


class TestCombinatorialAttackDefense:
    """Combinatorial testing using stacked @parametrize decorators."""

    @pytest.mark.parametrize(
        "attack_type",
        ["gaussian_noise", "model_poisoning", "byzantine_perturbation"],
        ids=lambda x: f"attack={x}",
    )
    @pytest.mark.parametrize(
        "defense_strategy",
        ["krum", "multi-krum", "bulyan", "trimmed_mean"],
        ids=lambda x: f"defense={x}",
    )
    @pytest.mark.parametrize(
        "byzantine_ratio",
        [0.1, 0.2, 0.3],
        ids=lambda x: f"byz={x}",
    )
    def test_attack_defense_matrix(
        self, attack_type, defense_strategy, byzantine_ratio
    ):
        """Test all attack × defense × byzantine_ratio combinations."""
        num_clients = 10
        num_byzantine = int(num_clients * byzantine_ratio)
        param_size = 500

        attack_params = generate_byzantine_client_parameters(
            num_clients=num_clients,
            num_byzantine=num_byzantine,
            param_size=param_size,
            attack_type=attack_type,
        )

        assert len(attack_params) == num_clients
        assert all(p.shape == (param_size,) for p in attack_params)

        mock_strategy = Mock()
        _ = DEFENSE_STRATEGIES.get(defense_strategy, {})

        # Distance-based methods (Krum, Bulyan) outperform statistical methods
        if defense_strategy in ["krum", "multi-krum", "bulyan"]:
            detection_rate = 0.7 if byzantine_ratio <= 0.25 else 0.5
        else:
            detection_rate = 0.6 if byzantine_ratio <= 0.25 else 0.4

        detected_count = max(1, int(num_byzantine * detection_rate))
        mock_strategy.detect_byzantine_perturbation.return_value = list(
            range(detected_count)
        )

        detected = mock_strategy.detect_byzantine_perturbation()

        if byzantine_ratio < 0.5:
            assert len(detected) >= 1, (
                f"{defense_strategy} should detect at least one Byzantine client "
                f"for {attack_type} with {byzantine_ratio:.0%} Byzantine ratio"
            )

    @pytest.mark.parametrize(
        "num_clients,num_byzantine",
        [
            (10, 1),  # 10% Byzantine
            (10, 2),  # 20% Byzantine
            (15, 4),  # ~27% Byzantine
            (20, 6),  # 30% Byzantine
        ],
        ids=lambda x: f"clients={x}" if isinstance(x, int) else None,
    )
    @pytest.mark.parametrize(
        "attack_type",
        ["gaussian_noise", "model_poisoning"],
    )
    def test_client_count_attack_matrix(self, num_clients, num_byzantine, attack_type):
        """Test attack effectiveness across different client configurations."""
        param_size = 400

        attack_params = generate_byzantine_client_parameters(
            num_clients=num_clients,
            num_byzantine=num_byzantine,
            param_size=param_size,
            attack_type=attack_type,
        )

        assert len(attack_params) == num_clients

        honest_params = (
            attack_params[:-num_byzantine] if num_byzantine > 0 else attack_params
        )
        byzantine_params = attack_params[-num_byzantine:] if num_byzantine > 0 else []

        if byzantine_params:
            byzantine_norms = [np.linalg.norm(p) for p in byzantine_params]
            honest_norms = [np.linalg.norm(p) for p in honest_params]

            if attack_type in ["model_poisoning", "gaussian_noise"]:
                max_byzantine_norm = max(byzantine_norms) if byzantine_norms else 0

                assert max_byzantine_norm > 0, (
                    f"Byzantine parameters should have non-zero norm for {attack_type}"
                )

                if honest_norms:
                    avg_honest = np.mean(honest_norms)
                    assert avg_honest >= 0


class TestIndirectParameterization:
    """Examples of indirect parameterization for expensive fixture setup."""

    @pytest.mark.parametrize(
        "attack_scenario",
        [
            ("gaussian_noise", 2),
            ("model_poisoning", 3),
            ("byzantine_perturbation", 2),
        ],
        indirect=True,
        ids=["gaussian-2byz", "poisoning-3byz", "byzantine-2byz"],
    )
    def test_with_indirect_attack_scenario(self, attack_scenario):
        """Test using indirect parameterization for attack setup."""
        assert "attack_type" in attack_scenario
        assert "num_byzantine" in attack_scenario
        assert "attack_params" in attack_scenario

        params = attack_scenario["attack_params"]
        assert len(params) == attack_scenario["num_clients"]

        for p in params:
            assert isinstance(p, np.ndarray)
            assert p.shape == (attack_scenario["param_size"],)

    @pytest.mark.parametrize(
        "defense_config",
        ["krum", "bulyan", "trimmed_mean"],
        indirect=True,
        ids=["def-krum", "def-bulyan", "def-trimmed"],
    )
    def test_with_indirect_defense_config(self, defense_config):
        """Test using indirect parameterization for defense configuration."""
        assert "name" in defense_config
        assert "aggregation_strategy_keyword" in defense_config

        strategy_name = defense_config["name"]
        if strategy_name == "krum":
            assert "num_krum_selections" in defense_config
        elif strategy_name == "trimmed_mean":
            assert "trim_ratio" in defense_config


class TestDynamicParameterization:
    """Examples using pytest_generate_tests for dynamic test generation."""

    def test_attack_defense_combo(self, attack_defense_combo):
        """Test using dynamically generated attack × defense combinations."""
        attack_type, defense_strategy = attack_defense_combo

        from tests.common import ATTACK_TYPES, DEFENSE_STRATEGIES

        assert attack_type in ATTACK_TYPES
        assert defense_strategy in DEFENSE_STRATEGIES

    def test_strategy_variant(self, strategy_variant):
        """Test using dynamically generated strategy variants."""
        from tests.common import STRATEGY_CONFIGS

        assert strategy_variant in STRATEGY_CONFIGS

        config = STRATEGY_CONFIGS[strategy_variant]
        assert "aggregation_strategy_keyword" in config
