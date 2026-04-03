#!/usr/bin/env python
"""Setup script for IntelliFL framework.

Orchestrates the complete project setup including dependency installation,
dataset preparation, and optional frontend setup. Gracefully handles missing
tools like npm by skipping their setup steps.
"""

import subprocess
import sys
from pathlib import Path

from logging_utils import setup_logger

logger = setup_logger(__name__, "setup.log")


def run_command(
    cmd: list[str], description: str, use_shell: bool = False, cwd: str | None = None
) -> bool:
    """Execute a shell command with error handling.

    Args:
        cmd: Command and arguments as a list of strings.
        description: Human-readable description of the command for logging.
        use_shell: If True, run through system shell to inherit PATH.
        cwd: Working directory to run command in. If None, uses current directory.

    Returns:
        True if command succeeded or was skipped due to missing tool.
        False if command failed with an error.
    """
    logger.info(f"Running: {description}")
    try:
        subprocess.run(cmd, check=True, shell=use_shell, cwd=cwd)
        logger.info(f"✓ {description} completed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        if isinstance(e, FileNotFoundError):
            logger.warning(f"Skipped {description} - command not found in PATH")
            return True
        logger.error(f"Failed: {description} (exit code {e.returncode})")
        return False


def has_npm() -> bool:
    """Check if npm is available and functional in PATH.

    Uses system shell to properly inherit PATH on all platforms.

    Returns:
        True if npm can be executed, False otherwise.
    """
    try:
        result = subprocess.run(
            "npm --version", capture_output=True, check=False, timeout=5, shell=True
        )
        available = result.returncode == 0
        if available:
            logger.info("npm is available")
        else:
            logger.warning("npm not found in PATH")
        return available
    except subprocess.TimeoutExpired:
        logger.warning("npm check timed out")
        return False


def main() -> int:
    """Execute the complete setup workflow.

    Returns:
        0 on success, 1 on failure.
    """
    logger.info("Starting IntelliFL setup...")
    project_root = Path(__file__).parent.parent

    logs_dir = project_root / "tests" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Logs directory: {logs_dir}")

    steps = [
        (["uv", "sync"], "Installing dependencies", False, None),
        (["uv", "run", "python", "scripts/setup_datasets.py"], "Setting up datasets", False, None),
    ]

    frontend_dir = project_root / "frontend"
    if frontend_dir.exists() and has_npm():
        steps.append(
            (["npm", "install"], "Installing frontend dependencies", True, str(frontend_dir))
        )
    elif frontend_dir.exists():
        logger.warning("frontend directory exists but npm not found - skipping frontend setup")

    for cmd, description, use_shell, cwd in steps:
        if not run_command(cmd, description, use_shell=use_shell, cwd=cwd):
            logger.error("Setup failed")
            return 1

    logger.info("Setup completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
