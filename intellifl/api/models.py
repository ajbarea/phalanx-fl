"""Pydantic models for API request and response validation.

This module provides strongly-typed request models with automatic boolean coercion
for the simulation API endpoints. Pydantic's native boolean coercion handles
string inputs like "true"/"false" automatically.

Response models provide accurate OpenAPI schema documentation.
"""

from __future__ import annotations

import warnings
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _coerce_bool(v: Any) -> bool | None:
    """Convert string boolean representations to actual booleans.

    Pydantic's native coercion handles most cases, but this provides
    explicit handling for edge cases and clear error messages.

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
            stacklevel=4,  # Adjusted for Pydantic validator call stack
        )
        lower = v.lower()
        if lower in ("true", "1", "yes", "on"):
            return True
        if lower in ("false", "0", "no", "off"):
            return False
    raise ValueError(f"Cannot coerce {v!r} to bool")


class SimulationSettings(BaseModel):
    """Simulation configuration settings with boolean coercion.

    All fields are optional to support partial configurations.
    Boolean fields accept both actual bools and "true"/"false" strings for input,
    but are always stored and returned as actual booleans.

    Field constraints provide validation at the API boundary.
    """

    model_config = ConfigDict(extra="allow")

    # Core settings
    display_name: str | None = None
    aggregation_strategy_keyword: str | None = None
    dataset_keyword: str | None = None
    dataset_source: str | None = None
    model_keyword: str | None = None
    model_type: str | None = None

    # Training parameters with validation constraints
    num_of_rounds: int | None = Field(default=None, ge=1, le=10000)
    num_of_clients: int | None = Field(default=None, ge=1, le=1000)
    num_of_malicious_clients: int | None = Field(default=None, ge=0)
    training_device: str | None = None
    cpus_per_client: int | float | None = Field(default=None, ge=0)
    gpus_per_client: float | None = Field(default=None, ge=0, le=1)
    training_subset_fraction: float | None = Field(default=None, gt=0, le=1)
    min_fit_clients: int | None = Field(default=None, ge=1)
    min_evaluate_clients: int | None = Field(default=None, ge=1)
    min_available_clients: int | None = Field(default=None, ge=1)
    num_of_client_epochs: int | None = Field(default=None, ge=1)
    batch_size: int | None = Field(default=None, ge=1)
    learning_rate: float | None = Field(default=None, gt=0)

    # Boolean flags - accept string input but store as actual booleans
    remove_clients: bool | None = None
    show_plots: bool | None = None
    save_plots: bool | None = None
    save_csv: bool | None = None
    save_attack_snapshots: bool | None = None
    preserve_dataset: bool | None = None
    strict_mode: bool | None = None
    use_llm: bool | None = None
    use_lora: bool | None = None

    # Strategy-specific parameters with constraints
    trust_threshold: float | None = Field(default=None, ge=0, le=1)
    reputation_threshold: float | None = Field(default=None, ge=0, le=1)
    beta_value: float | None = None
    num_of_clusters: int | None = Field(default=None, ge=1)
    begin_removing_from_round: int | None = Field(default=None, ge=1)
    Kp: float | None = None
    Ki: float | None = None
    Kd: float | None = None
    num_std_dev: float | None = Field(default=None, ge=0)
    num_krum_selections: int | None = Field(default=None, ge=1)
    trim_ratio: float | None = Field(default=None, ge=0, lt=0.5)

    # Attack settings with constraints
    attack_type: str | None = None
    attack_ratio: float | None = Field(default=None, ge=0, le=1)
    gaussian_noise_mean: int | float | None = None
    gaussian_noise_std: int | float | None = Field(default=None, ge=0)
    attack_schedule: list[dict[str, Any]] | None = None
    attack_snapshot_format: str | None = None
    snapshot_max_samples: int | None = Field(default=None, ge=1, le=50)

    # LLM settings with constraints
    llm_model: str | None = None
    llm_finetuning: str | None = None
    llm_task: str | None = None
    llm_chunk_size: int | None = Field(default=None, ge=1)
    mlm_probability: float | None = Field(default=None, ge=0, le=1)
    lora_rank: int | None = Field(default=None, ge=1)

    # Other settings
    evaluate_metrics_aggregation_fn: str | None = None
    hf_dataset_name: str | None = None
    partitioning_strategy: str | None = None
    partitioning_params: dict[str, Any] | None = None
    transformer_model: str | None = None
    max_seq_length: int | None = Field(default=None, ge=1)
    text_column: str | None = None
    label_column: str | None = None
    strategy_number: int | None = Field(default=None, ge=0)

    @field_validator(
        "remove_clients",
        "show_plots",
        "save_plots",
        "save_csv",
        "save_attack_snapshots",
        "preserve_dataset",
        "strict_mode",
        "use_llm",
        mode="before",
    )
    @classmethod
    def coerce_bool_strings(cls, v: Any) -> bool | None:
        """Convert string boolean representations to actual booleans."""
        return _coerce_bool(v)


class StrategyOverrides(BaseModel):
    """Strategy-specific overrides for multi-sim configurations."""

    model_config = ConfigDict(extra="allow")

    aggregation_strategy_keyword: str | None = None
    num_of_malicious_clients: int | None = None
    num_krum_selections: int | None = None
    remove_clients: bool | None = None
    begin_removing_from_round: int | None = None
    num_std_dev: float | None = None

    @field_validator("remove_clients", mode="before")
    @classmethod
    def coerce_bool_strings(cls, v: Any) -> bool | None:
        """Convert string boolean representations to actual booleans."""
        return _coerce_bool(v)


class CreateSimulationRequest(BaseModel):
    """Request model for POST /api/simulations.

    Supports two configuration modes:
    1. Single-sim mode: All config fields at root level
    2. Multi-sim mode: shared_settings + simulation_strategies

    Example single-sim:
        {"aggregation_strategy_keyword": "fedavg", "num_of_rounds": 10}

    Example multi-sim:
        {
            "shared_settings": {"num_of_rounds": 10},
            "simulation_strategies": [{"aggregation_strategy_keyword": "fedavg"}]
        }
    """

    model_config = ConfigDict(extra="allow")

    shared_settings: SimulationSettings | None = None
    simulation_strategies: list[StrategyOverrides] | None = None

    def is_multi_sim_mode(self) -> bool:
        """Check if this request uses multi-sim configuration format."""
        return self.shared_settings is not None and self.simulation_strategies is not None

    def to_config_dict(self) -> dict[str, Any]:
        """Convert to config dict format for storage/processing.

        Returns proper JSON types (booleans as actual booleans, not strings).
        """
        if self.is_multi_sim_mode():
            # Multi-sim mode - use structured format
            result: dict[str, Any] = {}
            if self.shared_settings:
                result["shared_settings"] = self.shared_settings.model_dump(exclude_none=True)
            if self.simulation_strategies:
                result["simulation_strategies"] = [
                    s.model_dump(exclude_none=True) for s in self.simulation_strategies
                ]
            return result
        else:
            # Single-sim mode - extra fields contain the config
            return dict(self.__pydantic_extra__) if self.__pydantic_extra__ else {}


# =============================================================================
# Response Models - For accurate OpenAPI documentation
# =============================================================================


class SimulationStatusResponse(BaseModel):
    """Response model for GET /api/simulations/{id}/status.

    Provides accurate schema documentation for simulation status endpoints.
    """

    model_config = ConfigDict(extra="allow")

    status: Literal["queued", "pending", "running", "completed", "failed", "stopped"]
    progress: float = Field(ge=0, le=1, default=0.0)
    current_round: int | None = None
    total_rounds: int | None = None
    current_strategy: int | None = None
    total_strategies: int | None = None
    error: str | None = None


class DatasetInfo(BaseModel):
    """Dataset metadata from HuggingFace."""

    splits: list[str]
    num_examples: int
    features: str
    has_label: bool
    key_features: list[str]


class DatasetValidationResponse(BaseModel):
    """Response model for GET /api/datasets/validate.

    Provides accurate schema documentation for dataset validation endpoint.
    """

    valid: bool
    compatible: bool
    info: DatasetInfo | None = None
    error: str | None = None
    reason: str | None = None


class StrategyPlotData(BaseModel):
    """Plot data for a single strategy."""

    strategy_number: int
    data: dict[str, Any]


class AllPlotDataResponse(BaseModel):
    """Response model for GET /api/simulations/{id}/all-plot-data."""

    strategies: list[StrategyPlotData]


class AttackSnapshotVisualization(BaseModel):
    """Visualization paths for an attack snapshot."""

    model_config = ConfigDict(extra="allow")

    primary: str
    confusion_matrix: str | None = None
    difference_heatmap: str | None = None
    html_diff: str | None = None
    prediction_grid: str | None = None
    weight_histogram: str | None = None
    comparison: str | None = None


class AttackSnapshot(BaseModel):
    """Individual attack snapshot data."""

    model_config = ConfigDict(extra="allow")

    client_id: int
    round_num: int
    attack_type: str
    image_path: str
    visualizations: AttackSnapshotVisualization | dict[str, str]
    metadata: dict[str, Any] | None = None
    flip_summary: dict[str, Any] | None = None
    is_text_attack: bool | None = None
    is_weight_attack: bool | None = None


class AttackSnapshotStrategy(BaseModel):
    """Attack snapshot data for a single strategy."""

    strategy_number: int
    summary: dict[str, Any] | None = None
    snapshots: list[AttackSnapshot]


class AttackSnapshotsResponse(BaseModel):
    """Response model for GET /api/simulations/{id}/attack-snapshots."""

    has_snapshots: bool
    strategies: list[AttackSnapshotStrategy]
