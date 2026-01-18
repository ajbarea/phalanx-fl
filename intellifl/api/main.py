from __future__ import annotations

from intellifl.utils.warnings_config import (
    apply_env_vars,
    configure_warnings,
    get_subprocess_env_vars,
)

apply_env_vars()

import asyncio
import concurrent.futures
import datetime
import json
import logging
import multiprocessing
import os
import re
import shutil
import struct
import subprocess
import sys
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

configure_warnings()

if sys.platform == "win32":
    import winpty
else:
    import fcntl
    import pty
    import select
    import termios

import pandas as pd
import psutil
from fastapi import (
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from datasets import load_dataset_builder  # type: ignore[attr-defined]
from intellifl.api.models import (
    AllPlotDataResponse,
    AttackSnapshotsResponse,
    CreateSimulationRequest,
    DatasetInfo,
    DatasetValidationResponse,
    SimulationStatusResponse,
    StrategyPlotData,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles the application lifespan events (startup and shutdown)."""
    logger.info("Federated Learning API initialized")
    yield


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        "http://localhost:5177",
        "http://127.0.0.1:5177",
        "http://localhost:5178",
        "http://127.0.0.1:5178",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "out"

running_processes: dict[str, subprocess.Popen] = {}


class SimulationMetadata(BaseModel):
    simulation_id: str
    display_name: str | None = None
    strategy_name: str
    num_of_rounds: int | str
    num_of_clients: int | str
    created_at: str | None = None


class SimulationDetails(BaseModel):
    config: dict[str, Any]
    result_files: list[str]
    status: str
    progress: float = 0.0
    current_round: int | None = None
    total_rounds: int | None = None
    current_strategy: int | None = None
    total_strategies: int | None = None


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


# Patterns for sensitive environment variables to filter out
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


def get_safe_env() -> dict:
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
    # Security: Validate that ID contains only alphanumeric chars and underscores
    # Prevents path traversal attacks like "api_run_../../etc/passwd"
    if not all(c.isalnum() or c == "_" for c in simulation_id):
        raise HTTPException(status_code=400, detail="Invalid simulation ID format.")

    sim_path = secure_join(OUTPUT_DIR, simulation_id)

    if not sim_path.is_dir():
        raise HTTPException(status_code=404, detail="Simulation not found.")
    return sim_path


@app.get("/api/simulations", response_model=list[SimulationMetadata])
def get_simulations() -> list[SimulationMetadata]:
    """Retrieves metadata for all available simulation runs.

    Returns:
        A list of SimulationMetadata objects sorted by creation time.
    """
    simulations = []
    if not OUTPUT_DIR.is_dir():
        return []

    for sim_dir in OUTPUT_DIR.iterdir():
        if sim_dir.is_dir():
            config_path = sim_dir / "config.json"
            if config_path.is_file():
                try:
                    with config_path.open("r") as f:
                        config = json.load(f)

                    settings = config.get("shared_settings", config)

                    created_at = datetime.datetime.fromtimestamp(
                        sim_dir.stat().st_ctime
                    ).isoformat()

                    simulations.append(
                        SimulationMetadata(
                            simulation_id=sim_dir.name,
                            display_name=settings.get("display_name"),
                            strategy_name=settings.get("aggregation_strategy_keyword", "Unknown"),
                            num_of_rounds=settings.get("num_of_rounds", "N/A"),
                            num_of_clients=settings.get("num_of_clients", "N/A"),
                            created_at=created_at,
                        )
                    )
                except (OSError, json.JSONDecodeError) as e:
                    logger.warning(f"Could not read or parse config for {sim_dir.name}: {e}")
                    continue
    return sorted(simulations, key=lambda s: s.simulation_id, reverse=True)


@app.get("/api/simulations/{simulation_id}", response_model=SimulationDetails)
def get_simulation_details(
    sim_path: Path = Depends(get_simulation_path), simulation_id: str = ""
) -> SimulationDetails:
    """Retrieves configuration and result files for a specific simulation.

    Args:
        sim_path: The validated path to the simulation directory.
        simulation_id: The simulation identifier.

    Returns:
        A SimulationDetails object containing config, results, and status.

    Raises:
        HTTPException: If the configuration file cannot be read.
    """
    config_path = sim_path / "config.json"
    if not config_path.is_file():
        raise HTTPException(status_code=404, detail="Simulation config.json not found.")

    try:
        with config_path.open("r") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=500, detail="Could not read simulation config.")

    result_files = []
    for item in sim_path.rglob("*"):
        if (
            item.is_file()
            and item.name != "config.json"
            and item.suffix in [".png", ".pdf", ".csv", ".json", ".html", ".txt"]
        ):
            rel_path = item.relative_to(sim_path)
            rel_path_str = str(rel_path).replace("\\", "/")
            if not rel_path_str.startswith("dataset_"):
                result_files.append(rel_path_str)

    status_info = _get_status_data(sim_path, simulation_id)

    return SimulationDetails(
        config=config,
        result_files=result_files,
        status=status_info["status"],
        progress=status_info.get("progress", 0.0),
        current_round=status_info.get("current_round"),
        total_rounds=status_info.get("total_rounds"),
        current_strategy=status_info.get("current_strategy"),
        total_strategies=status_info.get("total_strategies"),
    )


@app.get(
    "/api/simulations/{simulation_id}/results/{result_filename:path}",
    response_model=None,
)
def get_result_file(
    result_filename: str,
    sim_path: Path = Depends(get_simulation_path),
    download: bool = False,
) -> FileResponse | JSONResponse:
    """Retrieves a specific result file from a simulation.

    Args:
        result_filename: The name of the file to retrieve.
        sim_path: The validated path to the simulation directory.
        download: Whether to trigger a file download for CSVs.

    Returns:
        A FileResponse or JSONResponse containing the file data.

    Raises:
        HTTPException: If the file type is unsupported or file is missing.
    """
    if not result_filename.endswith((".png", ".pdf", ".csv", ".json", ".html", ".txt")):
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    file_path = secure_join(sim_path, result_filename)

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Result file not found.")

    if result_filename.endswith(".csv"):
        if download:
            filename = Path(result_filename).name
            return FileResponse(
                file_path,
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        try:
            df = pd.read_csv(file_path, encoding="latin-1")
            return JSONResponse(content=df.to_dict(orient="records"))
        except Exception as e:
            logger.exception(f"Failed to read or parse CSV file {file_path}")
            raise HTTPException(status_code=500, detail=f"Failed to process CSV file: {str(e)}")

    if result_filename.endswith(".html"):
        return FileResponse(file_path, media_type="text/html")

    if result_filename.endswith(".txt"):
        return FileResponse(file_path, media_type="text/plain")

    return FileResponse(file_path)


@app.post("/api/simulations", status_code=201)
async def create_simulation(request: CreateSimulationRequest) -> dict[str, Any]:
    """Creates and initiates a new simulation based on the provided configuration.

    Args:
        request: Validated simulation configuration request.

    Returns:
        A dictionary containing the simulation ID of the created or updated run.

    Raises:
        HTTPException: If the simulation process fails to start or config cannot be written.
    """
    add_to_queue = request.add_to_queue

    config = request.get_config_without_queue_flag()

    config_keys = list(config.keys())
    has_shared = "shared_settings" in config
    has_strategies = "simulation_strategies" in config
    logger.info(
        f"New simulation request. Keys: {config_keys}, Shared: {has_shared}, "
        f"Strategies: {has_strategies}, Queue: {add_to_queue}"
    )

    config_dict = config

    running_sim_id = None
    for sim_id, process in running_processes.items():
        if process.poll() is None:
            running_sim_id = sim_id
            break

    if (
        running_sim_id
        and add_to_queue is True
        and not ("shared_settings" in config_dict and "simulation_strategies" in config_dict)
    ):
        logger.info(f"User chose to add to running simulation {running_sim_id}")

        running_sim_path = OUTPUT_DIR / running_sim_id
        config_filepath = running_sim_path / "config.json"

        try:
            with config_filepath.open("r") as f:
                running_config = json.load(f)

            new_strategy = {}
            strategy_fields = [
                "aggregation_strategy_keyword",
                "num_of_malicious_clients",
                "num_krum_selections",
                "remove_clients",
                "begin_removing_from_round",
            ]
            for field in strategy_fields:
                if config_dict.get(field) is not None:
                    new_strategy[field] = config_dict[field]

            running_config["simulation_strategies"].append(new_strategy)

            with config_filepath.open("w") as f:
                json.dump(running_config, f, indent=4)

            logger.info(f"Added strategy to running simulation {running_sim_id}")
            return {"simulation_id": running_sim_id, "queued": True}

        except Exception:
            logger.exception("Failed to add to running queue, creating new simulation instead")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    simulation_id = f"api_run_{timestamp}"

    output_sim_path = OUTPUT_DIR / simulation_id
    output_sim_path.mkdir(parents=True, exist_ok=True)

    config_filepath = output_sim_path / "config.json"

    if "shared_settings" in config_dict and "simulation_strategies" in config_dict:
        logger.info("Multi-sim config detected, using as-is")
        wrapped_config = config_dict
    else:
        logger.info("Single sim config detected, wrapping with first strategy")
        wrapped_config = {
            "shared_settings": config_dict,
            "simulation_strategies": [config_dict.copy()],
        }

    try:
        with config_filepath.open("w") as f:
            json.dump(wrapped_config, f, indent=4)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write config file: {e}")

    try:
        error_log_path = output_sim_path / "execution.log"

        env = get_safe_env()
        try:
            physical_cores = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 1
            env["LOKY_MAX_CPU_COUNT"] = str(physical_cores)
        except ImportError:
            env["LOKY_MAX_CPU_COUNT"] = str(multiprocessing.cpu_count())
        env.update(get_subprocess_env_vars())

        with error_log_path.open("w") as error_log:
            command = [
                sys.executable,
                "-m",
                "intellifl.simulation_runner",
                str(config_filepath),
            ]
            process = subprocess.Popen(
                command, cwd=BASE_DIR, stderr=error_log, stdout=subprocess.PIPE, env=env
            )
        running_processes[simulation_id] = process
        logger.info(f"Started simulation {simulation_id} with PID {process.pid}")
    except Exception:
        logger.exception(f"Failed to start simulation process for {simulation_id}")
        raise HTTPException(status_code=500, detail="Failed to start simulation process")

    return {"simulation_id": simulation_id}


@app.post("/api/simulations/prepare", status_code=201)
async def prepare_simulation(request: CreateSimulationRequest) -> dict[str, Any]:
    """Prepares a simulation by creating config but not starting the process.

    This endpoint is used when the frontend wants to run the simulation
    directly in the terminal PTY for real-time output.

    Args:
        request: Validated simulation configuration request.

    Returns:
        A dictionary containing:
        - simulation_id: The unique identifier for the simulation
        - command: The command to run in the terminal

    Raises:
        HTTPException: If the config cannot be written.
    """
    config = request.get_config_without_queue_flag()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    simulation_id = f"api_run_{timestamp}"

    output_sim_path = OUTPUT_DIR / simulation_id
    output_sim_path.mkdir(parents=True, exist_ok=True)

    config_filepath = output_sim_path / "config.json"

    if "shared_settings" in config and "simulation_strategies" in config:
        logger.info("Multi-sim config detected, using as-is")
        wrapped_config = config
    else:
        logger.info("Single sim config detected, wrapping with first strategy")
        wrapped_config = {
            "shared_settings": config,
            "simulation_strategies": [config.copy()],
        }

    try:
        with config_filepath.open("w") as f:
            json.dump(wrapped_config, f, indent=4)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write config file: {e}")

    relative_config_path = f"out/{simulation_id}/config.json"
    command = f"python -m intellifl.simulation_runner {relative_config_path}"

    logger.info(f"Prepared simulation {simulation_id} for terminal execution")

    return {
        "simulation_id": simulation_id,
        "command": command,
        "config_path": relative_config_path,
    }


_TERMINAL_STATUSES = frozenset({"completed", "failed", "stopped"})


def _get_status_data(sim_path: Path, simulation_id: str) -> dict[str, Any]:
    """Extract status data from simulation directory.

    This helper is shared between the REST GET endpoint and SSE stream
    to ensure consistent status detection logic.

    Args:
        sim_path: The validated path to the simulation directory.
        simulation_id: The simulation identifier.

    Returns:
        A dictionary containing status, progress, and round information.
    """
    # Check for stopped marker first (highest priority)
    stopped_marker = sim_path / ".stopped"
    if stopped_marker.is_file():
        return {"status": "stopped", "progress": 0.0}

    # Check status.json for detailed progress (written by simulation runner)
    status_file = sim_path / "status.json"
    if status_file.is_file():
        try:
            with status_file.open("r") as f:
                status_data = json.load(f)

            raw_status = status_data.get("status", "running")
            pid = status_data.get("pid")

            # Detect orphaned simulations
            if raw_status in ["running", "queued"] and pid:
                process_alive = False
                with suppress(Exception):
                    process_alive = psutil.pid_exists(pid)

                if not process_alive:
                    logger.warning(
                        f"Simulation {simulation_id} marked as {raw_status} but PID {pid} is dead. Reporting as failed."
                    )
                    return {
                        "status": "failed",
                        "progress": status_data.get("progress", 0.0),
                        "error": "Process was interrupted (e.g. PC restart or crash)",
                    }

            return {
                "status": raw_status,
                "progress": status_data.get("progress", 0.0),
                "current_round": status_data.get("current_round"),
                "total_rounds": status_data.get("total_rounds"),
                "current_strategy": status_data.get("current_strategy"),
                "total_strategies": status_data.get("total_strategies"),
            }
        except (OSError, json.JSONDecodeError):
            pass

    running_marker = sim_path / ".running"
    if running_marker.is_file():
        return {"status": "running", "progress": 0.0}

    if simulation_id in running_processes:
        process = running_processes[simulation_id]
        poll_result = process.poll()

        if poll_result is None:
            return {"status": "running", "progress": 0.0}
        else:
            del running_processes[simulation_id]
            result_files = list(sim_path.glob("*.pdf")) + list(sim_path.glob("csv/*.csv"))
            if result_files or poll_result == 0:
                return {"status": "completed", "progress": 1.0}
            else:
                return {"status": "failed", "progress": 0.0}

    result_files = list(sim_path.glob("*.pdf")) + list(sim_path.glob("csv/*.csv"))
    if result_files:
        return {"status": "completed", "progress": 1.0}

    execution_log_path = sim_path / "execution.log"
    if execution_log_path.is_file():
        try:
            with execution_log_path.open("r") as f:
                error_content = f.read(1024)  # Read just enough to check
            if error_content.strip():
                return {"status": "failed", "progress": 0.0}
        except OSError:
            pass

    return {"status": "pending", "progress": 0.0}


@app.get("/api/simulations/{simulation_id}/status", response_model=SimulationStatusResponse)
def get_simulation_status(
    sim_path: Path = Depends(get_simulation_path), simulation_id: str = ""
) -> SimulationStatusResponse:
    """Retrieves the current execution status of a simulation.

    This endpoint uses the same status detection logic as the SSE stream
    via the shared `_get_status_data` helper, with additional error details
    for failed simulations.

    Args:
        sim_path: The validated path to the simulation directory.
        simulation_id: The simulation identifier.

    Returns:
        SimulationStatusResponse containing status, progress, and error details.
    """
    status_data = _get_status_data(sim_path, simulation_id)

    # For failed status, include error details from execution log
    if status_data.get("status") == "failed":
        execution_log_path = sim_path / "execution.log"
        if execution_log_path.is_file():
            try:
                with execution_log_path.open("r") as f:
                    # Limit to 100KB to prevent memory issues with large logs
                    error_message = f.read(102400).strip()
                if error_message:
                    status_data["error"] = error_message
            except OSError:
                pass

    return SimulationStatusResponse(**status_data)


@app.get("/api/simulations/{simulation_id}/stream")
async def stream_simulation_status(
    request: Request,
    sim_path: Path = Depends(get_simulation_path),
    simulation_id: str = "",
) -> EventSourceResponse:
    """SSE endpoint for real-time simulation status updates.

    Streams status changes until simulation reaches a terminal state
    (completed, failed, or stopped). Automatically closes connection
    when terminal state is reached.

    The stream sends JSON-encoded status objects with fields:
    - status: Current simulation state
    - progress: Float from 0.0 to 1.0
    - current_round: Current training round (optional)
    - total_rounds: Total rounds configured (optional)
    - current_strategy: Current strategy index (optional)
    - total_strategies: Total strategies count (optional)

    SSE Protocol:
    - Each message is prefixed with 'data: ' and ends with '\\n\\n'
    - Browser EventSource API handles parsing automatically
    - Built-in reconnection on network failures

    Args:
        request: The FastAPI request object (for disconnect detection).
        sim_path: The validated path to the simulation directory.
        simulation_id: The simulation identifier.

    Returns:
        EventSourceResponse streaming status updates.
    """

    async def event_generator():
        """Async generator yielding SSE events."""
        last_status: dict[str, Any] | None = None

        while True:
            if await request.is_disconnected():
                logger.debug(f"SSE client disconnected for {simulation_id}")
                break

            current_status = _get_status_data(sim_path, simulation_id)

            # Only send events when status changes
            if current_status != last_status:
                yield {"data": json.dumps(current_status)}
                last_status = current_status.copy()

                if current_status.get("status") in _TERMINAL_STATUSES:
                    logger.debug(
                        f"SSE stream closing for {simulation_id}: "
                        f"terminal status '{current_status.get('status')}'"
                    )
                    break

            await asyncio.sleep(1)  # Poll interval: 1 second

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@app.delete("/api/simulations/{simulation_id}", status_code=200)
def delete_simulation(
    sim_path: Path = Depends(get_simulation_path), simulation_id: str = ""
) -> dict[str, str]:
    """Permanently deletes a simulation and all associated files.

    Args:
        sim_path: The validated path to the simulation directory.
        simulation_id: The simulation identifier.

    Returns:
        A confirmation message and the deleted simulation ID.

    Raises:
        HTTPException: If the simulation is currently running or deletion fails.
    """
    if simulation_id in running_processes:
        process = running_processes[simulation_id]
        if process.poll() is None:
            raise HTTPException(status_code=409, detail="Cannot delete a running simulation.")
        del running_processes[simulation_id]

    try:
        shutil.rmtree(sim_path)
        logger.info(f"Deleted simulation: {simulation_id}")
        return {"message": "deleted", "simulation_id": simulation_id}
    except Exception:
        logger.exception(f"Failed to delete simulation {simulation_id}")
        raise HTTPException(status_code=500, detail="Failed to delete simulation")


@app.delete("/api/simulations", status_code=200)
def delete_multiple_simulations(
    simulation_ids: list[str] = Body(..., embed=True),
) -> dict[str, Any]:
    """Permanently deletes multiple simulations defined by their IDs.

    Args:
        simulation_ids: A list of simulation IDs to delete.

    Returns:
        A dictionary with lists of successfully deleted IDs and failure details.
    """
    deleted = []
    failed = []

    for simulation_id in simulation_ids:
        try:
            # Security: Validate that ID contains only alphanumeric chars and underscores
            if not all(c.isalnum() or c == "_" for c in simulation_id):
                failed.append({"simulation_id": simulation_id, "error": "Invalid simulation ID"})
                continue

            sim_path = secure_join(OUTPUT_DIR, simulation_id)

            if not sim_path.is_dir():
                failed.append({"simulation_id": simulation_id, "error": "Simulation not found"})
                continue

            if simulation_id in running_processes:
                process = running_processes[simulation_id]
                if process.poll() is None:
                    failed.append(
                        {
                            "simulation_id": simulation_id,
                            "error": "Simulation is running",
                        }
                    )
                    continue
                del running_processes[simulation_id]

            shutil.rmtree(sim_path)
            deleted.append(simulation_id)
            logger.info(f"Deleted simulation: {simulation_id}")

        except Exception as e:
            logger.exception(f"Failed to delete simulation {simulation_id}")
            failed.append({"simulation_id": simulation_id, "error": str(e)})

    return {"deleted": deleted, "failed": failed}


@app.patch("/api/simulations/{simulation_id}/rename", status_code=200)
def rename_simulation(
    simulation_id: str,
    display_name: str = Body(..., embed=True),
    sim_path: Path = Depends(get_simulation_path),
) -> dict[str, str]:
    """Updates the display name of a simulation.

    Args:
        simulation_id: The simulation identifier.
        display_name: The new display name.
        sim_path: The validated path to the simulation directory.

    Returns:
        A confirmation message and the updated display name.

    Raises:
        HTTPException: If the name is invalid or configuration cannot be updated.
    """
    if not display_name or not display_name.strip():
        raise HTTPException(
            status_code=400, detail="Display name cannot be empty or whitespace only"
        )

    display_name = display_name.strip()

    if len(display_name) > 100:
        raise HTTPException(status_code=400, detail="Display name must be 100 characters or less")

    config_path = sim_path / "config.json"
    if not config_path.is_file():
        raise HTTPException(status_code=404, detail="Simulation config.json not found.")

    try:
        with config_path.open("r") as f:
            config = json.load(f)

        if "shared_settings" in config:
            config["shared_settings"]["display_name"] = display_name
        else:
            config["display_name"] = display_name

        with config_path.open("w") as f:
            json.dump(config, f, indent=4)

        logger.info(f"Renamed simulation {simulation_id} to '{display_name}'")
        return {
            "message": "renamed",
            "simulation_id": simulation_id,
            "display_name": display_name,
        }

    except (OSError, json.JSONDecodeError) as e:
        logger.exception(f"Failed to rename simulation {simulation_id}")
        raise HTTPException(status_code=500, detail=f"Failed to update simulation config: {str(e)}")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Federated Learning Simulation Framework API"}


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Health check endpoint for startup detection and monitoring."""
    return {"status": "healthy"}


class GpuInfo(BaseModel):
    """GPU hardware information."""

    name: str
    vram_gb: float


class SystemDevicesResponse(BaseModel):
    """Response model for available training devices."""

    available_devices: list[str]
    gpu_available: bool
    gpu_info: GpuInfo | None
    recommended_device: str


@app.get("/api/system/devices", response_model=SystemDevicesResponse)
async def get_system_devices() -> SystemDevicesResponse:
    """Returns available training devices and GPU info.

    Detects CUDA-capable GPUs and returns hardware information
    for frontend device selection UI.

    Returns:
        SystemDevicesResponse with available devices, GPU info if present,
        and recommended device for training.
    """
    result = SystemDevicesResponse(
        available_devices=["cpu"],
        gpu_available=False,
        gpu_info=None,
        recommended_device="cpu",
    )

    try:
        import torch

        if torch.cuda.is_available():
            result.available_devices.append("gpu")
            result.gpu_available = True
            result.gpu_info = GpuInfo(
                name=torch.cuda.get_device_name(0),
                vram_gb=round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1),
            )
            result.recommended_device = "gpu"
    except Exception:
        # Graceful fallback if torch unavailable
        pass

    return result


@app.get("/api/simulations/{simulation_id}/plot-data")
async def get_plot_data(simulation_id: str) -> dict:
    """Retrieves JSON plot data for a specific simulation.

    Args:
        simulation_id: The simulation identifier.

    Returns:
        The content of the plot data JSON file.

    Raises:
        HTTPException: If data is unavailable or not found.
    """
    # Security: Validate simulation_id format
    if not all(c.isalnum() or c == "_" for c in simulation_id):
        raise HTTPException(status_code=400, detail="Invalid simulation ID format.")

    try:
        sim_dir = secure_join(OUTPUT_DIR, simulation_id)

        if not sim_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Simulation directory not found for {simulation_id}",
            )

        json_files = [
            f for f in os.listdir(sim_dir) if f.startswith("plot_data_") and f.endswith(".json")
        ]

        if not json_files:
            raise HTTPException(
                status_code=404,
                detail="Plot data not yet available - simulation may still be running",
            )

        json_path = sim_dir / json_files[0]

        with open(json_path) as f:
            return json.load(f)

    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Plot data not found for simulation {simulation_id}",
        )
    except Exception:
        logger.exception(f"Error loading plot data for {simulation_id}")
        raise HTTPException(status_code=500, detail="Failed to load plot data. Check server logs.")


@app.get("/api/simulations/{simulation_id}/all-plot-data", response_model=AllPlotDataResponse)
async def get_all_plot_data(simulation_id: str) -> AllPlotDataResponse:
    """Retrieves all plot data JSON files for a multi-strategy simulation.

    Args:
        simulation_id: The simulation identifier.

    Returns:
        AllPlotDataResponse containing plot data for each strategy.

    Raises:
        HTTPException: If data is unavailable or not found.
    """
    # Security: Validate simulation_id format
    if not all(c.isalnum() or c == "_" for c in simulation_id):
        raise HTTPException(status_code=400, detail="Invalid simulation ID format.")

    try:
        sim_dir = secure_join(OUTPUT_DIR, simulation_id)

        if not sim_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Simulation directory not found for {simulation_id}",
            )

        json_files = sorted(
            [f for f in os.listdir(sim_dir) if f.startswith("plot_data_") and f.endswith(".json")]
        )

        if not json_files:
            raise HTTPException(
                status_code=404,
                detail="Plot data not yet available - simulation may still be running",
            )

        all_plot_data = []
        for json_file in json_files:
            json_path = sim_dir / json_file
            with open(json_path) as f:
                data = json.load(f)
                strategy_num = int(json_file.replace("plot_data_", "").replace(".json", ""))
                all_plot_data.append(StrategyPlotData(strategy_number=strategy_num, data=data))

        return AllPlotDataResponse(strategies=all_plot_data)

    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Plot data not found for simulation {simulation_id}",
        )
    except Exception:
        logger.exception(f"Error loading all plot data for {simulation_id}")
        raise HTTPException(status_code=500, detail="Failed to load plot data. Check server logs.")


def _find_simulation_process(simulation_id: str) -> psutil.Process | None:
    """Find a running simulation process by its simulation ID.

    Searches for processes by:
    1. Command line pattern matching simulation_runner with config path
    2. PID stored in status.json file

    Args:
        simulation_id: The simulation identifier.

    Returns:
        The psutil.Process if found, None otherwise.
    """
    # Method 1: Search by command line pattern
    config_pattern = f"out/{simulation_id}/config.json"
    alt_config_pattern = f"out\\{simulation_id}\\config.json"

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            cmdline_str = " ".join(cmdline) if cmdline else ""

            if "simulation_runner" in cmdline_str and (
                config_pattern in cmdline_str or alt_config_pattern in cmdline_str
            ):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Method 2: Try to find process by PID from status.json
    status_path = OUTPUT_DIR / simulation_id / "status.json"
    if status_path.exists():
        try:
            with status_path.open() as f:
                status_data = json.load(f)
            pid = status_data.get("pid")
            if pid:
                try:
                    proc = psutil.Process(pid)
                    # Verify it's still a Python process (simulation might have reused PID)
                    if proc.is_running() and "python" in proc.name().lower():
                        return proc
                except psutil.NoSuchProcess:
                    pass
        except (OSError, json.JSONDecodeError):
            pass

    return None


@app.post("/api/simulations/{simulation_id}/stop", status_code=200)
def stop_simulation(simulation_id: str) -> dict[str, str]:
    """Terminates a running simulation and all its child processes.

    Args:
        simulation_id: The simulation identifier.

    Returns:
        A confirmation message.

    Raises:
        HTTPException: If the simulation is not running or termination fails.
    """
    process = None
    parent = None

    # First check if process is tracked in running_processes dict
    if simulation_id in running_processes:
        process = running_processes[simulation_id]
        if process.poll() is not None:
            del running_processes[simulation_id]
            process = None

    # If not found in dict, search for terminal-spawned processes by cmdline/PID
    if process is None:
        found_proc = _find_simulation_process(simulation_id)
        if found_proc:
            parent = found_proc
        else:
            # Check if status.json shows "running" but process is dead (orphaned status)
            status_path = OUTPUT_DIR / simulation_id / "status.json"
            if status_path.exists():
                try:
                    with status_path.open() as f:
                        status_data = json.load(f)
                    if status_data.get("status") == "running":
                        # Process died but status wasn't updated - mark as stopped
                        status_data["status"] = "stopped"
                        status_data["stopped_at"] = datetime.datetime.now(
                            tz=datetime.timezone.utc
                        ).isoformat()
                        status_data["error"] = "Process terminated unexpectedly"
                        with status_path.open("w") as f:
                            json.dump(status_data, f, indent=2)
                        logger.info(f"Marked orphaned simulation {simulation_id} as stopped")
                        return {"message": "stopped", "simulation_id": simulation_id}
                except (OSError, json.JSONDecodeError) as e:
                    logger.warning(f"Failed to update orphaned status for {simulation_id}: {e}")

            raise HTTPException(
                status_code=404, detail="Simulation is not running or does not exist."
            )
    else:
        # Process found in running_processes dict
        try:
            parent = psutil.Process(process.pid)
        except psutil.NoSuchProcess:
            del running_processes[simulation_id]
            raise HTTPException(status_code=409, detail="Simulation has already completed.")

    try:
        children = parent.children(recursive=True)

        parent.terminate()
        for child in children:
            with suppress(psutil.NoSuchProcess):
                child.terminate()

        try:
            parent.wait(timeout=5)
        except psutil.TimeoutExpired:
            parent.kill()
            for child in children:
                with suppress(psutil.NoSuchProcess):
                    child.kill()
            parent.wait()

        # Clean up running_processes dict if it was tracked there
        if simulation_id in running_processes:
            del running_processes[simulation_id]

        sim_path = OUTPUT_DIR / simulation_id
        stopped_marker = sim_path / ".stopped"
        try:
            with stopped_marker.open("w") as f:
                f.write(f"Simulation stopped at {datetime.datetime.now().isoformat()}")
        except OSError as e:
            logger.warning(f"Failed to write stopped marker for {simulation_id}: {e}")

        logger.info(f"Stopped simulation {simulation_id} and all child processes")
        return {"message": "stopped", "simulation_id": simulation_id}
    except psutil.NoSuchProcess:
        if simulation_id in running_processes:
            del running_processes[simulation_id]
        logger.info(f"Simulation {simulation_id} already terminated")
        return {"message": "stopped", "simulation_id": simulation_id}
    except Exception:
        logger.exception(f"Failed to stop simulation {simulation_id}")
        raise HTTPException(status_code=500, detail="Failed to stop simulation")


@app.get(
    "/api/simulations/{simulation_id}/attack-snapshots", response_model=AttackSnapshotsResponse
)
async def get_attack_snapshots(
    simulation_id: str, sim_path: Path = Depends(get_simulation_path)
) -> dict[str, Any]:
    """Retrieves attack snapshot data for visualization.

    Args:
        simulation_id: The simulation identifier.
        sim_path: The validated path to the simulation directory.

    Returns:
        A dictionary containing snapshot summaries, timelines, and image paths
        including additional visualizations (confusion matrices, heatmaps, etc.).
    """
    snapshot_dirs = sorted(sim_path.glob("attack_snapshots_*"))

    if not snapshot_dirs:
        return {"has_snapshots": False, "strategies": []}

    strategies_data = []

    for snapshot_dir in snapshot_dirs:
        strategy_num = int(snapshot_dir.name.replace("attack_snapshots_", ""))

        summary_path = snapshot_dir / "summary.json"
        summary = None
        if summary_path.is_file():
            try:
                with summary_path.open("r") as f:
                    summary = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to load attack summary: {summary_path}: {e}")

        snapshots = []
        for client_dir in sorted(snapshot_dir.glob("client_*")):
            client_id = int(client_dir.name.replace("client_", ""))

            for round_dir in sorted(client_dir.glob("round_*")):
                round_num = int(round_dir.name.replace("round_", ""))

                # Process standard visual/image attacks
                visual_files = list(round_dir.glob("*_visual.png"))
                for visual_file in visual_files:
                    attack_type = visual_file.stem.replace("_visual", "")
                    rel_path = visual_file.relative_to(sim_path)

                    metadata = None
                    metadata_path = round_dir / f"{attack_type}_metadata.json"
                    if metadata_path.is_file():
                        try:
                            with metadata_path.open("r") as f:
                                metadata = json.load(f)
                        except (OSError, json.JSONDecodeError) as e:
                            logger.warning(f"Failed to load attack metadata: {metadata_path}: {e}")

                    visualizations = {"primary": str(rel_path).replace("\\", "/")}

                    optional_viz = {
                        "confusion_matrix": f"{attack_type}_confusion_matrix.png",
                        "difference_heatmap": f"{attack_type}_difference_heatmap.png",
                        "html_diff": f"{attack_type}_samples.html",
                        "prediction_grid": f"{attack_type}_weight_prediction_grid.png",
                        "comparison": f"{attack_type}_comparison.png",
                    }
                    for key, filename in optional_viz.items():
                        file_path = round_dir / filename
                        if file_path.is_file():
                            visualizations[key] = str(file_path.relative_to(sim_path)).replace(
                                "\\", "/"
                            )

                    snapshot_data = {
                        "client_id": client_id,
                        "round_num": round_num,
                        "attack_type": attack_type,
                        "image_path": str(rel_path).replace("\\", "/"),
                        "visualizations": visualizations,
                        "metadata": metadata,
                    }

                    flip_summary = None
                    flip_summary_path = round_dir / f"{attack_type}_summary.json"
                    if flip_summary_path.is_file():
                        try:
                            with flip_summary_path.open("r") as f:
                                flip_summary = json.load(f)
                        except (OSError, json.JSONDecodeError) as e:
                            logger.warning(f"Failed to load flip summary: {flip_summary_path}: {e}")

                    if flip_summary:
                        snapshot_data["flip_summary"] = flip_summary

                    snapshots.append(snapshot_data)

                # Process text-based attacks (HTML diffs)
                html_files = list(round_dir.glob("*_samples.html"))
                for html_file in html_files:
                    attack_type = html_file.stem.replace("_samples", "")
                    # Avoid double-adding if a PNG also exists
                    if not any(
                        s["attack_type"] == attack_type
                        and s["client_id"] == client_id
                        and s["round_num"] == round_num
                        for s in snapshots
                    ):
                        visualizations = {
                            "html_diff": str(html_file.relative_to(sim_path)).replace("\\", "/"),
                            "primary": str(html_file.relative_to(sim_path)).replace("\\", "/"),
                        }
                        metadata = None
                        metadata_path = round_dir / f"{attack_type}_metadata.json"
                        if metadata_path.is_file():
                            try:
                                with metadata_path.open("r") as f:
                                    metadata = json.load(f)
                            except (OSError, json.JSONDecodeError) as e:
                                logger.warning(
                                    f"Failed to load attack metadata: {metadata_path}: {e}"
                                )

                        snapshots.append(
                            {
                                "client_id": client_id,
                                "round_num": round_num,
                                "attack_type": attack_type,
                                "image_path": "",
                                "visualizations": visualizations,
                                "metadata": metadata,
                                "is_text_attack": True,
                            }
                        )

                # Process weight-based attacks (histograms)
                histogram_files = list(round_dir.glob("*_weight_histogram.png"))
                for hist_file in histogram_files:
                    attack_type = hist_file.stem.replace("_weight_histogram", "")

                    existing = next(
                        (
                            s
                            for s in snapshots
                            if s["client_id"] == client_id
                            and s["round_num"] == round_num
                            and s["attack_type"] == attack_type
                        ),
                        None,
                    )

                    hist_rel_path = str(hist_file.relative_to(sim_path)).replace("\\", "/")

                    if existing:
                        if "visualizations" not in existing:
                            existing["visualizations"] = {}  # type: ignore[index]
                        existing["visualizations"]["weight_histogram"] = hist_rel_path  # type: ignore[index]
                    else:
                        hist_visualizations: dict[str, str] = {"weight_histogram": hist_rel_path}

                        # Check for prediction comparison visualizations (multiple naming patterns)
                        prediction_viz_patterns = [
                            f"{attack_type}_prediction_comparison.png",
                            f"{attack_type}_weight_prediction_grid.png",
                        ]
                        for pattern in prediction_viz_patterns:
                            file_path = round_dir / pattern
                            if file_path.is_file():
                                hist_visualizations["primary"] = str(
                                    file_path.relative_to(sim_path)
                                ).replace("\\", "/")
                                break

                        # Fall back to weight histogram if no prediction viz found
                        if "primary" not in hist_visualizations:
                            hist_visualizations["primary"] = hist_rel_path

                        weight_metadata = None
                        weight_meta_path = round_dir / f"{attack_type}_weight_metadata.json"
                        if weight_meta_path.is_file():
                            try:
                                with weight_meta_path.open("r") as f:
                                    weight_metadata = json.load(f)
                            except (OSError, json.JSONDecodeError) as e:
                                logger.warning(
                                    f"Failed to load weight metadata: {weight_meta_path}: {e}"
                                )

                        snapshots.append(
                            {
                                "client_id": client_id,
                                "round_num": round_num,
                                "attack_type": attack_type,
                                "image_path": hist_visualizations.get("primary", ""),
                                "visualizations": hist_visualizations,
                                "metadata": weight_metadata,
                                "is_weight_attack": True,
                            }
                        )

        strategies_data.append(
            {
                "strategy_number": strategy_num,
                "summary": summary,
                "snapshots": sorted(snapshots, key=lambda x: (x["round_num"], x["client_id"])),
            }
        )

    return {
        "has_snapshots": True,
        "strategies": strategies_data,
    }


def _load_json_file(path: Path) -> dict | None:
    """Safely loads and parses a JSON file."""
    if not path.is_file():
        return None
    try:
        with path.open("r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load JSON file {path}: {e}")
        return None


def _add_optional_visualizations(
    round_dir: Path, attack_type: str, sim_path: Path, visualizations: dict
) -> None:
    """Adds paths for optional secondary visualizations to the snapshot dictionary."""
    optional_viz = {
        "confusion_matrix": f"{attack_type}_confusion_matrix.png",
        "difference_heatmap": f"{attack_type}_difference_heatmap.png",
        "html_diff": f"{attack_type}_samples.html",
        "prediction_grid": f"{attack_type}_weight_prediction_grid.png",
        "comparison": f"{attack_type}_comparison.png",
    }
    for key, filename in optional_viz.items():
        file_path = round_dir / filename
        if file_path.is_file():
            visualizations[key] = str(file_path.relative_to(sim_path)).replace("\\", "/")


@app.get("/api/datasets/validate", response_model=DatasetValidationResponse)
async def validate_dataset(name: str) -> DatasetValidationResponse:
    """Validates if a HuggingFace dataset exists and is compatible with Flower.

    Args:
        name: The HuggingFace dataset identifier.

    Returns:
        DatasetValidationResponse indicating validity, compatibility, and metadata.
    """
    try:
        builder = load_dataset_builder(name)

        if builder.info.splits is None:
            return DatasetValidationResponse(
                valid=False,
                compatible=False,
                reason="Dataset has no splits information",
            )

        splits = list(builder.info.splits.keys())
        num_examples = sum(s.num_examples for s in builder.info.splits.values())
        features = str(builder.info.features)

        label_field_indicators = [
            "label",
            "labels",
            "class",
            "target",
            "fine_label",
            "coarse_label",
        ]
        has_label = any(field in features.lower() for field in label_field_indicators)

        key_features = []
        if builder.info.features:
            try:
                feature_matches = re.findall(r"(?:['\"](\w+)['\"]|(\w+))\s*:", features)
                feature_matches = [m[0] or m[1] for m in feature_matches]
                if feature_matches:
                    key_features = list(dict.fromkeys(feature_matches))[:5]
            except Exception as e:
                logger.debug(f"Failed to parse dataset features: {e}")
                key_features = []

        compatible = True

        return DatasetValidationResponse(
            valid=True,
            compatible=compatible,
            info=DatasetInfo(
                splits=splits,
                num_examples=num_examples,
                features=features,
                has_label=has_label,
                key_features=key_features,
            ),
            error=None,
        )

    except Exception as e:
        error_message = str(e)
        error_lower = error_message.lower()

        if "connection" in error_lower or "network" in error_lower or "timeout" in error_lower:
            error_message = "Network error: Unable to connect to HuggingFace Hub. Please check your internet connection."
        elif "not found" in error_lower or "doesn't exist" in error_lower or "404" in error_lower:
            error_message = (
                f"Dataset '{name}' not found on HuggingFace Hub. Please verify the dataset name."
            )
        elif (
            "authentication" in error_lower or "unauthorized" in error_lower or "401" in error_lower
        ):
            error_message = "Authentication error: This dataset may require HuggingFace login or access permissions."
        elif "forbidden" in error_lower or "403" in error_lower:
            error_message = "Access forbidden: You may not have permission to access this dataset."
        elif len(name) < 2 or "/" not in name:
            error_message = "Invalid dataset name format. Expected format: 'username/dataset-name' (e.g., 'ylecun/mnist')."
        else:
            error_message = f"Unable to validate dataset: {error_message}"

        return DatasetValidationResponse(
            valid=False,
            compatible=False,
            info=None,
            error=error_message,
        )


terminal_sessions: dict[str, dict[str, Any]] = {}


if sys.platform == "win32":

    @app.websocket("/api/terminal")
    async def terminal_websocket(websocket: WebSocket):
        """Manages interactive terminal sessions over WebSocket for Windows."""
        await websocket.accept()

        session_id = f"term_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        logger.info(f"Terminal session started: {session_id}")

        # Prefer Git Bash/MSYS2, fallback to cmd.exe
        bash_path = shutil.which("bash")
        if bash_path:
            shell_cmd = [bash_path]
            logger.info(f"Using bash: {bash_path}")
        else:
            shell_path = os.environ.get("COMSPEC", "cmd.exe")
            shell_cmd = [shell_path]
            logger.info(f"Bash not found, using cmd.exe: {shell_path}")

        env = get_safe_env()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"

        proc = winpty.PtyProcess.spawn(
            shell_cmd,
            cwd=str(BASE_DIR),
            dimensions=(24, 80),
            env=env,
        )

        terminal_sessions[session_id] = {"process": proc}

        async def read_from_pty():
            loop = asyncio.get_event_loop()
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

            def blocking_read():
                try:
                    return proc.read()
                except EOFError:
                    return None
                except Exception as e:
                    logger.debug(f"PTY read exception: {e}")
                    return None

            try:
                while proc.isalive():
                    try:
                        future = loop.run_in_executor(executor, blocking_read)
                        try:
                            data = await asyncio.wait_for(future, timeout=0.5)
                            if data:
                                logger.debug(f"PTY data: {len(data)} bytes")
                                await websocket.send_text(data)
                            else:
                                await asyncio.sleep(0.05)
                        except asyncio.TimeoutError:
                            await asyncio.sleep(0.01)
                            continue
                    except EOFError:
                        logger.debug("PTY EOF")
                        break
                    except Exception as e:
                        logger.debug(f"PTY read loop error: {e}")
                        await asyncio.sleep(0.05)
            except Exception:
                logger.exception("PTY read error")
            finally:
                executor.shutdown(wait=False)

        read_task = asyncio.create_task(read_from_pty())

        try:
            while True:
                message = await websocket.receive()

                if message["type"] == "websocket.disconnect":
                    break

                if "text" in message:
                    text = message["text"]

                    if text.startswith("{"):
                        try:
                            msg = json.loads(text)
                            if msg.get("type") == "resize":
                                # Validate and clamp terminal dimensions (1-500)
                                rows = max(1, min(500, int(msg.get("rows", 24))))
                                cols = max(1, min(500, int(msg.get("cols", 80))))
                                proc.setwinsize(rows, cols)
                                logger.debug(f"Terminal resized to {rows}x{cols}")
                                continue
                        except (json.JSONDecodeError, TypeError, ValueError):
                            pass

                    try:
                        proc.write(text)
                    except Exception:
                        logger.exception("PTY write error")
                        break

        except WebSocketDisconnect:
            logger.info(f"Terminal session disconnected: {session_id}")
        except Exception:
            logger.exception("Terminal WebSocket error")
        finally:
            read_task.cancel()
            with suppress(asyncio.CancelledError):
                await read_task

            if proc.isalive():
                proc.terminate()

            if session_id in terminal_sessions:
                del terminal_sessions[session_id]

            logger.info(f"Terminal session ended: {session_id}")

else:

    def _set_terminal_size(fd: int, rows: int, cols: int) -> None:
        """Sets the terminal size for a PTY file descriptor."""
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

    @app.websocket("/api/terminal")
    async def terminal_websocket(websocket: WebSocket):
        """Manages interactive terminal sessions over WebSocket for Unix."""
        await websocket.accept()

        session_id = f"term_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        logger.info(f"Terminal session started: {session_id}")

        master_fd, slave_fd = pty.openpty()
        _set_terminal_size(master_fd, 24, 80)

        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        env = get_safe_env()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"

        process = subprocess.Popen(
            ["/bin/bash"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(BASE_DIR),
            env=env,
            preexec_fn=os.setsid,
        )

        os.close(slave_fd)

        terminal_sessions[session_id] = {
            "process": process,
            "master_fd": master_fd,
        }

        async def read_from_pty():
            try:
                while True:
                    await asyncio.sleep(0.01)

                    if process.poll() is not None:
                        break

                    try:
                        ready, _, _ = select.select([master_fd], [], [], 0)
                        if ready:
                            data = os.read(master_fd, 4096)
                            if data:
                                await websocket.send_text(data.decode("utf-8", errors="replace"))
                    except (OSError, BlockingIOError):
                        pass

            except Exception:
                logger.exception("PTY read error")

        read_task = asyncio.create_task(read_from_pty())

        try:
            while True:
                message = await websocket.receive()

                if message["type"] == "websocket.disconnect":
                    break

                if "text" in message:
                    text = message["text"]

                    if text.startswith("{"):
                        try:
                            msg = json.loads(text)
                            if msg.get("type") == "resize":
                                # Validate and clamp terminal dimensions (1-500)
                                rows = max(1, min(500, int(msg.get("rows", 24))))
                                cols = max(1, min(500, int(msg.get("cols", 80))))
                                _set_terminal_size(master_fd, rows, cols)
                                logger.debug(f"Terminal resized to {rows}x{cols}")
                                continue
                        except (json.JSONDecodeError, TypeError, ValueError):
                            pass

                    try:
                        os.write(master_fd, text.encode("utf-8"))
                    except OSError:
                        logger.exception("PTY write error")
                        break

        except WebSocketDisconnect:
            logger.info(f"Terminal session disconnected: {session_id}")
        except Exception:
            logger.exception("Terminal WebSocket error")
        finally:
            read_task.cancel()
            with suppress(asyncio.CancelledError):
                await read_task

            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()

            os.close(master_fd)

            if session_id in terminal_sessions:
                del terminal_sessions[session_id]

            logger.info(f"Terminal session ended: {session_id}")
