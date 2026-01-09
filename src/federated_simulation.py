from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import flwr
import torch.nn as nn
from flwr.client import Client, ClientApp
from flwr.common import Context, ndarrays_to_parameters
from flwr.server import ServerApp, ServerAppComponents, ServerConfig
from flwr.simulation import run_simulation

from src.attack_utils.snapshot_html_reports import (
    generate_snapshot_index,
    generate_summary_json,
)
from src.client_models.flower_client import FlowerClient
from src.data_models.simulation_strategy_config import StrategyConfig
from src.data_models.simulation_strategy_history import SimulationStrategyHistory
from src.dataset_handlers.dataset_handler import DatasetHandler
from src.dataset_loaders.huggingface_text_dataset_loader import (
    HuggingFaceTextDatasetLoader,
)
from src.dataset_loaders.image_dataset_loader import ImageDatasetLoader
from src.dataset_loaders.image_transformers.femnist_image_transformer import (
    femnist_image_transformer,
)
from src.dataset_loaders.image_transformers.flair_image_transformer import (
    flair_image_transformer,
)
from src.dataset_loaders.image_transformers.its_image_transformer import (
    its_image_transformer,
)
from src.dataset_loaders.image_transformers.lung_photos_image_transformer import (
    lung_cancer_image_transformer,
)
from src.dataset_loaders.image_transformers.medmnist_2d_grayscale_image_transformer import (
    medmnist_2d_grayscale_image_transformer,
)
from src.dataset_loaders.image_transformers.medmnist_2d_rgb_image_transformer import (
    medmnist_2d_rgb_image_transformer,
)
from src.dataset_loaders.medquad_dataset_loader import MedQuADDatasetLoader
from src.network_models.bert_model_definition import load_model, load_model_with_lora
from src.network_models.bloodmnist_network_definition import BloodMNISTNetwork
from src.network_models.breastmnist_network_definition import BreastMNISTNetwork
from src.network_models.dermamnist_network_definition import DermaMNISTNetwork
from src.network_models.femnist_full_niid_network_definition import (
    FemnistFullNIIDNetwork,
)
from src.network_models.femnist_reduced_iid_network_definition import (
    FemnistReducedIIDNetwork,
)
from src.network_models.flair_network_definition import FlairNetwork
from src.network_models.its_network_definition import ITSNetwork
from src.network_models.lung_photos_network_definition import LungCancerCNN
from src.network_models.octmnist_network_definition import OctMNISTNetwork
from src.network_models.organamnist_network_definition import OrganAMNISTNetwork
from src.network_models.organcmnist_network_definition import OrganCMNISTNetwork
from src.network_models.organsmnist_network_definition import OrganSMNISTNetwork
from src.network_models.pathmnist_network_definition import PathMNISTNetwork
from src.network_models.pneumoniamnist_network_definition import PneumoniamnistNetwork
from src.network_models.retinamnist_network_definition import RetinaMNISTNetwork
from src.network_models.tissuemnist_network_definition import TissueMNISTNetwork
from src.simulation_strategies.arkrum_strategy import ArKrumStrategy
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
from src.utils.gpu_monitor import GPUMemoryMonitor
from src.utils.status_tracker import StatusTracker

if TYPE_CHECKING:
    from torch.utils.data import DataLoader

    from src.output_handlers.directory_handler import DirectoryHandler


def weighted_average(metrics: list[tuple[int, dict[str, Any]]]) -> dict[str, Any]:
    """Compute weighted average of metrics from multiple clients."""
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
    def __init__(
        self,
        strategy_config: StrategyConfig,
        dataset_dir: str,
        dataset_handler: DatasetHandler,
        directory_handler: DirectoryHandler | None = None,
        status_tracker: StatusTracker | None = None,
    ):
        self.strategy_config = strategy_config
        self.rounds_history: Any = None

        self.dataset_handler = dataset_handler
        self.directory_handler = directory_handler
        self.status_tracker = status_tracker

        self.strategy_history = SimulationStrategyHistory(
            strategy_config=self.strategy_config, dataset_handler=self.dataset_handler
        )

        # Assert training_device is not None for GPUMemoryMonitor
        assert self.strategy_config.training_device is not None, "training_device must be set"
        self.gpu_monitor = GPUMemoryMonitor(self.strategy_config.training_device)
        self._dataset_dir = dataset_dir

        self._network_model: nn.Module | None = None
        self._aggregation_strategy: flwr.server.strategy.Strategy | None = None
        self._dataset_loader: (
            ImageDatasetLoader | MedQuADDatasetLoader | HuggingFaceTextDatasetLoader | None
        ) = None

        self._trainloaders: list[DataLoader[Any]] | None = None
        self._valloaders: list[DataLoader[Any]] | None = None

        self._assign_all_properties()

    def run_simulation(self) -> None:
        """Start federated simulation using Flower's modern run_simulation API."""
        self.gpu_monitor.log_memory_usage("before simulation start")

        # Assert required config values are set
        assert self.strategy_config.num_of_clients is not None, "num_of_clients must be set"
        assert self.strategy_config.num_of_rounds is not None, "num_of_rounds must be set"
        assert self.strategy_config.cpus_per_client is not None, "cpus_per_client must be set"
        assert self.strategy_config.gpus_per_client is not None, "gpus_per_client must be set"

        # Research: Flower 1.13+ requires ClientApp/ServerApp architecture (Flower Framework Docs)
        # https://flower.ai/docs/framework/how-to-upgrade-to-flower-1.13.html
        # The start_simulation() API is deprecated; run_simulation() with App wrappers is preferred.
        client_app = ClientApp(client_fn=self.client_fn)

        # Capture strategy in closure for server_fn
        strategy = self._aggregation_strategy
        num_rounds = self.strategy_config.num_of_rounds

        def server_fn(context: Context) -> ServerAppComponents:
            """Create ServerAppComponents with the configured strategy."""
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
                }
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
        """Assign simulation properties based on strategy_dict"""

        self._assign_dataset_loaders_and_network_model()
        self._assign_aggregation_strategy()

    def _assign_dataset_loaders_and_network_model(self) -> None:
        """Assign dataset loader and the corresponding network model"""

        dataset_keyword = self.strategy_config.dataset_keyword

        # Assert required config values are set
        assert self.strategy_config.num_of_clients is not None, "num_of_clients must be set"
        assert self.strategy_config.batch_size is not None, "batch_size must be set"
        assert self.strategy_config.training_subset_fraction is not None, (
            "training_subset_fraction must be set"
        )

        num_of_clients = self.strategy_config.num_of_clients
        batch_size = self.strategy_config.batch_size
        training_subset_fraction = self.strategy_config.training_subset_fraction

        dataset_loader: ImageDatasetLoader | MedQuADDatasetLoader | HuggingFaceTextDatasetLoader

        # Helper function to create ImageDatasetLoader with common params
        def create_image_loader(transformer: Any) -> ImageDatasetLoader:
            return ImageDatasetLoader(
                transformer=transformer,
                dataset_dir=self._dataset_dir,
                num_of_clients=num_of_clients,
                batch_size=batch_size,
                training_subset_fraction=training_subset_fraction,
            )

        if dataset_keyword == "its":
            dataset_loader = create_image_loader(its_image_transformer)
            self._network_model = ITSNetwork()

        elif dataset_keyword == "femnist_iid":
            dataset_loader = create_image_loader(femnist_image_transformer)
            self._network_model = FemnistReducedIIDNetwork()

        elif dataset_keyword == "femnist_niid":
            dataset_loader = create_image_loader(femnist_image_transformer)
            self._network_model = FemnistFullNIIDNetwork()

        elif dataset_keyword == "flair":
            dataset_loader = create_image_loader(flair_image_transformer)
            self._network_model = FlairNetwork()

        elif dataset_keyword == "pneumoniamnist":
            dataset_loader = create_image_loader(medmnist_2d_grayscale_image_transformer)
            self._network_model = PneumoniamnistNetwork()

        elif dataset_keyword == "bloodmnist":
            dataset_loader = create_image_loader(medmnist_2d_rgb_image_transformer)
            self._network_model = BloodMNISTNetwork()

        elif dataset_keyword == "breastmnist":
            dataset_loader = create_image_loader(medmnist_2d_grayscale_image_transformer)
            self._network_model = BreastMNISTNetwork()

        elif dataset_keyword == "pathmnist":
            dataset_loader = create_image_loader(medmnist_2d_rgb_image_transformer)
            self._network_model = PathMNISTNetwork()

        elif dataset_keyword == "dermamnist":
            dataset_loader = create_image_loader(medmnist_2d_rgb_image_transformer)
            self._network_model = DermaMNISTNetwork()

        elif dataset_keyword == "octmnist":
            dataset_loader = create_image_loader(medmnist_2d_grayscale_image_transformer)
            self._network_model = OctMNISTNetwork()

        elif dataset_keyword == "retinamnist":
            dataset_loader = create_image_loader(medmnist_2d_rgb_image_transformer)
            self._network_model = RetinaMNISTNetwork()

        elif dataset_keyword == "tissuemnist":
            dataset_loader = create_image_loader(medmnist_2d_grayscale_image_transformer)
            self._network_model = TissueMNISTNetwork()

        elif dataset_keyword == "organamnist":
            dataset_loader = create_image_loader(medmnist_2d_grayscale_image_transformer)
            self._network_model = OrganAMNISTNetwork()

        elif dataset_keyword == "organcmnist":
            dataset_loader = create_image_loader(medmnist_2d_grayscale_image_transformer)
            self._network_model = OrganCMNISTNetwork()

        elif dataset_keyword == "organsmnist":
            dataset_loader = create_image_loader(medmnist_2d_grayscale_image_transformer)
            self._network_model = OrganSMNISTNetwork()

        elif dataset_keyword == "lung_photos":
            dataset_loader = create_image_loader(lung_cancer_image_transformer)
            self._network_model = LungCancerCNN()

        elif dataset_keyword == "medquad":
            dataset_loader = MedQuADDatasetLoader(
                dataset_dir=self._dataset_dir,
                num_of_clients=num_of_clients,
                training_subset_fraction=training_subset_fraction,
                model_name=self.strategy_config.llm_model,  # type: ignore[arg-type]
                batch_size=batch_size,
                chunk_size=self.strategy_config.llm_chunk_size,  # type: ignore[arg-type]
                mlm_probability=self.strategy_config.mlm_probability,  # type: ignore[arg-type]
                num_poisoned_clients=self.strategy_config.num_of_malicious_clients or 0,
                attack_schedule=self.strategy_config.attack_schedule,
            )
            if self.strategy_config.llm_finetuning == "lora":
                self._network_model = load_model_with_lora(
                    model_name=self.strategy_config.llm_model,
                    lora_rank=self.strategy_config.lora_rank,
                    lora_alpha=self.strategy_config.lora_alpha,
                    lora_dropout=self.strategy_config.lora_dropout,
                    lora_target_modules=self.strategy_config.lora_target_modules,
                )
            else:
                self._network_model = load_model(
                    model_name=self.strategy_config.llm_model,
                )

        elif dataset_keyword == "financial_phrasebank":
            dataset_loader = HuggingFaceTextDatasetLoader(
                hf_dataset_path="takala/financial_phrasebank",
                hf_dataset_name="sentences_allagree",
                tokenize_columns=["sentence"],
                remove_columns=["sentence", "label"],
                dataset_dir=self._dataset_dir,
                num_of_clients=num_of_clients,
                training_subset_fraction=training_subset_fraction,
                model_name=self.strategy_config.llm_model,  # type: ignore[arg-type]
                batch_size=batch_size,
                chunk_size=self.strategy_config.llm_chunk_size,  # type: ignore[arg-type]
                mlm_probability=self.strategy_config.mlm_probability,  # type: ignore[arg-type]
                num_poisoned_clients=self.strategy_config.num_of_malicious_clients or 0,
                attack_schedule=self.strategy_config.attack_schedule,
            )
            if self.strategy_config.llm_finetuning == "lora":
                self._network_model = load_model_with_lora(
                    model_name=self.strategy_config.llm_model,
                    lora_rank=self.strategy_config.lora_rank,
                    lora_alpha=self.strategy_config.lora_alpha,
                    lora_dropout=self.strategy_config.lora_dropout,
                    lora_target_modules=self.strategy_config.lora_target_modules,
                )
            else:
                self._network_model = load_model(
                    model_name=self.strategy_config.llm_model,
                )

        elif dataset_keyword == "lexglue":
            dataset_loader = HuggingFaceTextDatasetLoader(
                hf_dataset_path="coastalcph/lex_glue",
                hf_dataset_name="ledgar",
                tokenize_columns=["text"],
                remove_columns=["text", "label"],
                dataset_dir=self._dataset_dir,
                num_of_clients=num_of_clients,
                training_subset_fraction=training_subset_fraction,
                model_name=self.strategy_config.llm_model,  # type: ignore[arg-type]
                batch_size=batch_size,
                chunk_size=self.strategy_config.llm_chunk_size,  # type: ignore[arg-type]
                mlm_probability=self.strategy_config.mlm_probability,  # type: ignore[arg-type]
                num_poisoned_clients=self.strategy_config.num_of_malicious_clients or 0,
                attack_schedule=self.strategy_config.attack_schedule,
            )
            if self.strategy_config.llm_finetuning == "lora":
                self._network_model = load_model_with_lora(
                    model_name=self.strategy_config.llm_model,
                    lora_rank=self.strategy_config.lora_rank,
                    lora_alpha=self.strategy_config.lora_alpha,
                    lora_dropout=self.strategy_config.lora_dropout,
                    lora_target_modules=self.strategy_config.lora_target_modules,
                )
            else:
                self._network_model = load_model(
                    model_name=self.strategy_config.llm_model,
                )

        elif dataset_keyword == "medal":
            # For prod runs, omit max_samples to use full dataset
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
                model_name=self.strategy_config.llm_model,  # type: ignore[arg-type]
                batch_size=batch_size,
                chunk_size=self.strategy_config.llm_chunk_size,  # type: ignore[arg-type]
                mlm_probability=self.strategy_config.mlm_probability,  # type: ignore[arg-type]
                attack_schedule=self.strategy_config.attack_schedule,
                max_samples=max_samples,
            )
            if self.strategy_config.llm_finetuning == "lora":
                self._network_model = load_model_with_lora(
                    model_name=self.strategy_config.llm_model,
                    lora_rank=self.strategy_config.lora_rank,
                    lora_alpha=self.strategy_config.lora_alpha,
                    lora_dropout=self.strategy_config.lora_dropout,
                    lora_target_modules=self.strategy_config.lora_target_modules,
                )
            else:
                self._network_model = load_model(
                    model_name=self.strategy_config.llm_model,
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
        """Assign aggregation strategy"""

        aggregation_strategy_keyword = self.strategy_config.aggregation_strategy_keyword

        eval_fn = (
            weighted_average
            if self.strategy_config.evaluate_metrics_aggregation_fn == "weighted_average"
            else None
        )

        # Assert network model is set
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
                    self.strategy_config.use_llm and self.strategy_config.llm_finetuning == "lora"
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
        """Create a Flower client.

        Args:
            context: Flower Context object containing node configuration.
                     - context.node_config["partition-id"]: Client partition index (0, 1, 2, ...)
                     - context.node_id: Unique node identifier (large integer)

        Returns:
            A Flower Client instance.
        """
        # Assert required attributes are set
        assert self._network_model is not None, "_network_model must be set"
        assert self._trainloaders is not None, "_trainloaders must be set"
        assert self._valloaders is not None, "_valloaders must be set"
        partition_id: int = int(context.node_config["partition-id"])

        net = self._network_model.to(self.strategy_config.training_device)

        use_lora = bool(
            self.strategy_config.use_llm and self.strategy_config.llm_finetuning == "lora"
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
        if self.strategy_config.model_type == "transformer" and self._dataset_loader is not None:
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
            model_type=self.strategy_config.model_type,
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
        """
        Convert initial model params to suitable format.
        - For PEFT/LoRA models: return only LoRA adapter params
        - For regular models (CNN, etc.): return full state_dict
        """
        # Lazy import to avoid triggering sklearn -> threadpoolctl in Ray workers
        # This prevents GetModuleFileNameEx race condition on Windows
        from peft import PeftModel, get_peft_model_state_dict

        if isinstance(model, PeftModel):
            state_dict = get_peft_model_state_dict(model)
            return [val.cpu().numpy() for val in state_dict.values()]

        else:
            return [val.cpu().numpy() for _, val in model.state_dict().items()]
