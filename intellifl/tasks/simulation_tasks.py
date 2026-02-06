"""Celery tasks for simulation execution."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from intellifl.celery_app import app


@app.task(bind=True, name="run_simulation")
def run_simulation(self, config_path: str) -> dict[str, str]:
    """Execute a simulation as a Celery task.

    The simulation_runner's StatusTracker handles all status.json updates
    (queued -> running -> round progress -> completed/failed).
    This task just runs the subprocess and captures output to output.log.

    Args:
        config_path: Absolute path to the simulation config.json

    Returns:
        Dict with status and simulation_id

    Raises:
        RuntimeError: If simulation exits with non-zero code
    """
    config_path_obj = Path(config_path)
    sim_dir = config_path_obj.parent
    log_path = sim_dir / "output.log"

    with log_path.open("a") as log:
        result = subprocess.run(
            [sys.executable, "-m", "intellifl.simulation_runner", config_path, "--origin", "api"],
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=Path(__file__).resolve().parents[2],  # project root
            check=False,
        )

    if result.returncode == 0:
        return {"status": "completed", "simulation_id": sim_dir.name}

    raise RuntimeError(f"Simulation {sim_dir.name} failed: exit code {result.returncode}")
