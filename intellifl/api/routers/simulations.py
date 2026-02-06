"""Simulation CRUD and status router."""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import shutil
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

import pandas as pd
import psutil
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from intellifl.api.dependencies import (
    OUTPUT_DIR,
    get_simulation_path,
    secure_join,
)
from intellifl.api.models import CreateSimulationRequest, SimulationStatusResponse

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

            if raw_status in ["running", "queued"] and pid:
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

    log_path = sim_path / "output.log"
    if log_path.is_file():
        try:
            with log_path.open("r") as f:
                error_content = f.read(1024)
            if error_content.strip():
                return {"status": "failed", "progress": 0.0}
        except OSError:
            pass

    return {"status": "pending", "progress": 0.0}


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


@router.get("/api/simulations", response_model=list[SimulationMetadata])
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


@router.get("/api/simulations/{simulation_id}", response_model=SimulationDetails)
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


@router.get("/api/simulations/{simulation_id}/config")
def get_simulation_config(
    sim_path: Path = Depends(get_simulation_path),
) -> dict[str, Any]:
    """Retrieves just the configuration for a specific simulation.

    Args:
        sim_path: The validated path to the simulation directory.

    Returns:
        The simulation's config.json contents as a dictionary.

    Raises:
        HTTPException: If the configuration file cannot be read.
    """
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


# ---------------------------------------------------------------------------
# Subprocess execution backend (used when Celery/Redis is unavailable)
# ---------------------------------------------------------------------------


def _launch_subprocess(config_filepath: Path) -> None:
    """Fire-and-forget launch of simulation_runner as an async subprocess."""
    log_path = config_filepath.parent / "output.log"
    log_file = log_path.open("a")
    project_root = Path(__file__).resolve().parents[3]
    loop = asyncio.get_running_loop()
    loop.create_task(_run_subprocess(config_filepath, log_file, project_root))


async def _run_subprocess(config_filepath: Path, log_file: Any, project_root: Path) -> None:
    """Run simulation_runner as an async subprocess — mirrors the Celery task."""
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "intellifl.simulation_runner",
            str(config_filepath),
            "--origin",
            "api",
            stdout=log_file,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(project_root),
        )
        await proc.wait()
    except Exception:
        logger.exception(f"Subprocess execution failed for {config_filepath.parent.name}")
    finally:
        log_file.close()


@router.post("/api/simulations", status_code=201)
async def create_simulation(request: CreateSimulationRequest) -> dict[str, Any]:
    """Creates and initiates a new simulation based on the provided configuration.

    Args:
        request: Validated simulation configuration request.

    Returns:
        A dictionary containing the simulation ID of the created or updated run.

    Raises:
        HTTPException: If the simulation process fails to start or config cannot be written.
    """
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

    # Try Celery+Redis first; fall back to direct subprocess if unavailable.
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

        task = run_simulation.delay(str(config_filepath))  # type: ignore
        celery_task_id = task.id
        logger.info(f"Celery: queued simulation {simulation_id} (task_id: {celery_task_id})")
    except Exception as celery_err:
        # Redis unavailable or Celery not installed — subprocess fallback
        logger.info(f"Celery unavailable ({celery_err!r}), using subprocess for {simulation_id}")
        _launch_subprocess(config_filepath)
    # Create initial status.json
    try:
        total_strategies = len(wrapped_config.get("simulation_strategies", [1]))
        initial_status = {
            "status": "queued",
            "progress": 0.0,
            "current_strategy": 0,
            "total_strategies": total_strategies,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "origin": "api",
        }
        if celery_task_id:
            initial_status["celery_task_id"] = celery_task_id
        with status_filepath.open("w") as f:
            json.dump(initial_status, f, indent=2)
    except OSError as e:
        logger.warning(f"Failed to create initial status.json: {e}")

    return {"simulation_id": simulation_id}


@router.get("/api/simulations/{simulation_id}/status", response_model=SimulationStatusResponse)
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
    """Stream simulation status and output via Server-Sent Events.

    Sends two event types:
    - ``status``: JSON with status, progress, round/strategy info (on change)
    - ``output``: JSON with ``{"text": "..."}`` containing new log output

    The stream closes once the simulation reaches a terminal status
    (completed, failed, stopped).
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

            # Find log file if not yet found
            if log_path is None:
                candidate = sim_path / "output.log"
                if candidate.is_file():
                    log_path = candidate

            # Stream new output from log file
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
                # Final output flush after terminal status
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


@router.delete("/api/simulations/{simulation_id}", status_code=200)
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
            if not all(c.isalnum() or c == "_" for c in simulation_id):
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


@router.post("/api/simulations/{simulation_id}/stop", status_code=200)
def stop_simulation(simulation_id: str) -> dict[str, str]:
    """Terminates a running simulation and all its child processes.

    Supports both Celery tasks (revoke) and legacy subprocess termination.

    Args:
        simulation_id: The simulation identifier.

    Returns:
        A confirmation message.

    Raises:
        HTTPException: If the simulation is not running or does not exist.
    """
    status_path = OUTPUT_DIR / simulation_id / "status.json"

    # Try Celery task revocation first
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

                # Update status.json
                status_data["status"] = "stopped"
                status_data["stopped_at"] = datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat()
                with status_path.open("w") as f:
                    json.dump(status_data, f, indent=2)
                return {"message": "stopped", "simulation_id": simulation_id}
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Could not read status for Celery revocation: {e}")
        except Exception as e:
            logger.warning(f"Celery revocation failed, trying process termination: {e}")

    # Fallback: process-based termination (find by PID or cmdline pattern)
    parent = _find_simulation_process(simulation_id)

    if parent is None:
        if status_path.exists():
            try:
                with status_path.open() as f:
                    status_data = json.load(f)
                if status_data.get("status") == "running":
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
