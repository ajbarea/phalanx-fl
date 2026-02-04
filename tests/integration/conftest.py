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
