"""
Pytest configuration and fixtures for API integration tests.

Provides:
- api_client: FastAPI TestClient fixture for integration testing
- patch_output_dir: Helper to properly patch OUTPUT_DIR across all modules
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from intellifl.api.main import app


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
def mock_celery_task():
    """Mock Celery task and connection to prevent Redis connection attempts.

    Mocks both celery_app.connection() (for Redis connectivity check) and
    run_simulation.delay() (for task submission) to allow tests to run
    without requiring Celery/Redis to be available.
    """
    import sys
    from unittest.mock import MagicMock, patch

    mock_task = MagicMock()
    mock_task.id = "test-celery-task-id-12345"

    # Create mock connection that passes the Redis connectivity check
    mock_connection = MagicMock()
    mock_connection.ensure_connection = MagicMock(return_value=None)
    mock_connection.close = MagicMock()

    # Create mock celery app
    mock_celery_app = MagicMock()
    mock_celery_app.connection.return_value = mock_connection
    mock_celery_app.conf.broker_url = "redis://localhost:6379/0"

    # Create mock module structure for intellifl.tasks.simulation_tasks
    mock_run_simulation = MagicMock()
    mock_run_simulation.delay.return_value = mock_task

    mock_simulation_tasks = MagicMock()
    mock_simulation_tasks.run_simulation = mock_run_simulation

    mock_tasks = MagicMock()
    mock_tasks.simulation_tasks = mock_simulation_tasks

    # Create mock celery_app module
    mock_celery_app_module = MagicMock()
    mock_celery_app_module.app = mock_celery_app

    # Create mock AsyncResult that returns PENDING state (task is alive)
    mock_async_result = MagicMock()
    mock_async_result.state = "PENDING"

    mock_celery_result = MagicMock()
    mock_celery_result.AsyncResult.return_value = mock_async_result

    # Patch the modules in sys.modules before they get imported
    with patch.dict(
        sys.modules,
        {
            "intellifl.celery_app": mock_celery_app_module,
            "intellifl.tasks": mock_tasks,
            "intellifl.tasks.simulation_tasks": mock_simulation_tasks,
            "celery.result": mock_celery_result,
        },
    ):
        yield mock_run_simulation
