"""Cross-platform developer entrypoints for IntelliFL.

The canonical local workflow is:

    uv run intellifl-dev <command> [-- <args...>]

The Makefile remains available as a thin compatibility wrapper, but this
module is the single source of truth for supported developer commands.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from intellifl.dev_runner import LOG, StepFailedError
from intellifl.dev_runner import run as streamed_run

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV = {
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
    "UV_PROJECT_ENVIRONMENT": ".venv",
}
CommandFactory = Callable[[], list[str]]


@dataclass(frozen=True)
class Task:
    """Metadata describing a developer task."""

    description: str
    command_factory: CommandFactory
    timed: bool = True
    cwd: Path = PROJECT_ROOT


def configure_stdio() -> None:
    """Prefer UTF-8 console output across shells."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (LookupError, OSError, ValueError):
                continue


def build_env() -> dict[str, str]:
    """Build the environment for child processes."""
    env = os.environ.copy()
    for key, value in DEFAULT_ENV.items():
        env.setdefault(key, value)
    if sys.stdout.isatty() and os.environ.get("NO_COLOR") is None:
        env.setdefault("FORCE_COLOR", "1")
    return env


def strip_passthrough_marker(args: list[str]) -> list[str]:
    """Allow `--` before passthrough arguments."""
    if args[:1] == ["--"]:
        return args[1:]
    return args


def python_script(*parts: str) -> list[str]:
    """Build a command for a repository Python script."""
    return [sys.executable, str(PROJECT_ROOT.joinpath(*parts))]


TASK_GROUPS: tuple[tuple[str, tuple[tuple[str, Task], ...]], ...] = (
    (
        "Environment",
        (
            (
                "check-env",
                Task(
                    description="Verify uv, Python, and Docker are available",
                    command_factory=lambda: python_script("scripts", "check_env.py"),
                ),
            ),
        ),
    ),
    (
        "Setup & Maintenance",
        (
            (
                "setup",
                Task(
                    description="Install all Python dependencies + download datasets",
                    command_factory=lambda: python_script("scripts", "setup.py"),
                ),
            ),
            (
                "upgrade",
                Task(
                    description="Update all dependencies to latest versions",
                    command_factory=lambda: python_script("scripts", "upgrade.py"),
                ),
            ),
            (
                "yolo",
                Task(
                    description="Nuke and rebuild: clean → setup → upgrade",
                    command_factory=list,
                ),
            ),
        ),
    ),
    (
        "Development Workflows",
        (
            (
                "dev",
                Task(
                    description="Start all services (Docker Compose)",
                    command_factory=lambda: ["docker", "compose", "up"],
                ),
            ),
            (
                "dev-down",
                Task(
                    description="Stop all services",
                    command_factory=lambda: ["docker", "compose", "down"],
                ),
            ),
            (
                "docs",
                Task(
                    description="Serve documentation (Zensical)",
                    command_factory=lambda: ["zensical", "serve"],
                ),
            ),
            (
                "sim",
                Task(
                    description="Run local simulation with optimized Ray environment",
                    command_factory=lambda: python_script("scripts", "sim.py"),
                ),
            ),
            (
                "baselines",
                Task(
                    description="Record fast simulation baselines for CI",
                    command_factory=lambda: python_script(
                        "tests", "scripts", "record_baselines.py"
                    ),
                ),
            ),
        ),
    ),
    (
        "Quality Gates",
        (
            (
                "lint",
                Task(
                    description="Run code quality checks (ruff format, ruff check, ty)",
                    command_factory=lambda: python_script("scripts", "lint.py"),
                ),
            ),
            (
                "validate",
                Task(
                    description="Quick validation: lint + unit tests only (fast feedback)",
                    command_factory=lambda: python_script("scripts", "validate.py"),
                ),
            ),
            (
                "test",
                Task(
                    description="Run full test suite (unit + integration + performance)",
                    command_factory=lambda: python_script("scripts", "test.py"),
                ),
            ),
            (
                "audit",
                Task(
                    description="Auto-fix and audit security vulnerabilities (backend + frontend)",
                    command_factory=lambda: python_script("scripts", "audit.py"),
                ),
            ),
        ),
    ),
    (
        "Maintenance",
        (
            (
                "clean",
                Task(
                    description="Remove build artifacts and caches",
                    command_factory=lambda: python_script("scripts", "clean_build.py"),
                ),
            ),
            (
                "reset",
                Task(
                    description="Clean artifacts AND experiment results",
                    command_factory=lambda: python_script("scripts", "clean_build.py") + ["--out"],
                ),
            ),
        ),
    ),
)

TASKS = {name: task for _, group in TASK_GROUPS for name, task in group}


def print_help() -> None:
    """Print supported commands."""
    print("Usage:")
    print("  uv run intellifl-dev <command> [-- <args...>]")
    print("  make <command>  # optional compatibility wrapper")
    print()
    print("Commands:")
    for _, group in TASK_GROUPS:
        for name, task in group:
            print(f"  {name:<20} {task.description}")


def run_process(command: list[str], *, cwd: Path, label: str | None = None) -> int:
    """Run a subprocess, streaming output to console + session log."""
    try:
        return streamed_run(command, check=False, label=label, cwd=cwd, env=build_env())
    except StepFailedError as exc:
        return exc.returncode


def run_task(name: str, extra_args: list[str] | None = None) -> int:
    """Run a named task."""
    extra_args = strip_passthrough_marker(extra_args or [])

    if name == "help":
        print_help()
        return 0

    if name == "yolo":
        start = time.perf_counter()
        for task_name in ("clean", "setup", "upgrade"):
            result = run_task(task_name)
            if result != 0:
                elapsed = round(time.perf_counter() - start)
                print(f"[TIMER] Target yolo completed in {elapsed} seconds")
                return result
        elapsed = round(time.perf_counter() - start)
        print(f"[TIMER] Target yolo completed in {elapsed} seconds")
        return 0

    task = TASKS[name]
    command = task.command_factory() + extra_args
    start = time.perf_counter()
    result = run_process(command, cwd=task.cwd, label=name)
    if task.timed:
        elapsed = round(time.perf_counter() - start)
        print(f"[TIMER] Target {name} completed in {elapsed} seconds")
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="intellifl-dev",
        description="Cross-platform developer entrypoints for IntelliFL.",
    )
    parser.add_argument("command", nargs="?", default="help")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for the developer CLI."""
    configure_stdio()
    parsed = parse_args(argv or sys.argv[1:])

    if parsed.command not in TASKS and parsed.command != "help":
        print(f"Unknown command: {parsed.command}", file=sys.stderr)
        print_help()
        return 2

    if parsed.command == "help":
        return run_task(parsed.command, parsed.args)

    LOG.open(parsed.command)
    LOG.session_header(parsed.command, list(argv) if argv is not None else sys.argv[1:])
    if LOG.latest_path:
        print(
            f"log: {LOG.latest_path}"
            + (f" (archive: {LOG.archive_path})" if LOG.archive_path else ""),
            flush=True,
        )

    rc = 1
    try:
        rc = run_task(parsed.command, parsed.args)
        return rc
    except KeyboardInterrupt:
        rc = 130
        print("\n[INTERRUPT] Operation cancelled by user", file=sys.stderr)
        LOG.event("WARN", "interrupted (SIGINT)")
        return 0
    finally:
        LOG.session_footer(rc)


if __name__ == "__main__":
    raise SystemExit(main())
