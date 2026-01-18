"""Experiment execution logic."""

from __future__ import annotations

import gc
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import IO

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from intellifl.utils.warnings_config import get_subprocess_env_vars

from .timing_db import TimingDatabase

console = Console()


class ExecutionResult(Enum):
    """Result of experiment execution."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ExperimentResult:
    """Result of running a single experiment."""

    config_name: str
    result: ExecutionResult
    exit_code: int | None
    duration: float
    output_dir: str | None = None


class ExperimentExecutor:
    """Executes experiments with timeout and cleanup."""

    def __init__(
        self,
        project_root: Path,
        config_subdir: str = "examples",
        log_level: str = "INFO",
        timeout: int | None = None,
        cleanup_mode: str = "none",
        timing_db: TimingDatabase | None = None,
        skip_gc: bool = False,
    ):
        """Initialize executor.

        Args:
            project_root: Project root directory.
            config_subdir: Subdirectory under config/simulation_strategies.
            log_level: Logging level.
            timeout: Timeout in seconds per experiment.
            cleanup_mode: Cleanup mode (none, basic, aggressive).
            timing_db: Optional timing database.
            skip_gc: Skip manual garbage collection.
        """
        self.project_root = Path(project_root)
        self.config_subdir = config_subdir
        self.log_level = log_level
        self.timeout = timeout
        self.cleanup_mode = cleanup_mode
        self.timing_db = timing_db
        self.skip_gc = skip_gc
        self.python_exe = sys.executable
        self.log_file_handle: IO[str] | None = None
        self.log_file_path: Path | None = None

    def __enter__(self):
        """Enter context manager - return self for with statement."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - ensure log file is closed."""
        self._close_log_file()
        return False  # Don't suppress exceptions

    def _open_log_file(self) -> None:
        """Create and open a log file for capturing all experiment output."""
        logs_dir = self.project_root / "logs"
        logs_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%m-%d-%Y_%H-%M-%S")
        self.log_file_path = logs_dir / f"experiment_batch_{timestamp}.log"

        self.log_file_handle = open(self.log_file_path, "a", encoding="utf-8")

        self.log_file_handle.write("=" * 80 + "\n")
        self.log_file_handle.write(f"Experiment Batch Run - {timestamp}\n")
        self.log_file_handle.write(
            f"Config Directory: config/simulation_strategies/{self.config_subdir}\n"
        )
        self.log_file_handle.write("=" * 80 + "\n\n")
        self.log_file_handle.flush()

    def _close_log_file(self) -> None:
        """Close the log file."""
        if self.log_file_handle:
            self.log_file_handle.write("\n" + "=" * 80 + "\n")
            self.log_file_handle.write("Batch execution completed\n")
            self.log_file_handle.write("=" * 80 + "\n")
            self.log_file_handle.close()
            self.log_file_handle = None

    def _kill_ray_processes(self) -> None:
        """Kill stray Ray processes to prevent resource leaks."""
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/IM", "raylet.exe"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.run(
                    ["pkill", "-9", "-f", "raylet"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception:
            pass  # Don't crash if cleanup fails

    def _get_config_title(self, config_name: str) -> str | None:
        """Extract title from config file if available.

        Args:
            config_name: Name of config file.

        Returns:
            Title string if found, None otherwise.
        """
        # Handle "." as root directory
        if self.config_subdir == ".":
            config_path = self.project_root / "config" / "simulation_strategies" / config_name
        else:
            config_path = (
                self.project_root
                / "config"
                / "simulation_strategies"
                / self.config_subdir
                / config_name
            )
        try:
            with open(config_path) as f:
                config = json.load(f)
                return config.get("_title")
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return None

    def _get_config_device(self, config_name: str) -> str:
        """Extract training device from config file.

        Args:
            config_name: Name of config file.

        Returns:
            Device string ("gpu", "cpu").
        """
        # Handle "." as root directory
        if self.config_subdir == ".":
            config_path = self.project_root / "config" / "simulation_strategies" / config_name
        else:
            config_path = (
                self.project_root
                / "config"
                / "simulation_strategies"
                / self.config_subdir
                / config_name
            )
        try:
            with open(config_path) as f:
                config = json.load(f)
                if "shared_settings" in config:
                    return config["shared_settings"].get("training_device", "gpu")
                return config.get("training_device", "gpu")
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return "gpu"

    def _detect_device_from_output(self, stderr_lines: list[str]) -> str | None:
        """Parse stderr to detect actual device used.

        Args:
            stderr_lines: List of stderr output lines.

        Returns:
            "gpu" or "cpu" if detected, None otherwise.
        """
        for line in stderr_lines:
            if "Using CUDA" in line or "CUDA GPU" in line:
                return "gpu"
            if "Using CPU" in line or "Using device: CPU" in line:
                return "cpu"
        return None

    def _get_newest_output_dir(self) -> str | None:
        """Find the newest output directory in out/.

        Returns:
            Path to newest directory, or None.
        """
        out_dir = self.project_root / "out"
        if not out_dir.exists():
            return None

        dirs = [d for d in out_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"]
        if not dirs:
            return None

        newest_dir = max(dirs, key=lambda d: d.stat().st_mtime)
        return str(newest_dir.relative_to(self.project_root))

    def run_experiment(
        self, config_name: str, config_index: int, total_configs: int
    ) -> ExperimentResult:
        """Run a single experiment.

        Args:
            config_name: Name of config file.
            config_index: Current config index.
            total_configs: Total number of configs.

        Returns:
            ExperimentResult with execution details.
        """
        start_time = time.time()
        output_dir = None

        title = self._get_config_title(config_name)
        if title:
            console.print(f'\n[cyan][{config_index}/{total_configs}] Running "{title}"[/cyan]')
            console.print(f"[dim]  ({config_name})[/dim]")
        else:
            console.print(
                f"\n[cyan][{config_index}/{total_configs}] Running {config_name}...[/cyan]"
            )

        if self.log_file_handle:
            self.log_file_handle.write("\n" + "=" * 80 + "\n")
            self.log_file_handle.write(
                f"[{config_index}/{total_configs}] Experiment: {config_name}\n"
            )
            if title:
                self.log_file_handle.write(f"Title: {title}\n")
            self.log_file_handle.write(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.log_file_handle.write("=" * 80 + "\n\n")
            self.log_file_handle.flush()

        # Build config path for simulation_runner
        if self.config_subdir == ".":
            config_path_arg = config_name
        else:
            config_path_arg = f"{self.config_subdir}/{config_name}"

        cmd = [
            self.python_exe,
            "intellifl/simulation_runner.py",
            config_path_arg,
            "--log-level",
            self.log_level,
        ]

        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.project_root)
        env.update(get_subprocess_env_vars())

        stderr_buffer = []

        try:
            process = subprocess.Popen(
                cmd,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )

            if process.stdout:
                for line in process.stdout:
                    print(line, end="")
                    stderr_buffer.append(line)
                    if self.log_file_handle:
                        self.log_file_handle.write(line)
                        self.log_file_handle.flush()

            try:
                returncode = process.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                duration = time.time() - start_time
                assert self.timeout is not None
                timeout_str = (
                    f"{self.timeout // 60} minutes"
                    if self.timeout >= 60
                    else f"{self.timeout} seconds"
                )
                msg = f"[TIMEOUT] Timed out on {config_name} (exceeded {timeout_str})"
                console.print(f"[yellow]{msg}[/yellow]")
                if self.log_file_handle:
                    self.log_file_handle.write(f"\n{msg}\n")
                    self.log_file_handle.write(f"Duration: {duration:.1f}s\n")
                    self.log_file_handle.flush()
                output_dir = self._get_newest_output_dir()
                return ExperimentResult(
                    config_name, ExecutionResult.TIMEOUT, 124, duration, output_dir
                )

            duration = time.time() - start_time

            if returncode == 0:
                msg = f"[OK] Completed {config_index}/{total_configs} ({duration:.1f}s)"
                console.print(f"[green]{msg}[/green]")
                if self.log_file_handle:
                    self.log_file_handle.write(f"\n{msg}\n")
                    self.log_file_handle.flush()
                output_dir = self._get_newest_output_dir()
                if self.timing_db:
                    detected_device = self._detect_device_from_output(stderr_buffer)
                    if detected_device:
                        device = detected_device
                    else:
                        device = self._get_config_device(config_name)
                    self.timing_db.record(config_name, duration, device)
                return ExperimentResult(
                    config_name,
                    ExecutionResult.SUCCESS,
                    returncode,
                    duration,
                    output_dir,
                )
            else:
                msg = f"[FAIL] Failed on {config_name} (exit code: {returncode}, {duration:.1f}s)"
                console.print(f"[red]{msg}[/red]")
                if self.log_file_handle:
                    self.log_file_handle.write(f"\n{msg}\n")
                    self.log_file_handle.flush()
                return ExperimentResult(
                    config_name,
                    ExecutionResult.FAILED,
                    returncode,
                    duration,
                    output_dir,
                )

        except Exception as e:
            duration = time.time() - start_time
            msg = f"[ERROR] Exception on {config_name}: {e}"
            console.print(f"[red]{msg}[/red]")
            if self.log_file_handle:
                self.log_file_handle.write(f"\n{msg}\n")
                self.log_file_handle.flush()
            output_dir = self._get_newest_output_dir()
            return ExperimentResult(config_name, ExecutionResult.FAILED, -1, duration, output_dir)

        finally:
            self._kill_ray_processes()
            gc.collect()

    def cleanup(self, is_last: bool = False) -> None:
        """Perform cleanup between experiments.

        Args:
            is_last: Whether this is the last experiment (skip cleanup).
        """
        if is_last or self.cleanup_mode == "none":
            return

        console.print(f"[dim]Running cleanup (mode: {self.cleanup_mode})...[/dim]")

        if self.cleanup_mode in ["basic", "aggressive"]:
            if not self.skip_gc:
                gc.collect()
                console.print("[dim]Garbage collection complete[/dim]")
            else:
                console.print("[dim]Skipping gc.collect() - relying on subprocess cleanup[/dim]")

        if self.cleanup_mode == "aggressive":
            cache_dirs = list(self.project_root.rglob("__pycache__"))
            for cache_dir in cache_dirs:
                try:
                    for item in cache_dir.iterdir():
                        item.unlink()
                    cache_dir.rmdir()
                except Exception:
                    pass

            console.print("[dim]Pausing 3 seconds for resource cleanup...[/dim]")
            time.sleep(3)

    def run_batch(
        self,
        configs: list[str],
        on_complete=None,
        on_failed=None,
        on_timeout=None,
        should_stop=None,
    ) -> dict:
        """Run a batch of experiments.

        Args:
            configs: List of config filenames.
            on_complete: Callback for successful completion.
            on_failed: Callback for failures.
            on_timeout: Callback for timeouts.
            should_stop: Callable returning True to stop after current experiment.

        Returns:
            Dictionary with results summary.
        """
        total = len(configs)
        completed = []
        failed = []
        timedout = []
        output_dirs = {}

        self._open_log_file()
        console.print(f"[dim]Logging all output to: {self.log_file_path}[/dim]\n")

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("[cyan]Running experiments...", total=total)

                for idx, config in enumerate(configs, start=1):
                    if should_stop and should_stop():
                        console.print(
                            f"\n[yellow]Stopping early (user requested) - "
                            f"{idx - 1}/{total} completed[/yellow]"
                        )
                        break

                    result = self.run_experiment(config, idx, total)

                    if result.output_dir:
                        output_dirs[config] = result.output_dir

                    if result.result == ExecutionResult.SUCCESS:
                        completed.append(config)
                        if on_complete:
                            on_complete(config)
                    elif result.result == ExecutionResult.TIMEOUT:
                        timedout.append(config)
                        if on_timeout:
                            on_timeout(config)
                    else:
                        failed.append(config)
                        if on_failed:
                            on_failed(config)

                    self.cleanup(is_last=(idx == total))

                    progress.update(task, advance=1)
        finally:
            self._close_log_file()

        return {
            "completed": completed,
            "failed": failed,
            "timedout": timedout,
            "total": total,
            "output_dirs": output_dirs,
            "log_file_path": str(self.log_file_path) if self.log_file_path else None,
        }


def display_summary(
    results: dict,
    skipped: list[str] | None = None,
    project_root: Path | None = None,
    config_subdir: str | None = None,
) -> None:
    """Display summary of batch execution.

    Args:
        results: Results dictionary.
        skipped: List of skipped configs.
        project_root: Optional project root.
        config_subdir: Optional config subdirectory.
    """
    console.print("\n" + "=" * 50)
    console.print("[bold cyan]Execution Summary[/bold cyan]")
    console.print("=" * 50 + "\n")

    total_errors = len(results["failed"]) + len(results["timedout"])
    configs_run = results["total"]

    if skipped:
        console.print(f"[dim]Skipped {len(skipped)} already-completed config(s)[/dim]\n")

    def get_config_title(config_name: str) -> str | None:
        if not project_root or not config_subdir:
            return None
        # Handle "." as root directory
        if config_subdir == ".":
            config_path = project_root / "config" / "simulation_strategies" / config_name
        else:
            config_path = (
                project_root / "config" / "simulation_strategies" / config_subdir / config_name
            )
        try:
            with open(config_path) as f:
                config = json.load(f)
                return config.get("_title")
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return None

    output_dirs = results.get("output_dirs", {})

    if total_errors == 0:
        if configs_run == 0:
            console.print("[green]All selected configs were already completed![/green]")
        else:
            console.print(f"[green]All {configs_run} config(s) completed successfully![/green]\n")

            if results["completed"]:
                console.print("[cyan]Experiments run:[/cyan]")
                for config in results["completed"]:
                    title = get_config_title(config)
                    output_dir = output_dirs.get(config)

                    if title:
                        config_display = f"{title} [dim]({config})[/dim]"
                    else:
                        config_display = config

                    if output_dir:
                        console.print(f"  [green][OK][/green] {config_display}")
                        console.print(f"      [dim]-> {output_dir}[/dim]")
                    else:
                        console.print(f"  [green][OK][/green] {config_display}")
                console.print()
    else:
        console.print(f"[red]{total_errors}/{configs_run} config(s) failed:[/red]\n")

        if results["completed"]:
            console.print(f"[green]Completed ({len(results['completed'])}):[/green]")
            for config in results["completed"]:
                title = get_config_title(config)
                output_dir = output_dirs.get(config)

                if title:
                    config_display = f"{title} [dim]({config})[/dim]"
                else:
                    config_display = config

                if output_dir:
                    console.print(f"  [green][OK][/green] {config_display}")
                    console.print(f"      [dim]-> {output_dir}[/dim]")
                else:
                    console.print(f"  [green][OK][/green] {config_display}")
            console.print()

        if results["timedout"]:
            console.print(f"[yellow]Timed out ({len(results['timedout'])}):[/yellow]")
            for config in results["timedout"]:
                title = get_config_title(config)
                output_dir = output_dirs.get(config)

                if title:
                    config_display = f"{title} [dim]({config})[/dim]"
                else:
                    config_display = config

                if output_dir:
                    console.print(f"  [yellow][T][/yellow] {config_display}")
                    console.print(f"      [dim]-> {output_dir}[/dim]")
                else:
                    console.print(f"  [yellow][T][/yellow] {config_display}")
            console.print()

        if results["failed"]:
            console.print(f"[red]Failed ({len(results['failed'])}):[/red]")
            for config in results["failed"]:
                title = get_config_title(config)
                output_dir = output_dirs.get(config)

                if title:
                    config_display = f"{title} [dim]({config})[/dim]"
                else:
                    config_display = config

                if output_dir:
                    console.print(f"  [red][X][/red] {config_display}")
                    console.print(f"      [dim]-> {output_dir}[/dim]")
                else:
                    console.print(f"  [red][X][/red] {config_display}")
            console.print()

    log_file_path = results.get("log_file_path")
    if log_file_path:
        console.print(f"[cyan]Full output log:[/cyan] {log_file_path}\n")

    console.print("=" * 50)
