"""
API error handling and edge case tests.

These tests target uncovered error paths in intellifl/api/main.py:
- 404 responses for non-existent resources
- Validation errors for invalid configurations
- Edge cases in result retrieval
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


class TestAPIErrorResponses:
    """Test API error response handling."""

    def test_get_nonexistent_simulation(self, api_client: TestClient):
        """Test 404 for non-existent simulation."""
        response = api_client.get("/api/simulations/api_run_nonexistent_99999999")
        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()

    def test_get_nonexistent_simulation_status(self, api_client: TestClient):
        """Test 404 for non-existent simulation status."""
        response = api_client.get("/api/simulations/api_run_nonexistent/status")
        assert response.status_code == 404

    def test_get_nonexistent_simulation_results(self, api_client: TestClient):
        """Test 404 for non-existent simulation results."""
        response = api_client.get("/api/simulations/api_run_nonexistent/results/metrics.csv")
        assert response.status_code == 404

    def test_get_nonexistent_result_file(self, api_client: TestClient, tmp_path: Path, monkeypatch):
        """Test 404 for existing simulation but non-existent result file."""
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")

        # Create simulation directory without the requested file
        sim_dir = tmp_path / "out" / "api_run_20250101_120000"
        sim_dir.mkdir(parents=True)
        (sim_dir / "config.json").write_text(json.dumps({"shared_settings": {}}))

        response = api_client.get(
            "/api/simulations/api_run_20250101_120000/results/nonexistent.csv"
        )
        assert response.status_code == 404

    def test_invalid_simulation_id_format(self, api_client: TestClient):
        """Test 400 for invalid simulation ID with special characters."""
        # Use characters that FastAPI won't sanitize but will fail validation
        response = api_client.get("/api/simulations/api_run_test<>invalid")
        assert response.status_code == 400
        assert "invalid" in response.json().get("detail", "").lower()

    def test_unsupported_file_type(self, api_client: TestClient, tmp_path: Path, monkeypatch):
        """Test 400 for unsupported file types."""
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")

        sim_dir = tmp_path / "out" / "api_run_20250101_120000"
        sim_dir.mkdir(parents=True)
        (sim_dir / "config.json").write_text(json.dumps({"shared_settings": {}}))
        (sim_dir / "script.sh").write_text("#!/bin/bash")

        response = api_client.get("/api/simulations/api_run_20250101_120000/results/script.sh")
        assert response.status_code == 400
        assert "unsupported" in response.json().get("detail", "").lower()


class TestAPIValidationErrors:
    """Test API input validation."""

    def test_create_simulation_empty_config(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Test creating simulation with empty config."""
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
        monkeypatch.setattr("intellifl.api.main.BASE_DIR", tmp_path)

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll = MagicMock(return_value=None)
        monkeypatch.setattr(
            "intellifl.api.main.subprocess.Popen", lambda *args, **kwargs: mock_process
        )

        # Empty config should still work (uses defaults)
        response = api_client.post("/api/simulations", json={})
        assert response.status_code in [201, 422]  # 201 if defaults, 422 if validation

    def test_create_simulation_with_all_optional_fields(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Test creating simulation with all optional fields."""
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")
        monkeypatch.setattr("intellifl.api.main.BASE_DIR", tmp_path)

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll = MagicMock(return_value=None)
        monkeypatch.setattr(
            "intellifl.api.main.subprocess.Popen", lambda *args, **kwargs: mock_process
        )

        config = {
            "aggregation_strategy_keyword": "krum",
            "dataset_keyword": "bloodmnist",
            "num_of_rounds": 5,
            "num_of_clients": 10,
            "num_of_malicious_clients": 2,
            "attack_type": "label_flipping",
            "training_device": "cpu",
        }
        response = api_client.post("/api/simulations", json=config)
        assert response.status_code == 201
        assert "simulation_id" in response.json()

    def test_rename_simulation_empty_name(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Test renaming simulation with empty name."""
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")

        sim_dir = tmp_path / "out" / "api_run_20250101_120000"
        sim_dir.mkdir(parents=True)
        (sim_dir / "config.json").write_text(json.dumps({"shared_settings": {}}))

        response = api_client.patch(
            "/api/simulations/api_run_20250101_120000/rename",
            json={"display_name": ""},
        )
        assert response.status_code == 400
        assert "empty" in response.json().get("detail", "").lower()

    def test_rename_simulation_special_characters(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Test renaming simulation with special characters succeeds."""
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")

        sim_dir = tmp_path / "out" / "api_run_20250101_120000"
        sim_dir.mkdir(parents=True)
        (sim_dir / "config.json").write_text(json.dumps({"shared_settings": {}}))

        response = api_client.patch(
            "/api/simulations/api_run_20250101_120000/rename",
            json={"display_name": "Test<>Simulation"},
        )
        assert response.status_code == 200
        assert response.json()["display_name"] == "Test<>Simulation"

    def test_rename_simulation_too_long(self, api_client: TestClient, tmp_path: Path, monkeypatch):
        """Test renaming simulation with name exceeding 100 chars."""
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", tmp_path / "out")

        sim_dir = tmp_path / "out" / "api_run_20250101_120000"
        sim_dir.mkdir(parents=True)
        (sim_dir / "config.json").write_text(json.dumps({"shared_settings": {}}))

        long_name = "A" * 101
        response = api_client.patch(
            "/api/simulations/api_run_20250101_120000/rename",
            json={"display_name": long_name},
        )
        assert response.status_code == 400
        assert "100" in response.json().get("detail", "")


class TestAPIEdgeCases:
    """Test API edge cases and boundary conditions."""

    def test_list_simulations_empty(self, api_client: TestClient, tmp_path: Path, monkeypatch):
        """Test listing simulations when none exist."""
        empty_out = tmp_path / "out"
        empty_out.mkdir()
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", empty_out)

        response = api_client.get("/api/simulations")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_simulations_with_non_api_dirs(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Test that non-api_run directories are filtered correctly."""
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", out_dir)

        # Create non-api directories that should be ignored (no config.json)
        (out_dir / "some_other_dir").mkdir()
        (out_dir / "manual_run_123").mkdir()

        response = api_client.get("/api/simulations")
        assert response.status_code == 200
        assert response.json() == []  # No valid simulation dirs

    def test_simulation_with_malformed_config(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Test handling of simulation with malformed config.json."""
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", out_dir)

        # Create simulation with invalid JSON
        sim_dir = out_dir / "api_run_20250101_120000"
        sim_dir.mkdir()
        (sim_dir / "config.json").write_text("{ invalid json }")

        response = api_client.get("/api/simulations/api_run_20250101_120000")
        # Should handle gracefully
        assert response.status_code in [404, 500]

    def test_get_pdf_result(self, api_client: TestClient, tmp_path: Path, monkeypatch):
        """Test retrieving PDF result file."""
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", out_dir)

        sim_dir = out_dir / "api_run_20250101_120000"
        sim_dir.mkdir()
        (sim_dir / "config.json").write_text(json.dumps({"shared_settings": {}}))
        (sim_dir / "accuracy_plot.pdf").write_bytes(b"%PDF-1.4 fake pdf content")

        response = api_client.get(
            "/api/simulations/api_run_20250101_120000/results/accuracy_plot.pdf"
        )
        assert response.status_code == 200

    def test_get_csv_as_download(self, api_client: TestClient, tmp_path: Path, monkeypatch):
        """Test CSV download mode."""
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", out_dir)

        sim_dir = out_dir / "api_run_20250101_120000"
        sim_dir.mkdir()
        (sim_dir / "config.json").write_text(json.dumps({"shared_settings": {}}))
        (sim_dir / "metrics.csv").write_text("round,accuracy\n1,0.75\n2,0.85\n")

        response = api_client.get(
            "/api/simulations/api_run_20250101_120000/results/metrics.csv?download=true"
        )
        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "")

    def test_health_check(self, api_client: TestClient):
        """Test health check endpoint."""
        response = api_client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_endpoint(self, api_client: TestClient):
        """Test root endpoint."""
        response = api_client.get("/")
        assert response.status_code == 200
        assert "message" in response.json()

    def test_system_devices(self, api_client: TestClient):
        """Test system devices endpoint."""
        response = api_client.get("/api/system/devices")
        assert response.status_code == 200
        data = response.json()
        assert "available_devices" in data
        assert "cpu" in data["available_devices"]
        assert "recommended_device" in data


class TestAPIDeleteOperations:
    """Test API delete operations and edge cases."""

    def test_delete_nonexistent_simulation(self, api_client: TestClient):
        """Test deleting non-existent simulation."""
        response = api_client.delete("/api/simulations/api_run_nonexistent_99999999")
        assert response.status_code == 404

    def test_delete_multiple_simulations_mixed(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Test deleting multiple simulations with mixed results."""
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", out_dir)

        # Create one valid simulation
        sim_dir = out_dir / "api_run_valid_001"
        sim_dir.mkdir()
        (sim_dir / "config.json").write_text(json.dumps({"shared_settings": {}}))

        # Try to delete mix of existing and non-existing
        response = api_client.request(
            "DELETE",
            "/api/simulations",
            json={"simulation_ids": ["api_run_valid_001", "api_run_nonexistent"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "api_run_valid_001" in data["deleted"]
        assert any(f["simulation_id"] == "api_run_nonexistent" for f in data["failed"])


class TestAPIPlotData:
    """Test plot data retrieval endpoints."""

    def test_get_plot_data_no_files(self, api_client: TestClient, tmp_path: Path, monkeypatch):
        """Test plot data when no plot files exist."""
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", out_dir)

        sim_dir = out_dir / "api_run_20250101_120000"
        sim_dir.mkdir()
        (sim_dir / "config.json").write_text(json.dumps({"shared_settings": {}}))

        response = api_client.get("/api/simulations/api_run_20250101_120000/plot-data")
        assert response.status_code == 404
        assert "not yet available" in response.json().get("detail", "").lower()

    def test_get_all_plot_data_multiple_strategies(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Test retrieving all plot data for multi-strategy simulation."""
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", out_dir)

        sim_dir = out_dir / "api_run_20250101_120000"
        sim_dir.mkdir()
        (sim_dir / "config.json").write_text(json.dumps({"shared_settings": {}}))
        (sim_dir / "plot_data_0.json").write_text(
            json.dumps({"rounds": [1, 2], "accuracy": [0.7, 0.8]})
        )
        (sim_dir / "plot_data_1.json").write_text(
            json.dumps({"rounds": [1, 2], "accuracy": [0.6, 0.75]})
        )

        response = api_client.get("/api/simulations/api_run_20250101_120000/all-plot-data")
        assert response.status_code == 200
        data = response.json()
        assert "strategies" in data
        assert len(data["strategies"]) == 2

    def test_get_plot_data_invalid_id(self, api_client: TestClient):
        """Test plot data with invalid simulation ID format."""
        response = api_client.get("/api/simulations/invalid..id/plot-data")
        assert response.status_code == 400


class TestAPIAttackSnapshots:
    """Test attack snapshot retrieval."""

    def test_get_attack_snapshots_no_snapshots(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Test getting attack snapshots when none exist."""
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", out_dir)

        sim_dir = out_dir / "api_run_20250101_120000"
        sim_dir.mkdir()
        (sim_dir / "config.json").write_text(json.dumps({"shared_settings": {}}))

        response = api_client.get("/api/simulations/api_run_20250101_120000/attack-snapshots")
        assert response.status_code == 200
        data = response.json()
        assert data["has_snapshots"] is False
        assert data["strategies"] == []

    def test_get_attack_snapshots_with_data(
        self, api_client: TestClient, tmp_path: Path, monkeypatch
    ):
        """Test getting attack snapshots with data present."""
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        monkeypatch.setattr("intellifl.api.main.OUTPUT_DIR", out_dir)

        sim_dir = out_dir / "api_run_20250101_120000"
        sim_dir.mkdir()
        (sim_dir / "config.json").write_text(json.dumps({"shared_settings": {}}))

        # Create attack snapshot structure
        snapshot_dir = sim_dir / "attack_snapshots_0"
        snapshot_dir.mkdir()
        (snapshot_dir / "summary.json").write_text(
            json.dumps({"attack_types": ["label_flipping"], "total_attacks": 5})
        )

        client_dir = snapshot_dir / "client_0"
        client_dir.mkdir()
        round_dir = client_dir / "round_1"
        round_dir.mkdir()
        (round_dir / "label_flipping_visual.png").write_bytes(b"PNG mock data")
        (round_dir / "label_flipping_metadata.json").write_text(
            json.dumps({"attack_type": "label_flipping", "samples_affected": 10})
        )

        response = api_client.get("/api/simulations/api_run_20250101_120000/attack-snapshots")
        assert response.status_code == 200
        data = response.json()
        assert data["has_snapshots"] is True
        assert len(data["strategies"]) == 1
        assert data["strategies"][0]["strategy_number"] == 0
        assert len(data["strategies"][0]["snapshots"]) == 1
