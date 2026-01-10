from __future__ import annotations

import argparse
import gc
import json
import logging
import os
import time
from pathlib import Path

from src.utils.warnings_config import apply_env_vars, configure_warnings

apply_env_vars()

# Suppress joblib CPU count warnings
os.environ["LOKY_MAX_CPU_COUNT"] = str(os.cpu_count() or 1)
os.environ["OMP_NUM_THREADS"] = str(os.cpu_count() or 1)

# Prevent threadpoolctl from using GetModuleFileNameEx on Windows (causes OSError)
os.environ["THREADPOOLCTL_SKIP_WINDOWS_ENUM"] = "1"

# Set HuggingFace cache directory to avoid API rate limits
os.environ["HF_HOME"] = "./cache/huggingface"

import ray
import torch

configure_warnings()

from src.config_loaders.config_loader import ConfigLoader
from src.data_models.simulation_strategy_config import StrategyConfig
from src.dataset_handlers.dataset_handler import DatasetHandler
from src.federated_simulation import FederatedSimulation
from src.output_handlers import new_plot_handler
from src.output_handlers.directory_handler import DirectoryHandler
from src.utils.ray_logger import (
    RaySimulationMonitor,
    check_ray_cluster_health,
    log_ray_worker_event,
)
from src.utils.status_tracker import StatusTracker


def _serialize_config_for_logging(config_dict: dict) -> str:
    """Serialize config dict to JSON, converting torch.device to string."""
    serializable_dict = config_dict.copy()
    if isinstance(serializable_dict.get("training_device"), torch.device):
        serializable_dict["training_device"] = str(serializable_dict["training_device"])
    return json.dumps(serializable_dict, indent=4)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="FL Execution Framework - Run federated learning simulations"
    )

    parser.add_argument(
        "config_filename",
        type=str,
        nargs="?",
        default="example_strategy_config.json",
        help="Config filename (default: example_strategy_config.json)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging verbosity (default: INFO)",
    )

    return parser.parse_args()


class SimulationRunner:
    def __init__(self, config_filename: str, log_level: str = "INFO") -> None:
        if not logging.getLogger().hasHandlers():
            logging.basicConfig(
                level=getattr(logging, log_level), format="%(levelname)s: %(message)s"
            )
        logging.getLogger("flwr").propagate = False

        config_path = Path(config_filename)
        if not config_path.exists():
            config_path = Path("config/simulation_strategies") / config_filename

        self._config_loader = ConfigLoader(
            usecase_config_path=str(config_path),
            dataset_config_path="config/dataset_keyword_to_dataset_dir.json",
        )
        self._simulation_strategy_config_dicts = self._config_loader.get_usecase_config_list()
        self._dataset_config_list = self._config_loader.get_dataset_config_list()
        config_parent = config_path.parent.resolve()
        out_dir = Path("out").resolve()
        if config_parent != Path(".").resolve() and str(config_parent).startswith(str(out_dir)):
            self._directory_handler = DirectoryHandler(output_dir=str(config_parent))
        else:
            self._directory_handler = DirectoryHandler()

    def run(self):
        """Run simulations according to the specified usecase config"""

        # Extend Ray worker timeout to ensure reliability in multi-strategy runs
        os.environ["RAY_WORKER_REGISTER_TIMEOUT_SECONDS"] = "60"
        os.environ["RAY_ENABLE_RECORD_ACTOR_TASK_LOGGING"] = "1"
        logging.debug("Set RAY_worker_register_timeout_seconds=60 for multi-strategy reliability")

        first_config = self._simulation_strategy_config_dicts[0]
        total_rounds = first_config.get("num_of_rounds", 10)
        total_strategies = len(self._simulation_strategy_config_dicts)

        assert self._directory_handler.dirname is not None
        status_tracker = StatusTracker(
            output_dir=Path(self._directory_handler.dirname),
            total_rounds=total_rounds,
            total_strategies=total_strategies,
        )
        status_tracker.start()
        logging.debug(f"Status tracker started: {status_tracker.status_file}")

        simulation_id = Path(self._directory_handler.dirname).name
        ray_monitor = RaySimulationMonitor(
            output_dir=Path(self._directory_handler.dirname),
            simulation_id=simulation_id,
        )
        ray_monitor.start()

        try:
            executed_simulation_strategies = []

            for strategy_config_dict, strategy_number in zip(
                self._simulation_strategy_config_dicts,
                range(len(self._simulation_strategy_config_dicts)),
                strict=False,
            ):
                dataset_handler = None
                simulation_strategy = None
                strategy_start_time = time.time()

                try:
                    # Log strategy start event
                    log_ray_worker_event(
                        event_type="STRATEGY_START",
                        extra_info={
                            "strategy_number": strategy_number,
                            "total_strategies": total_strategies,
                            "simulation_id": simulation_id,
                        },
                    )

                    logging.info(
                        "\n"
                        + "-" * 50
                        + "Executing new strategy"
                        + "-" * 50
                        + "\n"
                        + "Strategy config:\n"
                        + _serialize_config_for_logging(strategy_config_dict)
                    )

                    strategy_config = StrategyConfig.from_dict(strategy_config_dict)
                    strategy_config.strategy_number = strategy_number

                    self._directory_handler.assign_dataset_dir(strategy_number)

                    dataset_handler = DatasetHandler(
                        strategy_config=strategy_config,
                        directory_handler=self._directory_handler,
                        dataset_config_list=self._dataset_config_list,
                    )
                    dataset_handler.setup_dataset()

                    assert self._directory_handler.dataset_dir is not None
                    simulation_strategy = FederatedSimulation(
                        strategy_config=strategy_config,
                        dataset_dir=self._directory_handler.dataset_dir,
                        dataset_handler=dataset_handler,
                        directory_handler=self._directory_handler,
                        status_tracker=status_tracker,
                    )
                    simulation_strategy.run_simulation()

                    executed_simulation_strategies.append(simulation_strategy)

                    new_plot_handler.show_plots_within_strategy(
                        simulation_strategy, self._directory_handler
                    )

                    simulation_strategy.strategy_history.calculate_additional_rounds_data()
                    self._directory_handler.save_csv_and_config(
                        simulation_strategy.strategy_history
                    )

                    strategy_duration = time.time() - strategy_start_time
                    ray_monitor.record_round(strategy_number, strategy_duration)
                    log_ray_worker_event(
                        event_type="STRATEGY_COMPLETE",
                        extra_info={
                            "strategy_number": strategy_number,
                            "duration_seconds": f"{strategy_duration:.2f}",
                            "simulation_id": simulation_id,
                        },
                    )

                except Exception as strategy_error:
                    # Log strategy-level errors
                    ray_monitor.record_error(strategy_error, strategy_number)
                    log_ray_worker_event(
                        event_type="STRATEGY_ERROR",
                        error_message=str(strategy_error),
                        extra_info={
                            "strategy_number": strategy_number,
                            "error_type": type(strategy_error).__name__,
                            "simulation_id": simulation_id,
                        },
                    )
                    raise

                finally:
                    # Cleanup resources even if simulation crashes
                    if dataset_handler is not None:
                        dataset_handler.teardown_dataset()

                    if ray.is_initialized():
                        health = check_ray_cluster_health()
                        if health.get("dead_nodes", 0) > 0:
                            log_ray_worker_event(
                                event_type="CLUSTER_DEGRADED",
                                extra_info={
                                    "dead_nodes": health.get("dead_nodes"),
                                    "alive_nodes": health.get("alive_nodes"),
                                    "simulation_id": simulation_id,
                                },
                            )
                        logging.debug(f"Ray cluster health before shutdown: {health}")

                    # Prevent errors in multi-strategy runs
                    if ray.is_initialized():
                        logging.debug("Shutting down Ray before cleanup...")
                        ray.shutdown()
                        time.sleep(3.0)
                        logging.debug("Ray shutdown complete after 3s cleanup delay")

                    logging.debug(f"Cleaning up resources after strategy {strategy_number}")

                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        logging.debug("GPU cache cleared")

                    # Keep only the strategy_history for plotting
                    if simulation_strategy is not None:
                        simulation_strategy._network_model = None
                        simulation_strategy._trainloaders = None
                        simulation_strategy._valloaders = None
                        simulation_strategy._dataset_loader = None

                    gc.collect()
                    logging.debug("Garbage collection completed")

                if strategy_number < total_strategies - 1:
                    status_tracker.next_strategy()

            new_plot_handler.show_inter_strategy_plots(
                executed_simulation_strategies, self._directory_handler
            )

            status_tracker.complete()
            logging.debug("Status tracker marked as completed")

            summary = ray_monitor.stop(success=True)
            logging.info(
                f"Ray simulation completed. Total errors: {summary.get('total_errors', 0)}"
            )

        except Exception as e:
            status_tracker.fail(str(e))
            logging.error(f"Simulation failed: {e}")

            ray_monitor.record_error(e)
            summary = ray_monitor.stop(success=False)
            logging.error(f"Ray simulation failed. Total errors: {summary.get('total_errors', 0)}")

            raise


if __name__ == "__main__":
    """Run simulation with config file and optional log level."""
    args = parse_arguments()

    simulation_runner = SimulationRunner(args.config_filename, args.log_level)
    simulation_runner.run()
