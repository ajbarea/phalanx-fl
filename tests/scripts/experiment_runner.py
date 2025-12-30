"""Interactive batch runner for testing configs."""

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


def _handle_interrupt(signum, frame):
    """Handle Ctrl+C for graceful shutdown."""
    global _stop_requested
    if _stop_requested:
        console.print("\n[red]Force quitting...[/red]")
        sys.exit(130)
    _stop_requested = True
    console.print(
        "\n[yellow]Stopping after current experiment completes... "
        "(Ctrl+C again to force quit)[/yellow]"
    )


def parse_selection(selection_input: str, max_index: int) -> set:
    """Parse user selection input into set of indices.

    Args:
        selection_input: User input string.
        max_index: Maximum valid index.

    Returns:
        Set of selected indices (0-based).
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
    configs: list,
    timing_db: TimingDatabase,
    config_reader: ConfigReader,
    config_subdir: str,
) -> None:
    """Display interactive config selection menu.

    Args:
        configs: List of config filenames.
        timing_db: Timing database for duration estimates.
        config_reader: Config reader for titles.
        config_subdir: Subdirectory under config/simulation_strategies.
    """
    console.print("\n[bold cyan]Available Experiments[/bold cyan]")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Experiment", style="white")
    table.add_column("Device", justify="center", style="magenta", width=8)
    table.add_column("Time", justify="right", style="yellow")

    config_base_dir = project_root / "config" / "simulation_strategies" / config_subdir

    for idx, config_name in enumerate(configs, start=1):
        title_text = config_reader.get_title(config_name)
        if title_text:
            title = f"{title_text} [dim]({config_name})[/dim]"
        else:
            title = config_name

        config_file_path = config_base_dir / config_name
        try:
            with open(config_file_path) as f:
                config_data = json.load(f)
                device = (
                    config_data.get("shared_settings", {}).get("training_device", "cpu").lower()
                )
        except (FileNotFoundError, json.JSONDecodeError):
            device = "cpu"

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
        table.add_row(str(idx), title, device_str, time_str)

    console.print(table)
    console.print()


def select_configs_interactive(
    all_configs: list,
    timing_db: TimingDatabase,
    config_reader: ConfigReader,
    config_subdir: str,
) -> list:
    """Interactively select configs to run.

    Args:
        all_configs: List of available config filenames.
        timing_db: Timing database.
        config_reader: Config reader.
        config_subdir: Subdirectory under config/simulation_strategies.

    Returns:
        List of selected config filenames.
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


def main():
    """Run selected configs with memory cleanup."""
    signal.signal(signal.SIGINT, _handle_interrupt)

    parser = argparse.ArgumentParser(description="Interactive batch runner for testing configs")
    parser.add_argument(
        "dir",
        nargs="?",
        default="examples",
        help="Subdirectory under config/simulation_strategies/ to use (default: examples)",
    )
    args = parser.parse_args()

    config_dir = project_root / "config" / "simulation_strategies" / args.dir

    if not config_dir.exists():
        console.print(f"[red]Config directory not found: {config_dir}[/red]")
        sys.exit(1)

    timing_db = TimingDatabase()
    config_reader = ConfigReader(project_root)

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

    console.print(f"\n[cyan]Found {len(all_configs)} config(s) in {args.dir}/[/cyan]")
    if len(configs_by_subdir) > 1 or "." not in configs_by_subdir:
        for subdir in sorted(configs_by_subdir.keys()):
            count = configs_by_subdir[subdir]
            display_dir = f"{args.dir}/" if subdir == "." else f"{args.dir}/{subdir}/"
            console.print(f"  [dim]•[/dim] {count} in [yellow]{display_dir}[/yellow]")

    def get_sort_key(config_name):
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

    selected_configs = select_configs_interactive(configs, timing_db, config_reader, args.dir)

    console.print(f"\n[cyan]Running {len(selected_configs)} configs with Ray cleanup[/cyan]\n")

    with ExperimentExecutor(
        project_root=project_root,
        config_subdir=args.dir,
        log_level="INFO",
        timeout=None,
        cleanup_mode="aggressive",
        timing_db=timing_db,
    ) as executor:
        results = executor.run_batch(
            selected_configs,
            should_stop=lambda: _stop_requested,
        )

        display_summary(results, project_root=project_root, config_subdir=args.dir)

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
