"""Celery tasks for simulation execution."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from celery import Task

from intellifl.celery_app import app


class SimulationTask(Task):
    """Base task with automatic status.json updates."""

    def on_failure(
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any
    ) -> None:
        """Update status.json when task fails."""
        if args:
            config_path = Path(args[0])
            _update_status(config_path.parent / "status.json", "failed", error=str(exc))

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        """Update status.json when task completes."""
        if args:
            config_path = Path(args[0])
            _update_status(config_path.parent / "status.json", "completed")


@app.task(bind=True, base=SimulationTask, name="run_simulation")
def run_simulation(self: Task, config_path: str) -> dict[str, str]:
    """Execute a simulation as a Celery task.

    Args:
        config_path: Absolute path to the simulation config.json

    Returns:
        Dict with status and simulation_id

    Raises:
        RuntimeError: If simulation exits with non-zero code
    """
    config_path_obj = Path(config_path)
    sim_dir = config_path_obj.parent
    status_path = sim_dir / "status.json"
    log_path = sim_dir / "execution.log"

    # Update status to running with Celery task ID
    _update_status(status_path, "running", task_id=self.request.id)

    # Run simulation - blocking call, stdout/stderr to log file
    with log_path.open("a") as log:
        result = subprocess.run(
            [sys.executable, "-m", "intellifl.simulation_runner", config_path],
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=Path(__file__).resolve().parents[2],  # project root
            check=False,
        )

    if result.returncode == 0:
        return {"status": "completed", "simulation_id": sim_dir.name}

    error_msg = f"Exit code: {result.returncode}"
    _update_status(status_path, "failed", error=error_msg)
    raise RuntimeError(f"Simulation {sim_dir.name} failed: {error_msg}")


def _update_status(
    status_path: Path,
    status: str,
    task_id: str | None = None,
    error: str | None = None,
) -> None:
    """Atomically update status.json with new status and metadata."""
    import tempfile

    data: dict[str, Any] = {}
    if status_path.exists():
        with status_path.open() as f:
            data = json.load(f)

    data["status"] = status
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    if task_id:
        data["celery_task_id"] = task_id
    if error:
        data["error"] = error

    # Write to temp file, then atomic rename (POSIX) / near-atomic (Windows)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=status_path.parent, delete=False, suffix=".tmp"
    ) as tmp:
        json.dump(data, tmp, indent=2)
        tmp_path = Path(tmp.name)
    tmp_path.replace(status_path)
