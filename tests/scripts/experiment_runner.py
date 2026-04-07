"""Interactive batch runner for simulation config testing.

Provides a TUI for selecting and running simulation configs with:
- Estimated run times from timing database's last successful execution
- Graceful interrupt handling
- Memory cleanup between runs
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.table import Table

from tests.scripts.runner.config_reader import ConfigReader
from tests.scripts.runner.executor import ExperimentExecutor, display_summary
from tests.scripts.runner.timing_db import TimingDatabase

project_root = Path(__file__).parent.parent.parent

console = Console()

_stop_requested = False


def _handle_interrupt(signum, frame) -> None:
    """Enable graceful shutdown on first Ctrl+C, force quit on second."""
    global _stop_requested
    if _stop_requested:
        console.print("\n[red]Force quitting...[/red]")
        sys.exit(130)
    _stop_requested = True
    console.print(
        "\n[yellow]Stopping after current experiment completes... "
        "(Ctrl+C again to force quit)[/yellow]"
    )


def parse_selection(selection_input: str, max_index: int) -> set[int]:
    """Parse selection input like "1,3,5" or "1-10" into index set.

    Args:
        selection_input: User input ("all", "1,3,5", "1-10", or combinations).
        max_index: Maximum valid index (exclusive).

    Returns:
        Set of selected 0-based indices.
    """
    selection_input = selection_input.strip().lower()

    if selection_input == "all":
        return set(range(max_index))

    selected: set[int] = set()
    parts = selection_input.split(",")

    for part in parts:
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-")
                start_idx = int(start.strip()) - 1
                end_idx = int(end.strip()) - 1
                if 0 <= start_idx <= end_idx < max_index:
                    selected.update(range(start_idx, end_idx + 1))
            except (ValueError, IndexError):
                pass
        else:
            try:
                idx = int(part) - 1
                if 0 <= idx < max_index:
                    selected.add(idx)
            except ValueError:
                pass

    return selected


def show_config_menu(
    configs: list[str],
    timing_db: TimingDatabase,
    config_reader: ConfigReader,
    config_subdir: str,
) -> None:
    """Display rich table of available experiments with metadata.

    Args:
        configs: List of config filenames.
        timing_db: Database for estimated run durations.
        config_reader: Reader for extracting config titles.
        config_subdir: Subdirectory under config/simulation_strategies/.
    """
    console.print("\n[bold cyan]Available Experiments[/bold cyan]")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Experiment", style="white")
    table.add_column("Config", style="dim", width=35)
    table.add_column("Gear", justify="center", style="magenta", width=4)
    table.add_column("Rounds", justify="right", style="cyan", width=6)
    table.add_column("Time", justify="right", style="yellow")

    config_base_dir = project_root / "config" / "simulation_strategies" / config_subdir

    for idx, config_name in enumerate(configs, start=1):
        title_text = config_reader.get_title(config_name)
        title = title_text if title_text else config_name

        config_file_path = config_base_dir / config_name
        try:
            with open(config_file_path) as f:
                config_data = json.load(f)
                device = (
                    config_data.get("shared_settings", {}).get("training_device", "cpu").lower()
                )
                num_rounds = config_data.get("shared_settings", {}).get("num_of_rounds")
        except (FileNotFoundError, json.JSONDecodeError):
            device = "cpu"
            num_rounds = None

        rounds_str = str(num_rounds) if num_rounds is not None else "—"

        duration = timing_db.get_duration(config_name, device=device)

        if duration == float("inf"):
            time_str = "[dim]unknown[/dim]"
        else:
            mins = int(duration // 60)
            secs = int(duration % 60)
            if mins > 0:
                time_str = f"{mins}m {secs}s"
            else:
                time_str = f"{secs}s"

        device_str = "GPU" if device == "gpu" else "CPU"
        config_display = config_name[:-5] if config_name.endswith(".json") else config_name
        table.add_row(str(idx), title, config_display, device_str, rounds_str, time_str)

    console.print(table)
    console.print()


def select_configs_interactive(
    all_configs: list[str],
    timing_db: TimingDatabase,
    config_reader: ConfigReader,
    config_subdir: str,
) -> list[str]:
    """Prompt user to select experiments from menu.

    Args:
        all_configs: Available config filenames.
        timing_db: Database for run time estimates.
        config_reader: Reader for config titles.
        config_subdir: Subdirectory under config/simulation_strategies/.

    Returns:
        User-confirmed list of config filenames to run.
    """
    stats = timing_db.get_stats(device="gpu")
    if stats["count"] > 0:
        console.print(
            f"[dim]Timing DB (GPU): {stats['count']} configs, "
            f"avg {stats['avg']}s (range: {stats['min']}-{stats['max']}s)[/dim]"
        )

    cpu_stats = timing_db.get_stats(device="cpu")
    if cpu_stats["count"] > 0:
        console.print(
            f"[dim]Timing DB (CPU): {cpu_stats['count']} configs, "
            f"avg {cpu_stats['avg']}s (range: {cpu_stats['min']}-{cpu_stats['max']}s)[/dim]"
        )

    while True:
        show_config_menu(all_configs, timing_db, config_reader, config_subdir)

        console.print("[yellow]Select experiments:[/yellow]")
        console.print("  [cyan]all[/cyan]      - Run all experiments")
        console.print("  [cyan]1,3,5[/cyan]    - Run specific experiments")
        console.print("  [cyan]1-10[/cyan]     - Run range of experiments")
        console.print("  [cyan]q[/cyan]        - Quit\n")

        selection = input("> ").strip().lower()

        if selection == "q":
            console.print("[yellow]Cancelled[/yellow]")
            sys.exit(0)

        selected_indices = parse_selection(selection, len(all_configs))

        if not selected_indices:
            console.print("[red]Invalid selection. Try again.[/red]")
            continue

        selected_configs = [all_configs[i] for i in sorted(selected_indices)]

        console.print(f"\n[green]Selected {len(selected_configs)} experiments:[/green]")
        for config in selected_configs:
            title_text = config_reader.get_title(config)
            if title_text:
                console.print(f"  [cyan]•[/cyan] {title_text} [dim]({config})[/dim]")
            else:
                console.print(f"  [cyan]•[/cyan] {config}")

        console.print(f"\n[yellow]Run these {len(selected_configs)} experiments?[/yellow] (y/n)")
        confirm = input("> ").strip().lower()

        if confirm in ["y", "yes"]:
            return selected_configs

        console.print("[yellow]Let's try again...[/yellow]")


def list_available_config_paths() -> list[tuple[str, int, str]]:
    """Discover config directories and standalone files.

    Returns:
        List of (path, config_count, path_type) tuples.
        path_type is "dir" for directories, "file" for standalone configs.
    """
    strategies_dir = project_root / "config" / "simulation_strategies"
    results = []

    for item in strategies_dir.iterdir():
        if item.is_dir():
            json_files = list(item.rglob("*.json"))
            if json_files:
                results.append((item.name, len(json_files), "dir"))

    for item in strategies_dir.glob("*.json"):
        if item.is_file():
            results.append((item.name, 1, "file"))

    return sorted(results, key=lambda x: (x[2], x[0]))


def select_config_path_interactive() -> str:
    """Prompt user to select a config directory or file.

    Returns:
        Selected directory name or config filename.
    """
    available = list_available_config_paths()

    if not available:
        console.print("[red]No config directories or files found![/red]")
        sys.exit(1)

    console.print("\n[bold cyan]Available Config Paths[/bold cyan]")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Path", style="white")
    table.add_column("Type", justify="center", style="magenta", width=10)
    table.add_column("Configs", justify="right", style="yellow", width=8)

    for idx, (path, count, path_type) in enumerate(available, start=1):
        type_display = "Directory" if path_type == "dir" else "File"
        table.add_row(str(idx), path, type_display, str(count))

    console.print(table)
    console.print()

    while True:
        console.print("[yellow]Select a config path:[/yellow]")
        console.print("  [cyan]1-N[/cyan]  - Select by number")
        console.print("  [cyan]q[/cyan]    - Quit\n")

        selection = input("> ").strip().lower()

        if selection == "q":
            console.print("[yellow]Cancelled[/yellow]")
            sys.exit(0)

        try:
            idx = int(selection) - 1
            if 0 <= idx < len(available):
                selected_path, count, path_type = available[idx]
                console.print(
                    f"\n[green]Selected:[/green] {selected_path} "
                    f"[dim]({count} config{'s' if count > 1 else ''})[/dim]\n"
                )
                return selected_path
            else:
                console.print("[red]Invalid selection. Try again.[/red]")
        except ValueError:
            console.print("[red]Invalid input. Enter a number or 'q'.[/red]")


def main() -> None:
    """Entry point: select and run experiments with cleanup between runs."""
    signal.signal(signal.SIGINT, _handle_interrupt)

    parser = argparse.ArgumentParser(description="Interactive batch runner for testing configs")
    parser.add_argument(
        "dir",
        nargs="?",
        default=None,
        help="Subdirectory under config/simulation_strategies/ to use (optional, will prompt if not provided)",
    )
    args = parser.parse_args()

    if args.dir is None:
        selected_path = select_config_path_interactive()
    else:
        selected_path = args.dir

    config_dir = project_root / "config" / "simulation_strategies" / selected_path

    if not config_dir.exists():
        console.print(f"[red]Config directory not found: {config_dir}[/red]")
        sys.exit(1)

    timing_db = TimingDatabase()
    config_reader = ConfigReader(project_root)

    if config_dir.is_file():
        single_file_name = config_dir.name
        config_dir = config_dir.parent
        all_configs = [single_file_name]
        selected_path = "."  # Executor expects "." for root-level configs
        selected_configs = all_configs

        console.print(f"\n[cyan]Running single config: {single_file_name}[/cyan]\n")
    else:
        all_config_paths = list(config_dir.rglob("*.json"))

        if not all_config_paths:
            console.print("[red]No config files found[/red]")
            sys.exit(1)

        all_configs = [str(f.relative_to(config_dir)).replace("\\", "/") for f in all_config_paths]

        configs_by_subdir: dict[str, int] = defaultdict(int)
        for config in all_configs:
            if "/" in config:
                subdir = config.rsplit("/", 1)[0]
                configs_by_subdir[subdir] += 1
            else:
                configs_by_subdir["."] += 1

        console.print(f"\n[cyan]Found {len(all_configs)} config(s) in {selected_path}/[/cyan]")
        if len(configs_by_subdir) > 1 or "." not in configs_by_subdir:
            for subdir in sorted(configs_by_subdir.keys()):
                count = configs_by_subdir[subdir]
                display_dir = f"{selected_path}/" if subdir == "." else f"{selected_path}/{subdir}/"
                console.print(f"  [dim]•[/dim] {count} in [yellow]{display_dir}[/yellow]")

        def get_sort_key(config_name: str) -> float:
            config_file_path = config_dir / config_name
            try:
                with open(config_file_path) as f:
                    config_data = json.load(f)
                    device = (
                        config_data.get("shared_settings", {}).get("training_device", "cpu").lower()
                    )
            except (FileNotFoundError, json.JSONDecodeError):
                device = "cpu"

            duration = timing_db.get_duration(config_name, device=device)
            return duration

        configs = sorted(all_configs, key=get_sort_key)

        selected_configs = select_configs_interactive(
            configs, timing_db, config_reader, selected_path
        )

    console.print(f"\n[cyan]Running {len(selected_configs)} configs with Ray cleanup[/cyan]\n")

    with ExperimentExecutor(
        project_root=project_root,
        config_subdir=selected_path,
        log_level="INFO",
        timeout=None,
        cleanup_mode="aggressive",
        timing_db=timing_db,
    ) as executor:
        results = executor.run_batch(
            selected_configs,
            should_stop=lambda: _stop_requested,
        )

        display_summary(results, project_root=project_root, config_subdir=selected_path)

    total_errors = len(results["failed"]) + len(results["timedout"])
    sys.exit(0 if total_errors == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback

        traceback.print_exc()
        sys.exit(1)
