"""Queue status router for aggregate queue monitoring."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

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


def _read_simulation_status(sim_dir: Path) -> ValidStatus:
    """Read status from a simulation directory.

    Fallback logic mirrors _get_status_data in simulations.py but simplified
    for aggregate counting (no PID checks).

    Returns:
        Status string or 'pending' as fallback.
    """
    if (sim_dir / ".stopped").is_file():
        return "stopped"

    status_path = sim_dir / "status.json"
    if status_path.is_file():
        try:
            with status_path.open() as f:
                data = json.load(f)
            raw = data.get("status", "pending")
            if raw in ("queued", "pending", "running", "completed", "failed", "stopped"):
                return raw  # type: ignore[return-value]
        except (OSError, json.JSONDecodeError):
            pass

    result_files = list(sim_dir.glob("*.pdf")) + list(sim_dir.glob("csv/*.csv"))
    if result_files:
        return "completed"

    if (sim_dir / "output.log").is_file():
        return "failed"

    return "pending"


@router.get("/api/queue/status", response_model=QueueStatusResponse)
def get_queue_status() -> QueueStatusResponse:
    """Get aggregate status counts for all simulations.

    Returns counts for each status type plus a boolean indicating
    if the queue is empty (no running or queued simulations).
    """
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
