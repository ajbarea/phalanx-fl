#!/usr/bin/env python3
"""Code quality checks and formatting.

Runs ruff format, ruff check, type checking with ty, and frontend linting.
Provides clear output and exits with appropriate status codes.
"""

import subprocess
import sys
from pathlib import Path

from logging_utils import setup_logger

logger = setup_logger(__name__, "lint.log")


def run_command(cmd: list[str], description: str, cwd: str | None = None) -> bool:
    """Execute a command and report results.

    Args:
        cmd: Command and arguments as a list.
        description: Human-readable description for logging.
        cwd: Working directory for the command (optional).

    Returns:
        True if successful, False otherwise.
    """
    logger.info(f"Running: {description}")
    try:
        # Use shell=True for npm commands to ensure PATH is properly resolved on Windows
        use_shell = cmd[0] == "npm"
        result = subprocess.run(
            cmd, check=True, capture_output=True, text=True, cwd=cwd, shell=use_shell
        )
        logger.info(f"✓ {description} passed")
        if result.stdout:
            logger.debug(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ {description} failed (exit code: {e.returncode})")
        if e.stdout:
            logger.error(f"STDOUT:\n{e.stdout}")
        if e.stderr:
            logger.error(f"STDERR:\n{e.stderr}")
        return False
    except FileNotFoundError:
        logger.error(f"✗ {description} - command not found")
        return False


def main() -> int:
    """Run all linting checks.

    Returns:
        0 if all checks pass, 1 if any fail.
    """
    print("\n🔍 Code Quality Checks")
    print("=" * 60)
    logger.info("Starting code quality checks...")

    checks = [
        (["uv", "run", "--no-active", "ruff", "format", "."], "Ruff format", None),
        (
            ["uv", "run", "--no-active", "ruff", "check", "--fix", "--unsafe-fixes", "."],
            "Ruff check",
            None,
        ),
        (
            ["uv", "run", "--no-active", "ty", "check", "intellifl", "tests"],
            "Type checking (ty)",
            None,
        ),
    ]

    # Add frontend linting if frontend directory exists
    frontend_dir = Path("frontend")
    if frontend_dir.exists():
        checks.append((["npm", "run", "lint"], "Frontend linting", "frontend"))

    results = []
    for i, (cmd, description, cwd) in enumerate(checks, 1):
        print(f"\n[{i}/{len(checks)}] {description}...")
        results.append(run_command(cmd, description, cwd))

    # Summary
    passed = sum(results)
    total = len(results)

    print("\n" + "=" * 60)
    print("📋 Summary")
    print("=" * 60)
    for (_, description, _), result in zip(checks, results, strict=False):
        status = "✓" if result else "✗"
        print(f"  {status} {description}")

    print("=" * 60)
    if passed == total:
        print(f"✓ All checks passed ({passed}/{total})\n")
        logger.info("All checks passed")
        return 0
    else:
        print(f"✗ Some checks failed ({passed}/{total})")
        print("   See logs/lint.log for details\n")
        logger.error(f"Some checks failed ({passed}/{total})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
