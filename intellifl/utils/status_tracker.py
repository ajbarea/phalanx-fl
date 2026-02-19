"""Status tracking for federated learning simulations.

This module provides a StatusTracker class that writes simulation progress
to a status.json file for real-time progress monitoring from the API.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path


class StatusTracker:
    """Tracks simulation status and progress via status.json file.

    This file contains rich metadata including current round, total rounds,
    current strategy, total strategies, progress percentage, and process ID.

    Attributes:
        status_file: Path to the status.json file
        total_rounds: Total number of rounds in the simulation
        total_strategies: Total number of strategies to execute
        current_strategy: Current strategy index (0-based)
    """

    def __init__(
        self,
        output_dir: Path,
        total_rounds: int,
        total_strategies: int = 1,
        origin: str | None = None,
    ):
        """Initialize the status tracker.

        Args:
            output_dir: Directory where status.json will be written
            total_rounds: Total number of rounds per strategy
            total_strategies: Total number of strategies to execute
            origin: Optional string to indicate run origin (e.g., 'api', 'cli')
        """
        self.status_file = Path(output_dir) / "status.json"
        self.total_rounds = total_rounds
        self.total_strategies = total_strategies
        self.current_strategy = 0
        self.current_round = 0
        self.started_at: str | None = None
        self._pid = os.getpid()
        self.origin = origin

    def _write_status(self, status_data: dict) -> None:
        """Write status data to status.json atomically.

        Args:
            status_data: Dictionary containing status information
        """
        try:
            # Carry over fields we don't own (e.g. celery_task_id written by the API)
            if self.status_file.exists():
                try:
                    with self.status_file.open() as f:
                        existing = json.load(f)
                    for key, value in existing.items():
                        if key not in status_data:
                            status_data[key] = value
                except (OSError, json.JSONDecodeError):
                    pass

            # Add timestamp
            status_data["updated_at"] = datetime.now(timezone.utc).isoformat()

            # Add origin if set
            if self.origin is not None:
                status_data["origin"] = self.origin

            # Write to temp file first, then rename for atomicity
            temp_file = self.status_file.with_suffix(".json.tmp")
            with temp_file.open("w") as f:
                json.dump(status_data, f, indent=2)
            temp_file.replace(self.status_file)

            logging.debug(f"Status updated: {status_data}")
        except Exception as e:
            logging.warning(f"Could not write status file: {e}")

    def _calculate_progress(self) -> float:
        """Calculate overall progress as a fraction between 0 and 1.

        Progress accounts for both strategy and round completion.

        Returns:
            Progress as a float between 0.0 and 1.0
        """
        if self.total_strategies == 0 or self.total_rounds == 0:
            return 0.0

        # Progress within current strategy
        strategy_progress = self.current_round / self.total_rounds

        # Overall progress across all strategies
        completed_strategies = self.current_strategy
        overall_progress = (completed_strategies + strategy_progress) / self.total_strategies

        return min(overall_progress, 1.0)

    def queue(self) -> None:
        """Mark the simulation as queued and waiting for hardware resources."""
        self._write_status(
            {
                "status": "queued",
                "current_round": 0,
                "total_rounds": self.total_rounds,
                "current_strategy": self.current_strategy,
                "total_strategies": self.total_strategies,
                "progress": 0.0,
                "pid": self._pid,
            }
        )

    def set_origin(self, origin: str) -> None:
        """Set the origin for this tracker and update status file."""
        self.origin = origin
        # Optionally update the status file immediately
        if self.status_file.exists():
            try:
                with self.status_file.open("r") as f:
                    status_data = json.load(f)
                status_data["origin"] = origin
                self._write_status(status_data)
            except Exception:
                pass

    def start(self) -> None:
        """Mark the simulation as started.

        Creates initial status.json with running status and zero progress.
        """
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.current_round = 0
        self.current_strategy = 0

        self._write_status(
            {
                "status": "running",
                "started_at": self.started_at,
                "current_round": 0,
                "total_rounds": self.total_rounds,
                "current_strategy": self.current_strategy,
                "total_strategies": self.total_strategies,
                "progress": 0.0,
                "pid": self._pid,
            }
        )

    def update_round(self, current_round: int) -> None:
        """Update the current round number.

        Called by aggregation strategies at the end of each round.

        Args:
            current_round: The round number that just completed (1-indexed)
        """
        self.current_round = current_round

        self._write_status(
            {
                "status": "running",
                "started_at": self.started_at,
                "current_round": current_round,
                "total_rounds": self.total_rounds,
                "current_strategy": self.current_strategy,
                "total_strategies": self.total_strategies,
                "progress": self._calculate_progress(),
                "pid": self._pid,
            }
        )

    def next_strategy(self) -> None:
        """Move to the next strategy in a multi-strategy run.

        Increments the current_strategy counter and resets round to 0.
        """
        self.current_strategy += 1
        self.current_round = 0

        self._write_status(
            {
                "status": "running",
                "started_at": self.started_at,
                "current_round": 0,
                "total_rounds": self.total_rounds,
                "current_strategy": self.current_strategy,
                "total_strategies": self.total_strategies,
                "progress": self._calculate_progress(),
                "pid": self._pid,
            }
        )

    def complete(self) -> None:
        """Mark the simulation as completed successfully.

        Sets status to 'completed' and progress to 1.0.
        """
        self._write_status(
            {
                "status": "completed",
                "started_at": self.started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "total_rounds": self.total_rounds,
                "total_strategies": self.total_strategies,
                "progress": 1.0,
            }
        )

    def fail(self, error: str | None = None) -> None:
        """Mark the simulation as failed.

        Args:
            error: Optional error message describing the failure
        """
        status_data = {
            "status": "failed",
            "started_at": self.started_at,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "current_strategy": self.current_strategy,
            "total_strategies": self.total_strategies,
            "progress": self._calculate_progress(),
        }
        if error:
            status_data["error"] = error

        self._write_status(status_data)

    def stop(self) -> None:
        """Mark the simulation as stopped (user-initiated).

        Sets status to 'stopped' with current progress preserved.
        """
        self._write_status(
            {
                "status": "stopped",
                "started_at": self.started_at,
                "stopped_at": datetime.now(timezone.utc).isoformat(),
                "current_round": self.current_round,
                "total_rounds": self.total_rounds,
                "current_strategy": self.current_strategy,
                "total_strategies": self.total_strategies,
                "progress": self._calculate_progress(),
            }
        )
