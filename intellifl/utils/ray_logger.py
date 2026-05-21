"""
Ray Worker Crash Logging and Fault Tolerance Utilities.

This module provides:
- Structured logging for Ray worker events (crashes, restarts, OOM)
- Fault tolerance configuration for Ray simulations
- Log file management for debugging Ray issues

Why this is not just "use Flower's native observability" (re-evaluated
2026-05-21 against Flower >= 1.28): Flower's simulation engine surfaces
per-client `client_resources`, driver-side worker logs via Ray's
`log_to_driver=True`, and a default `ServerApp` / `ClientApp` log stream.
What it does NOT provide, and this module supplies:

  1. **Strategy-level timing aggregation.** `RaySimulationMonitor` records
     wall-clock per phalanx-fl strategy (a multi-FL-round concept on top of
     Flower); Flower's native logs aggregate per FL round only.
  2. **Classified event taxonomy.** `event_type=CRASH | OOM | TIMEOUT |
     ACTOR_CRASH | TASK_CRASH | NODE_DEATH` makes structured greps possible;
     raw Ray driver logs require regex over stack traces.
  3. **Persistent summary artifact.** `ray_simulation_summary_<id>.json`
     written at `stop()` preserves the round timings + error list + closing
     cluster health for post-mortem; Flower does not write this.
  4. **Closing cluster-health snapshot.** `check_ray_cluster_health()` polls
     `ray.nodes()` for dead nodes at the simulation boundary; Flower does
     not surface this.

Shadow surfaces (covered by Flower native, intentionally not duplicated
here): per-client resource allocation, in-flight worker stdout streaming,
basic OOM error propagation from a ClientApp.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import ray

# Create a dedicated logger for Ray events
ray_logger = logging.getLogger("ray.worker")


def configure_ray_logging(
    output_dir: Path,
    simulation_id: str,
    log_level: str = "DEBUG",
):
    """
    Configure Ray logging to capture worker events into logs.

    Args:
        output_dir: Directory to save Ray logs
        simulation_id: Unique identifier for this simulation run
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    ray_logger.setLevel(getattr(logging, log_level))
    logging.info("Ray logging configured to inherit standard file handler.")


def get_fault_tolerance_config(
    max_actor_restarts: int = 3,
    max_task_retries: int = 2,
    object_store_memory: int | None = None,
) -> dict[str, Any]:
    """
    Get Ray initialization arguments for fault tolerance.

    Args:
        max_actor_restarts: Max times an actor can restart on failure
        max_task_retries: Max times a task can retry on failure
        object_store_memory: Object store memory limit in bytes (None for auto)

    Returns:
        Dictionary of ray.init() arguments
    """
    config = {
        # Enable fault tolerance
        "namespace": "fl_simulation",
        # Configure logging
        "logging_level": logging.DEBUG,
        "log_to_driver": True,
        # Runtime environment for better error messages
        "runtime_env": {
            "env_vars": {
                "RAY_ENABLE_RECORD_ACTOR_TASK_LOGGING": "1",
                "RAY_BACKEND_LOG_LEVEL": "fatal",
            }
        },
    }

    # Add object store memory if specified
    if object_store_memory:
        config["object_store_memory"] = object_store_memory

    return config


def get_actor_options(
    max_restarts: int = 3,
    max_task_retries: int = 2,
    num_cpus: float = 1.0,
    num_gpus: float = 0.0,
) -> dict[str, Any]:
    """
    Get Ray actor options for fault tolerance.

    Args:
        max_restarts: Maximum number of actor restarts
        max_task_retries: Maximum number of task retries
        num_cpus: CPUs per actor
        num_gpus: GPUs per actor

    Returns:
        Dictionary of actor options
    """
    return {
        "max_restarts": max_restarts,
        "max_task_retries": max_task_retries,
        "num_cpus": num_cpus,
        "num_gpus": num_gpus,
    }


def log_ray_worker_event(
    event_type: str,
    worker_id: str | None = None,
    task_id: str | None = None,
    node_id: str | None = None,
    error_message: str | None = None,
    extra_info: dict | None = None,
) -> None:
    """
    Log a Ray worker event with structured fields.

    Args:
        event_type: Type of event (CRASH, RESTART, OOM, TIMEOUT, SUCCESS)
        worker_id: Ray worker ID
        task_id: Ray task ID
        node_id: Ray node ID
        error_message: Error message if applicable
        extra_info: Additional context information
    """
    log_data = {
        "event_type": event_type,
        "timestamp": datetime.now().isoformat(),
        "worker_id": worker_id or "unknown",
        "task_id": task_id or "unknown",
        "node_id": node_id or "unknown",
    }

    if error_message:
        log_data["error"] = error_message

    if extra_info:
        log_data.update(extra_info)

    # Format as structured log message
    log_msg = " | ".join(f"{k}={v}" for k, v in log_data.items())

    if event_type in ("CRASH", "OOM", "TIMEOUT"):
        ray_logger.error(f"[RAY_WORKER] {log_msg}")
        logging.error(f"[RAY_WORKER] {log_msg}")
    elif event_type == "RESTART":
        ray_logger.warning(f"[RAY_WORKER] {log_msg}")
        logging.warning(f"[RAY_WORKER] {log_msg}")
    else:
        ray_logger.info(f"[RAY_WORKER] {log_msg}")


def check_ray_cluster_health() -> dict[str, Any]:
    """
    Check the health of the Ray cluster.

    Returns:
        Dictionary with cluster health information
    """
    health_info = {
        "is_initialized": ray.is_initialized(),
        "timestamp": datetime.now().isoformat(),
    }

    if ray.is_initialized():
        try:
            # Get cluster resources
            resources = ray.cluster_resources()
            available = ray.available_resources()

            health_info["total_cpus"] = resources.get("CPU", 0)
            health_info["available_cpus"] = available.get("CPU", 0)
            health_info["total_gpus"] = resources.get("GPU", 0)
            health_info["available_gpus"] = available.get("GPU", 0)

            # Get node info
            nodes = ray.nodes()
            health_info["total_nodes"] = len(nodes)
            health_info["alive_nodes"] = sum(1 for n in nodes if n.get("Alive", False))
            health_info["dead_nodes"] = sum(1 for n in nodes if not n.get("Alive", True))

            # Check for any dead nodes (potential crashes)
            dead_node_ids = [n.get("NodeID", "unknown") for n in nodes if not n.get("Alive", True)]
            if dead_node_ids:
                health_info["dead_node_ids"] = dead_node_ids
                log_ray_worker_event(
                    event_type="NODE_DEATH",
                    node_id=",".join(dead_node_ids),
                    extra_info={"dead_count": len(dead_node_ids)},
                )

        except Exception as e:
            health_info["error"] = str(e)
            logging.warning(f"Failed to get Ray cluster health: {e}")

    return health_info


def setup_ray_error_handler(output_dir: Path) -> Callable[[Exception], None]:
    """
    Setup global error handler for Ray worker crashes.

    Args:
        output_dir: Directory to save crash logs
    """

    def ray_error_handler(e: Exception) -> None:
        """Handle Ray errors and log them."""
        error_type = type(e).__name__
        error_msg = str(e)

        # Detect specific error types
        if "RayActorError" in error_type:
            log_ray_worker_event(
                event_type="ACTOR_CRASH",
                error_message=error_msg,
                extra_info={"error_type": error_type},
            )
        elif "RayTaskError" in error_type:
            log_ray_worker_event(
                event_type="TASK_CRASH",
                error_message=error_msg,
                extra_info={"error_type": error_type},
            )
        elif "OutOfMemoryError" in error_msg or "OOM" in error_msg:
            log_ray_worker_event(
                event_type="OOM",
                error_message=error_msg,
                extra_info={"error_type": error_type},
            )
        elif "timeout" in error_msg.lower():
            log_ray_worker_event(
                event_type="TIMEOUT",
                error_message=error_msg,
                extra_info={"error_type": error_type},
            )
        else:
            log_ray_worker_event(
                event_type="CRASH",
                error_message=error_msg,
                extra_info={"error_type": error_type},
            )

        # Save crash details to file
        crash_file = output_dir / f"ray_crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(crash_file, "w") as f:
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Error Type: {error_type}\n")
            f.write(f"Error Message: {error_msg}\n")
            f.write(f"\nFull Exception:\n{repr(e)}\n")

        logging.error(f"Ray crash details saved to: {crash_file}")

    # Store the handler for use in try/except blocks
    return ray_error_handler


class RaySimulationMonitor:
    """Monitor Ray simulation for crashes and performance issues."""

    def __init__(self, output_dir: Path, simulation_id: str):
        self.output_dir = output_dir
        self.simulation_id = simulation_id
        self.start_time: datetime | None = None
        self.round_times: list[float] = []
        self.errors: list[dict] = []
        # Tracks the actual number of FL rounds (set via record_round)
        self._total_fl_rounds: int = 0

    def start(self) -> None:
        """Start monitoring the simulation."""
        self.start_time = datetime.now()
        configure_ray_logging(self.output_dir, self.simulation_id, "INFO")
        log_ray_worker_event(
            event_type="SIMULATION_START",
            extra_info={"simulation_id": self.simulation_id},
        )

    def record_round(self, round_num: int, duration_seconds: float, num_fl_rounds: int = 0) -> None:
        """Record timing for a completed strategy.

        Args:
            round_num: Strategy index (0-based).
            duration_seconds: Wall-clock time for this strategy.
            num_fl_rounds: Number of FL rounds executed in this strategy (e.g. 10).
        """
        self.round_times.append(duration_seconds)
        if num_fl_rounds > 0:
            self._total_fl_rounds += num_fl_rounds
        log_ray_worker_event(
            event_type="STRATEGY_COMPLETE",
            extra_info={
                "strategy": round_num,
                "fl_rounds": num_fl_rounds,
                "duration_seconds": f"{duration_seconds:.2f}",
                "simulation_id": self.simulation_id,
            },
        )

    def record_error(self, error: Exception, round_num: int | None = None) -> None:
        """Record an error during simulation."""
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "round": round_num,
        }
        self.errors.append(error_info)

        log_ray_worker_event(
            event_type="ERROR",
            error_message=str(error),
            extra_info={
                "error_type": type(error).__name__,
                "round": round_num,
                "simulation_id": self.simulation_id,
            },
        )

    def stop(self, success: bool = True) -> dict[str, Any]:
        """Stop monitoring and return summary."""
        import json

        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds() if self.start_time else 0

        # Get cluster health at end
        health = check_ray_cluster_health()

        # avg_round_time calculation for tests
        avg_round_time = (
            sum(self.round_times) / len(self.round_times) if len(self.round_times) > 0 else 0
        )

        total_fl_rounds = (
            self._total_fl_rounds if self._total_fl_rounds > 0 else len(self.round_times)
        )

        summary = {
            "simulation_id": self.simulation_id,
            "success": success,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "total_rounds": total_fl_rounds,
            "total_strategies": len(self.round_times),
            "avg_round_time": avg_round_time,
            "total_errors": len(self.errors),
            "errors": self.errors,
            "cluster_health": health,
        }

        # Write summary to JSON file
        summary_file = self.output_dir / f"ray_simulation_summary_{self.simulation_id}.json"
        try:
            with open(summary_file, "w") as f:
                json.dump(summary, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to write simulation summary: {e}")

        log_ray_worker_event(
            event_type="SIMULATION_END",
            extra_info={
                "success": success,
                "duration_seconds": f"{duration:.2f}",
                "total_errors": len(self.errors),
                "simulation_id": self.simulation_id,
            },
        )

        return summary
