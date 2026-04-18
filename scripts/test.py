#!/usr/bin/env python3
"""Test suite runner with coverage reporting.

Runs unit, integration, and performance tests with coverage accumulation.
Supports running individual suites via --unit, --integration, --performance flags.
Generates XML coverage report consumed by CI.

Usage:
    python scripts/test.py              # Run all suites (with lint first)
    python scripts/test.py --unit       # Unit tests only
    python scripts/test.py --integration  # Integration tests only
    python scripts/test.py --performance  # Performance tests only
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from intellifl.dev_runner import (
    C_BOLD,
    C_GREEN,
    C_RED,
    C_RESET,
    LOG,
    PROJECT_ROOT,
    StepFailedError,
    print_header,
    run,
    run_capture,
)

COVERAGE_DIR = PROJECT_ROOT / "tests" / "logs"
COVERAGE_XML = COVERAGE_DIR / "coverage.xml"


def parse_pytest_summary(output: str) -> str:
    """Extract the short result line from pytest output."""
    matches = re.findall(r"=+ (.+?) =+\s*$", output, re.MULTILINE)
    if matches:
        return matches[-1].strip()
    for line in reversed(output.splitlines()):
        if any(kw in line for kw in ("passed", "failed", "error")):
            return line.strip()
    return ""


def suite_command(subpath: str, *, append_cov: bool, extra: list[str] | None = None) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        subpath,
        "-q",
        "--no-header",
        "--cov=intellifl",
        f"--cov-report=xml:{COVERAGE_XML}",
    ]
    if append_cov:
        cmd.insert(cmd.index("--cov=intellifl") + 1, "--cov-append")
    if extra:
        cmd.extend(extra)
    return cmd


def main() -> int:
    args = sys.argv[1:]
    run_unit = "--unit" in args
    run_integration = "--integration" in args
    run_performance = "--performance" in args
    run_all = not (run_unit or run_integration or run_performance)

    COVERAGE_DIR.mkdir(parents=True, exist_ok=True)

    suites: list[tuple[str, list[str]]] = []
    if run_all or run_unit:
        suites.append(
            ("unit tests", suite_command("tests/unit/", append_cov=False, extra=["-n", "auto"]))
        )
    if run_all or run_performance:
        suites.append(("performance tests", suite_command("tests/performance/", append_cov=True)))
    if run_all or run_integration:
        suites.append(("integration tests", suite_command("tests/integration/", append_cov=True)))

    print_header("Test suite")

    if run_all:
        try:
            rc = run(
                [sys.executable, str(Path(__file__).with_name("lint.py"))],
                check=False,
                label="lint (pre-flight)",
            )
        except StepFailedError as exc:
            rc = exc.returncode
        if rc != 0:
            print(f"\n{C_RED}Lint failed — fix issues before running tests{C_RESET}\n")
            return rc

    results: list[tuple[str, int, str]] = []
    try:
        for label, cmd in suites:
            rc, output = run_capture(cmd, label=label, check=False)
            results.append((label, rc, output))
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Test run cancelled by user", file=sys.stderr)
        return 130

    passed_count = sum(1 for _, rc, _ in results if rc == 0)
    total = len(results)

    print()
    print("=" * 60)
    print(f"{C_BOLD}Test summary{C_RESET}")
    print("=" * 60)
    for label, rc, output in results:
        status = f"{C_GREEN}✓{C_RESET}" if rc == 0 else f"{C_RED}✗{C_RESET}"
        summary = parse_pytest_summary(output)
        suffix = f" — {summary}" if summary else ""
        print(f"  {status} {label}{suffix}")

    print(f"\n  Coverage report: {COVERAGE_XML}")
    print("=" * 60)

    if passed_count == total:
        print(f"{C_GREEN}✓ all suites passed ({passed_count}/{total}){C_RESET}\n")
        return 0
    failed = total - passed_count
    print(f"{C_RED}✗ {failed}/{total} suite(s) failed{C_RESET}")
    if LOG.latest_path:
        print(f"  See {LOG.latest_path} for full output.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
