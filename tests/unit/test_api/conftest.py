"""
Pytest configuration and fixtures for API unit tests.

Provides:
- api_client: FastAPI TestClient fixture
- mock_simulation_dir: Mock simulation directory structure
- patch_output_dir: Helper to properly patch OUTPUT_DIR across all modules
"""

from __future__ import annotations

import json
import sys
import warnings
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from intellifl.api.main import app


@pytest.fixture(autouse=True)
def mock_celery_modules():
    """Mock Celery modules so tests run without Celery installed.

    The simulation_tasks module imports Celery at module level. This fixture
    pre-populates sys.modules with mocks so monkeypatch.setattr works.
    """
    if "celery" in sys.modules:
        # Celery is installed, no mocking needed
        yield
        return

    import intellifl

    # Create mock celery module
    mock_celery = ModuleType("celery")
    mock_celery.Celery = MagicMock()  # type: ignore[attr-defined]
    mock_celery.Task = MagicMock()  # type: ignore[attr-defined]

    # Create mock simulation_tasks module
    mock_tasks = ModuleType("intellifl.tasks.simulation_tasks")
    mock_run_simulation = MagicMock()
    mock_run_simulation.delay = MagicMock(return_value=MagicMock(id="mock-task-id"))
    mock_tasks.run_simulation = mock_run_simulation  # type: ignore[attr-defined]

    # Create mock tasks package and link simulation_tasks
    mock_tasks_pkg = ModuleType("intellifl.tasks")
    mock_tasks_pkg.simulation_tasks = mock_tasks  # type: ignore[attr-defined]

    # Insert into sys.modules
    modules_to_mock = {
        "celery": mock_celery,
        "intellifl.tasks": mock_tasks_pkg,
        "intellifl.tasks.simulation_tasks": mock_tasks,
    }

    original_modules = {k: sys.modules.get(k) for k in modules_to_mock}
    original_intellifl_tasks = getattr(intellifl, "tasks", None)

    for name, mock_module in modules_to_mock.items():
        sys.modules[name] = mock_module

    # Also set as attribute on intellifl module (for monkeypatch attribute resolution)
    intellifl.tasks = mock_tasks_pkg  # type: ignore[attr-defined]

    yield

    # Restore original state
    for name, original in original_modules.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original

    if original_intellifl_tasks is None:
        if hasattr(intellifl, "tasks"):
            delattr(intellifl, "tasks")
    else:
        intellifl.tasks = original_intellifl_tasks  # type: ignore[attr-defined]


@pytest.fixture
def api_client() -> TestClient:
    """Create a FastAPI TestClient for the app."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning, module="httpx")
        return TestClient(app)


@pytest.fixture
def patch_output_dir(monkeypatch) -> Callable[[Path], Path]:
    """Factory fixture to patch OUTPUT_DIR across all API modules.

    The API was refactored to use routers that import OUTPUT_DIR from
    intellifl.api.dependencies. Tests must patch all import locations.

    Usage:
        def test_example(api_client, tmp_path, patch_output_dir):
            out_dir = patch_output_dir(tmp_path / "out")
            # Now all API modules see the patched OUTPUT_DIR
    """

    def _patch(output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        base_dir = output_dir.parent

        # Patch all modules that import OUTPUT_DIR or BASE_DIR
        monkeypatch.setattr("intellifl.api.dependencies.OUTPUT_DIR", output_dir)
        monkeypatch.setattr("intellifl.api.dependencies.BASE_DIR", base_dir)
        monkeypatch.setattr("intellifl.api.routers.simulations.OUTPUT_DIR", output_dir)
        monkeypatch.setattr("intellifl.api.routers.visualizations.OUTPUT_DIR", output_dir)

        return output_dir

    return _patch


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
        "simulation_strategies": [{"strategy_name": "fedavg", "num_malicious_clients": 0}],
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

    monkeypatch.setattr("intellifl.api.dependencies.OUTPUT_DIR", out_dir)
    monkeypatch.setattr("intellifl.api.dependencies.BASE_DIR", tmp_path)
    monkeypatch.setattr("intellifl.api.routers.simulations.OUTPUT_DIR", out_dir)
    monkeypatch.setattr("intellifl.api.routers.simulations.BASE_DIR", tmp_path)
    monkeypatch.setattr("intellifl.api.routers.visualizations.OUTPUT_DIR", out_dir)
    monkeypatch.setattr("intellifl.api.routers.terminal.BASE_DIR", tmp_path)

    return out_dir


@pytest.fixture
def mock_output_with_simulation(
    mock_output_dir: Path, mock_simulation_dir: Path, monkeypatch
) -> Path:
    """
    Fixture combining mock_output_dir with a pre-populated simulation.

    Moves the mock_simulation_dir into mock_output_dir.

    Returns:
        Path to the simulation directory inside mock output
    """
    import shutil

    dest = mock_output_dir / mock_simulation_dir.name
    if not dest.exists():
        shutil.copytree(mock_simulation_dir, dest)

    return dest
