from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import flwr
import torch.nn as nn
from flwr.client import Client, ClientApp
from flwr.common import Context, ndarrays_to_parameters
from flwr.server import ServerApp, ServerAppComponents, ServerConfig
from flwr.simulation import run_simulation

from intellifl.attack_utils.snapshot_html_reports import (
    generate_snapshot_index,
    generate_summary_json,
)
from intellifl.client_models.flower_client import FlowerClient
from intellifl.data_models.simulation_strategy_config import StrategyConfig
from intellifl.data_models.simulation_strategy_history import SimulationStrategyHistory
from intellifl.dataset_handlers.dataset_handler import DatasetHandler
from intellifl.dataset_loaders.huggingface_image_dataset_loader import (
    HuggingFaceImageDatasetLoader,
)
from intellifl.dataset_loaders.huggingface_text_dataset_loader import (
    HuggingFaceTextDatasetLoader,
)
from intellifl.dataset_loaders.image_dataset_loader import ImageDatasetLoader
from intellifl.dataset_loaders.image_transformers.cifar100_image_transformer import (
    cifar100_image_transformer,
)
from intellifl.dataset_loaders.image_transformers.femnist_image_transformer import (
    femnist_image_transformer,
)
from intellifl.dataset_loaders.image_transformers.flair_image_transformer import (
    flair_image_transformer,
)
from intellifl.dataset_loaders.image_transformers.its_image_transformer import (
    its_image_transformer,
)
from intellifl.dataset_loaders.image_transformers.lung_photos_image_transformer import (
    lung_cancer_image_transformer,
)
from intellifl.dataset_loaders.image_transformers.medmnist_2d_grayscale_image_transformer import (
    medmnist_2d_grayscale_image_transformer,
)
from intellifl.dataset_loaders.image_transformers.medmnist_2d_rgb_image_transformer import (
    medmnist_2d_rgb_image_transformer,
)
from intellifl.dataset_loaders.medquad_dataset_loader import MedQuADDatasetLoader
from intellifl.network_models import build_cnn_model
from intellifl.network_models.bert_model_definition import load_model, load_model_with_lora
from intellifl.network_models.dynamic_cnn import DynamicCNN
from intellifl.simulation_strategies.arkrum_strategy import ArKrumStrategy
from intellifl.simulation_strategies.bulyan_strategy import BulyanStrategy
from intellifl.simulation_strategies.fedavg_strategy import FedAvgStrategy
from intellifl.simulation_strategies.krum_based_removal_strategy import (
    KrumBasedRemovalStrategy,
)
from intellifl.simulation_strategies.multi_krum_based_removal_strategy import (
    MultiKrumBasedRemovalStrategy,
)
from intellifl.simulation_strategies.multi_krum_strategy import MultiKrumStrategy
from intellifl.simulation_strategies.pid_based_removal_strategy import PIDBasedRemovalStrategy
from intellifl.simulation_strategies.rfa_based_removal_strategy import RFABasedRemovalStrategy
from intellifl.simulation_strategies.trimmed_mean_based_removal_strategy import (
    TrimmedMeanBasedRemovalStrategy,
)
from intellifl.simulation_strategies.trust_based_removal_strategy import (
    TrustBasedRemovalStrategy,
)
from intellifl.utils.gpu_monitor import GPUMemoryMonitor
from intellifl.utils.ray_config import RayConfig
from intellifl.utils.status_tracker import StatusTracker

if TYPE_CHECKING:
    from torch.utils.data import DataLoader

    from intellifl.output_handlers.directory_handler import DirectoryHandler


def get_hf_dataset_config(dataset_keyword: str) -> dict:
    """
    Load HuggingFace dataset config for a given keyword from config/huggingface_datasets.json.
    """
    config_path = os.path.join(os.path.dirname(__file__), "../config/huggingface_datasets.json")
    with open(config_path, encoding="utf-8") as f:
        all_configs = json.load(f)
    return all_configs[dataset_keyword]


# Registry of image transformer names to their actual transform objects.
# Keeps the JSON config declarative — transformer values are string keys resolved here.
_IMAGE_TRANSFORMER_REGISTRY: dict[str, Any] = {}


def _build_image_transformer_registry() -> dict[str, Any]:
    """Lazily build the image transformer registry on first use."""
    if not _IMAGE_TRANSFORMER_REGISTRY:
        _IMAGE_TRANSFORMER_REGISTRY.update(
            {
                "cifar100_image_transformer": cifar100_image_transformer,
                "medmnist_2d_rgb_image_transformer": medmnist_2d_rgb_image_transformer,
                "medmnist_2d_grayscale_image_transformer": medmnist_2d_grayscale_image_transformer,
                "femnist_image_transformer": femnist_image_transformer,
                "flair_image_transformer": flair_image_transformer,
                "its_image_transformer": its_image_transformer,
                "lung_cancer_image_transformer": lung_cancer_image_transformer,
            }
        )
    return _IMAGE_TRANSFORMER_REGISTRY


def _resolve_image_transformer(name: str | None) -> Any:
    """Resolve an image transformer string key from the JSON config to its transform object."""
    if name is None:
        return None
    registry = _build_image_transformer_registry()
    if name not in registry:
        raise ValueError(
            f"Unknown image_transformer '{name}'. Available: {sorted(registry.keys())}"
        )
    return registry[name]


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
        self._dataset_loader: (
            ImageDatasetLoader
            | MedQuADDatasetLoader
            | HuggingFaceTextDatasetLoader
            | HuggingFaceImageDatasetLoader
            | None
        ) = None

        self._trainloaders: list[DataLoader[Any]] | None = None
        self._valloaders: list[DataLoader[Any]] | None = None

        self._assign_all_properties()

    def run_simulation(self) -> None:
        """Execute federated simulation using Flower's run_simulation API."""
        self.gpu_monitor.log_memory_usage("before simulation start")

        assert self.strategy_config.num_of_clients is not None, "num_of_clients must be set"
        assert self.strategy_config.num_of_rounds is not None, "num_of_rounds must be set"
        assert self.strategy_config.cpus_per_client is not None, "cpus_per_client must be set"
        assert self.strategy_config.gpus_per_client is not None, "gpus_per_client must be set"

        # Research: Flower 1.13+ deprecates start_simulation() in favor of App wrappers
        # https://flower.ai/docs/framework/how-to-upgrade-to-flower-1.13.html
        client_app = ClientApp(client_fn=self.client_fn)

        strategy = self._aggregation_strategy
        num_rounds = self.strategy_config.num_of_rounds

        def server_fn(context: Context) -> ServerAppComponents:
            return ServerAppComponents(
                strategy=strategy,
                config=ServerConfig(num_rounds=num_rounds),
            )

        server_app = ServerApp(server_fn=server_fn)

        # Research: run_simulation replaces deprecated start_simulation (Flower 1.11+)
        # https://flower.ai/docs/framework/how-to-run-simulations.html
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
                "init_args": RayConfig.get_init_args(),
            },
        )

        self.gpu_monitor.log_memory_usage("after simulation complete")
        self.gpu_monitor.check_memory_threshold(threshold_percent=85.0)

        if self.strategy_config.attack_schedule and self.directory_handler:
            output_dir = getattr(self.directory_handler, "dirname", None)
            if output_dir and self.strategy_config.strategy_number is not None:
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
        dataset_keyword = self.strategy_config.dataset_keyword

        assert self.strategy_config.num_of_clients is not None, "num_of_clients must be set"
        assert self.strategy_config.batch_size is not None, "batch_size must be set"
        assert self.strategy_config.training_subset_fraction is not None, (
            "training_subset_fraction must be set"
        )

        num_of_clients = self.strategy_config.num_of_clients
        batch_size = self.strategy_config.batch_size
        training_subset_fraction = self.strategy_config.training_subset_fraction

        dataset_loader: (
            ImageDatasetLoader
            | MedQuADDatasetLoader
            | HuggingFaceTextDatasetLoader
            | HuggingFaceImageDatasetLoader
        )

        def create_image_loader(transformer: Any) -> ImageDatasetLoader:
            return ImageDatasetLoader(
                transformer=transformer,
                dataset_dir=self._dataset_dir,
                num_of_clients=num_of_clients,
                batch_size=batch_size,
                training_subset_fraction=training_subset_fraction,
            )

        # ── CNN datasets ─────────────────────────────────────────────────────
        # Maps each dataset keyword to its image transformer. Model is built
        # via the registry in intellifl.network_models (build_cnn_model).
        _cnn_loader_map: dict[str, Any] = {
            "its": its_image_transformer,
            "femnist_iid": femnist_image_transformer,
            "femnist_niid": femnist_image_transformer,
            "flair": flair_image_transformer,
            "pneumoniamnist": medmnist_2d_grayscale_image_transformer,
            "bloodmnist": medmnist_2d_rgb_image_transformer,
            "breastmnist": medmnist_2d_grayscale_image_transformer,
            "pathmnist": medmnist_2d_rgb_image_transformer,
            "dermamnist": medmnist_2d_rgb_image_transformer,
            "octmnist": medmnist_2d_grayscale_image_transformer,
            "retinamnist": medmnist_2d_rgb_image_transformer,
            "tissuemnist": medmnist_2d_grayscale_image_transformer,
            "organamnist": medmnist_2d_grayscale_image_transformer,
            "organcmnist": medmnist_2d_grayscale_image_transformer,
            "organsmnist": medmnist_2d_grayscale_image_transformer,
            "lung_photos": lung_cancer_image_transformer,
        }

        if dataset_keyword in _cnn_loader_map:
            dataset_loader = create_image_loader(_cnn_loader_map[dataset_keyword])
            self._network_model = build_cnn_model(dataset_keyword)

        elif dataset_keyword == "medquad":
            dataset_loader = MedQuADDatasetLoader(
                dataset_dir=self._dataset_dir,
                num_of_clients=num_of_clients,
                training_subset_fraction=training_subset_fraction,
                model_name=cast(str, getattr(self.strategy_config, "llm_model", "")),
                batch_size=batch_size,
                chunk_size=cast(int, getattr(self.strategy_config, "llm_chunk_size", 512)),
                mlm_probability=cast(float, getattr(self.strategy_config, "mlm_probability", 0.15)),
                num_poisoned_clients=self.strategy_config.num_of_malicious_clients or 0,
                attack_schedule=self.strategy_config.attack_schedule,
            )
            if getattr(self.strategy_config, "llm_finetuning", None) == "lora":
                self._network_model = load_model_with_lora(
                    model_name=cast(str, getattr(self.strategy_config, "llm_model", "")),
                    lora_rank=cast(int, getattr(self.strategy_config, "lora_rank", 8)),
                    lora_alpha=cast(int, getattr(self.strategy_config, "lora_alpha", 16)),
                    lora_dropout=cast(float, getattr(self.strategy_config, "lora_dropout", 0.05)),
                    lora_target_modules=cast(
                        list, getattr(self.strategy_config, "lora_target_modules", None)
                    ),
                )
            else:
                self._network_model = load_model(
                    model_name=cast(str, getattr(self.strategy_config, "llm_model", "")),
                )

        elif dataset_keyword in ["financial_phrasebank", "lexglue", "pubmed_classification_20k"]:
            hf_cfg = get_hf_dataset_config(dataset_keyword)
            dataset_loader = HuggingFaceTextDatasetLoader(
                hf_dataset_path=hf_cfg["hf_dataset_path"],
                hf_dataset_name=hf_cfg["hf_dataset_name"],
                tokenize_columns=hf_cfg.get("tokenize_columns"),
                remove_columns=hf_cfg.get("remove_columns"),
                dataset_dir=self._dataset_dir,
                num_of_clients=num_of_clients,
                training_subset_fraction=training_subset_fraction,
                model_name=cast(str, getattr(self.strategy_config, "llm_model", "")),
                batch_size=batch_size,
                chunk_size=cast(int, getattr(self.strategy_config, "llm_chunk_size", 512)),
                mlm_probability=cast(float, getattr(self.strategy_config, "mlm_probability", 0.15)),
                num_poisoned_clients=self.strategy_config.num_of_malicious_clients or 0,
                attack_schedule=self.strategy_config.attack_schedule,
            )
            if getattr(self.strategy_config, "llm_finetuning", None) == "lora":
                self._network_model = load_model_with_lora(
                    model_name=cast(str, getattr(self.strategy_config, "llm_model", "")),
                    lora_rank=cast(int, getattr(self.strategy_config, "lora_rank", 8)),
                    lora_alpha=cast(int, getattr(self.strategy_config, "lora_alpha", 16)),
                    lora_dropout=cast(float, getattr(self.strategy_config, "lora_dropout", 0.05)),
                    lora_target_modules=cast(
                        list, getattr(self.strategy_config, "lora_target_modules", None)
                    ),
                )
            else:
                self._network_model = load_model(
                    model_name=cast(str, getattr(self.strategy_config, "llm_model", "")),
                )

        elif dataset_keyword == "medal":
            max_samples = getattr(self.strategy_config, "max_dataset_samples", None)

            dataset_loader = HuggingFaceTextDatasetLoader(
                hf_dataset_path="cyrilzakka/pubmed-medline",
                hf_dataset_name=None,
                tokenize_columns=["content"],
                remove_columns=[
                    "id",
                    "title",
                    "authors",
                    "journal",
                    "content",
                    "source_url",
                    "publication_types",
                    "pubmed_id",
                    "split",
                ],
                dataset_dir=self._dataset_dir,
                num_of_clients=num_of_clients,
                training_subset_fraction=training_subset_fraction,
                model_name=cast(str, getattr(self.strategy_config, "llm_model", "")),
                batch_size=batch_size,
                chunk_size=cast(int, getattr(self.strategy_config, "llm_chunk_size", 512)),
                mlm_probability=cast(float, getattr(self.strategy_config, "mlm_probability", 0.15)),
                attack_schedule=self.strategy_config.attack_schedule,
                max_samples=max_samples,
            )
            if getattr(self.strategy_config, "llm_finetuning", None) == "lora":
                self._network_model = load_model_with_lora(
                    model_name=cast(str, getattr(self.strategy_config, "llm_model", "")),
                    lora_rank=cast(int, getattr(self.strategy_config, "lora_rank", 8)),
                    lora_alpha=cast(int, getattr(self.strategy_config, "lora_alpha", 16)),
                    lora_dropout=cast(float, getattr(self.strategy_config, "lora_dropout", 0.05)),
                    lora_target_modules=cast(
                        list, getattr(self.strategy_config, "lora_target_modules", None)
                    ),
                )
            else:
                self._network_model = load_model(
                    model_name=cast(str, getattr(self.strategy_config, "llm_model", "")),
                )

        elif dataset_keyword == "cifar100":
            hf_cfg = get_hf_dataset_config(dataset_keyword)
            transformer = _resolve_image_transformer(hf_cfg.get("image_transformer"))
            dataset_loader = HuggingFaceImageDatasetLoader(
                hf_dataset_path=hf_cfg["hf_dataset_path"],
                hf_dataset_name=hf_cfg.get("hf_dataset_name"),
                transformer=transformer,
                num_of_clients=num_of_clients,
                batch_size=batch_size,
                training_subset_fraction=training_subset_fraction,
                image_column=hf_cfg.get("image_column", "image"),
                label_column=hf_cfg.get("label_column", "label"),
            )
            self._network_model = DynamicCNN(
                num_classes=hf_cfg.get("num_classes", 100),
                input_channels=hf_cfg.get("input_channels", 3),
                input_height=hf_cfg.get("input_height", 32),
                input_width=hf_cfg.get("input_width", 32),
            )

        else:
            logging.error(
                f"You are parsing a strategy for dataset: {dataset_keyword}. "
                f"Check that you assign a correct dataset_loader at the code above."
            )
            sys.exit(-1)

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

        if aggregation_strategy_keyword == "trust":
            self._aggregation_strategy = TrustBasedRemovalStrategy(
                beta_value=self.strategy_config.beta_value,  # type: ignore[arg-type]
                trust_threshold=self.strategy_config.trust_threshold,  # type: ignore[arg-type]
                **common_kwargs,  # type: ignore[arg-type]
            )
        elif aggregation_strategy_keyword in (
            "pid",
            "pid_scaled",
            "pid_standardized",
            "pid_standardized_score_based",
        ):
            self._aggregation_strategy = PIDBasedRemovalStrategy(
                ki=self.strategy_config.Ki,  # type: ignore[arg-type]
                kp=self.strategy_config.Kp,  # type: ignore[arg-type]
                kd=self.strategy_config.Kd,  # type: ignore[arg-type]
                num_std_dev=self.strategy_config.num_std_dev,  # type: ignore[arg-type]
                network_model=self._network_model,
                aggregation_strategy_keyword=aggregation_strategy_keyword,
                use_lora=bool(
                    getattr(self.strategy_config, "use_llm", None)
                    and getattr(self.strategy_config, "llm_finetuning", None) == "lora"
                ),
                **common_kwargs,  # type: ignore[arg-type]
            )
        elif aggregation_strategy_keyword == "krum":
            self._aggregation_strategy = KrumBasedRemovalStrategy(
                num_malicious_clients=self.strategy_config.num_of_malicious_clients,  # type: ignore[arg-type]
                num_krum_selections=self.strategy_config.num_krum_selections,  # type: ignore[arg-type]
                **common_kwargs,  # type: ignore[arg-type]
            )
        elif aggregation_strategy_keyword == "multi-krum-based":
            self._aggregation_strategy = MultiKrumBasedRemovalStrategy(
                num_of_malicious_clients=self.strategy_config.num_of_malicious_clients,  # type: ignore[arg-type]
                num_krum_selections=self.strategy_config.num_krum_selections,  # type: ignore[arg-type]
                **common_kwargs,  # type: ignore[arg-type]
            )
        elif aggregation_strategy_keyword == "multi-krum":
            self._aggregation_strategy = MultiKrumStrategy(
                num_of_malicious_clients=self.strategy_config.num_of_malicious_clients,  # type: ignore[arg-type]
                num_krum_selections=self.strategy_config.num_krum_selections,  # type: ignore[arg-type]
                **common_kwargs,  # type: ignore[arg-type]
            )
        elif aggregation_strategy_keyword == "trimmed_mean":
            self._aggregation_strategy = TrimmedMeanBasedRemovalStrategy(
                trim_ratio=self.strategy_config.trim_ratio,  # type: ignore[arg-type]
                **common_kwargs,  # type: ignore[arg-type]
            )

        elif aggregation_strategy_keyword == "rfa":
            self._aggregation_strategy = RFABasedRemovalStrategy(
                num_of_malicious_clients=self.strategy_config.num_of_malicious_clients,  # type: ignore[arg-type]
                **common_kwargs,  # type: ignore[arg-type]
            )

        elif aggregation_strategy_keyword == "bulyan":
            self._aggregation_strategy = BulyanStrategy(
                num_krum_selections=self.strategy_config.num_krum_selections,  # type: ignore[arg-type]
                **common_kwargs,  # type: ignore[arg-type]
            )

        elif aggregation_strategy_keyword == "arkrum":
            self._aggregation_strategy = ArKrumStrategy(
                **common_kwargs,  # type: ignore[arg-type]
            )

        elif aggregation_strategy_keyword == "fedavg":
            self._aggregation_strategy = FedAvgStrategy(
                strategy_history=self.strategy_history,
                status_tracker=self.status_tracker,
                initial_parameters=ndarrays_to_parameters(
                    self._get_model_params(self._network_model)
                ),
                min_fit_clients=self.strategy_config.min_fit_clients,
                min_evaluate_clients=self.strategy_config.min_evaluate_clients,
                min_available_clients=self.strategy_config.min_available_clients,
                evaluate_metrics_aggregation_fn=eval_fn,
                fit_metrics_aggregation_fn=weighted_average,
            )

        else:
            raise NotImplementedError(
                f"The strategy {aggregation_strategy_keyword} not implemented!"
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
        snapshot_max_samples = getattr(self.strategy_config, "snapshot_max_samples", 5)

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
