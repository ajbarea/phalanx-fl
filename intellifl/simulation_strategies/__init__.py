"""Registry + factory for the federated aggregation strategies.

Maps each `aggregation_strategy_keyword` (the JSON config string) to a builder
callable that constructs the right Flower strategy class with the right
kwargs. The dispatch table here replaces what used to be an 80-line `if/elif`
chain in `intellifl.federated_simulation._assign_aggregation_strategy`.

Adding a new strategy = one entry in :data:`STRATEGY_REGISTRY` + (optionally)
one builder function below. The strategy class itself still lives in its own
file under `intellifl/simulation_strategies/` — this module is the seam that
joins config-keyword to constructor.

research(2026-05): registry + dispatch is the same pattern shipped in
`intellifl/network_models/__init__.py` (CNN datasets) and called out as the
shape for the whole "file-consolidation pass" in ROADMAP. Strategy classes
stay as separate files because each is substantial enough that combining
would only hurt navigability; the consolidation is at the dispatch seam, not
the per-strategy implementation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

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
from intellifl.simulation_strategies.pid_based_removal_strategy import (
    PIDBasedRemovalStrategy,
)
from intellifl.simulation_strategies.rfa_based_removal_strategy import (
    RFABasedRemovalStrategy,
)
from intellifl.simulation_strategies.trimmed_mean_based_removal_strategy import (
    TrimmedMeanBasedRemovalStrategy,
)
from intellifl.simulation_strategies.trust_based_removal_strategy import (
    TrustBasedRemovalStrategy,
)

if TYPE_CHECKING:
    from intellifl.data_models.simulation_strategy_config import StrategyConfig

# A builder takes the parsed strategy config, the kwargs shared across most
# strategies (initial_parameters, min_*_clients, removal flags, history,
# tracker), and a context dict for cross-cutting state that doesn't live on
# the config (currently just `network_model`). Returns the configured Flower
# strategy instance.
StrategyBuilder = Callable[["StrategyConfig", dict[str, Any], dict[str, Any]], Any]


def _build_fedavg(
    config: StrategyConfig, common_kwargs: dict[str, Any], _ctx: dict[str, Any]
) -> Any:
    # FedAvg has the vanilla Flower signature and intentionally drops the
    # `remove_clients` + `begin_removing_from_round` knobs that the removal
    # strategies forward to their base class. Picking what we need rather
    # than `**common_kwargs` preserves that.
    del config
    return FedAvgStrategy(
        strategy_history=common_kwargs["strategy_history"],
        status_tracker=common_kwargs["status_tracker"],
        initial_parameters=common_kwargs["initial_parameters"],
        min_fit_clients=common_kwargs["min_fit_clients"],
        min_evaluate_clients=common_kwargs["min_evaluate_clients"],
        min_available_clients=common_kwargs["min_available_clients"],
        evaluate_metrics_aggregation_fn=common_kwargs["evaluate_metrics_aggregation_fn"],
        fit_metrics_aggregation_fn=common_kwargs["fit_metrics_aggregation_fn"],
    )


def _build_trust(
    config: StrategyConfig, common_kwargs: dict[str, Any], _ctx: dict[str, Any]
) -> Any:
    return TrustBasedRemovalStrategy(
        beta_value=config.beta_value,
        trust_threshold=config.trust_threshold,
        **common_kwargs,
    )


def _build_pid(config: StrategyConfig, common_kwargs: dict[str, Any], ctx: dict[str, Any]) -> Any:
    # The PID strategy class branches on the variant string internally
    # (`pid` / `pid_scaled` / `pid_standardized` / ...). The keyword lives in
    # `ctx["keyword"]` rather than re-reading `config.aggregation_strategy_keyword`
    # because the config field is typed `str | None` and `ty` can't see that
    # registry-dispatch already guaranteed it's set.
    return PIDBasedRemovalStrategy(
        ki=config.Ki,
        kp=config.Kp,
        kd=config.Kd,
        num_std_dev=config.num_std_dev,
        network_model=ctx["network_model"],
        aggregation_strategy_keyword=ctx["keyword"],
        use_lora=bool(
            getattr(config, "use_llm", None) and getattr(config, "llm_finetuning", None) == "lora"
        ),
        **common_kwargs,
    )


def _build_krum(config: StrategyConfig, common_kwargs: dict[str, Any], _ctx: dict[str, Any]) -> Any:
    return KrumBasedRemovalStrategy(
        num_malicious_clients=config.num_of_malicious_clients,
        num_krum_selections=config.num_krum_selections,
        **common_kwargs,
    )


def _build_multi_krum_based(
    config: StrategyConfig, common_kwargs: dict[str, Any], _ctx: dict[str, Any]
) -> Any:
    return MultiKrumBasedRemovalStrategy(
        num_of_malicious_clients=config.num_of_malicious_clients,
        num_krum_selections=config.num_krum_selections,
        **common_kwargs,
    )


def _build_multi_krum(
    config: StrategyConfig, common_kwargs: dict[str, Any], _ctx: dict[str, Any]
) -> Any:
    return MultiKrumStrategy(
        num_of_malicious_clients=config.num_of_malicious_clients,
        num_krum_selections=config.num_krum_selections,
        **common_kwargs,
    )


def _build_trimmed_mean(
    config: StrategyConfig, common_kwargs: dict[str, Any], _ctx: dict[str, Any]
) -> Any:
    return TrimmedMeanBasedRemovalStrategy(
        trim_ratio=config.trim_ratio,
        **common_kwargs,
    )


def _build_rfa(config: StrategyConfig, common_kwargs: dict[str, Any], _ctx: dict[str, Any]) -> Any:
    return RFABasedRemovalStrategy(
        num_of_malicious_clients=config.num_of_malicious_clients,
        **common_kwargs,
    )


def _build_bulyan(
    config: StrategyConfig, common_kwargs: dict[str, Any], _ctx: dict[str, Any]
) -> Any:
    return BulyanStrategy(
        num_krum_selections=config.num_krum_selections,
        **common_kwargs,
    )


def _build_arkrum(
    _config: StrategyConfig, common_kwargs: dict[str, Any], _ctx: dict[str, Any]
) -> Any:
    return ArKrumStrategy(**common_kwargs)


# The four PID variants share one builder; the variant is read off the
# config inside `_build_pid`.
_PID_KEYWORDS = ("pid", "pid_scaled", "pid_standardized", "pid_standardized_score_based")


STRATEGY_REGISTRY: dict[str, StrategyBuilder] = {
    "fedavg": _build_fedavg,
    "trust": _build_trust,
    **dict.fromkeys(_PID_KEYWORDS, _build_pid),
    "krum": _build_krum,
    "multi-krum": _build_multi_krum,
    "multi-krum-based": _build_multi_krum_based,
    "trimmed_mean": _build_trimmed_mean,
    "rfa": _build_rfa,
    "bulyan": _build_bulyan,
    "arkrum": _build_arkrum,
}


def build_strategy(
    keyword: str | None,
    config: StrategyConfig,
    common_kwargs: dict[str, Any],
    ctx: dict[str, Any],
) -> Any:
    """Construct the configured aggregation strategy.

    Args:
        keyword: ``aggregation_strategy_keyword`` from the JSON config.
        config: parsed :class:`StrategyConfig`.
        common_kwargs: kwargs shared across most strategies
            (initial_parameters, min_*_clients, evaluate_metrics_aggregation_fn,
            fit_metrics_aggregation_fn, remove_clients,
            begin_removing_from_round, strategy_history, status_tracker).
        ctx: cross-cutting context. Currently only ``network_model`` is used
            (by PID variants); kept as a dict so future strategies can opt
            into more state without changing the builder signature.

    Returns:
        Configured Flower strategy instance.

    Raises:
        NotImplementedError: if ``keyword`` is not in :data:`STRATEGY_REGISTRY`.
    """
    # `None` is preserved as a valid input to match the pre-registry behavior
    # of the if/elif chain, which fell through to the `else` raise. The
    # builder dispatch table only contains string keys, so any non-match
    # (including None) lands in the same error path.
    if keyword is None or keyword not in STRATEGY_REGISTRY:
        raise NotImplementedError(f"The strategy {keyword} not implemented!")
    return STRATEGY_REGISTRY[keyword](config, common_kwargs, ctx)


__all__ = [
    "STRATEGY_REGISTRY",
    "StrategyBuilder",
    "build_strategy",
    # Strategy classes are re-exported so existing
    # `from intellifl.simulation_strategies import FooStrategy` patterns keep
    # working without forcing every consumer through the registry.
    "ArKrumStrategy",
    "BulyanStrategy",
    "FedAvgStrategy",
    "KrumBasedRemovalStrategy",
    "MultiKrumBasedRemovalStrategy",
    "MultiKrumStrategy",
    "PIDBasedRemovalStrategy",
    "RFABasedRemovalStrategy",
    "TrimmedMeanBasedRemovalStrategy",
    "TrustBasedRemovalStrategy",
]
