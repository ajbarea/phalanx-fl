"""Unit tests for API Pydantic models."""

from __future__ import annotations

import warnings

import pytest
from pydantic import ValidationError

from intellifl.api.models import (
    AllPlotDataResponse,
    CreateSimulationRequest,
    DatasetInfo,
    DatasetValidationResponse,
    SimulationSettings,
    SimulationStatusResponse,
    StrategyOverrides,
    StrategyPlotData,
)


class TestBooleanFields:
    """Test boolean fields in Pydantic models using actual boolean values."""

    @pytest.mark.parametrize(
        "input_val,expected",
        [
            (True, True),
            (False, False),
        ],
    )
    def test_bool_values_accepted(self, input_val: bool, expected: bool) -> None:
        """Test that actual boolean values are accepted correctly."""
        settings = SimulationSettings(remove_clients=input_val)
        assert settings.remove_clients is expected

    @pytest.mark.parametrize(
        "field_name",
        [
            "remove_clients",
            "show_plots",
            "save_plots",
            "save_csv",
            "save_attack_snapshots",
            "preserve_dataset",
            "strict_mode",
            "use_llm",
        ],
    )
    def test_all_bool_fields_accept_true(self, field_name: str) -> None:
        """Test that all boolean fields accept True."""
        settings = SimulationSettings(**{field_name: True})  # type: ignore[arg-type]
        assert getattr(settings, field_name) is True

    @pytest.mark.parametrize(
        "field_name",
        [
            "remove_clients",
            "show_plots",
            "save_plots",
            "save_csv",
            "save_attack_snapshots",
            "preserve_dataset",
            "strict_mode",
            "use_llm",
        ],
    )
    def test_all_bool_fields_accept_false(self, field_name: str) -> None:
        """Test that all boolean fields accept False."""
        settings = SimulationSettings(**{field_name: False})  # type: ignore[arg-type]
        assert getattr(settings, field_name) is False

    def test_invalid_bool_raises_error(self) -> None:
        """Test that invalid boolean values raise validation error."""
        with pytest.warns(DeprecationWarning):
            with pytest.raises(ValueError, match="Cannot coerce"):
                SimulationSettings(remove_clients="maybe")  # type: ignore[arg-type]

    def test_none_value_preserved(self) -> None:
        """Test that None values are preserved."""
        settings = SimulationSettings(remove_clients=None)
        assert settings.remove_clients is None


class TestSimulationSettings:
    """Test SimulationSettings model."""

    def test_accepts_all_standard_fields(self) -> None:
        """Test that standard fields are accepted."""
        settings = SimulationSettings(
            display_name="Test Sim",
            aggregation_strategy_keyword="fedavg",
            num_of_rounds=10,
            num_of_clients=5,
            remove_clients=True,
        )
        assert settings.display_name == "Test Sim"
        assert settings.aggregation_strategy_keyword == "fedavg"
        assert settings.num_of_rounds == 10
        assert settings.num_of_clients == 5
        assert settings.remove_clients is True

    def test_allows_extra_fields(self) -> None:
        """Test that extra fields are allowed (for future compatibility)."""
        settings = SimulationSettings(
            custom_field="custom_value",  # type: ignore[call-arg]
            another_field=123,  # type: ignore[call-arg]
        )
        assert (settings.model_extra or {})["custom_field"] == "custom_value"
        assert (settings.model_extra or {})["another_field"] == 123


class TestStrategyOverrides:
    """Test StrategyOverrides model."""

    def test_basic_overrides(self) -> None:
        """Test basic strategy overrides."""
        overrides = StrategyOverrides(
            aggregation_strategy_keyword="krum",
            num_krum_selections=3,
            remove_clients=True,
        )
        assert overrides.aggregation_strategy_keyword == "krum"
        assert overrides.num_krum_selections == 3
        assert overrides.remove_clients is True

    def test_bool_in_overrides(self) -> None:
        """Test boolean values work in StrategyOverrides."""
        overrides = StrategyOverrides(remove_clients=True)
        assert overrides.remove_clients is True


class TestCreateSimulationRequest:
    """Test CreateSimulationRequest model."""

    def test_single_sim_mode_detection(self) -> None:
        """Test that single-sim mode is detected correctly."""
        request = CreateSimulationRequest(
            aggregation_strategy_keyword="fedavg",  # type: ignore[call-arg]
            num_of_rounds=10,  # type: ignore[call-arg]
        )
        assert not request.is_multi_sim_mode()

    def test_multi_sim_mode_detection(self) -> None:
        """Test that multi-sim mode is detected correctly."""
        request = CreateSimulationRequest(
            shared_settings=SimulationSettings(num_of_rounds=10),
            simulation_strategies=[StrategyOverrides(aggregation_strategy_keyword="fedavg")],
        )
        assert request.is_multi_sim_mode()

    def test_single_sim_to_config_dict(self) -> None:
        """Test single-sim config dict conversion."""
        request = CreateSimulationRequest(
            aggregation_strategy_keyword="fedavg",  # type: ignore[call-arg]
            num_of_rounds=10,  # type: ignore[call-arg]
            remove_clients=True,  # type: ignore[call-arg]
        )
        config = request.to_config_dict()

        # Single-sim mode returns flat config
        assert config.get("aggregation_strategy_keyword") == "fedavg"
        assert config.get("num_of_rounds") == 10
        # Booleans are stored as actual booleans (best practice)
        assert config.get("remove_clients") is True

    def test_multi_sim_to_config_dict(self) -> None:
        """Test multi-sim config dict conversion."""
        request = CreateSimulationRequest(
            shared_settings=SimulationSettings(
                num_of_rounds=10,
                remove_clients=True,
            ),
            simulation_strategies=[
                StrategyOverrides(aggregation_strategy_keyword="fedavg"),
            ],
        )
        config = request.to_config_dict()

        # Multi-sim mode has nested structure
        assert "shared_settings" in config
        assert "simulation_strategies" in config
        assert config["shared_settings"]["num_of_rounds"] == 10
        # Booleans are stored as actual booleans (best practice)
        assert config["shared_settings"]["remove_clients"] is True

    def test_add_to_queue_default(self) -> None:
        """Test add_to_queue defaults to False."""
        request = CreateSimulationRequest(aggregation_strategy_keyword="fedavg")  # type: ignore[call-arg]
        assert request.add_to_queue is False

    def test_add_to_queue_explicit(self) -> None:
        """Test add_to_queue can be set explicitly."""
        request = CreateSimulationRequest(
            aggregation_strategy_keyword="fedavg",  # type: ignore[call-arg]
            add_to_queue=True,
        )
        assert request.add_to_queue is True

    def test_get_config_without_queue_flag(self) -> None:
        """Test that add_to_queue is excluded from config."""
        request = CreateSimulationRequest(
            aggregation_strategy_keyword="fedavg",  # type: ignore[call-arg]
            add_to_queue=True,
        )
        config = request.get_config_without_queue_flag()

        # add_to_queue should not be in the config
        assert "add_to_queue" not in config
        assert config.get("aggregation_strategy_keyword") == "fedavg"


class TestBooleanStorage:
    """Test that boolean values are stored correctly."""

    def test_bool_types_stored_as_actual_bools(self) -> None:
        """Test that boolean types are stored as actual booleans."""
        settings = SimulationSettings(
            aggregation_strategy_keyword="fedavg",
            remove_clients=True,
            show_plots=False,
            save_plots=False,
        )

        # All are stored as actual booleans
        assert settings.remove_clients is True
        assert settings.show_plots is False
        assert settings.save_plots is False

    def test_extra_fields_not_coerced(self) -> None:
        """Test that extra fields (not defined in model) are not coerced."""
        request = CreateSimulationRequest(
            aggregation_strategy_keyword="fedavg",  # type: ignore[call-arg]
            custom_bool_field="true",  # type: ignore[call-arg] # Extra field - won't be coerced
        )
        config = request.to_config_dict()

        # Extra fields passed through as-is
        assert config.get("custom_bool_field") == "true"


class TestDeprecationWarnings:
    """Test deprecation warnings for string boolean inputs."""

    def test_string_bool_emits_deprecation_warning(self) -> None:
        """Test that string boolean inputs emit deprecation warnings."""
        with pytest.warns(DeprecationWarning, match="deprecated"):
            SimulationSettings(remove_clients="true")  # type: ignore[arg-type]

    def test_actual_bool_no_warning(self) -> None:
        """Test that actual boolean inputs don't emit warnings."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            # This should not raise because we're using actual boolean
            SimulationSettings(remove_clients=True)

    def test_none_value_no_warning(self) -> None:
        """Test that None values don't emit warnings."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            SimulationSettings(remove_clients=None)


class TestFieldConstraints:
    """Test Field validation constraints."""

    def test_num_of_rounds_minimum(self) -> None:
        """Test num_of_rounds must be >= 1."""
        with pytest.raises(ValidationError):
            SimulationSettings(num_of_rounds=0)

    def test_num_of_rounds_valid(self) -> None:
        """Test valid num_of_rounds values."""
        settings = SimulationSettings(num_of_rounds=100)
        assert settings.num_of_rounds == 100

    def test_num_of_rounds_maximum(self) -> None:
        """Test num_of_rounds must be <= 10000."""
        with pytest.raises(ValidationError):
            SimulationSettings(num_of_rounds=10001)

    def test_num_of_clients_minimum(self) -> None:
        """Test num_of_clients must be >= 1."""
        with pytest.raises(ValidationError):
            SimulationSettings(num_of_clients=0)

    def test_training_subset_fraction_range(self) -> None:
        """Test training_subset_fraction must be (0, 1]."""
        with pytest.raises(ValidationError):
            SimulationSettings(training_subset_fraction=0)
        with pytest.raises(ValidationError):
            SimulationSettings(training_subset_fraction=1.5)

    def test_training_subset_fraction_valid(self) -> None:
        """Test valid training_subset_fraction values."""
        settings = SimulationSettings(training_subset_fraction=0.5)
        assert settings.training_subset_fraction == 0.5
        settings = SimulationSettings(training_subset_fraction=1.0)
        assert settings.training_subset_fraction == 1.0

    def test_trust_threshold_range(self) -> None:
        """Test trust_threshold must be [0, 1]."""
        with pytest.raises(ValidationError):
            SimulationSettings(trust_threshold=-0.1)
        with pytest.raises(ValidationError):
            SimulationSettings(trust_threshold=1.1)

    def test_trust_threshold_valid(self) -> None:
        """Test valid trust_threshold values."""
        settings = SimulationSettings(trust_threshold=0.0)
        assert settings.trust_threshold == 0.0
        settings = SimulationSettings(trust_threshold=1.0)
        assert settings.trust_threshold == 1.0

    def test_trim_ratio_range(self) -> None:
        """Test trim_ratio must be [0, 0.5)."""
        with pytest.raises(ValidationError):
            SimulationSettings(trim_ratio=-0.1)
        with pytest.raises(ValidationError):
            SimulationSettings(trim_ratio=0.5)

    def test_trim_ratio_valid(self) -> None:
        """Test valid trim_ratio values."""
        settings = SimulationSettings(trim_ratio=0.0)
        assert settings.trim_ratio == 0.0
        settings = SimulationSettings(trim_ratio=0.49)
        assert settings.trim_ratio == 0.49

    def test_learning_rate_positive(self) -> None:
        """Test learning_rate must be > 0."""
        with pytest.raises(ValidationError):
            SimulationSettings(learning_rate=0)
        with pytest.raises(ValidationError):
            SimulationSettings(learning_rate=-0.1)

    def test_learning_rate_valid(self) -> None:
        """Test valid learning_rate values."""
        settings = SimulationSettings(learning_rate=0.001)
        assert settings.learning_rate == 0.001

    def test_snapshot_max_samples_range(self) -> None:
        """Test snapshot_max_samples must be [1, 50]."""
        with pytest.raises(ValidationError):
            SimulationSettings(snapshot_max_samples=0)
        with pytest.raises(ValidationError):
            SimulationSettings(snapshot_max_samples=51)

    def test_snapshot_max_samples_valid(self) -> None:
        """Test valid snapshot_max_samples values."""
        settings = SimulationSettings(snapshot_max_samples=1)
        assert settings.snapshot_max_samples == 1
        settings = SimulationSettings(snapshot_max_samples=50)
        assert settings.snapshot_max_samples == 50


class TestResponseModels:
    """Test new response models."""

    def test_simulation_status_response(self) -> None:
        """Test SimulationStatusResponse model."""
        response = SimulationStatusResponse(
            status="running",
            progress=0.5,
            current_round=5,
            total_rounds=10,
        )
        assert response.status == "running"
        assert response.progress == 0.5
        assert response.current_round == 5
        assert response.total_rounds == 10

    def test_simulation_status_response_defaults(self) -> None:
        """Test SimulationStatusResponse default values."""
        response = SimulationStatusResponse(status="pending")
        assert response.status == "pending"
        assert response.progress == 0.0
        assert response.current_round is None
        assert response.error is None

    def test_simulation_status_response_invalid_status(self) -> None:
        """Test SimulationStatusResponse rejects invalid status."""
        with pytest.raises(ValidationError):
            SimulationStatusResponse(status="invalid_status")  # type: ignore[arg-type]

    def test_simulation_status_response_progress_range(self) -> None:
        """Test SimulationStatusResponse progress must be [0, 1]."""
        with pytest.raises(ValidationError):
            SimulationStatusResponse(status="running", progress=-0.1)
        with pytest.raises(ValidationError):
            SimulationStatusResponse(status="running", progress=1.1)

    def test_dataset_info(self) -> None:
        """Test DatasetInfo model."""
        info = DatasetInfo(
            splits=["train", "test"],
            num_examples=1000,
            features="{'image': Image, 'label': ClassLabel}",
            has_label=True,
            key_features=["image", "label"],
        )
        assert info.splits == ["train", "test"]
        assert info.num_examples == 1000
        assert info.has_label is True

    def test_dataset_validation_response_valid(self) -> None:
        """Test DatasetValidationResponse with valid dataset."""
        response = DatasetValidationResponse(
            valid=True,
            compatible=True,
            info=DatasetInfo(
                splits=["train", "test"],
                num_examples=1000,
                features="...",
                has_label=True,
                key_features=["label", "image"],
            ),
        )
        assert response.valid is True
        assert response.info is not None
        assert response.info.num_examples == 1000

    def test_dataset_validation_response_invalid(self) -> None:
        """Test DatasetValidationResponse with invalid dataset."""
        response = DatasetValidationResponse(
            valid=False,
            compatible=False,
            error="Dataset not found",
        )
        assert response.valid is False
        assert response.info is None
        assert response.error == "Dataset not found"

    def test_strategy_plot_data(self) -> None:
        """Test StrategyPlotData model."""
        data = StrategyPlotData(
            strategy_number=1,
            data={"rounds": [1, 2, 3], "accuracy": [0.5, 0.6, 0.7]},
        )
        assert data.strategy_number == 1
        assert data.data["accuracy"] == [0.5, 0.6, 0.7]

    def test_all_plot_data_response(self) -> None:
        """Test AllPlotDataResponse model."""
        response = AllPlotDataResponse(
            strategies=[
                StrategyPlotData(strategy_number=1, data={"accuracy": [0.5]}),
                StrategyPlotData(strategy_number=2, data={"accuracy": [0.6]}),
            ]
        )
        assert len(response.strategies) == 2
        assert response.strategies[0].strategy_number == 1
        assert response.strategies[1].strategy_number == 2
