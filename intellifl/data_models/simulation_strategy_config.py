from __future__ import annotations

import warnings
from typing import Any, NotRequired
from typing import TypedDict as TypingTypedDict

from pydantic import BaseModel, ConfigDict, field_validator

TypedDict = TypingTypedDict


def _coerce_bool(v: Any) -> bool | None:
    """Convert string boolean representations to actual booleans.

    Note:
        String boolean values are deprecated and will emit a DeprecationWarning.
        Use actual JSON booleans (true/false without quotes) instead.
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        warnings.warn(
            f"String boolean value '{v}' is deprecated. "
            "Use actual boolean (true/false without quotes).",
            DeprecationWarning,
            stacklevel=4,
        )
        lower = v.lower()
        if lower in ("true", "1", "yes", "on"):
            return True
        if lower in ("false", "0", "no", "off"):
            return False
    raise ValueError(f"Cannot coerce {v!r} to bool")


class AttackScheduleEntry(TypedDict):
    """Type definition for attack schedule entries.

    This TypedDict provides better type hints for internal configuration
    dictionaries without requiring Pydantic validation overhead.

    Required fields:
        start_round: First round the attack is active
        end_round: Last round the attack is active
        attack_type: Type of attack to apply
        selection_strategy: How to select malicious clients

    Optional fields depend on selection_strategy and attack_type.
    """

    start_round: int
    end_round: int
    attack_type: str
    selection_strategy: str

    # Client selection (depends on selection_strategy)
    malicious_percentage: NotRequired[float]
    malicious_client_count: NotRequired[int]
    malicious_client_ids: NotRequired[list[int]]
    random_seed: NotRequired[int]

    # Attack parameters (depends on attack_type)
    target_noise_snr: NotRequired[float]
    attack_ratio: NotRequired[float]

    # Weight poisoning parameters
    poison_ratio: NotRequired[float]
    magnitude: NotRequired[float]
    scale_factor: NotRequired[float]
    noise_scale: NotRequired[float]
    seed: NotRequired[int]

    # Token replacement parameters
    target_vocabulary: NotRequired[str]
    replacement_strategy: NotRequired[str]
    replacement_prob: NotRequired[float]

    # Internal field populated by validation
    _selected_clients: NotRequired[list[int]]


class StrategyConfig(BaseModel):
    """Configuration for a single simulation strategy.

    This Pydantic model provides type validation and coercion for all strategy
    parameters. It replaces the previous dataclass-based implementation.
    """

    model_config = ConfigDict(extra="allow")

    aggregation_strategy_keyword: str | None = None
    remove_clients: bool = False
    begin_removing_from_round: int = 0
    # Termination policies for client removal edge cases
    termination_policy: str | None = "graceful"  # strict | graceful | adaptive
    min_clients_ratio: float | None = 0.3  # For adaptive policy (30% threshold)
    dataset_keyword: str | None = None
    num_of_rounds: int | None = None
    num_of_clients: int | None = None
    num_of_malicious_clients: int = 1
    show_plots: bool | None = None
    save_plots: bool | None = None
    save_csv: bool | None = None
    save_attack_snapshots: bool | None = None
    attack_snapshot_format: str = "pickle"
    snapshot_max_samples: int = 5
    training_device: str | None = None
    cpus_per_client: float | None = None
    gpus_per_client: float | None = None

    trust_threshold: float = 0.1
    beta_value: float = 0.1
    num_of_clusters: int | None = None

    Kp: float = 1.0
    Ki: float = 1.0
    Kd: float = 0.0
    num_std_dev: float = 3.0

    training_subset_fraction: float | None = None
    min_fit_clients: int = 2
    min_evaluate_clients: int = 2
    min_available_clients: int = 2
    evaluate_metrics_aggregation_fn: str | None = None
    num_of_client_epochs: int | None = None
    batch_size: int | None = None
    preserve_dataset: bool | None = None

    num_krum_selections: int = 2

    trim_ratio: float = 0.1

    learning_rate: float | None = None

    strict_mode: bool | None = None

    strategy_number: int | None = None

    attack_schedule: list[AttackScheduleEntry] | None = None

    @field_validator(
        "remove_clients",
        "show_plots",
        "save_plots",
        "save_csv",
        "save_attack_snapshots",
        "preserve_dataset",
        "strict_mode",
        mode="before",
    )
    @classmethod
    def coerce_bool_strings(cls, v: Any) -> bool | None:
        """Convert string boolean representations to actual booleans."""
        return _coerce_bool(v)

    @classmethod
    def from_dict(cls, strategy_config: dict[str, Any]) -> StrategyConfig:
        """Create config instance from dict using Pydantic validation."""
        return cls.model_validate(strategy_config)

    def to_json(self) -> str:
        """Convert config to JSON string."""
        return self.model_dump_json()
