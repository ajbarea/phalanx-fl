"""
Pytest configuration and fixtures for API unit tests.

Provides:
- api_client: FastAPI TestClient fixture
- mock_simulation_dir: Mock simulation directory structure
"""

import json
import warnings
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def api_client() -> TestClient:
    """Create a FastAPI TestClient for the app."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning, module="httpx")
        return TestClient(app)


@pytest.fixture
def mock_simulation_dir(tmp_path: Path) -> Path:
    """
    Create a mock simulation directory structure for testing.

    Creates a simulation directory with:
    - config.json with valid simulation configuration
    - metrics.csv with sample metrics data
    - plot_data_0.json with sample plot data
    - accuracy_plot.pdf (empty file for testing)
    """
    sim_dir = tmp_path / "api_run_20250107_120000"
    sim_dir.mkdir(parents=True)

    config = {
        "shared_settings": {
            "aggregation_strategy_keyword": "fedavg",
            "num_of_rounds": 5,
            "num_of_clients": 3,
            "dataset_keyword": "bloodmnist",
            "fraction_fit": 1.0,
            "local_epochs": 1,
            "learning_rate": 0.01,
            "batch_size": 32,
        },
        "simulation_strategies": [
            {"strategy_name": "fedavg", "num_malicious_clients": 0}
        ],
    }
    (sim_dir / "config.json").write_text(json.dumps(config, indent=2))

    metrics_csv = """round,accuracy,loss
    1,0.85,0.6
    2,0.90,0.4
    """
    (sim_dir / "metrics.csv").write_text(metrics_csv)

    plot_data = {
        "rounds": [1, 2, 3],
        "accuracy": [0.75, 0.80, 0.85],
        "loss": [0.8, 0.6, 0.4],
    }
    (sim_dir / "plot_data_0.json").write_text(json.dumps(plot_data, indent=2))

    (sim_dir / "accuracy_plot.pdf").write_bytes(b"%PDF-1.4\n%mock pdf content")

    return sim_dir


@pytest.fixture
def mock_output_dir(tmp_path: Path, monkeypatch) -> Path:
    """
    Fixture for API tests requiring OUTPUT_DIR and BASE_DIR mocking.

    Returns:
        Path to the mock output directory
    """
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("src.api.main.OUTPUT_DIR", out_dir)
    monkeypatch.setattr("src.api.main.BASE_DIR", tmp_path)

    return out_dir


@pytest.fixture
def mock_output_with_simulation(
    mock_output_dir: Path, mock_simulation_dir: Path, monkeypatch
) -> Path:
    """
    Fixture combining mock_output_dir with a pre-populated simulation.

    Moves the mock_simulation_dir into mock_output_dir and patches OUTPUT_DIR
    to point to the parent containing the simulation.

    Returns:
        Path to the simulation directory inside mock output
    """
    import shutil

    # Move simulation into output dir
    dest = mock_output_dir / mock_simulation_dir.name
    if not dest.exists():
        shutil.copytree(mock_simulation_dir, dest)

    # Re-patch to parent of simulation
    monkeypatch.setattr("src.api.main.OUTPUT_DIR", mock_output_dir)

    return dest
