#!/usr/bin/env python3
"""Code quality checks and formatting.

Runs the auto-fixers first (ruff --fix, ruff format), then the strict
check pass (ruff check, ty, frontend lint). Exits non-zero if any check
still fails after the fix pass.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from intellifl.dev_runner import (
    C_BOLD,
    C_GREEN,
    C_RED,
    C_RESET,
    LOG,
    PROJECT_ROOT,
    StepFailedError,
    fix_and_check,
    print_header,
)

FRONTEND_DIR = PROJECT_ROOT / "frontend"


def _frontend_available() -> bool:
    return FRONTEND_DIR.is_dir() and shutil.which("npm") is not None


def _cwd_for(label: str) -> Path | None:
    if label.startswith("npm run "):
        return FRONTEND_DIR
    return None


def python_fixers() -> list[tuple[str, Sequence[str]]]:
    return [
        ("ruff format", ["uv", "run", "ruff", "format", "."]),
        ("ruff check --fix", ["uv", "run", "ruff", "check", "--fix", "--unsafe-fixes", "."]),
    ]


def python_checks() -> list[tuple[str, Sequence[str]]]:
    return [
        ("ruff format --check", ["uv", "run", "ruff", "format", "--check", "."]),
        ("ruff check", ["uv", "run", "ruff", "check", "."]),
        # ty has no auto-fix; it runs in the check phase only.
        ("ty check", ["uv", "run", "ty", "check", "intellifl", "tests"]),
    ]


def frontend_fixers() -> list[tuple[str, Sequence[str]]]:
    return [("npm run lint:fix", ["npm", "run", "lint:fix", "--if-present"])]


def frontend_checks() -> list[tuple[str, Sequence[str]]]:
    return [("npm run lint", ["npm", "run", "lint"])]


def main() -> int:
    failures: list[str] = []
    failures += fix_and_check("Python lint", python_fixers(), python_checks())

    if _frontend_available():
        failures += fix_and_check(
            "Frontend lint",
            frontend_fixers(),
            frontend_checks(),
            fixer_cwd=_cwd_for,
            check_cwd=_cwd_for,
        )
    else:
        print_header("Frontend lint")
        print("  skipped (no frontend/ or npm not on PATH)")

    print()
    print("=" * 60)
    print(f"{C_BOLD}Lint summary{C_RESET}")
    print("=" * 60)
    if failures:
        print(f"  {C_RED}{len(failures)} check(s) still failing:{C_RESET}")
        for f in failures:
            print(f"    - {f}")
        if LOG.latest_path:
            print(f"\n  See {LOG.latest_path} for full output.")
        return 1

    print(f"  {C_GREEN}all checks passed{C_RESET}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except StepFailedError as exc:
        print(f"FAILED: {' '.join(exc.cmd)} (exit {exc.returncode})", file=sys.stderr)
        sys.exit(exc.returncode)
