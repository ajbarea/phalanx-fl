#!/usr/bin/env python
"""Setup script for Phalanx framework.

Orchestrates the complete project setup including dependency installation,
dataset preparation, and optional frontend setup. Gracefully handles missing
tools like npm by skipping their setup steps.
"""

import shutil
import subprocess
import sys
from pathlib import Path

from logging_utils import setup_logger

logger = setup_logger(__name__, "setup.log")


def run_step(cmd: list[str], description: str, cwd: Path | None = None) -> bool:
    """Execute a setup step, printing progress and logging to file.

    Args:
        cmd: Command and arguments as a list of strings.
        description: Human-readable description for display and logging.
        cwd: Working directory. If None, uses current directory.

    Returns:
        True if the step succeeded or was skipped, False on failure.
    """
    print(f"  ▶ {description}...")
    logger.info(f"Running: {description}")
    try:
        result = subprocess.run(
            cmd,
            check=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
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
    except FileNotFoundError:
        print(f"  ⚠  {description} skipped (command not found)")
        logger.warning(f"Skipped: {description} — command not found in PATH")
        return True


def find_npm() -> str | None:
    """Return the resolved npm executable path, if available."""
    npm_path = shutil.which("npm")
    if not npm_path:
        return None

    try:
        result = subprocess.run(
            [npm_path, "--version"],
            capture_output=True,
            check=False,
            timeout=5,
            text=True,
            encoding="utf-8",
        )
        return npm_path if result.returncode == 0 else None
    except subprocess.TimeoutExpired:
        return None


def main() -> int:
    """Execute the complete setup workflow.

    Returns:
        0 on success, 1 on failure.
    """
    print("\n⚙️  Phalanx Setup")
    print("=" * 60)
    logger.info("Starting Phalanx setup...")

    project_root = Path(__file__).parent.parent

    steps: list[tuple[list[str], str, Path | None]] = [
        (["uv", "sync", "--locked"], "Installing dependencies", None),
        (
            [sys.executable, str(project_root / "scripts" / "setup_datasets.py")],
            "Setting up datasets",
            None,
        ),
    ]

    frontend_dir = project_root / "frontend"
    npm_path = find_npm()
    if frontend_dir.exists():
        if npm_path:
            steps.append(([npm_path, "install"], "Installing frontend dependencies", frontend_dir))
        else:
            print("  ⚠  Frontend directory exists but npm not found — skipping")
            logger.warning("frontend directory exists but npm not found — skipping frontend setup")

    for cmd, description, cwd in steps:
        if not run_step(cmd, description, cwd=cwd):
            print("\n" + "=" * 60)
            print("✗ Setup failed")
            print("=" * 60 + "\n")
            logger.error("Setup failed")
            return 1

    print("\n" + "=" * 60)
    print("✓ Setup completed successfully")
    print("=" * 60 + "\n")
    logger.info("Setup completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
