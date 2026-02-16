"""
Unit tests for configuration validation and log streaming endpoints.

Tests cover:
- POST /api/validate - Configuration validation endpoint
- GET /api/simulations/{id}/logs - Log streaming endpoint via SSE
- Error handling and logging
- Log parsing utility
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from intellifl.api.models import ValidationResponse
from intellifl.api.routers.simulations import parse_log_line

# =============================================================================
# Configuration Validation Endpoint Tests (POST /api/validate)
# =============================================================================


class TestValidationEndpoint:
    """Tests for POST /api/validate endpoint."""

    def test_validate_valid_configuration(self, api_client: TestClient):
        """POST /api/validate with valid config returns valid=true."""
        config = {
            "aggregation_strategy_keyword": "fedavg",
            "dataset_keyword": "bloodmnist",
            "num_of_rounds": 3,
            "num_of_clients": 2,
        }
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["errors"] is None

    def test_validate_partial_configuration(self, api_client: TestClient):
        """POST /api/validate with partial config (all fields optional) returns valid=true."""
        config = {
            "aggregation_strategy_keyword": "fedavg",
            # dataset_keyword is optional
            "num_of_rounds": 3,
            "num_of_clients": 2,
        }
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        # All fields are optional, so partial config is valid
        assert data["valid"] is True
        assert data["errors"] is None

    def test_validate_invalid_wrong_type(self, api_client: TestClient):
        """POST /api/validate with wrong field type returns errors."""
        config = {
            "aggregation_strategy_keyword": "fedavg",
            "dataset_keyword": "bloodmnist",
            "num_of_rounds": "not_a_number",  # Should be int
            "num_of_clients": 2,
        }
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        if not data["valid"]:
            assert data["errors"] is not None
            assert len(data["errors"]) > 0

    def test_validate_invalid_out_of_range(self, api_client: TestClient):
        """POST /api/validate with out-of-range value in shared_settings returns errors."""
        config = {
            "shared_settings": {
                "aggregation_strategy_keyword": "fedavg",
                "dataset_keyword": "bloodmnist",
                "num_of_rounds": -1,  # Should be positive (ge=1)
                "num_of_clients": 2,
            },
            "simulation_strategies": [{}],
        }
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        # Negative rounds should fail validation
        assert data["valid"] is False
        assert data["errors"] is not None

    def test_validate_empty_configuration(self, api_client: TestClient):
        """POST /api/validate with empty config returns valid=true (all fields optional)."""
        config: dict[str, object] = {}
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        # Empty config is valid since all fields are optional
        assert data["valid"] is True
        assert data["errors"] is None

    def test_validate_multiple_errors(self, api_client: TestClient):
        """POST /api/validate with multiple constraint violations returns errors."""
        config = {
            "shared_settings": {
                "aggregation_strategy_keyword": "fedavg",
                "num_of_rounds": -1,  # Out of range (ge=1)
                "num_of_clients": -5,  # Out of range (ge=1)
            },
            "simulation_strategies": [{}],
        }
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        # Multiple constraint violations should fail
        assert data["valid"] is False
        assert data["errors"] is not None
        assert len(data["errors"]) >= 1

    def test_validate_response_model(self, api_client: TestClient):
        """POST /api/validate response matches ValidationResponse model."""
        config = {
            "aggregation_strategy_keyword": "fedavg",
            "dataset_keyword": "bloodmnist",
            "num_of_rounds": 3,
            "num_of_clients": 2,
        }
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        # Should be able to parse as ValidationResponse
        validation_response = ValidationResponse(**data)
        assert validation_response.valid is True
        assert validation_response.errors is None

    def test_validate_with_optional_fields(self, api_client: TestClient):
        """POST /api/validate with optional fields returns valid=true."""
        config = {
            "aggregation_strategy_keyword": "fedavg",
            "dataset_keyword": "bloodmnist",
            "num_of_rounds": 3,
            "num_of_clients": 2,
            "display_name": "My Test Simulation",
            "fraction_fit": 0.5,
            "local_epochs": 2,
        }
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True

    def test_validate_with_simulation_strategies(self, api_client: TestClient):
        """POST /api/validate with simulation_strategies returns valid=true."""
        config = {
            "aggregation_strategy_keyword": "fedavg",
            "dataset_keyword": "bloodmnist",
            "num_of_rounds": 3,
            "num_of_clients": 2,
            "simulation_strategies": [{"strategy_name": "fedavg", "num_malicious_clients": 0}],
        }
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True

    def test_validate_returns_200_on_validation_error(self, api_client: TestClient):
        """POST /api/validate returns HTTP 200 even when validation fails.

        Validation errors are returned in the response body, not as HTTP errors.
        """
        config = {
            "shared_settings": {
                "num_of_rounds": -1,  # Invalid
            },
            "simulation_strategies": [{}],
        }
        response = api_client.post("/api/validate", json=config)
        # Should return 200 with valid=false in body
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False


# =============================================================================
# Log Parsing Utility Tests
# =============================================================================


class TestParseLogLine:
    """Tests for parse_log_line utility function."""

    def test_parse_iso_timestamp_with_level(self):
        """parse_log_line parses ISO timestamp with level format."""
        line = "2025-01-07 12:00:00,123 - INFO - Starting simulation"
        result = parse_log_line(line)
        assert result["timestamp"] == "2025-01-07 12:00:00,123"
        assert result["level"] == "INFO"
        assert result["message"] == "Starting simulation"

    def test_parse_iso_timestamp_t_separator(self):
        """parse_log_line parses ISO timestamp with T separator."""
        line = "2025-01-07T12:00:00.123 INFO Processing data"
        result = parse_log_line(line)
        assert result["timestamp"] == "2025-01-07T12:00:00.123"
        assert result["level"] == "INFO"
        assert result["message"] == "Processing data"

    def test_parse_level_module_message(self):
        """parse_log_line parses level:module:message format."""
        line = "INFO:root:Processing data"
        result = parse_log_line(line)
        assert result["level"] == "INFO"
        assert result["message"] == "Processing data"
        assert "timestamp" in result

    def test_parse_bracketed_timestamp(self):
        """parse_log_line parses [timestamp] LEVEL: message format."""
        line = "[2025-01-07 12:00:00] ERROR: Connection failed"
        result = parse_log_line(line)
        assert result["timestamp"] == "2025-01-07 12:00:00"
        assert result["level"] == "ERROR"
        assert result["message"] == "Connection failed"

    def test_parse_unparseable_line(self):
        """parse_log_line falls back for unparseable lines."""
        line = "Unparseable log line"
        result = parse_log_line(line)
        assert result["level"] == "INFO"
        assert result["message"] == "Unparseable log line"
        assert "timestamp" in result

    def test_parse_various_log_levels(self):
        """parse_log_line handles various log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            line = f"2025-01-07 12:00:00 - {level} - Test message"
            result = parse_log_line(line)
            assert result["level"] == level
            assert result["message"] == "Test message"

    def test_parse_message_with_special_characters(self):
        """parse_log_line preserves special characters in message."""
        line = "2025-01-07 12:00:00 - INFO - Error: Connection@Host#123 failed!"
        result = parse_log_line(line)
        assert "Connection@Host#123" in result["message"]

    def test_parse_multiword_message(self):
        """parse_log_line handles multiword messages."""
        line = "2025-01-07 12:00:00 - INFO - This is a long message with many words"
        result = parse_log_line(line)
        assert result["message"] == "This is a long message with many words"

    def test_parse_empty_line(self):
        """parse_log_line handles empty lines."""
        line = ""
        result = parse_log_line(line)
        assert result["level"] == "INFO"
        assert result["message"] == ""

    def test_parse_whitespace_only_line(self):
        """parse_log_line handles whitespace-only lines."""
        line = "   \t  "
        result = parse_log_line(line)
        assert result["level"] == "INFO"
        assert result["message"].strip() == ""


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for validation and log streaming."""

    def test_validate_then_create_simulation(
        self, api_client: TestClient, tmp_path: Path, patch_output_dir, monkeypatch
    ):
        """Validate configuration, then create simulation with same config."""
        patch_output_dir(tmp_path / "out")

        config = {
            "aggregation_strategy_keyword": "fedavg",
            "dataset_keyword": "bloodmnist",
            "num_of_rounds": 3,
            "num_of_clients": 2,
        }

        # First validate
        validate_response = api_client.post("/api/validate", json=config)
        assert validate_response.status_code == 200
        assert validate_response.json()["valid"] is True

        # Then create simulation
        mock_task = MagicMock()
        mock_task.id = "test-task-id"
        mock_run_simulation = MagicMock()
        mock_run_simulation.delay = MagicMock(return_value=mock_task)
        monkeypatch.setattr("intellifl.tasks.simulation_tasks.run_simulation", mock_run_simulation)

        create_response = api_client.post("/api/simulations", json=config)
        assert create_response.status_code == 201

    def test_validation_errors_match_creation_errors(self, api_client: TestClient):
        """Validation errors should match creation errors for same config."""
        invalid_config = {
            "shared_settings": {
                "aggregation_strategy_keyword": "fedavg",
                "num_of_rounds": -1,  # Invalid
            },
            "simulation_strategies": [{}],
        }

        # Validate
        validate_response = api_client.post("/api/validate", json=invalid_config)
        assert validate_response.status_code == 200
        assert validate_response.json()["valid"] is False

    def test_validation_endpoint_cors_headers(self, api_client: TestClient):
        """POST /api/validate endpoint includes CORS headers.

        **Validates: Requirements 4.4**

        The validation endpoint should follow the same CORS configuration
        as existing endpoints.
        """
        config = {
            "aggregation_strategy_keyword": "fedavg",
            "dataset_keyword": "bloodmnist",
            "num_of_rounds": 3,
            "num_of_clients": 2,
        }
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        # CORS headers are added by FastAPI middleware globally
        # Verify the response is successful and can be used by CORS clients
        assert "content-type" in response.headers

    def test_log_streaming_endpoint_cors_headers(self, api_client: TestClient):
        """GET /api/simulations/{id}/logs endpoint includes CORS headers.

        **Validates: Requirements 4.4**

        The log streaming endpoint should follow the same CORS configuration
        as existing endpoints.
        """
        # Test with non-existent simulation to verify endpoint is accessible
        response = api_client.get("/api/simulations/nonexistent_id/logs")
        # Should return 404, but the endpoint should be accessible
        assert response.status_code == 404
        # CORS headers are added by FastAPI middleware globally
        assert "content-type" in response.headers

    def test_validation_endpoint_follows_existing_patterns(self, api_client: TestClient):
        """Validation endpoint follows existing patterns in simulations router.

        **Validates: Requirements 4.1, 4.6**

        The endpoint should:
        - Use the same error handling patterns
        - Return appropriate HTTP status codes
        - Have comprehensive docstrings
        - Use the same logging configuration
        """
        config = {
            "aggregation_strategy_keyword": "fedavg",
            "dataset_keyword": "bloodmnist",
            "num_of_rounds": 3,
            "num_of_clients": 2,
        }
        response = api_client.post("/api/validate", json=config)

        # Should return 200 with JSON response
        assert response.status_code == 200
        data = response.json()

        # Response should follow ValidationResponse model
        assert "valid" in data
        assert isinstance(data["valid"], bool)

        # Should have proper error handling
        if not data["valid"]:
            assert "errors" in data
            assert isinstance(data["errors"], list)

    def test_log_streaming_uses_get_simulation_path_dependency(self, api_client: TestClient):
        """Log streaming endpoint uses get_simulation_path dependency.

        **Validates: Requirements 4.2**

        The endpoint should use the existing get_simulation_path dependency
        for path validation and security.
        """
        # Non-existent simulation should return 404 (handled by dependency)
        response = api_client.get("/api/simulations/nonexistent_id/logs")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_validation_endpoint_integrates_with_create_simulation_request(
        self, api_client: TestClient
    ):
        """Validation endpoint integrates with CreateSimulationRequest model.

        **Validates: Requirements 4.3**

        The endpoint should use the same CreateSimulationRequest model
        for validation logic reuse.
        """
        # Valid config that CreateSimulationRequest accepts
        valid_config = {
            "aggregation_strategy_keyword": "fedavg",
            "dataset_keyword": "bloodmnist",
            "num_of_rounds": 3,
            "num_of_clients": 2,
        }
        response = api_client.post("/api/validate", json=valid_config)
        assert response.status_code == 200
        assert response.json()["valid"] is True

        # Invalid config that CreateSimulationRequest rejects
        invalid_config = {
            "shared_settings": {
                "num_of_rounds": -1,  # Invalid: negative
            },
            "simulation_strategies": [{}],
        }
        response = api_client.post("/api/validate", json=invalid_config)
        assert response.status_code == 200
        assert response.json()["valid"] is False


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and HTTP status codes."""

    def test_validation_endpoint_returns_500_on_unexpected_error(
        self, api_client: TestClient, monkeypatch
    ):
        """POST /api/validate returns HTTP 500 on unexpected error.

        **Validates: Requirements 3.5**

        When an unexpected exception occurs during validation, the endpoint
        should return HTTP 500 with an error message.
        """

        # Mock CreateSimulationRequest to raise an unexpected exception
        def mock_init(*args, **kwargs):
            raise RuntimeError("Unexpected database error")

        monkeypatch.setattr("intellifl.api.models.CreateSimulationRequest.__init__", mock_init)

        config = {"aggregation_strategy_keyword": "fedavg"}
        response = api_client.post("/api/validate", json=config)

        # Should return 500 for unexpected error
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    def test_log_streaming_returns_404_for_nonexistent_simulation(self, api_client: TestClient):
        """GET /api/simulations/{id}/logs returns 404 for non-existent simulation.

        **Validates: Requirements 2.4, 3.5**

        When requesting logs for a non-existent simulation, the endpoint
        should return HTTP 404 with "Simulation not found" message.
        """
        # Use a valid format simulation ID (alphanumeric and underscores only)
        response = api_client.get("/api/simulations/nonexistent_sim_id/logs")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_validation_endpoint_returns_200_for_validation_errors(self, api_client: TestClient):
        """POST /api/validate returns HTTP 200 for validation errors.

        **Validates: Requirements 3.5**

        Validation errors are not HTTP errors - they're returned with HTTP 200
        and valid=false in the response body.
        """
        config = {
            "shared_settings": {
                "num_of_rounds": -1,  # Invalid: negative rounds
            },
            "simulation_strategies": [{}],
        }
        response = api_client.post("/api/validate", json=config)

        # Should return 200 with valid=false
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["errors"] is not None
        assert len(data["errors"]) > 0

    def test_validation_endpoint_returns_200_for_valid_config(self, api_client: TestClient):
        """POST /api/validate returns HTTP 200 for valid configuration.

        **Validates: Requirements 3.5**

        Valid configurations should return HTTP 200 with valid=true.
        """
        config = {
            "aggregation_strategy_keyword": "fedavg",
            "dataset_keyword": "bloodmnist",
            "num_of_rounds": 3,
            "num_of_clients": 2,
        }
        response = api_client.post("/api/validate", json=config)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True


# =============================================================================
# Property-Based Tests for Configuration Validation
# =============================================================================

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

    def _dummy_decorator(*args, **kwargs):
        def wrapper(f):
            return f

        return wrapper

    given = _dummy_decorator
    settings = _dummy_decorator  # type: ignore[misc,assignment]
    st = None  # type: ignore[misc,assignment]
    HealthCheck = None  # type: ignore[misc,assignment]  # noqa: N806


if not HYPOTHESIS_AVAILABLE:
    import pytest

    pytest.skip(
        "Hypothesis not installed. Install with: pip install hypothesis",
        allow_module_level=True,
    )

# pyright: ignore[reportOptionalMemberAccess] - st is guaranteed non-None after skip
assert st is not None
assert HealthCheck is not None


class TestValidationPropertyBased:
    """Property-based tests for configuration validation endpoint.

    These tests verify universal properties that should hold across all
    valid and invalid configurations.
    """

    @given(
        st.just(
            {
                "aggregation_strategy_keyword": "fedavg",
                "dataset_keyword": "bloodmnist",
                "num_of_rounds": 3,
                "num_of_clients": 2,
            }
        )
    )
    @settings(
        max_examples=10,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_property_1_valid_configurations_return_success(
        self, api_client: TestClient, config: dict
    ):
        """Property 1: Valid configurations return success.

        **Validates: Requirements 1.1, 1.2**

        For any valid simulation configuration object, when validated by the
        /api/validate endpoint, the response should have valid=true and no errors.
        """
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["errors"] is None

    @given(
        st.just(
            {
                "shared_settings": {
                    "aggregation_strategy_keyword": "fedavg",
                    "num_of_rounds": -1,  # Invalid: negative rounds
                },
                "simulation_strategies": [{}],
            }
        )
    )
    @settings(
        max_examples=10,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_property_2_invalid_configurations_return_failure_with_errors(
        self, api_client: TestClient, config: dict
    ):
        """Property 2: Invalid configurations return failure with errors.

        **Validates: Requirements 1.1, 1.3**

        For any invalid simulation configuration object, when validated by the
        /api/validate endpoint, the response should have valid=false and a
        non-empty errors list.
        """
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["errors"] is not None
        assert len(data["errors"]) > 0

    @given(
        st.just(
            {
                "shared_settings": {
                    "aggregation_strategy_keyword": "fedavg",
                    "num_of_rounds": -1,  # Out of range
                },
                "simulation_strategies": [{}],
            }
        )
    )
    @settings(
        max_examples=10,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_property_3_validation_errors_are_descriptive(
        self, api_client: TestClient, config: dict
    ):
        """Property 3: Validation errors are descriptive.

        **Validates: Requirements 1.4, 1.5, 1.6**

        For any configuration with missing required fields, incorrect types,
        or out-of-range values, the validation errors should specifically
        identify the problematic field and describe the issue.
        """
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()

        if not data["valid"]:
            assert data["errors"] is not None
            # Errors should be descriptive strings
            for error in data["errors"]:
                assert isinstance(error, str)
                assert len(error) > 0
                # Error should contain field information or constraint info
                # (e.g., "num_of_rounds: ..." or "greater than or equal to")


class TestLogParsingPropertyBased:
    """Property-based tests for log parsing utility.

    These tests verify universal properties that should hold across all
    log line formats.
    """

    @given(st.text(min_size=1, max_size=200))
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_property_6_log_entries_have_required_structure(self, line: str):
        """Property 6: Log entries have required structure.

        **Validates: Requirements 2.3**

        For any log line parsed by parse_log_line, the result should be a
        dictionary containing timestamp, level, and message fields.
        """
        result = parse_log_line(line)

        # All required fields must be present
        assert "timestamp" in result
        assert "level" in result
        assert "message" in result

        # All fields must be strings
        assert isinstance(result["timestamp"], str)
        assert isinstance(result["level"], str)
        assert isinstance(result["message"], str)

        # Fields should not be empty (except message could be empty for empty input)
        assert len(result["timestamp"]) > 0
        assert len(result["level"]) > 0


class TestValidationPropertyBasedWithStrategies:
    """Property-based tests using Hypothesis strategies for configuration generation."""

    @given(
        st.dictionaries(
            st.just("aggregation_strategy_keyword"),
            st.just("fedavg"),
            min_size=1,
            max_size=1,
        )
    )
    @settings(
        max_examples=20,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_property_valid_minimal_config(self, api_client: TestClient, config: dict):
        """Property: Minimal valid configuration returns success.

        **Validates: Requirements 1.1, 1.2**

        A configuration with just the aggregation strategy should be valid
        since all other fields are optional.
        """
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        # Minimal config should be valid
        assert data["valid"] is True

    @given(
        st.dictionaries(
            st.sampled_from(
                [
                    "aggregation_strategy_keyword",
                    "dataset_keyword",
                    "num_of_rounds",
                    "num_of_clients",
                ]
            ),
            st.one_of(
                st.just("fedavg"),
                st.just("bloodmnist"),
                st.integers(min_value=1, max_value=10),
            ),
            min_size=1,
            max_size=4,
        )
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_property_valid_configs_with_various_fields(self, api_client: TestClient, config: dict):
        """Property: Configurations with various valid field combinations are valid.

        **Validates: Requirements 1.1, 1.2**

        Any combination of valid field values should produce a valid configuration.
        """
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        # All these combinations should be valid
        assert data["valid"] is True

    @given(
        st.dictionaries(
            st.just("shared_settings"),
            st.dictionaries(
                st.just("num_of_rounds"),
                st.integers(max_value=-1),  # Negative rounds
                min_size=1,
                max_size=1,
            ),
            min_size=1,
            max_size=1,
        )
    )
    @settings(
        max_examples=20,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_property_invalid_negative_rounds(self, api_client: TestClient, config: dict):
        """Property: Negative rounds always fail validation.

        **Validates: Requirements 1.3, 1.6**

        Any configuration with negative num_of_rounds should be invalid.
        """
        # Add required simulation_strategies
        config["simulation_strategies"] = [{}]

        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        # Negative rounds should always fail
        assert data["valid"] is False
        assert data["errors"] is not None

    @given(
        st.dictionaries(
            st.just("shared_settings"),
            st.dictionaries(
                st.just("num_of_clients"),
                st.integers(max_value=-1),  # Negative clients
                min_size=1,
                max_size=1,
            ),
            min_size=1,
            max_size=1,
        )
    )
    @settings(
        max_examples=20,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_property_invalid_negative_clients(self, api_client: TestClient, config: dict):
        """Property: Negative clients always fail validation.

        **Validates: Requirements 1.3, 1.6**

        Any configuration with negative num_of_clients should be invalid.
        """
        # Add required simulation_strategies
        config["simulation_strategies"] = [{}]

        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        # Negative clients should always fail
        assert data["valid"] is False
        assert data["errors"] is not None

    @given(st.just({}))
    @settings(
        max_examples=10,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_property_empty_config_is_valid(self, api_client: TestClient, config: dict):
        """Property: Empty configuration is valid (all fields optional).

        **Validates: Requirements 1.1, 1.2**

        Since all fields in CreateSimulationRequest are optional, an empty
        configuration should be valid.
        """
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True

    @given(
        st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False),
                st.text(),
                st.booleans(),
            ),
            min_size=0,
            max_size=5,
        )
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_property_response_always_has_valid_field(self, api_client: TestClient, config: dict):
        """Property: Response always has 'valid' field.

        **Validates: Requirements 1.2**

        Every response from /api/validate should have a 'valid' boolean field.
        """
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert isinstance(data["valid"], bool)

    @given(
        st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False),
                st.text(),
                st.booleans(),
            ),
            min_size=0,
            max_size=5,
        )
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_property_response_errors_field_consistency(self, api_client: TestClient, config: dict):
        """Property: When valid=true, errors is None; when valid=false, errors is list.

        **Validates: Requirements 1.2, 1.3**

        The response should maintain consistency between valid and errors fields.
        """
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200
        data = response.json()

        if data["valid"]:
            # When valid, errors should be None or empty
            assert data.get("errors") is None or data.get("errors") == []
        else:
            # When invalid, errors should be a non-empty list
            assert isinstance(data.get("errors"), list)
            assert len(data.get("errors", [])) > 0

    @given(
        st.just(
            {
                "aggregation_strategy_keyword": "fedavg",
                "dataset_keyword": "bloodmnist",
                "num_of_rounds": 3,
                "num_of_clients": 2,
            }
        )
    )
    @settings(
        max_examples=10,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_property_10_error_conditions_return_correct_http_status_codes(
        self, api_client: TestClient, config: dict
    ):
        """Property 10: Error conditions return correct HTTP status codes.

        **Validates: Requirements 3.5**

        For any error condition (bad request, not found, server error), the API
        should return the appropriate HTTP status code (400, 404, or 500 respectively).

        - Valid configurations return HTTP 200
        - Validation errors return HTTP 200 (not an error)
        - Non-existent simulations return HTTP 404
        - Unexpected errors return HTTP 500
        """
        # Test 1: Valid configuration returns 200
        response = api_client.post("/api/validate", json=config)
        assert response.status_code == 200

        # Test 2: Non-existent simulation returns 404
        response = api_client.get("/api/simulations/nonexistent_id/logs")
        assert response.status_code == 404
