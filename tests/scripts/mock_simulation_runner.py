#!/usr/bin/env python3
"""Mock simulation runner - runs full output generation with real strategy execution."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import torch
from flwr.common import ndarrays_to_parameters
from rich.console import Console

from src.attack_utils.attack_snapshots import save_attack_snapshot
from src.attack_utils.snapshot_html_reports import (
    generate_main_dashboard,
    generate_snapshot_index,
    generate_summary_json,
)
from src.data_models.simulation_strategy_config import StrategyConfig
from src.data_models.simulation_strategy_history import SimulationStrategyHistory
from src.output_handlers import new_plot_handler
from src.output_handlers.directory_handler import DirectoryHandler
from src.simulation_strategies.bulyan_strategy import BulyanStrategy
from src.simulation_strategies.fedavg_strategy import FedAvgStrategy
from src.simulation_strategies.krum_based_removal_strategy import (
    KrumBasedRemovalStrategy,
)
from src.simulation_strategies.multi_krum_based_removal_strategy import (
    MultiKrumBasedRemovalStrategy,
)
from src.simulation_strategies.multi_krum_strategy import MultiKrumStrategy
from src.simulation_strategies.pid_based_removal_strategy import PIDBasedRemovalStrategy
from src.simulation_strategies.rfa_based_removal_strategy import RFABasedRemovalStrategy
from src.simulation_strategies.trimmed_mean_based_removal_strategy import (
    TrimmedMeanBasedRemovalStrategy,
)
from src.simulation_strategies.trust_based_removal_strategy import (
    TrustBasedRemovalStrategy,
)
from tests.fixtures.mock_flower_components import (
    MockClient,
    MockNumPyClient,
    MockServerConfig,
    mock_start_simulation,
)
from tests.scripts.constants import FAST_CONFIGS

project_root = Path(__file__).parent.parent.parent
console = Console()


def load_baseline(config_name: str, baselines_dir: Path) -> dict | None:
    """Load baseline data for a config."""
    baseline_name = config_name.replace(".json", ".baseline.json")
    baseline_path = baselines_dir / baseline_name

    if not baseline_path.exists():
        return None

    with open(baseline_path) as f:
        return json.load(f)


def load_config(config_name: str, config_dir: Path) -> dict:
    """Load simulation config."""
    config_path = config_dir / config_name
    with open(config_path) as f:
        return json.load(f)


def create_strategy_for_mock(
    strategy_config: StrategyConfig,
    strategy_history: SimulationStrategyHistory,
    initial_params: Any,
) -> Any:
    """Creates a real strategy instance for mock testing.

    Args:
        strategy_config: Strategy configuration from config JSON.
        strategy_history: History object for recording metrics.
        initial_params: Mock initial parameters.

    Returns:
        Real strategy instance that will execute actual aggregation code.
    """
    common_kwargs = {
        "initial_parameters": initial_params,
        "min_fit_clients": 2,
        "min_evaluate_clients": 2,
        "min_available_clients": 2,
        "strategy_history": strategy_history,
        "remove_clients": getattr(strategy_config, "remove_clients", False),
        "begin_removing_from_round": getattr(strategy_config, "begin_removing_from_round", 1),
    }

    keyword = strategy_config.aggregation_strategy_keyword

    if keyword == "fedavg":
        return FedAvgStrategy(
            strategy_history=strategy_history,
            initial_parameters=initial_params,
            min_fit_clients=2,
            min_evaluate_clients=2,
            min_available_clients=2,
        )

    elif keyword == "krum":
        return KrumBasedRemovalStrategy(
            num_malicious_clients=getattr(strategy_config, "num_of_malicious_clients", 0),
            num_krum_selections=getattr(strategy_config, "num_krum_selections", 1),
            **common_kwargs,
        )

    elif keyword == "multi-krum":
        return MultiKrumStrategy(
            num_of_malicious_clients=getattr(strategy_config, "num_of_malicious_clients", 0),
            num_krum_selections=getattr(strategy_config, "num_krum_selections", 1),
            **common_kwargs,
        )

    elif keyword == "multi-krum-based":
        return MultiKrumBasedRemovalStrategy(
            num_of_malicious_clients=getattr(strategy_config, "num_of_malicious_clients", 0),
            num_krum_selections=getattr(strategy_config, "num_krum_selections", 1),
            **common_kwargs,
        )

    elif keyword == "bulyan":
        return BulyanStrategy(
            num_krum_selections=getattr(strategy_config, "num_krum_selections", 1),
            **common_kwargs,
        )

    elif keyword == "rfa":
        return RFABasedRemovalStrategy(
            num_of_malicious_clients=getattr(strategy_config, "num_of_malicious_clients", 0),
            **common_kwargs,
        )

    elif keyword == "trimmed_mean":
        return TrimmedMeanBasedRemovalStrategy(
            trim_ratio=getattr(strategy_config, "trim_ratio", 0.1),
            **common_kwargs,
        )

    elif keyword in (
        "pid",
        "pid_scaled",
        "pid_standardized",
        "pid_standardized_score_based",
    ):
        return PIDBasedRemovalStrategy(
            ki=getattr(strategy_config, "Ki", 0.1),
            kp=getattr(strategy_config, "Kp", 1.0),
            kd=getattr(strategy_config, "Kd", 0.1),
            num_std_dev=getattr(strategy_config, "num_std_dev", 2.0),
            network_model=None,
            aggregation_strategy_keyword=keyword,
            use_lora=False,
            **common_kwargs,
        )

    elif keyword == "trust":
        return TrustBasedRemovalStrategy(
            beta_value=getattr(strategy_config, "beta_value", 0.9),
            trust_threshold=getattr(strategy_config, "trust_threshold", 0.5),
            **common_kwargs,
        )

    else:
        logging.warning(f"Unknown strategy '{keyword}', falling back to FedAvg")
        return FedAvgStrategy(
            strategy_history=strategy_history,
            initial_parameters=initial_params,
            min_fit_clients=2,
            min_evaluate_clients=2,
            min_available_clients=2,
        )


def populate_history_from_baseline(strategy_history, baseline_strategy: dict, num_clients: int):
    """Populates SimulationStrategyHistory with baseline data."""
    per_round = baseline_strategy.get("per_round", {})
    per_client = baseline_strategy.get("per_client", {})
    total_rounds = baseline_strategy.get("total_rounds", 10)

    for client_id in range(num_clients):
        client_data = per_client.get(str(client_id), {})
        for round_num in range(1, total_rounds + 1):
            idx = round_num - 1

            strategy_history.insert_single_client_history_entry(
                client_id=client_id,
                current_round=round_num,
                removal_criterion=client_data.get("removal_criterion", [0.0] * total_rounds)[idx],
                absolute_distance=client_data.get("absolute_distance", [0.0] * total_rounds)[idx],
                loss=client_data.get("loss", [0.0] * total_rounds)[idx],
                accuracy=client_data.get("accuracy", [0.0] * total_rounds)[idx],
                aggregation_participation=client_data.get("participation", [1] * total_rounds)[idx],
            )

    aggregated_loss = per_round.get("aggregated_loss", [0.0] * total_rounds)
    for round_num in range(1, total_rounds + 1):
        idx = round_num - 1
        strategy_history.insert_round_history_entry(
            score_calculation_time_nanos=0,
            removal_threshold=0.0,
            loss_aggregated=aggregated_loss[idx] if idx < len(aggregated_loss) else 0.0,
        )


class MockFederatedSimulation:
    """Mock simulation that uses baseline data instead of real training."""

    def __init__(self, strategy_config, strategy_history, attack_schedule=None):
        self.strategy_config = strategy_config
        self.strategy_history = strategy_history
        self._attack_schedule = attack_schedule or []

    def get_attack_schedule_as_dict(self):
        return self._attack_schedule


def generate_mock_attack_snapshots(
    attack_schedule: list,
    output_dir: str,
    num_clients: int,
    total_rounds: int,
    strategy_number: int,
    max_samples: int = 5,
    save_format: str = "pickle",
) -> int:
    """Generates mock attack snapshots for CI testing.

    Args:
        attack_schedule: List of attack configurations.
        output_dir: Output directory path.
        num_clients: Total number of clients.
        total_rounds: Total number of rounds.
        strategy_number: Strategy index.
        max_samples: Max samples per snapshot.
        save_format: Snapshot format.

    Returns:
        Number of snapshots generated.
    """
    snapshots_generated = 0

    for attack in attack_schedule:
        attack_type = attack.get("attack_type", "unknown")
        start_round = attack.get("start_round", 1)
        end_round = attack.get("end_round", total_rounds)

        selection = attack.get("selection_strategy", "percentage")
        if selection == "percentage":
            percentage = attack.get("malicious_percentage", 0.2)
            num_malicious = max(1, int(num_clients * percentage))
            malicious_clients = list(range(num_malicious))
        elif selection == "specific":
            malicious_clients = attack.get("client_ids", [0])
        else:
            malicious_clients = [0]

        for round_num in range(start_round, min(end_round, total_rounds) + 1):
            for client_id in malicious_clients:
                mock_data = torch.rand(max_samples, 1, 28, 28)
                mock_labels = torch.randint(0, 10, (max_samples,))

                if attack_type == "label_flipping":
                    original_labels = (mock_labels + 1) % 10
                else:
                    original_labels = mock_labels.clone()

                try:
                    save_attack_snapshot(
                        client_id=client_id,
                        round_num=round_num,
                        attack_config=attack,
                        data_sample=mock_data,
                        labels_sample=mock_labels,
                        original_labels_sample=original_labels,
                        output_dir=output_dir,
                        max_samples=max_samples,
                        save_format=save_format,
                        strategy_number=strategy_number,
                    )
                    snapshots_generated += 1
                except Exception as e:
                    logging.warning(
                        f"Failed to generate mock snapshot for client {client_id}, "
                        f"round {round_num}: {e}"
                    )

    return snapshots_generated


def run_mock_simulation(
    config_name: str,
    config_dir: Path,
    baselines_dir: Path,
    output_base: Path,
) -> tuple[bool, Path | None, list[str]]:
    """Runs mock simulation with REAL strategy code execution.

    Args:
        config_name: Name of config file.
        config_dir: Directory containing config files.
        baselines_dir: Directory containing baselines.
        output_base: Base output directory.

    Returns:
        Tuple of (success, output_dir, errors).
    """
    errors = []

    baseline = load_baseline(config_name, baselines_dir)

    try:
        config = load_config(config_name, config_dir)
    except Exception as e:
        errors.append(f"Failed to load config: {e}")
        return False, None, errors

    try:
        directory_handler = DirectoryHandler()
        assert directory_handler.dirname is not None
        dirname: str = directory_handler.dirname
        output_dir = Path(dirname)

        shared_settings = config.get("shared_settings", {})
        strategies = config.get("simulation_strategies", [{}])
        num_clients = shared_settings.get("num_of_clients", 10)
        if baseline:
            num_clients = baseline.get("num_clients", num_clients)

        executed_simulations = []

        for strat_idx, strategy_overrides in enumerate(strategies):
            merged_config = {**shared_settings, **strategy_overrides}
            merged_config["strategy_number"] = strat_idx

            strategy_config = StrategyConfig.from_dict(merged_config)
            strategy_config.strategy_number = strat_idx

            class MockDatasetHandler:
                def __init__(self):
                    self.malicious_clients = set()
                    for attack in merged_config.get("attack_schedule", []):
                        selected = attack.get("_selected_clients", [])
                        self.malicious_clients.update(selected)

            dataset_handler = MockDatasetHandler()

            strategy_history = SimulationStrategyHistory(
                strategy_config=strategy_config,
                dataset_handler=dataset_handler,  # type: ignore[arg-type]
            )

            rng = np.random.default_rng(42)
            initial_params = ndarrays_to_parameters(
                [
                    rng.standard_normal((100, 10)).astype(np.float32),
                    rng.standard_normal(10).astype(np.float32),
                ]
            )

            strategy = create_strategy_for_mock(
                strategy_config=strategy_config,
                strategy_history=strategy_history,
                initial_params=initial_params,
            )

            num_rounds = merged_config.get("num_of_rounds", 10)
            mock_start_simulation(
                client_fn=lambda cid: MockClient(MockNumPyClient(int(cid))),
                num_clients=num_clients,
                config=MockServerConfig(num_rounds),
                strategy=strategy,
                initial_parameters=ndarrays_to_parameters(
                    [
                        rng.standard_normal((100, 10)).astype(np.float32),
                        rng.standard_normal(10).astype(np.float32),
                    ]
                ),
            )

            strategy_history.calculate_additional_rounds_data()

            mock_sim = MockFederatedSimulation(
                strategy_config=strategy_config,
                strategy_history=strategy_history,
                attack_schedule=merged_config.get("attack_schedule", []),
            )

            if strategy_config.save_plots:
                new_plot_handler.show_plots_within_strategy(
                    mock_sim,  # type: ignore[arg-type]
                    directory_handler,
                )

            if strategy_config.save_csv:
                directory_handler.save_csv_and_config(strategy_history)

            attack_schedule = merged_config.get("attack_schedule", [])
            save_snapshots = merged_config.get("save_attack_snapshots", "false")
            if attack_schedule and str(save_snapshots).lower() == "true":
                total_rounds = merged_config.get("num_of_rounds", 10)
                snapshot_format = merged_config.get("attack_snapshot_format", "pickle")
                max_samples = merged_config.get("snapshot_max_samples", 5)

                generate_mock_attack_snapshots(
                    attack_schedule=attack_schedule,
                    output_dir=dirname,
                    num_clients=num_clients,
                    total_rounds=total_rounds,
                    strategy_number=strat_idx,
                    max_samples=max_samples,
                    save_format=snapshot_format,
                )

                try:
                    generate_summary_json(
                        dirname,
                        run_config=merged_config,
                        strategy_number=strat_idx,
                    )
                    generate_snapshot_index(
                        dirname,
                        run_config=merged_config,
                        strategy_number=strat_idx,
                    )
                except Exception as e:
                    logging.warning(f"Failed to generate snapshot index: {e}")

            executed_simulations.append(mock_sim)

        if len(executed_simulations) > 1:
            new_plot_handler.show_inter_strategy_plots(executed_simulations, directory_handler)

        generate_main_dashboard(dirname)

        return True, output_dir, []

    except Exception as e:
        errors.append(f"Error running mock simulation: {e}")
        errors.append(traceback.format_exc())
        return False, None, errors


def verify_outputs(output_dir: Path) -> tuple[bool, list[str], dict]:
    """Verifies expected outputs were created and return file counts.

    Args:
        output_dir: Path to output directory.

    Returns:
        Tuple of (success, errors, counts).
    """
    errors = []
    counts = {"plots": 0, "csvs": 0, "snapshots": 0, "html": False}

    if not output_dir.exists():
        errors.append(f"Output directory not found: {output_dir}")
        return False, errors, counts

    csv_dir = output_dir / "csv"
    if not csv_dir.exists():
        errors.append("Missing csv/ directory")
    else:
        csv_files = list(csv_dir.glob("*.csv"))
        if not csv_files:
            errors.append("No CSV files found")
        else:
            counts["csvs"] = len(csv_files)
            for csv_file in csv_files:
                csv_errors = _validate_csv_file(csv_file)
                errors.extend(csv_errors)

    plots = list(output_dir.glob("*.pdf"))
    if not plots:
        errors.append("No plot files (*.pdf) found")
    else:
        counts["plots"] = len(plots)

    if not (output_dir / "index.html").exists():
        errors.append("Missing index.html")
    else:
        counts["html"] = True

    counts["snapshots"] = _count_attack_snapshots(output_dir)

    return len(errors) == 0, errors, counts


def _validate_csv_file(csv_path: Path) -> list[str]:
    """Validates a CSV file has expected structure."""
    errors = []
    try:
        with open(csv_path) as f:
            reader = csv.reader(f)
            headers = next(reader, None)

            if headers is None:
                errors.append(f"{csv_path.name}: Empty CSV file")
                return errors

            if not csv_path.name.startswith("exec_stats") and "round" not in headers:
                errors.append(f"{csv_path.name}: Missing 'round' column")

            first_row = next(reader, None)
            if first_row is None:
                errors.append(f"{csv_path.name}: No data rows")

    except Exception as e:
        errors.append(f"{csv_path.name}: Error reading CSV - {e}")

    return errors


def _count_attack_snapshots(output_dir: Path) -> int:
    """Counts attack snapshot files across all strategies."""
    total = 0
    for snapshots_dir in output_dir.glob("attack_snapshots_*"):
        if snapshots_dir.is_dir():
            pickles = list(snapshots_dir.glob("client_*/round_*/*.pickle"))
            jsons = list(snapshots_dir.glob("client_*/round_*/*_metadata.json"))
            total += len(pickles) if pickles else len(jsons)
    return total


def main():
    parser = argparse.ArgumentParser(
        description="Run mock simulations using recorded baseline data"
    )
    parser.add_argument(
        "--config",
        help="Single config filename to run",
    )
    parser.add_argument(
        "--all-fast",
        action="store_true",
        help="Run all fast configs",
    )
    parser.add_argument(
        "--config-dir",
        default="testing",
        help="Subdirectory under config/simulation_strategies/ (default: testing)",
    )
    parser.add_argument(
        "--baselines-dir",
        default="tests/fixtures/baselines",
        help="Directory containing baselines (default: tests/fixtures/baselines)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify outputs after generation",
    )

    args = parser.parse_args()

    if args.all_fast:
        configs = FAST_CONFIGS
    elif args.config:
        configs = [args.config]
    else:
        configs = FAST_CONFIGS

    config_dir = project_root / "config" / "simulation_strategies" / args.config_dir
    baselines_dir = project_root / args.baselines_dir
    output_base = project_root / "out"

    missing_baselines = []
    for config_name in configs:
        baseline_name = config_name.replace(".json", ".baseline.json")
        if not (baselines_dir / baseline_name).exists():
            missing_baselines.append(config_name)

    if missing_baselines:
        console.print(f"[yellow]Missing baselines for: {missing_baselines}[/yellow]")
        console.print("[yellow]Run record_baselines.py first to create them.[/yellow]")

    configs = [c for c in configs if c not in missing_baselines]

    if not configs:
        console.print("[red]No configs with baselines to run[/red]")
        sys.exit(1)

    console.print(f"[cyan]Running {len(configs)} mock simulation(s)...[/cyan]\n")

    passed = 0
    failed = 0

    for idx, config_name in enumerate(configs, start=1):
        console.print(f"[{idx}/{len(configs)}] {config_name}...", end=" ")

        success, output_dir, errors = run_mock_simulation(
            config_name, config_dir, baselines_dir, output_base
        )

        if success:
            if args.verify and output_dir:
                verify_ok, verify_errors, counts = verify_outputs(output_dir)
                if verify_ok:
                    console.print(
                        f"[green]OK[/green] "
                        f"({counts['plots']} plots, {counts['csvs']} CSVs, {counts['snapshots']} snapshots)"
                    )
                    passed += 1
                else:
                    console.print("[red]VERIFY FAILED[/red]")
                    for err in verify_errors:
                        console.print(f"  - {err}")
                    failed += 1
            else:
                console.print("[green]OK[/green]")
                passed += 1
        else:
            console.print("[red]FAILED[/red]")
            for err in errors:
                console.print(f"  - {err}")
            failed += 1

    console.print(f"\n[bold]Summary: {passed} passed, {failed} failed[/bold]")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(130)
