"""Shared dependencies and utilities for the IntelliFL API."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fastapi import HTTPException

# Directory constants
BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "out"

# Shared state for tracking running simulation processes
running_processes: dict[str, subprocess.Popen] = {}

# Patterns for filtering sensitive environment variables
SENSITIVE_ENV_PATTERNS = frozenset(
    {
        "API_KEY",
        "API_SECRET",
        "SECRET",
        "TOKEN",
        "PASSWORD",
        "PASSWD",
        "CREDENTIAL",
        "AUTH",
        "PRIVATE_KEY",
        "AWS_",
        "AZURE_",
        "GCP_",
        "GITHUB_TOKEN",
        "GITLAB_TOKEN",
        "NPM_TOKEN",
        "PYPI_TOKEN",
        "DATABASE_URL",
        "REDIS_URL",
        "MONGODB_URI",
        "DB_PASSWORD",
    }
)


def secure_join(base: Path, *paths: str) -> Path:
    """Safely joins a base directory with other paths to prevent traversal.

    Args:
        base: The base directory path.
        *paths: Variable length argument list of paths to join.

    Returns:
        The resolved safe path.

    Raises:
        HTTPException: If the resulting path is outside the base directory.
    """
    try:
        final_path = (base / Path(*paths)).resolve()
        final_path.relative_to(base.resolve())
        return final_path
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=400, detail="Invalid path specified.")


def get_safe_env() -> dict[str, str]:
    """Returns a filtered copy of environment variables with sensitive data removed.

    Filters out environment variables matching known sensitive patterns like
    API keys, tokens, passwords, and cloud provider credentials.

    Returns:
        A dictionary of environment variables safe to pass to subprocesses.
    """
    safe_env = {}
    for key, value in os.environ.items():
        key_upper = key.upper()
        if any(pattern in key_upper for pattern in SENSITIVE_ENV_PATTERNS):
            continue
        safe_env[key] = value
    return safe_env


def get_simulation_path(simulation_id: str) -> Path:
    """Validates and returns the path for a specific simulation ID.

    Args:
        simulation_id: The unique identifier for the simulation.

    Returns:
        The valid path object for the simulation.

    Raises:
        HTTPException: If the ID is invalid format or the directory does not exist.
    """
    if not all(c.isalnum() or c == "_" for c in simulation_id):
        raise HTTPException(status_code=400, detail="Invalid simulation ID format.")

    sim_path = secure_join(OUTPUT_DIR, simulation_id)

    if not sim_path.is_dir():
        raise HTTPException(status_code=404, detail="Simulation not found.")
    return sim_path
