#!/usr/bin/env python3
"""Upgrade all project dependencies to their latest versions."""

import subprocess
import sys

from logging_utils import setup_logger

logger = setup_logger(__name__, "upgrade.log")


def run_step(cmd: list[str], description: str) -> bool:
    """Execute an upgrade step, printing progress and logging to file.

    Args:
        cmd: Command and arguments as a list of strings.
        description: Human-readable description for display and logging.

    Returns:
        True if the step succeeded, False on failure.
    """
    print(f"  ▶ {description}...")
    logger.info(f"Running: {description}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")
        print(f"  ✓ {description}")
        logger.info(f"✓ {description} completed")
        if result.stdout:
            logger.debug(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ {description} failed (exit code {e.returncode})")
        logger.error(f"Failed: {description} (exit code {e.returncode})")
        if e.stdout:
            logger.debug(f"stdout: {e.stdout.strip()}")
        if e.stderr:
            logger.debug(f"stderr: {e.stderr.strip()}")
        return False


def main() -> int:
    """Update lockfile and sync all dependencies.

    Returns:
        0 on success, 1 on failure.
    """
    print("\n🔄 IntelliFL Upgrade")
    print("=" * 60)
    logger.info("Starting dependency upgrade...")

    steps = [
        (["uv", "lock", "--upgrade"], "Updating lockfile"),
        (["uv", "sync"], "Syncing dependencies"),
    ]

    for cmd, description in steps:
        if not run_step(cmd, description):
            print("\n" + "=" * 60)
            print("✗ Upgrade failed")
            print("=" * 60 + "\n")
            logger.error("Upgrade failed")
            return 1

    print("\n" + "=" * 60)
    print("✓ Upgrade completed successfully")
    print("=" * 60 + "\n")
    logger.info("Upgrade completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
