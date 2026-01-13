"""Ray configuration with platform-specific workarounds for FL simulations."""

import logging
import os
import platform
from typing import Any

import ray

logger = logging.getLogger(__name__)


class RayConfig:
    """Platform-aware Ray initialization for FL simulations."""

    @staticmethod
    def get_init_args() -> dict[str, Any]:
        """Generate ray.init() arguments with platform-specific fixes.

        Returns:
            Arguments for ray.init() with OS-appropriate settings.
        """
        ray_args: dict[str, Any] = {
            "include_dashboard": False,
            "ignore_reinit_error": True,
            "configure_logging": True,
            "logging_level": logging.INFO,
        }

        # Suppress Ray 2.0+ accelerator warning for cleaner output
        os.environ["RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO"] = "0"

        system_os = platform.system()

        if system_os == "Windows":
            logger.info("Platform detected: Windows. Applying stability patches.")
            # Metrics agent fails to bind ports/init gRPC on Windows (RpcError: 14)
            # Reference: https://github.com/ray-project/ray/issues/46453
            ray_args["_system_config"] = {
                "enable_metrics_collection": False,
            }
        elif system_os == "Linux":
            logger.debug("Platform detected: Linux. Using standard configuration.")
        elif system_os == "Darwin":
            logger.debug("Platform detected: macOS. Using standard configuration.")
        else:
            logger.warning(
                f"Unrecognized operating system '{system_os}'. "
                "Proceeding with default Ray configuration."
            )

        return ray_args

    @staticmethod
    def initialize() -> None:
        """Initialize Ray runtime with platform-appropriate configuration."""
        if ray.is_initialized():
            logger.info("Ray runtime is already active. Skipping initialization.")
            return

        config = RayConfig.get_init_args()
        logger.info(f"Initializing Ray runtime with configuration: {config}")

        try:
            context = ray.init(**config)
            logger.info(
                f"Ray initialized successfully. "
                f"Version: {ray.__version__}, Address: {context.address_info.get('node_ip_address')}"
            )
        except Exception as e:
            logger.error(f"Critical failure initializing Ray runtime: {e}")
            raise
