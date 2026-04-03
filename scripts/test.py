#!/usr/bin/env python3
"""Test suite runner with coverage reporting.

Runs unit, integration, and performance tests with coverage accumulation.
Generates XML and terminal coverage reports.
"""

import subprocess
import sys
from pathlib import Path

from logging_utils import setup_logger

logger = setup_logger(__name__, "test.log")


def run_command(cmd: list[str], description: str) -> bool:
    """Execute a command and report results.

    Args:
        cmd: Command and arguments as a list.
        description: Human-readable description for logging.

    Returns:
        True if successful, False otherwise.
    """
    logger.info(f"Running: {description}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
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
    """Run full test suite with coverage.

    Returns:
        0 if all tests pass, 1 if any fail.
    """
    print("\n🧪 Test Suite")
    print("=" * 60)
    logger.info("Starting test suite...")

    # Create logs directory
    log_dir = Path("tests/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Logs directory: {log_dir}")

    coverage_xml = log_dir / "coverage.xml"
    coverage_report = "term-missing"

    tests = [
        (
            [
                "uv",
                "run",
                "--no-active",
                "pytest",
                "tests/unit/",
                "-n",
                "auto",
                "-v",
                "--tb=short",
                "--cov=intellifl",
                f"--cov-report=xml:{coverage_xml}",
                f"--cov-report={coverage_report}",
            ],
            "Unit tests",
        ),
        (
            [
                "uv",
                "run",
                "--no-active",
                "pytest",
                "tests/integration/",
                "-v",
                "--tb=short",
                "--cov=intellifl",
                "--cov-append",
                f"--cov-report=xml:{coverage_xml}",
            ],
            "Integration tests",
        ),
        (
            [
                "uv",
                "run",
                "--no-active",
                "pytest",
                "tests/performance/",
                "-v",
                "--tb=short",
                "--cov=intellifl",
                "--cov-append",
                f"--cov-report=xml:{coverage_xml}",
                f"--cov-report={coverage_report}",
            ],
            "Performance tests",
        ),
    ]

    results = []
    for i, (cmd, description) in enumerate(tests, 1):
        print(f"\n[{i}/{len(tests)}] {description}...")
        results.append(run_command(cmd, description))

    # Summary
    passed = sum(results)
    total = len(results)

    print("\n" + "=" * 60)
    print("📋 Summary")
    print("=" * 60)
    for (_, description), result in zip(tests, results, strict=False):
        status = "✓" if result else "✗"
        print(f"  {status} {description}")

    print(f"\n  Coverage report: {coverage_xml}")
    print("=" * 60)

    if passed == total:
        print(f"✓ All tests passed ({passed}/{total})\n")
        logger.info("All tests passed")
        return 0
    else:
        print(f"✗ Some tests failed ({passed}/{total})")
        print("   See logs/test.log for details\n")
        logger.error(f"Some tests failed ({passed}/{total})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
