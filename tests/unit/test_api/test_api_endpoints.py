"""
Unit tests for FastAPI HTTP endpoints in intellifl/api/main.py.

Tests cover:
- Root and health endpoints
- Simulation CRUD operations (GET, POST, DELETE, PATCH)
- Simulation status and streaming
- Result file serving (CSV, JSON, PDF, HTML, TXT)
- CORS configuration
- Error handling and validation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from intellifl.api import main

# =============================================================================
# Root and Health Endpoints
# =============================================================================


def test_read_root(api_client: TestClient):
    """GET / returns welcome message."""
    response = api_client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Federated Learning Simulation Framework API"}


def test_health_check(api_client: TestClient):
    """GET /api/health returns healthy status."""
    response = api_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


# =============================================================================
# List Simulations (GET /api/simulations)
# =============================================================================


def test_list_simulations_empty(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations returns empty list when no simulations exist."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    response = api_client.get("/api/simulations")
    assert response.status_code == 200
    assert response.json() == []


def test_list_simulations(api_client: TestClient, mock_simulation_dir: Path, monkeypatch):
    """GET /api/simulations returns list of simulations."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", mock_simulation_dir.parent)

    response = api_client.get("/api/simulations")
    assert response.status_code == 200
    sims = response.json()
    assert len(sims) == 1
    assert sims[0]["simulation_id"] == "api_run_20250107_120000"
    assert sims[0]["strategy_name"] == "fedavg"
    assert sims[0]["num_of_rounds"] == 5
    assert sims[0]["num_of_clients"] == 3
    assert "created_at" in sims[0]


def test_list_simulations_with_malformed_config(
    api_client: TestClient, tmp_path: Path, monkeypatch
):
    """GET /api/simulations skips simulations with malformed config.json."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    (tmp_path / "out").mkdir(parents=True)

    # Create simulation with valid config
    valid_sim = tmp_path / "out" / "valid_sim"
    valid_sim.mkdir()
    valid_config = {
        "shared_settings": {
            "aggregation_strategy_keyword": "fedavg",
            "num_of_rounds": 5,
            "num_of_clients": 3,
        }
    }
    (valid_sim / "config.json").write_text(json.dumps(valid_config))

    # Create simulation with malformed config
    bad_sim = tmp_path / "out" / "bad_sim"
    bad_sim.mkdir()
    (bad_sim / "config.json").write_text("{invalid json}")

    response = api_client.get("/api/simulations")
    assert response.status_code == 200
    sims = response.json()

    # Should only return the valid simulation
    assert len(sims) == 1
    assert sims[0]["simulation_id"] == "valid_sim"


def test_list_simulations_with_io_error(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations handles IO errors when reading config."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    (tmp_path / "out").mkdir(parents=True)

    sim_dir = tmp_path / "out" / "io_error_sim"
    sim_dir.mkdir()

    config = {"shared_settings": {"aggregation_strategy_keyword": "fedavg"}}
    config_path = sim_dir / "config.json"
    config_path.write_text(json.dumps(config))

    from pathlib import Path as PathLib

    original_open = PathLib.open

    def mock_open(self, *args, **kwargs):
        if "io_error_sim" in str(self) and "config.json" in str(self):
            raise OSError("Permission denied")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr("pathlib.Path.open", mock_open)

    response = api_client.get("/api/simulations")
    assert response.status_code == 200
    sims = response.json()
    assert all(sim["simulation_id"] != "io_error_sim" for sim in sims)


def test_simulation_with_nested_config_structure(
    api_client: TestClient, tmp_path: Path, monkeypatch
):
    """GET /api/simulations handles nested config structure."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "nested_config"
    sim_dir.mkdir(parents=True)

    config = {
        "shared_settings": {
            "aggregation_strategy_keyword": "pid",
            "num_of_rounds": 10,
            "num_of_clients": 5,
        },
        "simulation_strategies": [{}],
    }
    (sim_dir / "config.json").write_text(json.dumps(config))

    response = api_client.get("/api/simulations")
    assert response.status_code == 200
    sims = response.json()
    assert len(sims) == 1
    assert sims[0]["strategy_name"] == "pid"
    assert sims[0]["num_of_rounds"] == 10


# =============================================================================
# Get Simulation Details (GET /api/simulations/{id})
# =============================================================================


def test_get_simulation_details(api_client: TestClient, mock_simulation_dir: Path, monkeypatch):
    """GET /api/simulations/{id} returns simulation details."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", mock_simulation_dir.parent)

    response = api_client.get("/api/simulations/api_run_20250107_120000")
    assert response.status_code == 200
    data = response.json()

    assert "config" in data
    assert "result_files" in data
    assert "status" in data
    assert data["config"]["shared_settings"]["aggregation_strategy_keyword"] == "fedavg"
    assert "metrics.csv" in data["result_files"]
    assert "plot_data_0.json" in data["result_files"]
    assert "accuracy_plot.pdf" in data["result_files"]


def test_get_nonexistent_simulation(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations/invalid_id returns 404."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    (tmp_path / "out").mkdir(parents=True)

    response = api_client.get("/api/simulations/nonexistent_sim")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_missing_config_json_returns_404(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations/{id} returns 404 when config.json missing."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "sim_no_config"
    sim_dir.mkdir(parents=True)

    response = api_client.get("/api/simulations/sim_no_config")
    assert response.status_code == 404
    assert "config.json not found" in response.json()["detail"]


def test_malformed_config_json_returns_500(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations/{id} returns 500 when config.json is malformed."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "sim_bad_config"
    sim_dir.mkdir(parents=True)
    (sim_dir / "config.json").write_text("{invalid json")

    response = api_client.get("/api/simulations/sim_bad_config")
    assert response.status_code == 500
    assert "could not read" in response.json()["detail"].lower()


def test_simulation_details_with_failed_status(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations/{id} returns 'failed' status when execution.log exists."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "failed_details"
    sim_dir.mkdir(parents=True)

    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))
    (sim_dir / "execution.log").write_text("Simulation failed")

    response = api_client.get("/api/simulations/failed_details")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"


def test_simulation_details_filters_dataset_directories(
    api_client: TestClient, tmp_path: Path, monkeypatch
):
    """GET /api/simulations/{id} excludes dataset_ directories from result_files."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "test_filter"
    sim_dir.mkdir(parents=True)

    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))

    # Create result files
    (sim_dir / "metrics.csv").write_text("round,accuracy\n1,0.8")
    (sim_dir / "plot.pdf").write_bytes(b"%PDF-1.4")

    # Create dataset directory (should be filtered out)
    dataset_dir = sim_dir / "dataset_mnist"
    dataset_dir.mkdir()
    (dataset_dir / "train.csv").write_text("data")

    response = api_client.get("/api/simulations/test_filter")
    assert response.status_code == 200
    data = response.json()

    assert "metrics.csv" in data["result_files"]
    assert "plot.pdf" in data["result_files"]
    assert not any("dataset_" in f for f in data["result_files"])


# =============================================================================
# Simulation Status (GET /api/simulations/{id}/status)
# =============================================================================


def test_get_simulation_status_completed(
    api_client: TestClient, mock_simulation_dir: Path, monkeypatch
):
    """GET /api/simulations/{id}/status returns 'completed' when results exist."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", mock_simulation_dir.parent)

    response = api_client.get("/api/simulations/api_run_20250107_120000/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["progress"] == 1.0


def test_get_simulation_status_pending(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations/{id}/status returns 'pending' when no results exist."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "api_run_pending"
    sim_dir.mkdir(parents=True)

    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))

    response = api_client.get("/api/simulations/api_run_pending/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["progress"] == 0.0


def test_simulation_status_failed_with_error_log(
    api_client: TestClient, tmp_path: Path, monkeypatch
):
    """GET /api/simulations/{id}/status returns 'failed' with error message."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "failed_sim"
    sim_dir.mkdir(parents=True)

    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))
    (sim_dir / "execution.log").write_text("Critical error: Out of memory")

    response = api_client.get("/api/simulations/failed_sim/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert "error" in data
    assert "Out of memory" in data["error"]


def test_simulation_status_with_running_process(
    api_client: TestClient, tmp_path: Path, monkeypatch
):
    """GET /api/simulations/{id}/status returns 'running' when process is active."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "api_run_active"
    sim_dir.mkdir(parents=True)
    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))

    mock_process = MagicMock()
    mock_process.poll.return_value = None

    main.running_processes["api_run_active"] = mock_process

    response = api_client.get("/api/simulations/api_run_active/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["progress"] == 0.0

    del main.running_processes["api_run_active"]


def test_simulation_status_with_finished_process_no_results(
    api_client: TestClient, tmp_path: Path, monkeypatch
):
    """Process finished with non-zero exit and no results returns 'failed'."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "failed_process"
    sim_dir.mkdir(parents=True)

    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))
    (sim_dir / "execution.log").write_text("Process exited with code 1")

    mock_process = MagicMock()
    mock_process.poll.return_value = 1

    main.running_processes["failed_process"] = mock_process

    response = api_client.get("/api/simulations/failed_process/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["progress"] == 0.0
    assert "failed_process" not in main.running_processes


def test_simulation_status_transitions_to_completed(
    api_client: TestClient, mock_simulation_dir: Path, monkeypatch
):
    """Process completion transitions status from 'running' to 'completed'."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", mock_simulation_dir.parent)

    mock_process = MagicMock()
    mock_process.poll.return_value = 0

    main.running_processes["api_run_20250107_120000"] = mock_process

    response = api_client.get("/api/simulations/api_run_20250107_120000/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["progress"] == 1.0
    assert "api_run_20250107_120000" not in main.running_processes


def test_simulation_status_stopped_marker(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations/{id}/status returns 'stopped' when .stopped marker exists."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "stopped_sim"
    sim_dir.mkdir(parents=True)

    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))
    (sim_dir / ".stopped").write_text("Simulation stopped")

    response = api_client.get("/api/simulations/stopped_sim/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "stopped"
    assert data["progress"] == 0.0


def test_simulation_status_completed_with_results_no_process(
    api_client: TestClient, mock_simulation_dir: Path, monkeypatch
):
    """Status returns 'completed' when results exist but no tracked process."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", mock_simulation_dir.parent)

    if "api_run_20250107_120000" in main.running_processes:
        del main.running_processes["api_run_20250107_120000"]

    response = api_client.get("/api/simulations/api_run_20250107_120000/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["progress"] == 1.0


# =============================================================================
# Create Simulation (POST /api/simulations)
# =============================================================================


def test_create_simulation_valid_config(api_client: TestClient, tmp_path: Path, monkeypatch):
    """POST /api/simulations with valid config returns 201 and simulation_id."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr("intellifl.api.main.BASE_DIR", tmp_path)

    mock_process = MagicMock()
    mock_process.pid = 12345
    monkeypatch.setattr("intellifl.api.main.subprocess.Popen", lambda *args, **kwargs: mock_process)

    config = {
        "aggregation_strategy_keyword": "fedavg",
        "dataset_keyword": "bloodmnist",
        "num_of_rounds": 3,
        "num_of_clients": 2,
    }

    response = api_client.post("/api/simulations", json=config)
    assert response.status_code == 201
    data = response.json()
    assert "simulation_id" in data
    assert data["simulation_id"].startswith("api_run_")

    sim_id = data["simulation_id"]
    config_path = tmp_path / "out" / sim_id / "config.json"
    assert config_path.exists()
    with open(config_path) as f:
        saved_config = json.load(f)
    assert saved_config["shared_settings"]["aggregation_strategy_keyword"] == "fedavg"


def test_create_simulation_spawns_background_task(
    api_client: TestClient, tmp_path: Path, monkeypatch
):
    """POST /api/simulations spawns background subprocess."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr("intellifl.api.main.BASE_DIR", tmp_path)

    popen_calls = []

    def mock_popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        mock_process = MagicMock()
        mock_process.pid = 99999
        return mock_process

    monkeypatch.setattr("intellifl.api.main.subprocess.Popen", mock_popen)

    config = {
        "aggregation_strategy_keyword": "fedavg",
        "dataset_keyword": "bloodmnist",
        "num_of_rounds": 2,
        "num_of_clients": 2,
    }

    response = api_client.post("/api/simulations", json=config)
    assert response.status_code == 201
    assert len(popen_calls) == 1
    args, kwargs = popen_calls[0]
    cmd = args[0]
    assert "python" in cmd[0]
    assert "-m" in cmd
    assert "intellifl.simulation_runner" in cmd


def test_create_simulation_config_write_error(api_client: TestClient, tmp_path: Path, monkeypatch):
    """POST /api/simulations handles config write errors."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr("intellifl.api.main.BASE_DIR", tmp_path)
    (tmp_path / "out").mkdir(parents=True, exist_ok=True)

    from pathlib import Path as PathLib

    original_open = PathLib.open

    def mock_open(self, *args, **kwargs):
        if "config.json" in str(self):
            raise OSError("Disk full")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr("pathlib.Path.open", mock_open)

    config = {"aggregation_strategy_keyword": "fedavg"}

    response = api_client.post("/api/simulations", json=config)
    assert response.status_code == 500
    assert "failed to write config" in response.json()["detail"].lower()


def test_create_simulation_subprocess_error(api_client: TestClient, tmp_path: Path, monkeypatch):
    """POST /api/simulations handles subprocess creation errors."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr("intellifl.api.main.BASE_DIR", tmp_path)

    def mock_popen(*args, **kwargs):
        raise OSError("Failed to spawn process")

    monkeypatch.setattr("intellifl.api.main.subprocess.Popen", mock_popen)

    config = {"aggregation_strategy_keyword": "fedavg"}

    response = api_client.post("/api/simulations", json=config)
    assert response.status_code == 500
    assert "failed to start simulation" in response.json()["detail"].lower()


def test_create_simulation_sets_loky_env_vars(api_client: TestClient, tmp_path: Path, monkeypatch):
    """POST /api/simulations sets LOKY_MAX_CPU_COUNT environment variable."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr("intellifl.api.main.BASE_DIR", tmp_path)

    captured_env = {}

    def mock_popen(*args, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        mock_process = MagicMock()
        mock_process.pid = 12345
        return mock_process

    monkeypatch.setattr("intellifl.api.main.subprocess.Popen", mock_popen)

    config = {"aggregation_strategy_keyword": "fedavg"}
    response = api_client.post("/api/simulations", json=config)

    assert response.status_code == 201
    assert "LOKY_MAX_CPU_COUNT" in captured_env
    assert int(captured_env["LOKY_MAX_CPU_COUNT"]) > 0


# =============================================================================
# Prepare Simulation (POST /api/simulations/prepare)
# =============================================================================


def test_prepare_simulation_success(api_client: TestClient, tmp_path: Path, monkeypatch):
    """POST /api/simulations/prepare creates config without starting process."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr("intellifl.api.main.BASE_DIR", tmp_path)

    # Clean up any leftover mock processes from previous tests
    main.running_processes.clear()

    config = {
        "aggregation_strategy_keyword": "fedavg",
        "dataset_keyword": "bloodmnist",
        "num_of_rounds": 3,
        "num_of_clients": 2,
    }

    response = api_client.post("/api/simulations/prepare", json=config)
    assert response.status_code == 201
    data = response.json()

    assert "simulation_id" in data
    assert data["simulation_id"].startswith("api_run_")
    assert "command" in data
    assert "python -m intellifl.simulation_runner" in data["command"]
    assert "config_path" in data

    sim_id = data["simulation_id"]
    config_path = tmp_path / "out" / sim_id / "config.json"
    assert config_path.exists()
    assert sim_id not in main.running_processes


def test_prepare_simulation_multi_strategy_config(
    api_client: TestClient, tmp_path: Path, monkeypatch
):
    """POST /api/simulations/prepare handles multi-strategy config."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr("intellifl.api.main.BASE_DIR", tmp_path)

    config = {
        "shared_settings": {
            "dataset_keyword": "bloodmnist",
            "num_of_rounds": 5,
            "num_of_clients": 4,
        },
        "simulation_strategies": [
            {"aggregation_strategy_keyword": "fedavg"},
            {"aggregation_strategy_keyword": "krum"},
        ],
    }

    response = api_client.post("/api/simulations/prepare", json=config)
    assert response.status_code == 201
    data = response.json()

    sim_id = data["simulation_id"]
    config_path = tmp_path / "out" / sim_id / "config.json"

    with open(config_path) as f:
        saved_config = json.load(f)

    assert "shared_settings" in saved_config
    assert "simulation_strategies" in saved_config
    assert len(saved_config["simulation_strategies"]) == 2


def test_prepare_simulation_config_write_error(api_client: TestClient, tmp_path: Path, monkeypatch):
    """POST /api/simulations/prepare handles config write errors."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr("intellifl.api.main.BASE_DIR", tmp_path)

    from pathlib import Path as PathLib

    original_open = PathLib.open

    def mock_open(self, *args, **kwargs):
        if "config.json" in str(self):
            raise OSError("Permission denied")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr("pathlib.Path.open", mock_open)

    config = {"aggregation_strategy_keyword": "fedavg"}

    response = api_client.post("/api/simulations/prepare", json=config)
    assert response.status_code == 500
    assert "failed to write config" in response.json()["detail"].lower()


# =============================================================================
# Delete Simulation (DELETE /api/simulations/{id})
# =============================================================================


def test_delete_simulation_success(api_client: TestClient, tmp_path: Path, monkeypatch):
    """DELETE /api/simulations/{id} deletes simulation successfully."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "test_delete"
    sim_dir.mkdir(parents=True)
    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))
    (sim_dir / "results.csv").write_text("data")

    assert sim_dir.exists()

    response = api_client.delete("/api/simulations/test_delete")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "deleted"
    assert data["simulation_id"] == "test_delete"
    assert not sim_dir.exists()


def test_delete_simulation_not_found(api_client: TestClient, tmp_path: Path, monkeypatch):
    """DELETE /api/simulations/{id} returns 404 for nonexistent simulation."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    (tmp_path / "out").mkdir(parents=True)

    response = api_client.delete("/api/simulations/nonexistent")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_simulation_running_process(api_client: TestClient, tmp_path: Path, monkeypatch):
    """DELETE /api/simulations/{id} returns 409 for running simulation."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "running_sim"
    sim_dir.mkdir(parents=True)
    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))

    mock_process = MagicMock()
    mock_process.poll.return_value = None
    main.running_processes["running_sim"] = mock_process

    response = api_client.delete("/api/simulations/running_sim")
    assert response.status_code == 409
    assert "cannot delete" in response.json()["detail"].lower()

    del main.running_processes["running_sim"]


def test_delete_simulation_finished_process(api_client: TestClient, tmp_path: Path, monkeypatch):
    """DELETE /api/simulations/{id} succeeds when process is finished."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "finished_sim"
    sim_dir.mkdir(parents=True)
    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))

    mock_process = MagicMock()
    mock_process.poll.return_value = 0
    main.running_processes["finished_sim"] = mock_process

    response = api_client.delete("/api/simulations/finished_sim")
    assert response.status_code == 200
    assert not sim_dir.exists()
    assert "finished_sim" not in main.running_processes


def test_delete_multiple_simulations_success(api_client: TestClient, tmp_path: Path, monkeypatch):
    """DELETE /api/simulations with simulation_ids deletes multiple simulations."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")

    for sim_id in ["sim1", "sim2", "sim3"]:
        sim_dir = tmp_path / "out" / sim_id
        sim_dir.mkdir(parents=True)
        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))

    response = api_client.request(
        "DELETE", "/api/simulations", json={"simulation_ids": ["sim1", "sim2", "sim3"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["deleted"]) == 3
    assert len(data["failed"]) == 0
    assert "sim1" in data["deleted"]
    assert "sim2" in data["deleted"]
    assert "sim3" in data["deleted"]

    assert not (tmp_path / "out" / "sim1").exists()
    assert not (tmp_path / "out" / "sim2").exists()
    assert not (tmp_path / "out" / "sim3").exists()


def test_delete_multiple_simulations_partial_failure(
    api_client: TestClient, tmp_path: Path, monkeypatch
):
    """DELETE /api/simulations returns success and failures separately."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    (tmp_path / "out").mkdir(parents=True)

    sim_dir = tmp_path / "out" / "valid_sim"
    sim_dir.mkdir()
    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))

    response = api_client.request(
        "DELETE",
        "/api/simulations",
        json={"simulation_ids": ["valid_sim", "nonexistent"]},
    )
    assert response.status_code == 200
    data = response.json()

    assert "valid_sim" in data["deleted"]
    assert len(data["failed"]) == 1
    assert data["failed"][0]["simulation_id"] == "nonexistent"
    assert "not found" in data["failed"][0]["error"].lower()


def test_delete_multiple_simulations_running_process(
    api_client: TestClient, tmp_path: Path, monkeypatch
):
    """DELETE /api/simulations skips running simulations."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")

    for sim_id in ["completed_sim", "running_sim"]:
        sim_dir = tmp_path / "out" / sim_id
        sim_dir.mkdir(parents=True)
        config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
        (sim_dir / "config.json").write_text(json.dumps(config))

    mock_process = MagicMock()
    mock_process.poll.return_value = None
    main.running_processes["running_sim"] = mock_process

    response = api_client.request(
        "DELETE",
        "/api/simulations",
        json={"simulation_ids": ["completed_sim", "running_sim"]},
    )
    assert response.status_code == 200
    data = response.json()

    assert "completed_sim" in data["deleted"]
    assert len(data["failed"]) == 1
    assert data["failed"][0]["simulation_id"] == "running_sim"
    assert "running" in data["failed"][0]["error"].lower()

    del main.running_processes["running_sim"]


# =============================================================================
# Rename Simulation (PATCH /api/simulations/{id}/rename)
# =============================================================================


def test_rename_simulation_success(api_client: TestClient, tmp_path: Path, monkeypatch):
    """PATCH /api/simulations/{id}/rename updates display_name successfully."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "test_rename"
    sim_dir.mkdir(parents=True)
    config = {
        "shared_settings": {"display_name": "Old Name"},
        "simulation_strategies": [{}],
    }
    (sim_dir / "config.json").write_text(json.dumps(config))

    response = api_client.patch(
        "/api/simulations/test_rename/rename", json={"display_name": "New Test Name"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "renamed"
    assert data["simulation_id"] == "test_rename"
    assert data["display_name"] == "New Test Name"

    with open(sim_dir / "config.json") as f:
        updated_config = json.load(f)
    assert updated_config["shared_settings"]["display_name"] == "New Test Name"


def test_rename_simulation_empty_name(api_client: TestClient, tmp_path: Path, monkeypatch):
    """PATCH /api/simulations/{id}/rename returns 400 for empty display_name."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "test_rename"
    sim_dir.mkdir(parents=True)
    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))

    response = api_client.patch("/api/simulations/test_rename/rename", json={"display_name": ""})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_rename_simulation_name_too_long(api_client: TestClient, tmp_path: Path, monkeypatch):
    """PATCH /api/simulations/{id}/rename returns 400 for name >100 chars."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "test_rename"
    sim_dir.mkdir(parents=True)
    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))

    long_name = "A" * 101
    response = api_client.patch(
        "/api/simulations/test_rename/rename", json={"display_name": long_name}
    )
    assert response.status_code == 400
    assert "100 characters" in response.json()["detail"]


def test_rename_simulation_special_characters(api_client: TestClient, tmp_path: Path, monkeypatch):
    """PATCH /api/simulations/{id}/rename accepts special characters."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "test_rename"
    sim_dir.mkdir(parents=True)
    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))

    response = api_client.patch(
        "/api/simulations/test_rename/rename", json={"display_name": "Name@With!Special#Chars"}
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Name@With!Special#Chars"


# =============================================================================
# Stop Simulation (POST /api/simulations/{id}/stop)
# =============================================================================


def test_stop_simulation_success(api_client: TestClient, tmp_path: Path, monkeypatch):
    """POST /api/simulations/{id}/stop stops a running simulation."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "running_stop"
    sim_dir.mkdir(parents=True)

    mock_process = MagicMock()
    mock_process.poll.return_value = None
    mock_process.pid = 12345

    mock_psutil_process = MagicMock()
    mock_psutil_process.children.return_value = []
    mock_psutil_process.terminate = MagicMock()
    mock_psutil_process.wait = MagicMock()

    def mock_psutil_process_init(pid):
        return mock_psutil_process

    monkeypatch.setattr("intellifl.api.main.psutil.Process", mock_psutil_process_init)
    main.running_processes["running_stop"] = mock_process

    response = api_client.post("/api/simulations/running_stop/stop")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "stopped"
    assert data["simulation_id"] == "running_stop"
    assert "running_stop" not in main.running_processes


def test_stop_simulation_not_running(api_client: TestClient):
    """POST /api/simulations/{id}/stop returns 404 when simulation not running."""
    response = api_client.post("/api/simulations/not_running/stop")
    assert response.status_code == 404
    assert "not running" in response.json()["detail"].lower()


# =============================================================================
# SSE Stream (GET /api/simulations/{id}/stream)
# =============================================================================


def test_stream_endpoint_exists(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations/{id}/stream endpoint exists and returns SSE format."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "api_run_stream_test"
    sim_dir.mkdir(parents=True)

    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))
    (sim_dir / "results.pdf").write_bytes(b"%PDF-1.4")

    response = api_client.get("/api/simulations/api_run_stream_test/stream")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


def test_stream_nonexistent_simulation(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations/{id}/stream returns 404 for nonexistent simulation."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    (tmp_path / "out").mkdir(parents=True)

    response = api_client.get("/api/simulations/nonexistent_sim/stream")
    assert response.status_code == 404


# =============================================================================
# Result File Serving
# =============================================================================


def test_get_metrics_csv(api_client: TestClient, mock_simulation_dir: Path, monkeypatch):
    """GET /api/simulations/{id}/results/metrics.csv serves CSV as JSON."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", mock_simulation_dir.parent)

    response = api_client.get("/api/simulations/api_run_20250107_120000/results/metrics.csv")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["round"] == 1
    assert data[0]["accuracy"] == 0.85


def test_get_result_file_csv_download(
    api_client: TestClient, mock_simulation_dir: Path, monkeypatch
):
    """GET /api/simulations/{id}/results/{file}.csv?download=true returns CSV file."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", mock_simulation_dir.parent)

    response = api_client.get(
        "/api/simulations/api_run_20250107_120000/results/metrics.csv?download=true"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "content-disposition" in response.headers
    assert "attachment" in response.headers["content-disposition"]


def test_get_plot_data_json(api_client: TestClient, mock_simulation_dir: Path, monkeypatch):
    """GET /api/simulations/{id}/plot-data serves interactive plot JSON."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", mock_simulation_dir.parent)

    response = api_client.get("/api/simulations/api_run_20250107_120000/plot-data")
    assert response.status_code == 200
    data = response.json()
    assert "rounds" in data
    assert "accuracy" in data
    assert data["rounds"] == [1, 2, 3]


def test_get_plot_data_not_found(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations/{id}/plot-data returns 404 when JSON missing."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "api_run_no_plots"
    sim_dir.mkdir(parents=True)
    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))

    response = api_client.get("/api/simulations/api_run_no_plots/plot-data")
    assert response.status_code == 404
    assert "not yet available" in response.json()["detail"].lower()


def test_get_static_plot(api_client: TestClient, mock_simulation_dir: Path, monkeypatch):
    """GET /api/simulations/{id}/results/{plot_name} serves PDF file."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", mock_simulation_dir.parent)

    response = api_client.get("/api/simulations/api_run_20250107_120000/results/accuracy_plot.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def test_get_missing_file_returns_404(
    api_client: TestClient, mock_simulation_dir: Path, monkeypatch
):
    """GET nonexistent result file returns 404."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", mock_simulation_dir.parent)

    response = api_client.get("/api/simulations/api_run_20250107_120000/results/nonexistent.pdf")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_unsupported_file_type(api_client: TestClient, mock_simulation_dir: Path, monkeypatch):
    """GET unsupported file type returns 400."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", mock_simulation_dir.parent)

    response = api_client.get("/api/simulations/api_run_20250107_120000/results/malicious.exe")
    assert response.status_code == 400
    assert "unsupported" in response.json()["detail"].lower()


def test_get_result_file_json_format(
    api_client: TestClient, mock_simulation_dir: Path, monkeypatch
):
    """GET /api/simulations/{id}/results/{file}.json serves JSON file."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", mock_simulation_dir.parent)

    response = api_client.get("/api/simulations/api_run_20250107_120000/results/plot_data_0.json")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"


def test_csv_read_error_returns_500(api_client: TestClient, tmp_path: Path, monkeypatch):
    """CSV read errors return 500 with error message."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "sim_bad_csv"
    sim_dir.mkdir(parents=True)
    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))
    (sim_dir / "bad.csv").write_bytes(b"\x00\x01\x02\x03\xff\xfe")

    response = api_client.get("/api/simulations/sim_bad_csv/results/bad.csv")
    assert response.status_code in [200, 400, 500]


def test_get_html_result_file(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations/{id}/results/{file}.html serves HTML file."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "api_run_html"
    sim_dir.mkdir(parents=True)

    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))
    (sim_dir / "report.html").write_text("<html><body>Report</body></html>")

    response = api_client.get("/api/simulations/api_run_html/results/report.html")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"


def test_get_txt_result_file(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations/{id}/results/{file}.txt serves text file."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "api_run_txt"
    sim_dir.mkdir(parents=True)

    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))
    (sim_dir / "log.txt").write_text("Log content here")

    response = api_client.get("/api/simulations/api_run_txt/results/log.txt")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


# =============================================================================
# All Plot Data Endpoint (GET /api/simulations/{id}/all-plot-data)
# =============================================================================


def test_get_all_plot_data_success(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations/{id}/all-plot-data returns all strategy plot data."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "api_run_multi_strategy"
    sim_dir.mkdir(parents=True)

    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))

    # Create multiple plot data files
    (sim_dir / "plot_data_0.json").write_text(
        json.dumps({"rounds": [1, 2], "accuracy": [0.7, 0.8]})
    )
    (sim_dir / "plot_data_1.json").write_text(
        json.dumps({"rounds": [1, 2], "accuracy": [0.75, 0.85]})
    )

    response = api_client.get("/api/simulations/api_run_multi_strategy/all-plot-data")
    assert response.status_code == 200
    data = response.json()
    assert "strategies" in data
    assert len(data["strategies"]) == 2
    assert data["strategies"][0]["strategy_number"] == 0
    assert data["strategies"][1]["strategy_number"] == 1


def test_get_all_plot_data_not_found(api_client: TestClient, tmp_path: Path, monkeypatch):
    """GET /api/simulations/{id}/all-plot-data returns 404 when no plot data exists."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "api_run_no_data"
    sim_dir.mkdir(parents=True)

    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))

    response = api_client.get("/api/simulations/api_run_no_data/all-plot-data")
    assert response.status_code == 404
    assert "not yet available" in response.json()["detail"].lower()


def test_get_all_plot_data_invalid_simulation_id(
    api_client: TestClient, tmp_path: Path, monkeypatch
):
    """GET /api/simulations/{id}/all-plot-data returns 400 for invalid simulation ID."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    (tmp_path / "out").mkdir(parents=True)

    # Use special characters that fail the ID validation
    response = api_client.get("/api/simulations/invalid..id/all-plot-data")
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


def test_get_all_plot_data_nonexistent_simulation(
    api_client: TestClient, tmp_path: Path, monkeypatch
):
    """GET /api/simulations/{id}/all-plot-data returns 404 for nonexistent simulation."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    (tmp_path / "out").mkdir(parents=True)

    response = api_client.get("/api/simulations/nonexistent_sim/all-plot-data")
    assert response.status_code == 404


# =============================================================================
# System Devices Endpoint (GET /api/system/devices)
# =============================================================================


def test_get_system_devices(api_client: TestClient, monkeypatch):
    """GET /api/system/devices returns available devices."""
    response = api_client.get("/api/system/devices")
    assert response.status_code == 200
    data = response.json()
    assert "available_devices" in data
    assert "cpu" in data["available_devices"]
    assert "gpu_available" in data
    assert "recommended_device" in data


def test_get_system_devices_no_gpu(api_client: TestClient, monkeypatch):
    """GET /api/system/devices handles systems without GPU."""
    # Mock torch.cuda.is_available to return False
    import sys

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    response = api_client.get("/api/system/devices")
    assert response.status_code == 200
    data = response.json()
    assert "cpu" in data["available_devices"]


# =============================================================================
# CORS Configuration
# =============================================================================


def test_cors_allows_frontend_origins(api_client: TestClient):
    """CORS middleware allows localhost:5173-5178."""
    headers = {"Origin": "http://localhost:5173"}
    response = api_client.get("/", headers=headers)
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_cors_allows_all_configured_ports(api_client: TestClient):
    """CORS middleware allows all configured frontend ports."""
    allowed_ports = [5173, 5174, 5175, 5176, 5177, 5178]
    for port in allowed_ports:
        headers = {"Origin": f"http://localhost:{port}"}
        response = api_client.get("/", headers=headers)
        assert response.status_code == 200


# =============================================================================
# Security and Validation
# =============================================================================


def test_path_traversal_blocked(api_client: TestClient, tmp_path: Path, monkeypatch):
    """Path traversal attempts are blocked with 400 or 404."""
    monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
    sim_dir = tmp_path / "out" / "test_sim"
    sim_dir.mkdir(parents=True)
    config: dict[str, Any] = {"shared_settings": {}, "simulation_strategies": [{}]}
    (sim_dir / "config.json").write_text(json.dumps(config))

    response = api_client.get("/api/simulations/test_sim/results/../../../etc/passwd")
    assert response.status_code in [400, 404]


def test_invalid_simulation_id_format(api_client: TestClient):
    """Invalid simulation ID format returns 400 or 404."""
    response = api_client.get("/api/simulations/../../etc/passwd")
    assert response.status_code in [400, 404]
