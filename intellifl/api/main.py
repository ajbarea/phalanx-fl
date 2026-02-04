"""IntelliFL API - FastAPI application for federated learning simulation management."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles the application lifespan events (startup and shutdown).

    Note: Simulation execution is now handled by Celery workers, not an async task.
    Start workers with: celery -A intellifl.celery_app worker --loglevel=info
    """
    logger.info("Federated Learning API initialized")
    logger.info(
        "Simulations are executed by Celery workers (start with: celery -A intellifl.celery_app worker)"
    )
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

app.include_router(assistant_router)
app.include_router(queue_router)
app.include_router(system_router)
app.include_router(simulations_router)
app.include_router(visualizations_router)
app.include_router(datasets_router)
app.include_router(terminal_router)
