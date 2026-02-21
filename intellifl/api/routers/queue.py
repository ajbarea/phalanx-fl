"""Queue status router for aggregate queue monitoring."""

from __future__ import annotations

import datetime
import json
import logging
from contextlib import suppress
from datetime import timezone
from pathlib import Path
from typing import Literal

import psutil
from fastapi import APIRouter
from pydantic import BaseModel

from intellifl.api.dependencies import OUTPUT_DIR

logger = logging.getLogger(__name__)

router = APIRouter(tags=["queue"])


class QueueStatusResponse(BaseModel):
    """Aggregate queue status counts."""

    queued: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    stopped: int = 0
    total: int = 0
    is_empty: bool = True


ValidStatus = Literal["queued", "pending", "running", "completed", "failed", "stopped"]

# How recently status.json must have been updated to trust the file-based
# status without performing PID / Celery liveness checks.
_STATUS_FRESHNESS_SECONDS = 120


def _status_is_fresh(data: dict) -> bool:
    """Return True if status.json was updated recently enough to trust."""
    updated_at = data.get("updated_at")
    if not updated_at:
        return False
    try:
        ts = datetime.datetime.fromisoformat(updated_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (datetime.datetime.now(timezone.utc) - ts).total_seconds()
        return age < _STATUS_FRESHNESS_SECONDS
    except (ValueError, TypeError):
        return False


def _read_simulation_status(sim_dir: Path) -> ValidStatus:
    """Read status from a simulation directory, reporting orphaned tasks as failed."""
    if (sim_dir / ".stopped").is_file():
        return "stopped"

    status_path = sim_dir / "status.json"
    if status_path.is_file():
        try:
            with status_path.open() as f:
                data = json.load(f)
            raw = data.get("status", "pending")
            if raw in ("queued", "pending", "running", "completed", "failed", "stopped"):
                if raw in ("queued", "running"):
                    result_files = list(sim_dir.glob("*.pdf")) + list(sim_dir.glob("csv/*.csv"))
                    if result_files:
                        return "completed"

                    # If the status file was recently written, trust it without
                    # performing PID / Celery liveness checks.  This prevents
                    # CLI-originated runs from being incorrectly reported as
                    # failed due to psutil namespace mismatches on Windows.
                    if _status_is_fresh(data):
                        return raw  # type: ignore[return-value]

                    celery_task_id = data.get("celery_task_id")
                    pid = data.get("pid")
                    if celery_task_id:
                        # PID belongs to the worker container — use AsyncResult instead
                        task_alive = False
                        with suppress(Exception):
                            from celery.result import AsyncResult

                            from intellifl.celery_app import app as celery_app

                            result = AsyncResult(celery_task_id, app=celery_app)
                            task_alive = result.state in (
                                "PENDING",
                                "STARTED",
                                "RETRY",
                                "RECEIVED",
                            )
                        if not task_alive:
                            return "failed"
                    elif pid:
                        # Subprocess mode: PID is in the same namespace — safe to check
                        process_alive = False
                        with suppress(Exception):
                            process_alive = psutil.pid_exists(pid)
                        if not process_alive:
                            return "failed"

                return raw  # type: ignore[return-value]
        except (OSError, json.JSONDecodeError):
            pass

    result_files = list(sim_dir.glob("*.pdf")) + list(sim_dir.glob("csv/*.csv"))
    if result_files:
        return "completed"

    # Only treat output.log as a failure if it contains error-level messages.
    # CLI simulations write routine INFO/WARNING output to this file.
    log_path = sim_dir / "output.log"
    if log_path.is_file():
        try:
            with log_path.open("r") as f:
                log_content = f.read(4096)
            if log_content.strip():
                has_error_markers = any(
                    marker in log_content
                    for marker in [
                        "ERROR:",
                        "CRITICAL:",
                        "Traceback (most recent call last)",
                        "Exception:",
                        "Simulation failed",
                    ]
                )
                if has_error_markers:
                    return "failed"
                return "pending"
        except OSError:
            pass

    return "pending"


@router.get("/api/queue/status", response_model=QueueStatusResponse)
def get_queue_status() -> QueueStatusResponse:
    """Return aggregate status counts across all simulations."""
    counts: dict[str, int] = {
        "queued": 0,
        "pending": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "stopped": 0,
    }

    if not OUTPUT_DIR.is_dir():
        return QueueStatusResponse(is_empty=True)

    for sim_dir in OUTPUT_DIR.iterdir():
        if not sim_dir.is_dir():
            continue
        if not (sim_dir / "config.json").is_file():
            continue

        status = _read_simulation_status(sim_dir)
        counts[status] = counts.get(status, 0) + 1

    total = sum(counts.values())
    is_empty = counts["queued"] == 0 and counts["running"] == 0

    return QueueStatusResponse(
        queued=counts["queued"],
        pending=counts["pending"],
        running=counts["running"],
        completed=counts["completed"],
        failed=counts["failed"],
        stopped=counts["stopped"],
        total=total,
        is_empty=is_empty,
    )
