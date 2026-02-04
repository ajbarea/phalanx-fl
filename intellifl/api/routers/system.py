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


@router.get("/api/health")
def health_check() -> dict[str, str]:
    """Health check endpoint for startup detection and monitoring."""
    return {"status": "healthy"}


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
