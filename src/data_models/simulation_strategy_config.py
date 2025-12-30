from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class StrategyConfig:
    aggregation_strategy_keyword: str | None = None
    remove_clients: bool | None = None
    begin_removing_from_round: int | None = None
    dataset_keyword: str | None = None
    num_of_rounds: int | None = None
    num_of_clients: int | None = None
    num_of_malicious_clients: int | None = None
    show_plots: bool | None = None
    save_plots: bool | None = None
    save_csv: bool | None = None
    save_attack_snapshots: bool | None = None
    attack_snapshot_format: str = "pickle"
    snapshot_max_samples: int = 5
    training_device: str | None = None
    cpus_per_client: float | None = None
    gpus_per_client: float | None = None

    trust_threshold: float | None = None
    beta_value: float | None = None
    num_of_clusters: int | None = None

    Kp: float | None = None
    Ki: float | None = None
    Kd: float | None = None
    num_std_dev: float | None = None

    training_subset_fraction: float | None = None
    min_fit_clients: int | None = None
    min_evaluate_clients: int | None = None
    min_available_clients: int | None = None
    evaluate_metrics_aggregation_fn: str | None = None
    num_of_client_epochs: int | None = None
    batch_size: int | None = None
    preserve_dataset: bool | None = None

    num_krum_selections: int | None = None

    trim_ratio: float | None = None

    learning_rate: float | None = None

    strict_mode: bool | None = None

    strategy_number: int | None = None

    attack_schedule: list[Any] | None = None

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if value in ("true", "false"):
                setattr(self, key, value == "true")
            else:
                setattr(self, key, value)

    def __getattr__(self, name: str) -> Any:
        """Allow access to dynamically set attributes"""
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    @classmethod
    def from_dict(cls, strategy_config: dict[str, Any]) -> StrategyConfig:
        """Create config instance from dict"""
        return cls(**strategy_config)

    def to_json(self) -> str:
        """Convert config to json"""
        return json.dumps(asdict(self))
