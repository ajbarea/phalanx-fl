#!/usr/bin/env python3
"""Quick validation: lint + unit tests for fast developer feedback."""

import re
import subprocess
import sys
from pathlib import Path

from logging_utils import setup_logger

logger = setup_logger(__name__, "validate.log")
LINT_SCRIPT = Path(__file__).with_name("lint.py")


def run_step(cmd: list[str], description: str) -> tuple[bool, str]:
    """Run a validation step and return (passed, output).

    Args:
        cmd: Command and arguments.
        description: Human-readable label for display and logging.

    Returns:
        (True if passed, False on failure), combined stdout+stderr.
    """
    print(f"  ▶ {description}...")
    logger.info(f"Running: {description}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    output = (result.stdout + result.stderr).strip()
    passed = result.returncode == 0
    if output:
        logger.debug(output)
    return passed, output


def parse_pytest_summary(output: str) -> str:
    """Extract the short result line from pytest output.

    Args:
        output: Combined pytest stdout/stderr.

    Returns:
        Summary line like '2155 passed, 2 skipped in 48.98s', or empty string.
    """
    match = re.search(r"(\d+ passed.*?)\s*={3,}", output)
    if match:
        return match.group(1).strip()
    # Fallback: last line containing 'passed' or 'failed'
    for line in reversed(output.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            return line.strip()
    return ""


def main() -> int:
    """Run lint and unit tests, report combined result.

    Returns:
        0 if all checks pass, 1 if any fail.
    """
    print("\n✅ Phalanx Validate")
    print("=" * 60)
    logger.info("Starting validation...")

    results: list[tuple[str, bool, str]] = []

    # Step 1: Lint
    passed, output = run_step(
        [sys.executable, str(LINT_SCRIPT)],
        "Lint",
    )
    if passed:
        print("  ✓ Lint")
    else:
        print("  ✗ Lint failed")
        if output:
            print()
            for line in output.splitlines():
                print(f"    {line}")
            print()
    logger.info(f"Lint: {'passed' if passed else 'FAILED'}")
    results.append(("Lint", passed, output))

    # Step 2: Unit tests
    passed, output = run_step(
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
        ],
        "Unit tests",
    )
    summary = parse_pytest_summary(output)
    if passed:
        print(f"  ✓ Unit tests — {summary}")
    else:
        print(f"  ✗ Unit tests — {summary}")
        # Show failures
        in_failure = False
        for line in output.splitlines():
            if line.startswith("FAILED") or line.startswith("ERROR"):
                in_failure = True
            if in_failure:
                print(f"    {line}")
    logger.info(f"Unit tests: {'passed' if passed else 'FAILED'} — {summary}")
    results.append(("Unit tests", passed, output))

    # Summary
    all_passed = all(p for _, p, _ in results)
    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)

    print("\n" + "=" * 60)
    if all_passed:
        print(f"✓ All checks passed ({passed_count}/{total})")
    else:
        print(f"✗ {total - passed_count}/{total} checks failed")
    print("=" * 60 + "\n")

    logger.info(f"Validation complete — {passed_count}/{total} passed")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
