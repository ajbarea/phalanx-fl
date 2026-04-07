#!/usr/bin/env python3
"""Federated learning simulation runner.

Configures the Ray environment for minimal logging overhead and runs the
simulation. Provides clear error reporting and logs output to file.
"""

import os
import subprocess
import sys

from logging_utils import setup_logger

logger = setup_logger(__name__, "sim.log")

# Ray environment overrides for cleaner output and reduced overhead
RAY_ENV = {
    "RAY_ENABLE_METRICS_COLLECTION": "0",
    "RAY_METRICS_EXPORT_PORT_ENABLED": "0",
    "RAY_enable_export_api_write": "0",
    "RAY_BACKEND_LOG_LEVEL": "fatal",
    "RAY_DEDUP_LOGS_SKIP_REGEX": r"logging\.cc.*Set ray log level",
}


def main() -> int:
    """Run the federated learning simulation.

    Returns:
        0 on success, 1 on failure.
    """
    print("\n🚀 Federated Learning Simulation")
    print("=" * 60)
    logger.info("Starting simulation...")

    env = {**os.environ, **RAY_ENV}
    cmd = [sys.executable, "-m", "intellifl.simulation_runner"]

    try:
        result = subprocess.run(cmd, env=env, check=False)

        if result.returncode == 0:
            print("\n" + "=" * 60)
            print("✓ Simulation completed successfully")
            print("  Results saved to out/")
            print("=" * 60 + "\n")
            logger.info("Simulation completed successfully")
            return 0
        else:
            print("\n" + "=" * 60)
            print(f"✗ Simulation failed (exit code {result.returncode})")
            print("  Check logs/sim.log and console output for details")
            print("=" * 60 + "\n")
            logger.error(f"Simulation failed with exit code {result.returncode}")
            return 1

    except FileNotFoundError:
        print("\n✗ Python interpreter not found")
        logger.error("Python interpreter not found")
        return 1
    except KeyboardInterrupt:
        print("\n⚠  Simulation interrupted by user")
        logger.warning("Simulation interrupted by user")
        return 130


if __name__ == "__main__":
    sys.exit(main())
