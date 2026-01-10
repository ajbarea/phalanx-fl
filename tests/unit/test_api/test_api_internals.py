"""
Unit tests for internal functions and edge cases in src/api/main.py.

Tests cover:
- Helper functions (get_safe_env, secure_join, _get_status_data, _find_simulation_process)
- Dataset validation
- Attack snapshot processing
- Status marker detection edge cases
- Add to queue functionality
- System devices endpoint
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock

from fastapi.testclient import TestClient

from src.api import main

# =============================================================================
# get_safe_env() Tests
# =============================================================================


class TestGetSafeEnv:
    """Tests for the get_safe_env function."""

    def test_get_safe_env_filters_api_keys(self, monkeypatch):
        """get_safe_env filters out API_KEY environment variables."""
        monkeypatch.setenv("SAFE_VAR", "safe_value")
        monkeypatch.setenv("MY_API_KEY", "secret_key")
        monkeypatch.setenv("OTHER_VAR", "other_value")

        result = main.get_safe_env()

        assert "SAFE_VAR" in result
        assert result["SAFE_VAR"] == "safe_value"
        assert "MY_API_KEY" not in result
        assert "OTHER_VAR" in result

    def test_get_safe_env_filters_tokens(self, monkeypatch):
        """get_safe_env filters out TOKEN environment variables."""
        monkeypatch.setenv("NORMAL_VAR", "normal")
        monkeypatch.setenv("GITHUB_TOKEN", "gh_secret")
        monkeypatch.setenv("NPM_TOKEN", "npm_secret")

        result = main.get_safe_env()

        assert "NORMAL_VAR" in result
        assert "GITHUB_TOKEN" not in result
        assert "NPM_TOKEN" not in result

    def test_get_safe_env_filters_passwords(self, monkeypatch):
        """get_safe_env filters out PASSWORD environment variables."""
        monkeypatch.setenv("DB_PASSWORD", "secret_password")
        monkeypatch.setenv("USER_PASSWD", "user_secret")
        monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@localhost")

        result = main.get_safe_env()

        assert "DB_PASSWORD" not in result
        assert "USER_PASSWD" not in result
        assert "DATABASE_URL" not in result

    def test_get_safe_env_filters_cloud_credentials(self, monkeypatch):
        """get_safe_env filters out cloud provider credentials."""
        monkeypatch.setenv("AWS_ACCESS_KEY", "aws_key")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "azure_secret")
        monkeypatch.setenv("GCP_SERVICE_ACCOUNT", "gcp_account")
        monkeypatch.setenv("SAFE_CONFIG", "config_value")

        result = main.get_safe_env()

        assert "AWS_ACCESS_KEY" not in result
        assert "AZURE_CLIENT_SECRET" not in result
        assert "GCP_SERVICE_ACCOUNT" not in result
        assert "SAFE_CONFIG" in result

    def test_get_safe_env_case_insensitive(self, monkeypatch):
        """get_safe_env filters case-insensitively."""
        monkeypatch.setenv("my_api_key_test", "lowercase_key")
        monkeypatch.setenv("Test_Api_Secret", "mixed_case")
        monkeypatch.setenv("SAFE_NORMAL_VAR", "normal")

        result = main.get_safe_env()

        assert "my_api_key_test" not in result
        assert "Test_Api_Secret" not in result
        assert "SAFE_NORMAL_VAR" in result


# =============================================================================
# secure_join() Tests
# =============================================================================


class TestSecureJoin:
    """Tests for the secure_join function."""

    def test_secure_join_valid_path(self, tmp_path):
        """secure_join allows valid subdirectory paths."""
        base = tmp_path / "safe"
        base.mkdir()

        result = main.secure_join(base, "subdir", "file.txt")
        assert result.resolve().is_relative_to(base.resolve())

    def test_secure_join_prevents_traversal(self, tmp_path):
        """secure_join prevents path traversal attacks."""
        base = tmp_path / "safe"
        base.mkdir()

        try:
            main.secure_join(base, "..", "..", "etc", "passwd")
            raise AssertionError("Should have raised HTTPException")
        except main.HTTPException as e:
            assert e.status_code == 400
            assert "invalid path" in e.detail.lower()


# =============================================================================
# get_simulation_path() Tests
# =============================================================================


class TestGetSimulationPath:
    """Tests for the get_simulation_path function."""

    def test_get_simulation_path_invalid_id(self):
        """get_simulation_path rejects invalid simulation IDs."""
        try:
            main.get_simulation_path("../../malicious")
            raise AssertionError("Should have raised HTTPException")
        except main.HTTPException as e:
            assert e.status_code in [400, 404]


# =============================================================================
# _get_status_data() Tests
# =============================================================================


class TestGetStatusData:
    """Tests for the _get_status_data helper function."""

    def test_get_status_data_stopped(self, tmp_path: Path, monkeypatch):
        """_get_status_data returns 'stopped' when .stopped marker exists."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "stopped_test"
        sim_dir.mkdir(parents=True)

        (sim_dir / ".stopped").write_text("Stopped at 2025-01-01")

        result = main._get_status_data(sim_dir, "stopped_test")
        assert result["status"] == "stopped"
        assert result["progress"] == 0.0

    def test_get_status_data_with_status_json(self, tmp_path: Path, monkeypatch):
        """_get_status_data reads detailed progress from status.json."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "progress_test"
        sim_dir.mkdir(parents=True)

        status_data = {
            "status": "running",
            "progress": 0.75,
            "current_round": 8,
            "total_rounds": 10,
            "current_strategy": 1,
            "total_strategies": 2,
        }
        (sim_dir / "status.json").write_text(json.dumps(status_data))

        result = main._get_status_data(sim_dir, "progress_test")
        assert result["status"] == "running"
        assert result["progress"] == 0.75
        assert result["current_round"] == 8
        assert result["total_rounds"] == 10
        assert result["current_strategy"] == 1
        assert result["total_strategies"] == 2

    def test_get_status_data_running_marker(self, tmp_path: Path, monkeypatch):
        """_get_status_data returns 'running' when .running marker exists."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "running_marker_test"
        sim_dir.mkdir(parents=True)

        (sim_dir / ".running").write_text("Running")

        result = main._get_status_data(sim_dir, "running_marker_test")
        assert result["status"] == "running"
        assert result["progress"] == 0.0

    def test_get_status_data_completed_with_results(self, tmp_path: Path, monkeypatch):
        """_get_status_data returns 'completed' when result files exist."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "completed_test"
        sim_dir.mkdir(parents=True)

        (sim_dir / "results.pdf").write_bytes(b"%PDF-1.4")

        result = main._get_status_data(sim_dir, "completed_test")
        assert result["status"] == "completed"
        assert result["progress"] == 1.0

    def test_get_status_data_execution_log_error(self, tmp_path: Path, monkeypatch):
        """_get_status_data handles execution.log read errors."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        monkeypatch.setattr("src.api.main.running_processes", {})
        sim_dir = tmp_path / "out" / "execution_log_issue"
        sim_dir.mkdir(parents=True)

        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))
        (sim_dir / "execution.log").write_text("Some error")

        mock_process = MagicMock()
        mock_process.poll.return_value = 1

        main.running_processes["execution_log_issue"] = mock_process

        from pathlib import Path as PathLib

        original_open = PathLib.open

        def mock_open(self, *args, **kwargs):
            if "execution.log" in str(self):
                raise OSError("Cannot read execution log")
            return original_open(self, *args, **kwargs)

        monkeypatch.setattr("pathlib.Path.open", mock_open)

        result = main._get_status_data(sim_dir, "execution_log_issue")
        assert result["status"] == "failed"


# =============================================================================
# _find_simulation_process() Tests
# =============================================================================


class TestFindSimulationProcess:
    """Tests for _find_simulation_process helper function."""

    def test_find_process_by_cmdline(self, tmp_path: Path, monkeypatch):
        """_find_simulation_process finds process by command line pattern."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")

        mock_proc = MagicMock()
        mock_proc.info = {
            "pid": 12345,
            "name": "python",
            "cmdline": [
                "python",
                "-m",
                "src.simulation_runner",
                "out/test_sim/config.json",
            ],
        }

        def mock_process_iter(attrs):
            return [mock_proc]

        monkeypatch.setattr("src.api.main.psutil.process_iter", mock_process_iter)

        result = main._find_simulation_process("test_sim")
        assert result == mock_proc

    def test_find_process_by_status_json_pid(self, tmp_path: Path, monkeypatch):
        """_find_simulation_process finds process by PID from status.json."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")

        sim_dir = tmp_path / "out" / "test_sim_pid"
        sim_dir.mkdir(parents=True)
        (sim_dir / "status.json").write_text(json.dumps({"status": "running", "pid": 99999}))

        def mock_process_iter(attrs):
            return []

        monkeypatch.setattr("src.api.main.psutil.process_iter", mock_process_iter)

        mock_psutil_proc = MagicMock()
        mock_psutil_proc.is_running.return_value = True
        mock_psutil_proc.name.return_value = "python.exe"

        def mock_process(pid):
            if pid == 99999:
                return mock_psutil_proc
            raise main.psutil.NoSuchProcess(pid)

        monkeypatch.setattr("src.api.main.psutil.Process", mock_process)

        result = main._find_simulation_process("test_sim_pid")
        assert result == mock_psutil_proc

    def test_find_process_not_found(self, tmp_path: Path, monkeypatch):
        """_find_simulation_process returns None when process not found."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        (tmp_path / "out").mkdir(parents=True)

        def mock_process_iter(attrs):
            return []

        monkeypatch.setattr("src.api.main.psutil.process_iter", mock_process_iter)

        result = main._find_simulation_process("nonexistent_sim")
        assert result is None


# =============================================================================
# Status Marker Edge Cases
# =============================================================================


class TestStatusMarkers:
    """Tests for status detection with various marker files."""

    def test_status_with_running_marker(self, api_client: TestClient, tmp_path: Path, monkeypatch):
        """GET /api/simulations/{id}/status returns 'running' with .running marker."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "api_run_running_marker"
        sim_dir.mkdir(parents=True)

        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))
        (sim_dir / ".running").write_text("Running")

        response = api_client.get("/api/simulations/api_run_running_marker/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["progress"] == 0.0

    def test_status_stopped_takes_priority(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """GET /api/simulations/{id}/status returns 'stopped' even with .running."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "api_run_stopped_priority"
        sim_dir.mkdir(parents=True)

        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))
        (sim_dir / ".running").write_text("Running")
        (sim_dir / ".stopped").write_text("Stopped")

        response = api_client.get("/api/simulations/api_run_stopped_priority/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"

    def test_status_json_takes_priority_over_markers(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """status.json takes priority over marker files for running status."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "api_run_status_json_priority"
        sim_dir.mkdir(parents=True)

        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))

        status_data = {
            "status": "running",
            "progress": 0.75,
            "current_round": 8,
            "total_rounds": 10,
        }
        (sim_dir / "status.json").write_text(json.dumps(status_data))

        response = api_client.get("/api/simulations/api_run_status_json_priority/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["progress"] == 0.75
        assert data["current_round"] == 8

    def test_status_json_malformed(self, api_client: TestClient, tmp_path: Path, monkeypatch):
        """Malformed status.json falls back to other detection methods."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "api_run_malformed_status"
        sim_dir.mkdir(parents=True)

        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))
        (sim_dir / "status.json").write_text("{invalid json")
        (sim_dir / ".running").write_text("Running")

        response = api_client.get("/api/simulations/api_run_malformed_status/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"


# =============================================================================
# Add to Queue Tests
# =============================================================================


class TestAddToQueue:
    """Tests for adding strategies to running simulations."""

    def test_add_to_queue_with_running_simulation(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """POST /api/simulations with add_to_queue=true adds to running simulation."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        monkeypatch.setattr("src.api.main.BASE_DIR", tmp_path)
        monkeypatch.setattr("src.api.main.running_processes", {})

        existing_sim = tmp_path / "out" / "api_run_running"
        existing_sim.mkdir(parents=True)
        existing_config = {
            "shared_settings": {"dataset_keyword": "bloodmnist", "num_of_rounds": 5},
            "simulation_strategies": [{"aggregation_strategy_keyword": "fedavg"}],
        }
        (existing_sim / "config.json").write_text(json.dumps(existing_config))

        mock_process = MagicMock()
        mock_process.poll.return_value = None
        main.running_processes["api_run_running"] = mock_process

        new_config = {
            "aggregation_strategy_keyword": "krum",
            "num_of_malicious_clients": 2,
            "add_to_queue": True,
        }

        response = api_client.post("/api/simulations", json=new_config)
        assert response.status_code == 201
        data = response.json()

        assert data["simulation_id"] == "api_run_running"
        assert data.get("queued") is True

        with open(existing_sim / "config.json") as f:
            updated_config = json.load(f)

        assert len(updated_config["simulation_strategies"]) == 2
        assert updated_config["simulation_strategies"][1]["aggregation_strategy_keyword"] == "krum"


# =============================================================================
# Stop Endpoint Edge Cases
# =============================================================================


class TestStopEndpointEdgeCases:
    """Tests for stop endpoint edge cases."""

    def test_stop_orphaned_simulation(self, api_client: TestClient, tmp_path: Path, monkeypatch):
        """POST /api/simulations/{id}/stop handles orphaned status.json."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "orphaned_sim"
        sim_dir.mkdir(parents=True)

        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))
        (sim_dir / "status.json").write_text(json.dumps({"status": "running", "pid": 99999}))

        def mock_process_iter(attrs):
            return []

        monkeypatch.setattr("src.api.main.psutil.process_iter", mock_process_iter)

        def mock_process(pid):
            raise main.psutil.NoSuchProcess(pid)

        monkeypatch.setattr("src.api.main.psutil.Process", mock_process)

        response = api_client.post("/api/simulations/orphaned_sim/stop")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "stopped"

        with open(sim_dir / "status.json") as f:
            status = json.load(f)
        assert status["status"] == "stopped"

    def test_stop_already_completed(self, api_client: TestClient, tmp_path: Path, monkeypatch):
        """POST /api/simulations/{id}/stop returns 409 for already completed process."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        monkeypatch.setattr("src.api.main.running_processes", {})
        sim_dir = tmp_path / "out" / "completed_sim"
        sim_dir.mkdir(parents=True)

        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))

        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 12345
        main.running_processes["completed_sim"] = mock_process

        def mock_psutil_process(pid):
            raise main.psutil.NoSuchProcess(pid)

        monkeypatch.setattr("src.api.main.psutil.Process", mock_psutil_process)

        response = api_client.post("/api/simulations/completed_sim/stop")
        assert response.status_code == 409
        assert "already completed" in response.json()["detail"].lower()


# =============================================================================
# Attack Snapshot Tests
# =============================================================================


class TestAttackSnapshots:
    """Tests for attack snapshot processing."""

    def test_attack_snapshots_no_snapshots(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Attack snapshots returns empty when no snapshot directories exist."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "api_run_no_attacks"
        sim_dir.mkdir(parents=True)

        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))

        response = api_client.get("/api/simulations/api_run_no_attacks/attack-snapshots")
        assert response.status_code == 200
        data = response.json()
        assert data["has_snapshots"] is False
        assert data["strategies"] == []

    def test_attack_snapshots_with_text_attack_html(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Attack snapshots with HTML-only text attacks are detected."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "api_run_text_attack"
        sim_dir.mkdir(parents=True)

        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))

        snapshot_dir = sim_dir / "attack_snapshots_0"
        client_dir = snapshot_dir / "client_0" / "round_1"
        client_dir.mkdir(parents=True)

        (client_dir / "token_replacement_samples.html").write_text(
            "<html><body>Text attack samples</body></html>"
        )
        (client_dir / "token_replacement_metadata.json").write_text(
            json.dumps({"attack_type": "token_replacement", "samples_affected": 5})
        )

        response = api_client.get("/api/simulations/api_run_text_attack/attack-snapshots")
        assert response.status_code == 200
        data = response.json()

        assert data["has_snapshots"] is True
        assert len(data["strategies"]) == 1
        assert len(data["strategies"][0]["snapshots"]) == 1

        snapshot = data["strategies"][0]["snapshots"][0]
        assert snapshot["attack_type"] == "token_replacement"
        assert snapshot.get("is_text_attack") is True
        assert "html_diff" in snapshot["visualizations"]

    def test_attack_snapshots_with_weight_only(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Weight snapshots without corresponding attack snapshots."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "api_run_weight_only"
        sim_dir.mkdir(parents=True)

        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))

        weight_dir = sim_dir / "attack_snapshots_0" / "client_0" / "round_1"
        weight_dir.mkdir(parents=True)

        (weight_dir / "model_poisoning_weight_histogram.png").write_bytes(b"PNG data")
        (weight_dir / "model_poisoning_weight_metadata.json").write_text(
            json.dumps({"scale_factor": 100.0, "layers_affected": 3})
        )

        response = api_client.get("/api/simulations/api_run_weight_only/attack-snapshots")
        assert response.status_code == 200
        data = response.json()

        assert data["has_snapshots"] is True

    def test_attack_snapshots_with_confusion_matrix(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Attack snapshots with additional visualizations are included."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "api_run_confusion"
        sim_dir.mkdir(parents=True)

        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))

        snapshot_dir = sim_dir / "attack_snapshots_0"
        client_dir = snapshot_dir / "client_0" / "round_1"
        client_dir.mkdir(parents=True)

        (client_dir / "label_flipping_visual.png").write_bytes(b"PNG")
        (client_dir / "label_flipping_confusion_matrix.png").write_bytes(b"PNG")
        (client_dir / "label_flipping_difference_heatmap.png").write_bytes(b"PNG")
        (client_dir / "label_flipping_summary.json").write_text(
            json.dumps({"flip_rate": 0.25, "source_label": 0, "target_label": 1})
        )

        response = api_client.get("/api/simulations/api_run_confusion/attack-snapshots")
        assert response.status_code == 200
        data = response.json()

        snapshot = data["strategies"][0]["snapshots"][0]
        assert "confusion_matrix" in snapshot["visualizations"]
        assert "difference_heatmap" in snapshot["visualizations"]
        assert "flip_summary" in snapshot

    def test_attack_snapshots_with_comparison_viz(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Attack snapshots with comparison visualization."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "api_run_comparison"
        sim_dir.mkdir(parents=True)

        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))

        snapshot_dir = sim_dir / "attack_snapshots_0"
        client_dir = snapshot_dir / "client_0" / "round_1"
        client_dir.mkdir(parents=True)

        (client_dir / "gaussian_noise_visual.png").write_bytes(b"PNG")
        (client_dir / "gaussian_noise_comparison.png").write_bytes(b"PNG")

        response = api_client.get("/api/simulations/api_run_comparison/attack-snapshots")
        assert response.status_code == 200
        data = response.json()

        snapshot = data["strategies"][0]["snapshots"][0]
        assert "comparison" in snapshot["visualizations"]


# =============================================================================
# Dataset Validation Tests
# =============================================================================


class TestDatasetValidation:
    """Tests for dataset validation endpoint."""

    def test_validate_dataset_valid(self, api_client: TestClient, monkeypatch):
        """GET /api/datasets/validate returns valid dataset info."""
        mock_builder = Mock()
        mock_builder.info.splits = {
            "train": Mock(num_examples=60000),
            "test": Mock(num_examples=10000),
        }
        mock_builder.info.features = "{'image': Image, 'label': ClassLabel}"

        def mock_load_builder(name):
            return mock_builder

        monkeypatch.setattr("src.api.main.load_dataset_builder", mock_load_builder)

        response = api_client.get("/api/datasets/validate?name=ylecun/mnist")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["compatible"] is True
        assert "info" in data
        assert data["info"]["has_label"] is True

    def test_validate_dataset_not_found(self, api_client: TestClient, monkeypatch):
        """GET /api/datasets/validate handles dataset not found."""

        def mock_load_builder(name):
            raise Exception("Dataset not found on HuggingFace Hub")

        monkeypatch.setattr("src.api.main.load_dataset_builder", mock_load_builder)

        response = api_client.get("/api/datasets/validate?name=invalid/dataset")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["compatible"] is False
        assert "not found" in data["error"].lower()

    def test_validate_dataset_network_error(self, api_client: TestClient, monkeypatch):
        """GET /api/datasets/validate handles network errors."""

        def mock_load_builder(name):
            raise Exception("Connection timeout")

        monkeypatch.setattr("src.api.main.load_dataset_builder", mock_load_builder)

        response = api_client.get("/api/datasets/validate?name=ylecun/mnist")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "network" in data["error"].lower() or "connection" in data["error"].lower()

    def test_validate_dataset_authentication_error(self, api_client: TestClient, monkeypatch):
        """GET /api/datasets/validate handles authentication errors."""

        def mock_load_builder(name):
            raise Exception("Unauthorized: 401")

        monkeypatch.setattr("src.api.main.load_dataset_builder", mock_load_builder)

        response = api_client.get("/api/datasets/validate?name=private/dataset")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "authentication" in data["error"].lower() or "unauthorized" in data["error"].lower()

    def test_validate_dataset_forbidden_error(self, api_client: TestClient, monkeypatch):
        """GET /api/datasets/validate handles forbidden errors."""

        def mock_load_builder(name):
            raise Exception("Forbidden: 403")

        monkeypatch.setattr("src.api.main.load_dataset_builder", mock_load_builder)

        response = api_client.get("/api/datasets/validate?name=restricted/dataset")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "forbidden" in data["error"].lower() or "permission" in data["error"].lower()

    def test_validate_dataset_invalid_format(self, api_client: TestClient, monkeypatch):
        """GET /api/datasets/validate handles invalid dataset name format."""

        def mock_load_builder(name):
            raise Exception("Invalid dataset identifier")

        monkeypatch.setattr("src.api.main.load_dataset_builder", mock_load_builder)

        response = api_client.get("/api/datasets/validate?name=invalidformat")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "format" in data["error"].lower()

    def test_validate_dataset_no_splits(self, api_client: TestClient, monkeypatch):
        """GET /api/datasets/validate handles dataset with no splits."""
        mock_builder = Mock()
        mock_builder.info.splits = None

        def mock_load_builder(name):
            return mock_builder

        monkeypatch.setattr("src.api.main.load_dataset_builder", mock_load_builder)

        response = api_client.get("/api/datasets/validate?name=test/dataset")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "no splits" in data["reason"].lower()

    def test_validate_dataset_with_complex_features(self, api_client: TestClient, monkeypatch):
        """GET /api/datasets/validate parses complex feature strings."""
        mock_builder = Mock()
        mock_builder.info.splits = {"train": Mock(num_examples=1000)}
        mock_builder.info.features = (
            "{'image': Image, 'label': ClassLabel, 'metadata': {'source': Value}}"
        )

        def mock_load_builder(name):
            return mock_builder

        monkeypatch.setattr("src.api.main.load_dataset_builder", mock_load_builder)

        response = api_client.get("/api/datasets/validate?name=test/complex")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["info"]["has_label"] is True
        assert "image" in data["info"]["key_features"]


# =============================================================================
# Plot Data Edge Cases
# =============================================================================


class TestPlotDataEdgeCases:
    """Tests for plot data endpoint edge cases."""

    def test_get_plot_data_nonexistent_simulation(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """GET /api/simulations/{id}/plot-data returns 404 for nonexistent simulation."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        (tmp_path / "out").mkdir(parents=True)

        response = api_client.get("/api/simulations/nonexistent/plot-data")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_plot_data_json_parse_error(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """GET /api/simulations/{id}/plot-data handles JSON parse errors."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "bad_json"
        sim_dir.mkdir(parents=True)

        (sim_dir / "plot_data_0.json").write_text("{invalid json")

        response = api_client.get("/api/simulations/bad_json/plot-data")
        assert response.status_code == 500

    def test_get_plot_data_file_not_found_error(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """GET /api/simulations/{id}/plot-data handles FileNotFoundError explicitly."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "missing_plot"
        sim_dir.mkdir(parents=True)

        plot_file = sim_dir / "plot_data_0.json"
        plot_file.write_text('{"rounds": [1, 2, 3]}')

        original_open = open

        def mock_open(*args, **kwargs):
            if "plot_data_0.json" in str(args[0]):
                raise FileNotFoundError("File disappeared")
            return original_open(*args, **kwargs)

        monkeypatch.setattr("builtins.open", mock_open)

        response = api_client.get("/api/simulations/missing_plot/plot-data")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# =============================================================================
# Simulation Details Edge Cases
# =============================================================================


class TestAllPlotDataEdgeCases:
    """Tests for all-plot-data endpoint edge cases."""

    def test_all_plot_data_json_parse_error(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """GET /api/simulations/{id}/all-plot-data handles JSON parse errors."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "bad_all_json"
        sim_dir.mkdir(parents=True)

        (sim_dir / "plot_data_0.json").write_text("{invalid json")

        response = api_client.get("/api/simulations/bad_all_json/all-plot-data")
        assert response.status_code == 500

    def test_all_plot_data_file_not_found(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """GET /api/simulations/{id}/all-plot-data handles FileNotFoundError."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "missing_all_plot"
        sim_dir.mkdir(parents=True)

        plot_file = sim_dir / "plot_data_0.json"
        plot_file.write_text('{"rounds": [1, 2, 3]}')

        original_open = open

        def mock_open(*args, **kwargs):
            if "plot_data_0.json" in str(args[0]):
                raise FileNotFoundError("File disappeared")
            return original_open(*args, **kwargs)

        monkeypatch.setattr("builtins.open", mock_open)

        response = api_client.get("/api/simulations/missing_all_plot/all-plot-data")
        assert response.status_code == 404


class TestSimulationDetailsEdgeCases:
    """Tests for simulation details edge cases."""

    def test_details_with_nested_result_files(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """GET /api/simulations/{id} includes nested subdirectory files."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "api_run_nested"
        sim_dir.mkdir(parents=True)

        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))

        csv_dir = sim_dir / "csv"
        csv_dir.mkdir()
        (csv_dir / "round_metrics_0.csv").write_text("round,accuracy\n1,0.8")

        snapshot_dir = sim_dir / "attack_snapshots_0" / "client_0" / "round_1"
        snapshot_dir.mkdir(parents=True)
        (snapshot_dir / "visual.png").write_bytes(b"PNG")

        response = api_client.get("/api/simulations/api_run_nested")
        assert response.status_code == 200
        data = response.json()

        result_files = data["result_files"]
        assert "csv/round_metrics_0.csv" in result_files
        assert any("attack_snapshots_0" in f for f in result_files)

    def test_details_with_legacy_config_structure(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """GET /api/simulations handles legacy config without shared_settings."""
        monkeypatch.setattr("src.api.main.OUTPUT_DIR", tmp_path / "out")
        sim_dir = tmp_path / "out" / "api_run_legacy"
        sim_dir.mkdir(parents=True)

        legacy_config = {
            "aggregation_strategy_keyword": "fedavg",
            "num_of_rounds": 5,
            "num_of_clients": 3,
        }
        (sim_dir / "config.json").write_text(json.dumps(legacy_config))
        (sim_dir / "results.pdf").write_bytes(b"%PDF")

        response = api_client.get("/api/simulations")
        assert response.status_code == 200
        sims = response.json()

        legacy_sim = next((s for s in sims if s["simulation_id"] == "api_run_legacy"), None)
        assert legacy_sim is not None
        assert legacy_sim["strategy_name"] == "fedavg"
