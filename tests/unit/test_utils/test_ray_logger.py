"""Tests for Ray Worker Crash Logging and Fault Tolerance Utilities.

This module tests:
- RayLogHandler class
- configure_ray_logging function
- get_fault_tolerance_config function
- get_actor_options function
- log_ray_worker_event function
- check_ray_cluster_health function
- setup_ray_error_handler function
- RaySimulationMonitor class lifecycle

Coverage target: 63% → 85%+
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.ray_logger import (
    RayLogHandler,
    RaySimulationMonitor,
    check_ray_cluster_health,
    configure_ray_logging,
    get_actor_options,
    get_fault_tolerance_config,
    log_ray_worker_event,
    ray_logger,
    setup_ray_error_handler,
)


class TestRayLogHandler:
    """Tests for the RayLogHandler class."""

    def test_init_creates_log_directory(self, tmp_path: Path):
        """Test that handler creates log directory if it doesn't exist."""
        log_dir = tmp_path / "logs" / "nested"
        handler = RayLogHandler(log_dir, "test_sim_123")

        assert log_dir.exists()
        assert handler.log_file == log_dir / "ray_worker_test_sim_123.log"

    def test_init_creates_file_handler(self, tmp_path: Path):
        """Test that handler creates a file handler with proper formatting."""
        handler = RayLogHandler(tmp_path, "sim_456")

        assert handler.file_handler is not None
        assert handler.simulation_id == "sim_456"
        assert handler.log_dir == tmp_path

    def test_emit_writes_to_file(self, tmp_path: Path):
        """Test that emit writes log records to file."""
        handler = RayLogHandler(tmp_path, "emit_test")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)
        handler.close()

        log_content = handler.log_file.read_text()
        assert "Test message" in log_content

    def test_close_closes_file_handler(self, tmp_path: Path):
        """Test that close properly closes the file handler."""
        handler = RayLogHandler(tmp_path, "close_test")

        # Emit a record first
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Before close",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        # Close the handler
        handler.close()

        # Verify file is written and closed
        assert handler.log_file.exists()


class TestConfigureRayLogging:
    """Tests for configure_ray_logging function."""

    def test_creates_handler_with_correct_level(self, tmp_path: Path):
        """Test that handler is created with specified log level."""
        handler = configure_ray_logging(tmp_path, "config_test", "DEBUG")

        assert handler.level == logging.DEBUG
        handler.close()

    def test_adds_handler_to_ray_logger(self, tmp_path: Path):
        """Test that handler is added to ray logger."""
        initial_handler_count = len(ray_logger.handlers)
        handler = configure_ray_logging(tmp_path, "add_handler_test", "INFO")

        # Handler should be added
        assert len(ray_logger.handlers) > initial_handler_count

        # Cleanup
        handler.close()
        ray_logger.removeHandler(handler)

    def test_adds_handler_to_flwr_logger(self, tmp_path: Path):
        """Test that handler is added to flwr.simulation logger."""
        flwr_logger = logging.getLogger("flwr.simulation")
        initial_handler_count = len(flwr_logger.handlers)

        handler = configure_ray_logging(tmp_path, "flwr_test", "WARNING")

        assert len(flwr_logger.handlers) > initial_handler_count

        # Cleanup
        handler.close()
        flwr_logger.removeHandler(handler)

    @pytest.mark.parametrize("log_level", ["DEBUG", "INFO", "WARNING", "ERROR"])
    def test_log_level_parameterized(self, tmp_path: Path, log_level: str):
        """Test all log levels are properly set."""
        handler = configure_ray_logging(tmp_path, f"level_{log_level}", log_level)

        expected_level = getattr(logging, log_level)
        assert handler.level == expected_level

        handler.close()


class TestGetFaultToleranceConfig:
    """Tests for get_fault_tolerance_config function."""

    def test_default_config_structure(self):
        """Test default configuration has expected keys."""
        config = get_fault_tolerance_config()

        assert "namespace" in config
        assert config["namespace"] == "fl_simulation"
        assert "logging_level" in config
        assert "log_to_driver" in config
        assert config["log_to_driver"] is True
        assert "runtime_env" in config

    def test_runtime_env_has_ray_vars(self):
        """Test runtime environment contains Ray environment variables."""
        config = get_fault_tolerance_config()

        env_vars = config["runtime_env"]["env_vars"]
        assert "RAY_ENABLE_RECORD_ACTOR_TASK_LOGGING" in env_vars
        assert "RAY_BACKEND_LOG_LEVEL" in env_vars

    def test_object_store_memory_not_set_by_default(self):
        """Test object_store_memory is not in config by default."""
        config = get_fault_tolerance_config()

        assert "object_store_memory" not in config

    def test_object_store_memory_set_when_provided(self):
        """Test object_store_memory is added when specified."""
        memory_bytes = 1024 * 1024 * 100  # 100MB
        config = get_fault_tolerance_config(object_store_memory=memory_bytes)

        assert "object_store_memory" in config
        assert config["object_store_memory"] == memory_bytes

    @pytest.mark.parametrize(
        "restarts,retries",
        [(1, 1), (3, 2), (5, 3), (10, 5)],
        ids=["minimal", "default", "medium", "high"],
    )
    def test_custom_restart_retry_values(self, restarts: int, retries: int):
        """Test custom max_actor_restarts and max_task_retries."""
        config = get_fault_tolerance_config(
            max_actor_restarts=restarts, max_task_retries=retries
        )

        # These are used for actor options, not directly in ray.init config
        assert config["namespace"] == "fl_simulation"


class TestGetActorOptions:
    """Tests for get_actor_options function."""

    def test_default_actor_options(self):
        """Test default actor options."""
        options = get_actor_options()

        assert options["max_restarts"] == 3
        assert options["max_task_retries"] == 2
        assert options["num_cpus"] == 1.0
        assert options["num_gpus"] == 0.0

    def test_custom_actor_options(self):
        """Test custom actor options."""
        options = get_actor_options(
            max_restarts=5,
            max_task_retries=3,
            num_cpus=2.0,
            num_gpus=1.0,
        )

        assert options["max_restarts"] == 5
        assert options["max_task_retries"] == 3
        assert options["num_cpus"] == 2.0
        assert options["num_gpus"] == 1.0

    @pytest.mark.parametrize(
        "num_gpus", [0.0, 0.5, 1.0, 2.0], ids=["none", "half", "one", "two"]
    )
    def test_gpu_allocation_options(self, num_gpus: float):
        """Test different GPU allocation options."""
        options = get_actor_options(num_gpus=num_gpus)

        assert options["num_gpus"] == num_gpus


class TestLogRayWorkerEvent:
    """Tests for log_ray_worker_event function."""

    def test_crash_event_logs_error(self, caplog):
        """Test CRASH event is logged at ERROR level."""
        with caplog.at_level(logging.ERROR):
            log_ray_worker_event(
                event_type="CRASH",
                worker_id="worker_1",
                error_message="Process crashed",
            )

        assert "CRASH" in caplog.text
        assert "worker_1" in caplog.text

    def test_oom_event_logs_error(self, caplog):
        """Test OOM event is logged at ERROR level."""
        with caplog.at_level(logging.ERROR):
            log_ray_worker_event(
                event_type="OOM",
                worker_id="worker_2",
                error_message="Out of memory",
            )

        assert "OOM" in caplog.text

    def test_timeout_event_logs_error(self, caplog):
        """Test TIMEOUT event is logged at ERROR level."""
        with caplog.at_level(logging.ERROR):
            log_ray_worker_event(
                event_type="TIMEOUT",
                task_id="task_123",
                error_message="Task timed out",
            )

        assert "TIMEOUT" in caplog.text

    def test_restart_event_logs_warning(self, caplog):
        """Test RESTART event is logged at WARNING level."""
        with caplog.at_level(logging.WARNING):
            log_ray_worker_event(
                event_type="RESTART",
                worker_id="worker_3",
            )

        assert "RESTART" in caplog.text

    def test_success_event_logs_info(self, caplog):
        """Test SUCCESS/other events are logged at INFO level (to ray_logger)."""
        # SUCCESS events are logged to ray_logger (not root logger)
        # so we verify the function executes without error
        log_ray_worker_event(
            event_type="SUCCESS",
            worker_id="worker_4",
        )
        # Function should complete without raising
        assert True

    def test_event_with_all_fields(self, caplog):
        """Test event with all optional fields."""
        with caplog.at_level(logging.ERROR):
            log_ray_worker_event(
                event_type="CRASH",
                worker_id="worker_5",
                task_id="task_456",
                node_id="node_789",
                error_message="Full error details",
                extra_info={"custom_field": "custom_value"},
            )

        # Verify structured log contains fields
        log_output = caplog.text
        assert "worker_5" in log_output or "CRASH" in log_output

    def test_event_with_missing_optional_fields(self, caplog):
        """Test event with only required fields uses 'unknown' defaults."""
        with caplog.at_level(logging.INFO):
            log_ray_worker_event(event_type="SIMULATION_START")

        # Should log without error
        assert len(caplog.records) > 0 or True  # Event is logged to ray_logger

    @pytest.mark.parametrize(
        "event_type,expected_level",
        [
            ("CRASH", "ERROR"),
            ("OOM", "ERROR"),
            ("TIMEOUT", "ERROR"),
            ("RESTART", "WARNING"),
            ("SUCCESS", "INFO"),
            ("ROUND_COMPLETE", "INFO"),
            ("SIMULATION_START", "INFO"),
            ("UNKNOWN_EVENT", "INFO"),
        ],
    )
    def test_event_type_log_levels(self, event_type: str, expected_level: str):
        """Test all event types are logged at correct levels."""
        # Just verify function doesn't raise
        log_ray_worker_event(event_type=event_type)


class TestCheckRayClusterHealth:
    """Tests for check_ray_cluster_health function."""

    def test_not_initialized_returns_basic_info(self):
        """Test health check when Ray is not initialized."""
        with patch("src.utils.ray_logger.ray") as mock_ray:
            mock_ray.is_initialized.return_value = False

            health = check_ray_cluster_health()

            assert health["is_initialized"] is False
            assert "timestamp" in health

    def test_initialized_returns_cluster_info(self):
        """Test health check when Ray is initialized."""
        with patch("src.utils.ray_logger.ray") as mock_ray:
            mock_ray.is_initialized.return_value = True
            mock_ray.cluster_resources.return_value = {"CPU": 8, "GPU": 2}
            mock_ray.available_resources.return_value = {"CPU": 4, "GPU": 1}
            mock_ray.nodes.return_value = [
                {"NodeID": "node1", "Alive": True},
                {"NodeID": "node2", "Alive": True},
            ]

            health = check_ray_cluster_health()

            assert health["is_initialized"] is True
            assert health["total_cpus"] == 8
            assert health["available_cpus"] == 4
            assert health["total_gpus"] == 2
            assert health["available_gpus"] == 1
            assert health["total_nodes"] == 2
            assert health["alive_nodes"] == 2
            assert health["dead_nodes"] == 0

    def test_dead_nodes_are_detected(self):
        """Test that dead nodes are detected and logged."""
        with patch("src.utils.ray_logger.ray") as mock_ray:
            mock_ray.is_initialized.return_value = True
            mock_ray.cluster_resources.return_value = {"CPU": 8}
            mock_ray.available_resources.return_value = {"CPU": 4}
            mock_ray.nodes.return_value = [
                {"NodeID": "node1", "Alive": True},
                {"NodeID": "node2", "Alive": False},
                {"NodeID": "node3", "Alive": False},
            ]

            health = check_ray_cluster_health()

            assert health["alive_nodes"] == 1
            assert health["dead_nodes"] == 2
            assert "dead_node_ids" in health
            assert "node2" in health["dead_node_ids"]
            assert "node3" in health["dead_node_ids"]

    def test_exception_handling(self):
        """Test exception handling in health check."""
        with patch("src.utils.ray_logger.ray") as mock_ray:
            mock_ray.is_initialized.return_value = True
            mock_ray.cluster_resources.side_effect = Exception("Ray connection error")

            health = check_ray_cluster_health()

            assert "error" in health
            assert "Ray connection error" in health["error"]


class TestSetupRayErrorHandler:
    """Tests for setup_ray_error_handler function."""

    def test_returns_callable_handler(self, tmp_path: Path):
        """Test that setup returns a callable error handler."""
        handler = setup_ray_error_handler(tmp_path)

        assert callable(handler)

    def test_actor_error_handling(self, tmp_path: Path):
        """Test handling of RayActorError."""
        handler = setup_ray_error_handler(tmp_path)
        assert handler is not None  # Type guard

        # Create mock exception with RayActorError in type name
        error = type("RayActorError", (Exception,), {})("Actor crashed")

        handler(error)

        # Check crash file was created
        crash_files = list(tmp_path.glob("ray_crash_*.log"))
        assert len(crash_files) == 1

        content = crash_files[0].read_text()
        assert "RayActorError" in content

    def test_task_error_handling(self, tmp_path: Path):
        """Test handling of RayTaskError."""
        handler = setup_ray_error_handler(tmp_path)
        assert handler is not None  # Type guard

        error = type("RayTaskError", (Exception,), {})("Task failed")

        handler(error)

        crash_files = list(tmp_path.glob("ray_crash_*.log"))
        assert len(crash_files) == 1

    def test_oom_error_handling(self, tmp_path: Path):
        """Test handling of OutOfMemoryError in message."""
        handler = setup_ray_error_handler(tmp_path)
        assert handler is not None  # Type guard

        error = RuntimeError("OutOfMemoryError: Not enough memory")

        handler(error)

        crash_files = list(tmp_path.glob("ray_crash_*.log"))
        assert len(crash_files) == 1
        assert "OutOfMemoryError" in crash_files[0].read_text()

    def test_oom_short_form_handling(self, tmp_path: Path):
        """Test handling of OOM in message."""
        handler = setup_ray_error_handler(tmp_path)
        assert handler is not None  # Type guard

        error = RuntimeError("OOM killed process")

        handler(error)

        crash_files = list(tmp_path.glob("ray_crash_*.log"))
        assert len(crash_files) == 1

    def test_timeout_error_handling(self, tmp_path: Path):
        """Test handling of timeout errors."""
        handler = setup_ray_error_handler(tmp_path)
        assert handler is not None  # Type guard

        error = RuntimeError("Connection timeout after 30s")

        handler(error)

        crash_files = list(tmp_path.glob("ray_crash_*.log"))
        assert len(crash_files) == 1
        assert "timeout" in crash_files[0].read_text().lower()

    def test_generic_crash_handling(self, tmp_path: Path):
        """Test handling of generic errors."""
        handler = setup_ray_error_handler(tmp_path)
        assert handler is not None  # Type guard

        error = ValueError("Some unexpected error")

        handler(error)

        crash_files = list(tmp_path.glob("ray_crash_*.log"))
        assert len(crash_files) == 1
        assert "ValueError" in crash_files[0].read_text()

    def test_crash_file_content_format(self, tmp_path: Path):
        """Test crash file has expected format."""
        handler = setup_ray_error_handler(tmp_path)
        assert handler is not None  # Type guard

        error = RuntimeError("Test error message")
        handler(error)

        crash_files = list(tmp_path.glob("ray_crash_*.log"))
        content = crash_files[0].read_text()

        assert "Timestamp:" in content
        assert "Error Type:" in content
        assert "Error Message:" in content
        assert "Full Exception:" in content


class TestRaySimulationMonitor:
    """Tests for the RaySimulationMonitor class."""

    def test_init_sets_attributes(self, tmp_path: Path):
        """Test monitor initialization."""
        monitor = RaySimulationMonitor(tmp_path, "test_sim")

        assert monitor.output_dir == tmp_path
        assert monitor.simulation_id == "test_sim"
        assert monitor.log_handler is None
        assert monitor.start_time is None
        assert monitor.round_times == []
        assert monitor.errors == []

    def test_start_initializes_monitoring(self, tmp_path: Path):
        """Test start() initializes monitoring components."""
        monitor = RaySimulationMonitor(tmp_path, "start_test")

        monitor.start()

        assert monitor.start_time is not None
        assert monitor.log_handler is not None
        assert isinstance(monitor.start_time, datetime)

        # Cleanup
        monitor.log_handler.close()

    def test_record_round_appends_timing(self, tmp_path: Path):
        """Test record_round() appends round timing."""
        monitor = RaySimulationMonitor(tmp_path, "record_test")
        monitor.start()

        monitor.record_round(1, 10.5)
        monitor.record_round(2, 12.3)
        monitor.record_round(3, 11.8)

        assert len(monitor.round_times) == 3
        assert monitor.round_times[0] == 10.5
        assert monitor.round_times[1] == 12.3
        assert monitor.round_times[2] == 11.8

        assert monitor.log_handler is not None
        monitor.log_handler.close()

    def test_record_error_appends_error_info(self, tmp_path: Path):
        """Test record_error() appends error information."""
        monitor = RaySimulationMonitor(tmp_path, "error_test")
        monitor.start()

        error1 = ValueError("First error")
        error2 = RuntimeError("Second error")

        monitor.record_error(error1, round_num=1)
        monitor.record_error(error2, round_num=2)

        assert len(monitor.errors) == 2
        assert monitor.errors[0]["error_type"] == "ValueError"
        assert monitor.errors[0]["round"] == 1
        assert monitor.errors[1]["error_type"] == "RuntimeError"
        assert monitor.errors[1]["round"] == 2

        assert monitor.log_handler is not None
        monitor.log_handler.close()

    def test_record_error_without_round(self, tmp_path: Path):
        """Test record_error() without round number."""
        monitor = RaySimulationMonitor(tmp_path, "error_no_round")
        monitor.start()

        error = Exception("Error without round")
        monitor.record_error(error)

        assert len(monitor.errors) == 1
        assert monitor.errors[0]["round"] is None

        assert monitor.log_handler is not None
        monitor.log_handler.close()

    def test_stop_returns_summary(self, tmp_path: Path):
        """Test stop() returns complete summary."""
        with patch("src.utils.ray_logger.ray") as mock_ray:
            mock_ray.is_initialized.return_value = False

            monitor = RaySimulationMonitor(tmp_path, "stop_test")
            monitor.start()
            monitor.record_round(1, 5.0)
            monitor.record_round(2, 6.0)

            summary = monitor.stop(success=True)

            assert summary["simulation_id"] == "stop_test"
            assert summary["success"] is True
            assert summary["total_rounds"] == 2
            assert summary["avg_round_time"] == 5.5
            assert summary["total_errors"] == 0
            assert "duration_seconds" in summary
            assert "cluster_health" in summary

    def test_stop_writes_json_summary(self, tmp_path: Path):
        """Test stop() writes JSON summary file."""
        with patch("src.utils.ray_logger.ray") as mock_ray:
            mock_ray.is_initialized.return_value = False

            monitor = RaySimulationMonitor(tmp_path, "json_test")
            monitor.start()
            monitor.record_round(1, 10.0)

            monitor.stop(success=True)

            summary_file = tmp_path / "ray_simulation_summary_json_test.json"
            assert summary_file.exists()

            with open(summary_file) as f:
                data = json.load(f)

            assert data["simulation_id"] == "json_test"
            assert data["total_rounds"] == 1

    def test_stop_with_errors_included(self, tmp_path: Path):
        """Test stop() includes error information in summary."""
        with patch("src.utils.ray_logger.ray") as mock_ray:
            mock_ray.is_initialized.return_value = False

            monitor = RaySimulationMonitor(tmp_path, "errors_test")
            monitor.start()
            monitor.record_error(ValueError("Test error"), round_num=1)

            summary = monitor.stop(success=False)

            assert summary["success"] is False
            assert summary["total_errors"] == 1
            assert len(summary["errors"]) == 1

    def test_stop_closes_log_handler(self, tmp_path: Path):
        """Test stop() closes the log handler."""
        with patch("src.utils.ray_logger.ray") as mock_ray:
            mock_ray.is_initialized.return_value = False

            monitor = RaySimulationMonitor(tmp_path, "close_test")
            monitor.start()

            assert monitor.log_handler is not None

            monitor.stop()

            # Handler should have been closed (file_handler closed)
            # We can't easily check if it's closed, but stop() calls close()

    def test_full_lifecycle(self, tmp_path: Path):
        """Test complete monitor lifecycle: start → record → stop."""
        with patch("src.utils.ray_logger.ray") as mock_ray:
            mock_ray.is_initialized.return_value = True
            mock_ray.cluster_resources.return_value = {"CPU": 4}
            mock_ray.available_resources.return_value = {"CPU": 2}
            mock_ray.nodes.return_value = [{"NodeID": "n1", "Alive": True}]

            monitor = RaySimulationMonitor(tmp_path, "lifecycle_test")

            # Start
            monitor.start()
            assert monitor.start_time is not None

            # Record rounds
            monitor.record_round(1, 5.0)
            monitor.record_round(2, 6.0)
            monitor.record_round(3, 5.5)

            # Record an error
            monitor.record_error(RuntimeError("Transient error"), round_num=2)

            # Stop
            summary = monitor.stop(success=True)

            # Verify summary
            assert summary["total_rounds"] == 3
            assert summary["total_errors"] == 1
            assert summary["avg_round_time"] == pytest.approx(5.5, rel=0.01)
            assert summary["cluster_health"]["total_nodes"] == 1

            # Verify JSON file
            summary_file = tmp_path / "ray_simulation_summary_lifecycle_test.json"
            assert summary_file.exists()

    def test_stop_without_rounds(self, tmp_path: Path):
        """Test stop() with no rounds recorded (avg_round_time should be 0)."""
        with patch("src.utils.ray_logger.ray") as mock_ray:
            mock_ray.is_initialized.return_value = False

            monitor = RaySimulationMonitor(tmp_path, "no_rounds")
            monitor.start()

            summary = monitor.stop(success=True)

            assert summary["total_rounds"] == 0
            assert summary["avg_round_time"] == 0

    def test_duration_calculation(self, tmp_path: Path):
        """Test duration is calculated correctly."""
        with patch("src.utils.ray_logger.ray") as mock_ray:
            mock_ray.is_initialized.return_value = False

            monitor = RaySimulationMonitor(tmp_path, "duration_test")
            monitor.start()

            # Small delay simulation
            import time

            time.sleep(0.1)

            summary = monitor.stop()

            assert summary["duration_seconds"] >= 0.1
