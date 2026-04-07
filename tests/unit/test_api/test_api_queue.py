"""Unit tests for queue status API endpoint."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from intellifl.api import main


@pytest.fixture
def api_client():
    """Create a TestClient for the FastAPI app."""
    return TestClient(main.app)


@pytest.fixture
def patch_output_dir(monkeypatch, tmp_path: Path):
    """Patch OUTPUT_DIR to use a temporary directory."""
    monkeypatch.setattr("intellifl.api.routers.queue.OUTPUT_DIR", tmp_path)
    return tmp_path


def _create_simulation(output_dir: Path, sim_id: str, status: str | None = None) -> Path:
    """Helper to create a mock simulation directory with status."""
    sim_dir = output_dir / sim_id
    sim_dir.mkdir(parents=True, exist_ok=True)

    config = {"num_of_rounds": 5, "num_of_clients": 3}
    (sim_dir / "config.json").write_text(json.dumps(config))

    if status:
        status_data = {"status": status, "progress": 0.5}
        (sim_dir / "status.json").write_text(json.dumps(status_data))

    return sim_dir


# =============================================================================
# GET /api/queue/status Tests
# =============================================================================


def test_queue_status_empty_dir(api_client: TestClient, patch_output_dir: Path):
    """GET /api/queue/status returns zeros when no simulations exist."""
    response = api_client.get("/api/queue/status")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 0
    assert data["queued"] == 0
    assert data["running"] == 0
    assert data["completed"] == 0
    assert data["is_empty"] is True


def test_queue_status_all_completed(api_client: TestClient, patch_output_dir: Path):
    """GET /api/queue/status with all completed simulations shows is_empty=True."""
    _create_simulation(patch_output_dir, "sim_1", status="completed")
    _create_simulation(patch_output_dir, "sim_2", status="completed")

    response = api_client.get("/api/queue/status")
    assert response.status_code == 200

    data = response.json()
    assert data["completed"] == 2
    assert data["running"] == 0
    assert data["queued"] == 0
    assert data["total"] == 2
    assert data["is_empty"] is True


def test_queue_status_mixed_states(api_client: TestClient, patch_output_dir: Path):
    """GET /api/queue/status returns correct counts for mixed simulation states."""
    _create_simulation(patch_output_dir, "sim_running", status="running")
    _create_simulation(patch_output_dir, "sim_queued_1", status="queued")
    _create_simulation(patch_output_dir, "sim_queued_2", status="queued")
    _create_simulation(patch_output_dir, "sim_completed", status="completed")
    _create_simulation(patch_output_dir, "sim_failed", status="failed")

    response = api_client.get("/api/queue/status")
    assert response.status_code == 200

    data = response.json()
    assert data["running"] == 1
    assert data["queued"] == 2
    assert data["completed"] == 1
    assert data["failed"] == 1
    assert data["total"] == 5
    assert data["is_empty"] is False


def test_queue_status_with_stopped_marker(api_client: TestClient, patch_output_dir: Path):
    """GET /api/queue/status respects .stopped marker over status.json."""
    sim_dir = _create_simulation(patch_output_dir, "sim_stopped", status="running")
    # Add .stopped marker - should override status.json
    (sim_dir / ".stopped").write_text("Stopped by user")

    response = api_client.get("/api/queue/status")
    assert response.status_code == 200

    data = response.json()
    assert data["stopped"] == 1
    assert data["running"] == 0
    assert data["is_empty"] is True


def test_queue_status_infers_completed_from_results(api_client: TestClient, patch_output_dir: Path):
    """GET /api/queue/status infers completed status from result files."""
    sim_dir = _create_simulation(patch_output_dir, "sim_no_status")
    # No status.json, but has result files
    (sim_dir / "results.pdf").write_text("dummy pdf")

    response = api_client.get("/api/queue/status")
    assert response.status_code == 200

    data = response.json()
    assert data["completed"] == 1
    assert data["is_empty"] is True


def test_queue_status_ignores_dirs_without_config(api_client: TestClient, patch_output_dir: Path):
    """GET /api/queue/status ignores directories without config.json."""
    _create_simulation(patch_output_dir, "valid_sim", status="running")

    # Create invalid dir (no config.json)
    invalid_dir = patch_output_dir / "invalid_sim"
    invalid_dir.mkdir()
    (invalid_dir / "status.json").write_text('{"status": "running"}')

    response = api_client.get("/api/queue/status")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1  # Only counts valid simulation
    assert data["running"] == 1
