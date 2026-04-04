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


def run_step(
    cmd: list[str], description: str, use_shell: bool = False, cwd: str | None = None
) -> bool:
    """Execute a setup step, printing progress and logging to file.

    Args:
        cmd: Command and arguments as a list of strings.
        description: Human-readable description for display and logging.
        use_shell: If True, run through system shell to inherit PATH.
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
            shell=use_shell,
            cwd=cwd,
            capture_output=True,
            text=True,
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


def has_npm() -> bool:
    """Check if npm is available and functional in PATH."""
    try:
        result = subprocess.run(
            "npm --version", capture_output=True, check=False, timeout=5, shell=True
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def main() -> int:
    """Execute the complete setup workflow.

    Returns:
        0 on success, 1 on failure.
    """
    print("\n⚙️  IntelliFL Setup")
    print("=" * 60)
    logger.info("Starting IntelliFL setup...")

    project_root = Path(__file__).parent.parent

    steps: list[tuple[list[str], str, bool, str | None]] = [
        (["uv", "sync"], "Installing dependencies", False, None),
        (["uv", "run", "python", "scripts/setup_datasets.py"], "Setting up datasets", False, None),
    ]

    frontend_dir = project_root / "frontend"
    if frontend_dir.exists():
        if has_npm():
            steps.append(
                (["npm", "install"], "Installing frontend dependencies", True, str(frontend_dir))
            )
        else:
            print("  ⚠  Frontend directory exists but npm not found — skipping")
            logger.warning("frontend directory exists but npm not found — skipping frontend setup")

    for cmd, description, use_shell, cwd in steps:
        if not run_step(cmd, description, use_shell=use_shell, cwd=cwd):
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
