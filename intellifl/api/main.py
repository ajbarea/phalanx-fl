"""Phalanx API - FastAPI application for federated learning simulation management."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parents[2] / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from intellifl.utils.warnings_config import apply_env_vars, configure_warnings

apply_env_vars()
configure_warnings()

from intellifl.api.routers.assistant import router as assistant_router
from intellifl.api.routers.datasets import router as datasets_router
from intellifl.api.routers.queue import router as queue_router
from intellifl.api.routers.simulations import router as simulations_router
from intellifl.api.routers.system import router as system_router
from intellifl.api.routers.terminal import router as terminal_router
from intellifl.api.routers.visualizations import router as visualizations_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _recover_orphaned_simulations() -> None:
    """Re-enqueue simulations left queued/running after an unclean shutdown."""
    from intellifl.api.dependencies import OUTPUT_DIR

    if not OUTPUT_DIR.is_dir():
        return

    try:
        from intellifl.celery_app import app as celery_app

        conn = celery_app.connection()
        try:
            conn.ensure_connection(max_retries=0, timeout=2)
        finally:
            conn.close()
    except Exception:
        logger.info("Celery/Redis not available — skipping orphan recovery")
        return

    import psutil
    from celery.result import AsyncResult

    from intellifl.tasks.simulation_tasks import run_simulation

    recovered = 0
    for sim_dir in OUTPUT_DIR.iterdir():
        if not sim_dir.is_dir():
            continue
        status_path = sim_dir / "status.json"
        config_path = sim_dir / "config.json"
        if not status_path.is_file() or not config_path.is_file():
            continue

        try:
            with status_path.open() as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        raw_status = data.get("status")
        if raw_status not in ("queued", "running"):
            continue

        result_files = list(sim_dir.glob("*.pdf")) + list(sim_dir.glob("csv/*.csv"))
        if result_files:
            continue

        pid = data.get("pid")
        celery_task_id = data.get("celery_task_id")

        if raw_status == "queued" and pid is None and data.get("origin") == "api":
            # Celery returns PENDING for unknown task IDs, so it can't distinguish
            # "waiting in queue" from "never existed". Only STARTED/RETRY are trustworthy.
            task_alive = False
            if celery_task_id:
                with suppress(Exception):
                    result = AsyncResult(celery_task_id, app=celery_app)
                    task_alive = result.state in ("STARTED", "RETRY")

            if task_alive:
                continue  # Worker is actively processing — leave it.

            # Revoke stale task (no-op if already gone) and re-enqueue.
            if celery_task_id:
                with suppress(Exception):
                    AsyncResult(celery_task_id, app=celery_app).revoke()
            try:
                task = run_simulation.delay(str(config_path))  # type: ignore[attr-defined]
                data["celery_task_id"] = task.id
                data["status"] = "queued"
                with status_path.open("w") as f:
                    json.dump(data, f, indent=2)
                recovered += 1
                logger.info(f"Re-enqueued orphaned simulation {sim_dir.name} (new task: {task.id})")
            except Exception as e:
                logger.warning(f"Failed to re-enqueue {sim_dir.name}: {e}")

        elif raw_status == "running" and pid is not None:
            # Dead process with no results — mark failed so the UI doesn't show a phantom "running" state.
            process_alive = False
            with suppress(Exception):
                process_alive = psutil.pid_exists(pid)
            if not process_alive:
                try:
                    data["status"] = "failed"
                    data["error"] = "Process was interrupted (e.g. PC restart or crash)"
                    with status_path.open("w") as f:
                        json.dump(data, f, indent=2)
                    logger.info(f"Marked crashed simulation {sim_dir.name} as failed")
                except Exception as e:
                    logger.warning(f"Failed to mark {sim_dir.name} as failed: {e}")
        # else: leave alone — ambiguous state, let Celery or the user resolve it.

    if recovered:
        logger.info(f"Recovered {recovered} orphaned simulation(s)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks (orphan recovery) and log readiness."""
    logger.info("Federated Learning API initialized")
    logger.info(
        "Simulations are executed by Celery workers (start with: celery -A intellifl.celery_app worker)"
    )
    _recover_orphaned_simulations()
    yield


app = FastAPI(title="Phalanx API", lifespan=lifespan)

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

app.include_router(assistant_router)
app.include_router(queue_router)
app.include_router(system_router)
app.include_router(simulations_router)
app.include_router(visualizations_router)
app.include_router(datasets_router)
app.include_router(terminal_router)
