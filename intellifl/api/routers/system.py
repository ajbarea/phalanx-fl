"""System information and health check router."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


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


@router.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Federated Learning Simulation Framework API"}


class HealthResponse(BaseModel):
    """Health check response with service statuses."""

    status: str
    redis: str
    celery_workers: int
    execution_mode: str


@router.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Health check endpoint including Redis and Celery worker status."""
    redis_status = "unavailable"
    worker_count = 0

    try:
        from intellifl.celery_app import app as celery_app

        # Check Redis broker connectivity
        conn = celery_app.connection()
        try:
            conn.ensure_connection(max_retries=0, timeout=1)
            redis_status = "connected"
        except Exception:
            pass
        finally:
            conn.close()

        # Check active Celery workers
        if redis_status == "connected":
            try:
                inspect = celery_app.control.inspect(timeout=1)
                active = inspect.active()
                if active:
                    worker_count = len(active)
            except Exception:
                pass

    except ImportError:
        redis_status = "celery_not_installed"

    overall = "healthy" if redis_status == "connected" else "degraded"
    execution_mode = "celery" if redis_status == "connected" else "subprocess"

    return HealthResponse(
        status=overall,
        redis=redis_status,
        celery_workers=worker_count,
        execution_mode=execution_mode,
    )


@router.get("/api/system/devices", response_model=SystemDevicesResponse)
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
        pass

    return result
