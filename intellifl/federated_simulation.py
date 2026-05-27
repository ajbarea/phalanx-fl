from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import flwr
import torch.nn as nn
from flwr.client import Client, ClientApp
from flwr.common import Context, ndarrays_to_parameters
from flwr.server import ServerApp, ServerAppComponents, ServerConfig

from intellifl.attack_utils.snapshot_html_reports import (
    generate_snapshot_index,
    generate_summary_json,
)
from intellifl.client_models.flower_client import FlowerClient
from intellifl.data_models.simulation_strategy_config import StrategyConfig
from intellifl.data_models.simulation_strategy_history import SimulationStrategyHistory
from intellifl.dataset_handlers.dataset_handler import DatasetHandler
from intellifl.dataset_loaders import (
    build_dataset_loader_and_model,
    get_hf_dataset_config,
)
from intellifl.simulation_strategies import build_strategy
from intellifl.utils.gpu_monitor import GPUMemoryMonitor
from intellifl.utils.status_tracker import StatusTracker

if TYPE_CHECKING:
    from torch.utils.data import DataLoader

    from intellifl.output_handlers.directory_handler import DirectoryHandler


def run_simulation(
    server_app: ServerApp,
    client_app: ClientApp,
    num_supernodes: int,
    backend_name: str = "ray",
    backend_config: dict[str, dict[str, Any]] | None = None,
    enable_tf_gpu_growth: bool = False,
    verbose_logging: bool = False,
) -> None:
    """Run Flower simulation without relying on deprecated public shim when possible.

    Flower is deprecating `flwr.simulation.run_simulation` in favor of `flwr run`.
    Until Phalanx fully migrates to CLI-managed runs, call the underlying
    simulation engine entrypoint used by Flower CLI and fall back for compatibility.
    """
    try:
        from flwr.common.telemetry import EventType
        from flwr.simulation.run_simulation import _run_simulation

        _run_simulation(
            num_supernodes=num_supernodes,
            client_app=client_app,
            server_app=server_app,
            backend_name=backend_name,
            backend_config=backend_config,
            enable_tf_gpu_growth=enable_tf_gpu_growth,
            verbose_logging=verbose_logging,
            exit_event=EventType.PYTHON_API_RUN_SIMULATION_LEAVE,
        )
        return
    except (ImportError, AttributeError, TypeError):
        # Compatibility fallback for Flower versions where internals differ.
        pass

    from flwr.simulation import run_simulation as _flwr_run_simulation

    _flwr_run_simulation(
        server_app=server_app,
        client_app=client_app,
        num_supernodes=num_supernodes,
        backend_name=backend_name,
        backend_config=backend_config,
        enable_tf_gpu_growth=enable_tf_gpu_growth,
        verbose_logging=verbose_logging,
    )


def weighted_average(metrics: list[tuple[int, dict[str, Any]]]) -> dict[str, Any]:
    """Compute weighted average of metrics from multiple clients.

    Args:
        metrics: List of (num_samples, metrics_dict) tuples from each client.

    Returns:
        Dict of metric names to their weighted average values.
    """
    if not metrics:
        return {}

    metric_names: set[str] = set()
    for _, client_metrics in metrics:
        metric_names.update(client_metrics.keys())

    weighted_metrics = {}
    for metric_name in metric_names:
        total_samples = 0
        weighted_sum = 0.0

        for num_samples, client_metrics in metrics:
            if metric_name in client_metrics:
                weighted_sum += num_samples * client_metrics[metric_name]
                total_samples += num_samples

        if total_samples > 0:
            weighted_metrics[metric_name] = weighted_sum / total_samples

    return weighted_metrics


class FederatedSimulation:
    """Orchestrates federated learning simulations via Flower framework."""

    def __init__(
        self,
        strategy_config: StrategyConfig,
        dataset_dir: str,
        dataset_handler: DatasetHandler,
        directory_handler: DirectoryHandler | None = None,
        status_tracker: StatusTracker | None = None,
    ):
        self.strategy_config = strategy_config

        dataset_keyword = getattr(self.strategy_config, "dataset_keyword", None)
        if (
            getattr(self.strategy_config, "dataset_source", None) == "huggingface"
            and dataset_keyword is not None
        ):
            try:
                hf_cfg = get_hf_dataset_config(dataset_keyword)
                for k, v in hf_cfg.items():
                    if not hasattr(self.strategy_config, k):
                        setattr(self.strategy_config, k, v)
                vocab_domain = hf_cfg.get("vocabulary_domain")
                if (
                    vocab_domain
                    and hasattr(self.strategy_config, "attack_schedule")
                    and self.strategy_config.attack_schedule
                ):
                    for attack in self.strategy_config.attack_schedule:
                        if (
                            attack.get("attack_type") == "token_replacement"
                            and "target_vocabulary" not in attack
                        ):
                            attack["target_vocabulary"] = vocab_domain
            except Exception as e:
                logging.warning(
                    f"Could not inject dataset fields from huggingface_datasets.json: {e}"
                )

        if self.strategy_config.training_device and isinstance(
            self.strategy_config.training_device, str
        ):
            if self.strategy_config.training_device.lower() == "gpu":
                self.strategy_config.training_device = "cuda"

        self.rounds_history: Any = None

        self.dataset_handler = dataset_handler
        self.directory_handler = directory_handler
        self.status_tracker = status_tracker

        self.strategy_history = SimulationStrategyHistory(
            strategy_config=self.strategy_config, dataset_handler=self.dataset_handler
        )

        assert self.strategy_config.training_device is not None, "training_device must be set"
        self.gpu_monitor = GPUMemoryMonitor(self.strategy_config.training_device)
        self._dataset_dir = dataset_dir

        self._network_model: nn.Module | None = None
        self._aggregation_strategy: flwr.server.strategy.Strategy | None = None
        # Concrete loader type comes back from
        # `dataset_loaders.build_dataset_loader_and_model` — the union of
        # FederatedDatasetLoader / MedQuADDatasetLoader / HuggingFaceTextDatasetLoader
        # is wider than this attribute needs to know.
        self._dataset_loader: Any = None

        self._trainloaders: list[DataLoader[Any]] | None = None
        self._valloaders: list[DataLoader[Any]] | None = None

        self._assign_all_properties()

    def run_simulation(self) -> None:
        """Execute federated simulation using Flower's simulation engine."""
        self.gpu_monitor.log_memory_usage("before simulation start")

        assert self.strategy_config.num_of_clients is not None, "num_of_clients must be set"
        assert self.strategy_config.num_of_rounds is not None, "num_of_rounds must be set"
        assert self.strategy_config.cpus_per_client is not None, "cpus_per_client must be set"
        assert self.strategy_config.gpus_per_client is not None, "gpus_per_client must be set"

        client_app = ClientApp(client_fn=self.client_fn)

        strategy = self._aggregation_strategy
        num_rounds = self.strategy_config.num_of_rounds

        def server_fn(context: Context) -> ServerAppComponents:
            return ServerAppComponents(
                strategy=strategy,
                config=ServerConfig(num_rounds=num_rounds),
            )

        server_app = ServerApp(server_fn=server_fn)

        # num_supernodes = number of virtual clients; backend_config sets resource allocation
        run_simulation(
            server_app=server_app,
            client_app=client_app,
            num_supernodes=self.strategy_config.num_of_clients,
            backend_config={
                "client_resources": {
                    "num_cpus": self.strategy_config.cpus_per_client,
                    "num_gpus": self.strategy_config.gpus_per_client,
                },
            },
        )

        self.gpu_monitor.log_memory_usage("after simulation complete")
        self.gpu_monitor.check_memory_threshold(threshold_percent=85.0)

        if self.directory_handler:
            output_dir = getattr(self.directory_handler, "dirname", None)
            if output_dir and self.strategy_config.strategy_number is not None:
                if self.strategy_config.attack_schedule:
                    try:
                        run_config: dict[str, int | None] = {
                            "num_of_clients": self.strategy_config.num_of_clients,
                            "num_of_rounds": self.strategy_config.num_of_rounds,
                        }
                        generate_summary_json(
                            output_dir, run_config, self.strategy_config.strategy_number
                        )
                        generate_snapshot_index(
                            output_dir, run_config, self.strategy_config.strategy_number
                        )
                    except Exception as e:
                        logging.warning(f"Failed to generate attack snapshot index/summary: {e}")

    def _assign_all_properties(self) -> None:
        """Initialize dataset loaders, network model, and aggregation strategy."""
        self._assign_dataset_loaders_and_network_model()
        self._assign_aggregation_strategy()

    def _assign_dataset_loaders_and_network_model(self) -> None:
        """Configure dataset loader and network model based on dataset_keyword."""
        assert self.strategy_config.num_of_clients is not None, "num_of_clients must be set"
        assert self.strategy_config.batch_size is not None, "batch_size must be set"
        assert self.strategy_config.training_subset_fraction is not None, (
            "training_subset_fraction must be set"
        )

        dataset_loader, self._network_model = build_dataset_loader_and_model(
            keyword=self.strategy_config.dataset_keyword,
            config=self.strategy_config,
            dataset_dir=self._dataset_dir,
        )

        self._dataset_loader = dataset_loader
        self._trainloaders, self._valloaders = dataset_loader.load_datasets()

    def _assign_aggregation_strategy(self) -> None:
        """Configure aggregation strategy based on aggregation_strategy_keyword."""

        aggregation_strategy_keyword = self.strategy_config.aggregation_strategy_keyword

        eval_fn = (
            weighted_average
            if self.strategy_config.evaluate_metrics_aggregation_fn == "weighted_average"
            else None
        )

        assert self._network_model is not None, "_network_model must be set before strategy"

        common_kwargs: dict[str, Any] = {
            "initial_parameters": ndarrays_to_parameters(
                self._get_model_params(self._network_model)
            ),
            "min_fit_clients": self.strategy_config.min_fit_clients,
            "min_evaluate_clients": self.strategy_config.min_evaluate_clients,
            "min_available_clients": self.strategy_config.min_available_clients,
            "evaluate_metrics_aggregation_fn": eval_fn,
            "fit_metrics_aggregation_fn": weighted_average,
            "remove_clients": self.strategy_config.remove_clients,
            "begin_removing_from_round": self.strategy_config.begin_removing_from_round,
            "strategy_history": self.strategy_history,
            "status_tracker": self.status_tracker,
        }

        self._aggregation_strategy = build_strategy(
            keyword=aggregation_strategy_keyword,
            config=self.strategy_config,
            common_kwargs=common_kwargs,
            ctx={
                "network_model": self._network_model,
                "keyword": aggregation_strategy_keyword,
            },
        )

    def client_fn(self, context: Context) -> Client:
        """Create a Flower client for the given partition.

        Args:
            context: Flower Context with node_config["partition-id"] identifying the client.

        Returns:
            Configured FlowerClient instance.
        """
        assert self._network_model is not None, "_network_model must be set"
        assert self._trainloaders is not None, "_trainloaders must be set"
        assert self._valloaders is not None, "_valloaders must be set"
        partition_id: int = int(context.node_config["partition-id"])

        net = self._network_model.to(self.strategy_config.training_device)

        use_lora = bool(
            getattr(self.strategy_config, "use_llm", None)
            and getattr(self.strategy_config, "llm_finetuning", None) == "lora"
        )

        trainloader = self._trainloaders[partition_id]
        valloader = self._valloaders[partition_id]

        attacks_schedule = None
        if self.strategy_config.attack_schedule:
            attacks_schedule = self.strategy_config.attack_schedule

        output_dir: str | None = None
        if self.directory_handler:
            output_dir = getattr(self.directory_handler, "dirname", None)

        save_attack_snapshots = getattr(self.strategy_config, "save_attack_snapshots", False)

        attack_snapshot_format = getattr(
            self.strategy_config, "attack_snapshot_format", "pickle_and_visual"
        )
        snapshot_max_samples = getattr(self.strategy_config, "snapshot_max_samples", 6)

        experiment_info: dict[str, Any] | None = None
        if output_dir:
            experiment_info = {
                "run_id": Path(output_dir).name,
                "total_clients": self.strategy_config.num_of_clients,
                "total_rounds": self.strategy_config.num_of_rounds,
            }

        tokenizer = None
        if (
            getattr(self.strategy_config, "model_type", None) == "transformer"
            and self._dataset_loader is not None
        ):
            tokenizer = getattr(self._dataset_loader, "tokenizer", None)

        num_malicious = self.strategy_config.num_of_malicious_clients or 0
        strategy_num = self.strategy_config.strategy_number or 0

        return FlowerClient(
            client_id=partition_id,
            net=net,
            trainloader=trainloader,
            valloader=valloader,
            training_device=self.strategy_config.training_device,
            num_of_client_epochs=self.strategy_config.num_of_client_epochs,
            model_type=cast(str, getattr(self.strategy_config, "model_type", "cnn")),
            use_lora=use_lora,
            num_malicious_clients=num_malicious,
            attacks_schedule=attacks_schedule,
            save_attack_snapshots=save_attack_snapshots,
            attack_snapshot_format=attack_snapshot_format,
            snapshot_max_samples=snapshot_max_samples,
            output_dir=output_dir,
            experiment_info=experiment_info,
            strategy_number=strategy_num,
            tokenizer=tokenizer,
            learning_rate=getattr(self.strategy_config, "learning_rate", None),
        ).to_client()

    @staticmethod
    def _get_model_params(model: nn.Module) -> list[Any]:
        """Extract model parameters as numpy arrays for Flower serialization."""
        # Lazy import prevents sklearn->threadpoolctl race condition in Ray workers on Windows
        from peft import PeftModel, get_peft_model_state_dict

        if isinstance(model, PeftModel):
            # LoRA models only transmit adapter params, not full base model
            state_dict = get_peft_model_state_dict(model)
            return [val.cpu().numpy() for val in state_dict.values()]

        return [val.cpu().numpy() for _, val in model.state_dict().items()]
