"""Simulation CRUD and status router."""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import shutil
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

import pandas as pd
import psutil
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ValidationError
from sse_starlette.sse import EventSourceResponse

from intellifl.api.dependencies import (
    OUTPUT_DIR,
    get_simulation_path,
    secure_join,
)
from intellifl.api.models import (
    CreateSimulationRequest,
    SimulationStatusResponse,
    ValidationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["simulations"])


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


_TERMINAL_STATUSES = frozenset({"completed", "failed", "stopped"})

_SUPPORTED_RESULT_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".csv",
    ".json",
    ".html",
    ".txt",
)

# How recently status.json must have been updated to trust the file-based
# status without performing PID / Celery liveness checks.  This covers the
# gap between status writes (round updates, strategy transitions, etc.).
_STATUS_FRESHNESS_SECONDS = 120


def _status_is_fresh(status_data: dict) -> bool:
    """Return True if status.json was updated recently enough to trust."""
    updated_at = status_data.get("updated_at")
    if not updated_at:
        return False
    try:
        ts = datetime.datetime.fromisoformat(updated_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.UTC)
        age = (datetime.datetime.now(datetime.UTC) - ts).total_seconds()
        return age < _STATUS_FRESHNESS_SECONDS
    except (ValueError, TypeError):
        return False


def _get_status_data(sim_path: Path, simulation_id: str) -> dict[str, Any]:
    """Extract status data from a simulation directory; shared by REST and SSE endpoints."""
    stopped_marker = sim_path / ".stopped"
    if stopped_marker.is_file():
        return {"status": "stopped", "progress": 0.0}
    status_file = sim_path / "status.json"
    if status_file.is_file():
        try:
            with status_file.open("r") as f:
                status_data = json.load(f)

            raw_status = status_data.get("status", "running")
            pid = status_data.get("pid")

            result_files = list(sim_path.glob("*.pdf")) + list(sim_path.glob("csv/*.csv"))
            if result_files and raw_status in ["queued", "pending", "running"]:
                return {
                    "status": "completed",
                    "progress": 1.0,
                    "current_round": status_data.get("current_round"),
                    "total_rounds": status_data.get("total_rounds"),
                    "current_strategy": status_data.get("current_strategy"),
                    "total_strategies": status_data.get("total_strategies"),
                    "origin": status_data.get("origin"),
                }

            # If the status file was recently written, the process is alive —
            # skip expensive / unreliable PID and Celery liveness checks.
            # This is critical for CLI-originated runs that don't use Celery
            # and where psutil.pid_exists() can return a false negative
            # (e.g. Windows + MSYS2/Git Bash namespace mismatch).
            if raw_status in ["running", "queued"] and _status_is_fresh(status_data):
                return {
                    "status": raw_status,
                    "progress": status_data.get("progress", 0.0),
                    "current_round": status_data.get("current_round"),
                    "total_rounds": status_data.get("total_rounds"),
                    "current_strategy": status_data.get("current_strategy"),
                    "total_strategies": status_data.get("total_strategies"),
                    "origin": status_data.get("origin"),
                }

            celery_task_id = status_data.get("celery_task_id")

            if raw_status in ["running", "queued"] and celery_task_id:
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
                    try:
                        with status_file.open("r") as f:
                            fresh_status = json.load(f)
                        if fresh_status.get("status") == "completed":
                            return {
                                "status": "completed",
                                "progress": 1.0,
                                "current_round": fresh_status.get("current_round"),
                                "total_rounds": fresh_status.get("total_rounds"),
                                "current_strategy": fresh_status.get("current_strategy"),
                                "total_strategies": fresh_status.get("total_strategies"),
                                "origin": fresh_status.get("origin"),
                            }
                    except (OSError, json.JSONDecodeError):
                        pass

                    logger.warning(
                        f"Simulation {simulation_id} {raw_status} but Celery task "
                        f"{celery_task_id} is gone. Reporting as failed."
                    )
                    return {
                        "status": "failed",
                        "progress": status_data.get("progress", 0.0),
                        "error": "Task was lost from queue (e.g. Redis restart). "
                        "Re-submit or restart the API server to auto-recover.",
                        "origin": status_data.get("origin"),
                    }

            elif raw_status in ["running", "queued"] and pid:
                # Subprocess mode: PID is in the same namespace — safe to check
                process_alive = False
                with suppress(Exception):
                    process_alive = psutil.pid_exists(pid)

                if not process_alive:
                    try:
                        with status_file.open("r") as f:
                            fresh_status = json.load(f)
                        if fresh_status.get("status") == "completed":
                            return {
                                "status": "completed",
                                "progress": 1.0,
                                "current_round": fresh_status.get("current_round"),
                                "total_rounds": fresh_status.get("total_rounds"),
                                "current_strategy": fresh_status.get("current_strategy"),
                                "total_strategies": fresh_status.get("total_strategies"),
                                "origin": fresh_status.get("origin"),
                            }
                    except (OSError, json.JSONDecodeError):
                        pass

                    logger.warning(
                        f"Simulation {simulation_id} marked as {raw_status} but PID {pid} is dead. Reporting as failed."
                    )
                    return {
                        "status": "failed",
                        "progress": status_data.get("progress", 0.0),
                        "error": "Process was interrupted (e.g. PC restart or crash)",
                        "origin": status_data.get("origin"),
                    }

            return {
                "status": raw_status,
                "progress": status_data.get("progress", 0.0),
                "current_round": status_data.get("current_round"),
                "total_rounds": status_data.get("total_rounds"),
                "current_strategy": status_data.get("current_strategy"),
                "total_strategies": status_data.get("total_strategies"),
                "origin": status_data.get("origin"),
            }
        except (OSError, json.JSONDecodeError):
            pass

    running_marker = sim_path / ".running"
    if running_marker.is_file():
        return {"status": "running", "progress": 0.0}

    result_files = list(sim_path.glob("*.pdf")) + list(sim_path.glob("csv/*.csv"))
    if result_files:
        return {"status": "completed", "progress": 1.0}

    # Only treat output.log as a failure indicator if it contains actual
    # error-level messages — not routine INFO / WARNING / DEBUG output that
    # CLI-originated simulations write via file logging.
    log_path = sim_path / "output.log"
    if log_path.is_file():
        try:
            with log_path.open("r") as f:
                log_content = f.read(4096)
            if log_content.strip():
                log_content_lower = log_content.lower()
                has_error_markers = any(
                    marker.lower() in log_content_lower
                    for marker in [
                        "ERROR:",
                        "CRITICAL:",
                        "CRITICAL ERROR:",
                        "Traceback (most recent call last)",
                        "Exception:",
                        "Simulation failed",
                    ]
                )
                if has_error_markers:
                    return {"status": "failed", "progress": 0.0}
                # Log file exists with only normal output — simulation is
                # either currently running (CLI) or was interrupted without
                # writing a terminal status.  Don't falsely report failure.
                return {"status": "pending", "progress": 0.0}
        except OSError:
            pass

    return {"status": "pending", "progress": 0.0}


def _find_simulation_process(simulation_id: str) -> psutil.Process | None:
    """Find a running simulation process by cmdline pattern or stored PID."""
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

    status_path = OUTPUT_DIR / simulation_id / "status.json"
    if status_path.exists():
        try:
            with status_path.open() as f:
                status_data = json.load(f)
            pid = status_data.get("pid")
            if pid:
                try:
                    proc = psutil.Process(pid)
                    if proc.is_running() and "python" in proc.name().lower():
                        return proc
                except psutil.NoSuchProcess:
                    pass
        except (OSError, json.JSONDecodeError):
            pass

    return None


def parse_log_line(line: str) -> dict[str, str]:
    """Parse a log line into structured fields (timestamp, level, message).

    Args:
        line: Raw log line string to parse.

    Returns:
        Dict with timestamp, level, and message. Unrecognised formats default to INFO.
    """
    import re

    _LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})

    # Ray logger: "2025-01-07 12:00:00 | INFO | name | message"
    match = re.match(
        r"^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s*\|\s*(\w+)\s*\|\s*[\w.]+\s*\|\s*(.+)$",
        line,
    )
    if match and match.group(2).upper() in _LOG_LEVELS:
        return {
            "timestamp": match.group(1),
            "level": match.group(2).upper(),
            "message": match.group(3).strip(),
        }

    # simulation_runner file handler: "LEVEL: message"
    match = re.match(r"^([A-Z]+):\s+(.+)$", line)
    if match and match.group(1) in _LOG_LEVELS:
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "level": match.group(1),
            "message": match.group(2).strip(),
        }

    # Python basicConfig: "LEVEL:module:message"
    match = re.match(r"^([A-Z]+):[\w.]+:(.+)$", line)
    if match and match.group(1) in _LOG_LEVELS:
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "level": match.group(1),
            "message": match.group(2).strip(),
        }

    # Fallback — unrecognised format
    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "level": "INFO",
        "message": line.strip(),
    }


@router.get("/api/simulations", response_model=list[SimulationMetadata])
def get_simulations() -> list[SimulationMetadata]:
    """List all simulations, sorted by most recent first."""
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


@router.get("/api/simulations/{simulation_id}", response_model=SimulationDetails)
def get_simulation_details(
    sim_path: Path = Depends(get_simulation_path), simulation_id: str = ""
) -> SimulationDetails:
    """Return config, result files, and current status for a simulation."""
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
            and item.suffix.lower() in _SUPPORTED_RESULT_EXTENSIONS
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


@router.get("/api/simulations/{simulation_id}/config")
def get_simulation_config(
    sim_path: Path = Depends(get_simulation_path),
) -> dict[str, Any]:
    """Return the raw config.json for a simulation."""
    config_path = sim_path / "config.json"
    if not config_path.is_file():
        raise HTTPException(status_code=404, detail="Simulation config.json not found.")

    try:
        with config_path.open("r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=500, detail="Could not read simulation config.")


@router.get(
    "/api/simulations/{simulation_id}/results/{result_filename:path}",
    response_model=None,
)
def get_result_file(
    result_filename: str,
    sim_path: Path = Depends(get_simulation_path),
    download: bool = False,
) -> FileResponse | JSONResponse:
    """Serve a result file; CSVs are returned as JSON records unless ?download=true."""
    if not result_filename.lower().endswith(_SUPPORTED_RESULT_EXTENSIONS):
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


# Subprocess fallback (used when Celery/Redis is unavailable).
# Uses Popen+executor because asyncio.create_subprocess_exec is broken on Windows.


def _launch_subprocess(config_filepath: Path) -> None:
    """Fire-and-forget launch of simulation_runner as an async subprocess."""
    log_path = config_filepath.parent / "output.log"
    log_file = log_path.open("a")
    project_root = Path(__file__).resolve().parents[3]
    loop = asyncio.get_running_loop()
    loop.create_task(_run_subprocess(config_filepath, log_file, project_root))


def _find_python() -> str:
    """Return the venv Python interpreter, falling back to sys.executable."""
    # sys.executable can point to system Python when uvicorn --reload is active
    project_root = Path(__file__).resolve().parents[3]
    for candidate in (
        project_root / ".venv" / "Scripts" / "python.exe",
        project_root / ".venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def _run_subprocess_blocking(config_filepath: Path, log_file: Any, project_root: Path) -> None:
    """Synchronous subprocess wrapper (runs in a thread via run_in_executor)."""
    proc = subprocess.Popen(
        [
            _find_python(),
            "-m",
            "intellifl.simulation_runner",
            str(config_filepath),
            "--origin",
            "api",
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=str(project_root),
    )
    proc.wait()


async def _run_subprocess(config_filepath: Path, log_file: Any, project_root: Path) -> None:
    """Run simulation_runner in a thread executor."""
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, _run_subprocess_blocking, config_filepath, log_file, project_root
        )
    except Exception:
        logger.exception(f"Subprocess execution failed for {config_filepath.parent.name}")
    finally:
        log_file.close()


@router.post("/api/simulations", status_code=201)
async def create_simulation(request: CreateSimulationRequest) -> dict[str, Any]:
    """Create a simulation directory, write config, and dispatch to Celery or subprocess."""
    config = request.to_config_dict()

    config_keys = list(config.keys())
    has_shared = "shared_settings" in config
    has_strategies = "simulation_strategies" in config
    logger.info(
        f"New simulation request. Keys: {config_keys}, Shared: {has_shared}, "
        f"Strategies: {has_strategies}"
    )

    config_dict = config

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
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

    # Try Celery+Redis first; fall back to subprocess if unavailable
    status_filepath = output_sim_path / "status.json"
    celery_task_id = None
    try:
        from intellifl.celery_app import app as celery_app
        from intellifl.tasks.simulation_tasks import run_simulation

        conn = celery_app.connection()
        try:
            conn.ensure_connection(max_retries=0, timeout=2)
        finally:
            conn.close()

        task = run_simulation.delay(str(config_filepath))
        celery_task_id = task.id
        logger.info(f"Celery: queued simulation {simulation_id} (task_id: {celery_task_id})")
    except Exception as celery_err:
        logger.info(f"Celery unavailable ({celery_err!r}), using subprocess for {simulation_id}")
        _launch_subprocess(config_filepath)

    try:
        total_strategies = len(wrapped_config.get("simulation_strategies", [1]))
        initial_status = {
            "status": "queued",
            "progress": 0.0,
            "current_strategy": 0,
            "total_strategies": total_strategies,
            "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "origin": "api",
        }
        if celery_task_id:
            initial_status["celery_task_id"] = celery_task_id
        with status_filepath.open("w") as f:
            json.dump(initial_status, f, indent=2)
    except OSError as e:
        logger.warning(f"Failed to create initial status.json: {e}")

    return {"simulation_id": simulation_id}


@router.post("/api/validate", response_model=ValidationResponse)
def validate_configuration(request: dict[str, Any] = Body(...)) -> ValidationResponse:
    """Dry-run config validation without creating a simulation."""
    try:
        CreateSimulationRequest(**request)
        logger.debug("Configuration validation succeeded")
        return ValidationResponse(valid=True)
    except ValidationError as e:
        errors = [f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()]
        logger.info(f"Configuration validation failed with {len(errors)} error(s): {errors[:3]}")
        return ValidationResponse(valid=False, errors=errors)
    except Exception as e:
        logger.error(
            f"Unexpected error during configuration validation: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")


@router.get("/api/simulations/{simulation_id}/status", response_model=SimulationStatusResponse)
def get_simulation_status(
    sim_path: Path = Depends(get_simulation_path), simulation_id: str = ""
) -> SimulationStatusResponse:
    """Return current status, progress, and error details for a simulation."""
    status_data = _get_status_data(sim_path, simulation_id)

    if status_data.get("status") == "failed":
        log_path = sim_path / "output.log"
        if log_path.is_file():
            try:
                with log_path.open("r") as f:
                    error_message = f.read(102400).strip()
                if error_message:
                    status_data["error"] = error_message
            except OSError:
                pass

    return SimulationStatusResponse(**status_data)


@router.get("/api/simulations/{simulation_id}/stream")
async def stream_simulation_status(
    request: Request,
    sim_path: Path = Depends(get_simulation_path),
    simulation_id: str = "",
) -> EventSourceResponse:
    """Stream simulation status and log output via SSE.

    Events: ``status`` (JSON progress), ``output`` (log text), ``done``.
    """

    async def event_generator():
        last_status: dict[str, Any] | None = None
        log_position = 0
        log_path: Path | None = None

        while True:
            if await request.is_disconnected():
                logger.debug(f"SSE client disconnected for {simulation_id}")
                break

            current_status = _get_status_data(sim_path, simulation_id)

            if current_status != last_status:
                yield {"event": "status", "data": json.dumps(current_status)}
                last_status = current_status.copy()

            if log_path is None:
                candidate = sim_path / "output.log"
                if candidate.is_file():
                    log_path = candidate

            if log_path is not None and log_path.is_file():
                try:
                    with log_path.open("rb") as f:
                        f.seek(log_position)
                        new_bytes = f.read()
                        if new_bytes:
                            log_position = f.tell()
                            new_content = new_bytes.decode("utf-8", errors="replace")
                            yield {
                                "event": "output",
                                "data": json.dumps({"text": new_content}),
                            }
                except OSError:
                    pass

            if current_status.get("status") in _TERMINAL_STATUSES:
                # Flush any remaining log bytes before closing
                if log_path is not None and log_path.is_file():
                    try:
                        with log_path.open("rb") as f:
                            f.seek(log_position)
                            final_bytes = f.read()
                            if final_bytes:
                                final_content = final_bytes.decode("utf-8", errors="replace")
                                yield {
                                    "event": "output",
                                    "data": json.dumps({"text": final_content}),
                                }
                    except OSError:
                        pass

                yield {"event": "done", "data": ""}

                logger.debug(
                    f"SSE stream closing for {simulation_id}: "
                    f"terminal status '{current_status.get('status')}'"
                )
                break

            await asyncio.sleep(0.5)

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/simulations/{simulation_id}/logs")
async def stream_simulation_logs(
    request: Request,
    sim_path: Path = Depends(get_simulation_path),
    simulation_id: str = "",
) -> EventSourceResponse:
    """Stream parsed log entries via SSE until the simulation reaches a terminal status."""

    async def event_generator():
        log_path = sim_path / "output.log"
        log_position = 0

        logger.debug(f"Starting log stream for simulation {simulation_id}")

        try:
            while True:
                if await request.is_disconnected():
                    logger.debug(f"Log stream client disconnected for simulation {simulation_id}")
                    break

                if not log_path.exists():
                    await asyncio.sleep(0.5)
                    continue

                try:
                    with log_path.open("rb") as f:
                        f.seek(log_position)
                        new_bytes = f.read()

                        if new_bytes:
                            log_position = f.tell()
                            new_content = new_bytes.decode("utf-8", errors="replace")

                            for line in new_content.splitlines():
                                if line.strip():
                                    log_entry = parse_log_line(line)
                                    yield {"event": "log", "data": json.dumps(log_entry)}
                except OSError as e:
                    logger.warning(
                        f"I/O error reading log file for simulation {simulation_id} at position {log_position}: "
                        f"{type(e).__name__}: {str(e)}"
                    )
                    await asyncio.sleep(1)
                    continue

                status_data = _get_status_data(sim_path, simulation_id)
                if status_data.get("status") in _TERMINAL_STATUSES:
                    # Flush remaining log bytes before closing
                    try:
                        with log_path.open("rb") as f:
                            f.seek(log_position)
                            final_bytes = f.read()
                            if final_bytes:
                                final_content = final_bytes.decode("utf-8", errors="replace")
                                for line in final_content.splitlines():
                                    if line.strip():
                                        log_entry = parse_log_line(line)
                                        yield {"event": "log", "data": json.dumps(log_entry)}
                    except OSError as e:
                        logger.warning(
                            f"I/O error during final log flush for simulation {simulation_id}: "
                            f"{type(e).__name__}: {str(e)}"
                        )

                    yield {"event": "done", "data": ""}
                    logger.debug(
                        f"Log stream closing for simulation {simulation_id}: "
                        f"terminal status '{status_data.get('status')}' reached"
                    )
                    break

                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(
                f"Unexpected error in log stream for simulation {simulation_id}: "
                f"{type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            raise

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/api/simulations/{simulation_id}", status_code=200)
def delete_simulation(
    sim_path: Path = Depends(get_simulation_path), simulation_id: str = ""
) -> dict[str, str]:
    """Permanently delete a simulation directory and all its output."""
    try:
        shutil.rmtree(sim_path)
        logger.info(f"Deleted simulation: {simulation_id}")
        return {"message": "deleted", "simulation_id": simulation_id}
    except Exception:
        logger.exception(f"Failed to delete simulation {simulation_id}")
        raise HTTPException(status_code=500, detail="Failed to delete simulation")


@router.delete("/api/simulations", status_code=200)
def delete_multiple_simulations(
    simulation_ids: list[str] = Body(..., embed=True),
) -> dict[str, Any]:
    """Batch-delete simulations; returns lists of deleted IDs and failures."""
    deleted = []
    failed = []

    for simulation_id in simulation_ids:
        try:
            if not all(c.isalnum() or c in "_-" for c in simulation_id):
                failed.append({"simulation_id": simulation_id, "error": "Invalid simulation ID"})
                continue

            sim_path = secure_join(OUTPUT_DIR, simulation_id)

            if not sim_path.is_dir():
                failed.append({"simulation_id": simulation_id, "error": "Simulation not found"})
                continue

            shutil.rmtree(sim_path)
            deleted.append(simulation_id)
            logger.info(f"Deleted simulation: {simulation_id}")

        except Exception as e:
            logger.exception(f"Failed to delete simulation {simulation_id}")
            failed.append({"simulation_id": simulation_id, "error": str(e)})

    return {"deleted": deleted, "failed": failed}


@router.patch("/api/simulations/{simulation_id}/rename", status_code=200)
def rename_simulation(
    simulation_id: str,
    display_name: str = Body(..., embed=True),
    sim_path: Path = Depends(get_simulation_path),
) -> dict[str, str]:
    """Update the display_name field in a simulation's config.json."""
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


@router.post("/api/simulations/{simulation_id}/stop", status_code=200)
def stop_simulation(simulation_id: str) -> dict[str, str]:
    """Stop a simulation via Celery revoke or process termination."""
    status_path = OUTPUT_DIR / simulation_id / "status.json"

    # Celery revocation
    if status_path.exists():
        try:
            with status_path.open() as f:
                status_data = json.load(f)
            celery_task_id = status_data.get("celery_task_id")
            if celery_task_id and status_data.get("status") in ("queued", "running"):
                from celery.result import AsyncResult

                from intellifl.celery_app import app as celery_app

                result = AsyncResult(celery_task_id, app=celery_app)
                result.revoke(terminate=True)
                logger.info(f"Revoked Celery task {celery_task_id} for {simulation_id}")

                status_data["status"] = "stopped"
                status_data["stopped_at"] = datetime.datetime.now(tz=datetime.UTC).isoformat()
                with status_path.open("w") as f:
                    json.dump(status_data, f, indent=2)
                return {"message": "stopped", "simulation_id": simulation_id}
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Could not read status for Celery revocation: {e}")
        except Exception as e:
            logger.warning(f"Celery revocation failed, trying process termination: {e}")

    # Fallback: process-based termination
    parent = _find_simulation_process(simulation_id)

    if parent is None:
        if status_path.exists():
            try:
                with status_path.open() as f:
                    status_data = json.load(f)
                if status_data.get("status") == "running":
                    status_data["status"] = "stopped"
                    status_data["stopped_at"] = datetime.datetime.now(tz=datetime.UTC).isoformat()
                    status_data["error"] = "Process terminated unexpectedly"
                    with status_path.open("w") as f:
                        json.dump(status_data, f, indent=2)
                    logger.info(f"Marked orphaned simulation {simulation_id} as stopped")
                    return {"message": "stopped", "simulation_id": simulation_id}
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to update orphaned status for {simulation_id}: {e}")

        raise HTTPException(status_code=404, detail="Simulation is not running or does not exist.")

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
        logger.info(f"Simulation {simulation_id} already terminated")
        return {"message": "stopped", "simulation_id": simulation_id}
    except Exception:
        logger.exception(f"Failed to stop simulation {simulation_id}")
        raise HTTPException(status_code=500, detail="Failed to stop simulation")
