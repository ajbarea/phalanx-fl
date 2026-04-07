#!/usr/bin/env python3
"""Test suite runner with coverage reporting.

Runs unit, integration, and performance tests with coverage accumulation.
Generates XML coverage report consumed by CI.
"""

import re
import subprocess
import sys
from pathlib import Path

from logging_utils import setup_logger

logger = setup_logger(__name__, "test.log")


def run_suite(cmd: list[str], description: str) -> tuple[bool, str]:
    """Execute a test suite and return (passed, output).

    Args:
        cmd: Command and arguments as a list.
        description: Human-readable description for logging.

    Returns:
        (True if successful, False otherwise), combined stdout+stderr.
    """
    logger.info(f"Running: {description}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")
        output = (result.stdout + result.stderr).strip()
        logger.info(f"✓ {description} passed")
        if output:
            logger.debug(output)
        return True, output
    except subprocess.CalledProcessError as e:
        output = (e.stdout + e.stderr).strip()
        logger.error(f"✗ {description} failed (exit code: {e.returncode})")
        if output:
            logger.error(output)
        return False, output
    except FileNotFoundError:
        logger.error(f"✗ {description} — command not found")
        return False, ""


def parse_pytest_summary(output: str) -> str:
    """Extract the short result line from pytest output.

    Args:
        output: Combined pytest stdout/stderr.

    Returns:
        Summary string like '2155 passed, 2 skipped in 48.98s'.
    """
    match = re.search(r"=+ (.+?) =+\s*$", output, re.MULTILINE)
    if match:
        return match.group(1).strip()
    for line in reversed(output.splitlines()):
        if any(kw in line for kw in ("passed", "failed", "error")):
            return line.strip()
    return ""


def main() -> int:
    """Run full test suite with coverage.

    Returns:
        0 if all tests pass, 1 if any fail.
    """
    print("\n🧪 Test Suite")
    print("=" * 60)
    logger.info("Starting test suite...")

    log_dir = Path("tests/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    coverage_xml = log_dir / "coverage.xml"

    suites: list[tuple[list[str], str]] = [
        (
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/unit/",
                "-n",
                "auto",
                "--tb=short",
                "-q",
                "--no-header",
                "--cov=intellifl",
                f"--cov-report=xml:{coverage_xml}",
            ],
            "Unit tests",
        ),
        (
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/integration/",
                "--tb=short",
                "-q",
                "--no-header",
                "--cov=intellifl",
                "--cov-append",
                f"--cov-report=xml:{coverage_xml}",
            ],
            "Integration tests",
        ),
        (
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/performance/",
                "--tb=short",
                "-q",
                "--no-header",
                "--cov=intellifl",
                "--cov-append",
                f"--cov-report=xml:{coverage_xml}",
            ],
            "Performance tests",
        ),
    ]

    results: list[tuple[str, bool, str]] = []
    for i, (cmd, description) in enumerate(suites, 1):
        print(f"\n[{i}/{len(suites)}] {description}...")
        passed, output = run_suite(cmd, description)
        results.append((description, passed, output))

    # Summary
    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)

    print("\n" + "=" * 60)
    print("📋 Summary")
    print("=" * 60)
    for description, passed, output in results:
        status = "✓" if passed else "✗"
        summary = parse_pytest_summary(output)
        suffix = f" — {summary}" if summary else ""
        print(f"  {status} {description}{suffix}")

    print(f"\n  Coverage report: {coverage_xml}")
    print("=" * 60)

    if passed_count == total:
        print(f"✓ All tests passed ({passed_count}/{total})\n")
        logger.info(f"All tests passed ({passed_count}/{total})")
        return 0
    else:
        failed = total - passed_count
        print(f"✗ {failed}/{total} suites failed")
        print("  See logs/test.log for details\n")
        logger.error(f"{failed}/{total} suites failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
