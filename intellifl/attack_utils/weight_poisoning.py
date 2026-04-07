"""Weight-level poisoning attacks for FL model updates."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Default threshold for overflow warnings
_MAX_SAFE_WEIGHT_VALUE = 1e6

# Keys that are scheduling metadata, not attack parameters
_SCHEDULING_KEYS = frozenset(
    {
        "attack_type",
        "start_round",
        "end_round",
        "selection_strategy",
        "malicious_client_ids",
        "_selected_clients",
        "percentage",
    }
)


def _check_and_warn_overflow(
    params: list[NDArray],
    attack_type: str,
    max_safe_value: float = _MAX_SAFE_WEIGHT_VALUE,
) -> list[NDArray]:
    """
    Detects and warns about numerical overflow in poisoned weights.

    Args:
        params: List of parameter arrays to check.
        attack_type: Name of the attack for logging context.
        max_safe_value: Threshold above which to warn.

    Returns:
        The input params unchanged.
    """
    for i, param in enumerate(params):
        max_val = np.max(np.abs(param))
        if max_val > max_safe_value:
            logger.warning(
                f"{attack_type}: param[{i}] has extreme value {max_val:.2e} "
                f"(exceeds {max_safe_value:.0e}). May cause loss explosion."
            )
        if not np.isfinite(param).all():
            logger.error(f"{attack_type}: param[{i}] contains NaN/Inf values!")
    return params

# ---------------------------------------------------------------------------
# Attack type registry
# ---------------------------------------------------------------------------

WEIGHT_ATTACK_TYPE_NAMES = (
    "model_poisoning",
    "gradient_scaling",
    "byzantine_perturbation",
    "boosted_scaling",
    "inner_product_manipulation",
    "alternating_min_poisoning",
)

WEIGHT_ATTACK_TYPES = frozenset(WEIGHT_ATTACK_TYPE_NAMES)


# ---------------------------------------------------------------------------
# Attack implementations
# ---------------------------------------------------------------------------


# Research: Model poisoning via adversarial objective in FL (Bhagoji et al., ICML 2019)
# https://proceedings.mlr.press/v97/bhagoji19a.html
def apply_model_poisoning(
    parameters: list[NDArray],
    poison_ratio: float = 0.1,
    magnitude: float = 5.0,
    seed: int | None = None,
    **_kwargs: object,
) -> list[NDArray]:
    """
    Applies targeted weight manipulation to a subset of parameters.

    Args:
        parameters: List of model parameter arrays.
        poison_ratio: Fraction of weights to poison.
        magnitude: Number of standard deviations for poisoned values.
        seed: Random seed.

    Returns:
        List of poisoned parameter arrays.
    """
    rng = np.random.default_rng(seed)
    poisoned_params = []

    for param in parameters:
        poisoned = param.copy()
        flat = poisoned.flatten()
        num_poison = max(1, int(len(flat) * poison_ratio))
        poison_indices = rng.choice(len(flat), size=num_poison, replace=False)

        param_std = np.std(flat) + 1e-8
        poison_value = magnitude * param_std
        flat[poison_indices] = np.sign(flat[poison_indices]) * poison_value

        poisoned_params.append(flat.reshape(param.shape))

    logger.debug(f"Model poisoning applied: ratio={poison_ratio}, magnitude={magnitude} std")
    return poisoned_params


# Research: Model replacement via constrain-and-scale in FL (Bagdasaryan et al., AISTATS 2020)
# https://proceedings.mlr.press/v108/bagdasaryan20a.html
def apply_gradient_scaling(
    parameters: list[NDArray],
    scale_factor: float = 2.0,
    seed: int | None = None,
    **_kwargs: object,
) -> list[NDArray]:
    """
    Scales all model parameters by a constant factor.

    .. deprecated::
        This is a naive constant-factor scaling. For research-grade FedAvg-aware
        scaling, use ``apply_boosted_scaling`` instead, which computes the scale
        as ``n_total / n_malicious`` to counteract averaging (Baruch et al. 2019).

    Args:
        parameters: List of model parameter arrays.
        scale_factor: Multiplier for all weights.
        seed: Random seed (unused, kept for interface consistency).

    Returns:
        List of scaled parameter arrays.
    """
    scaled_params = [param * scale_factor for param in parameters]

    logger.debug(f"Gradient scaling applied: scale_factor={scale_factor}")
    return scaled_params


# Research: Byzantine threat model for distributed ML (Blanchard et al., 2017)
# https://proceedings.neurips.cc/paper/2017/hash/f4b9ec30ad9f68f89b29639786cb62ef-Abstract.html
# Research: Norm clipping for defense evasion (Sun et al., 2019)
# https://arxiv.org/abs/1911.07963
def apply_byzantine_perturbation(
    parameters: list[NDArray],
    noise_scale: float = 3.0,
    clip_norm: float | None = None,
    seed: int | None = None,
    **_kwargs: object,
) -> list[NDArray]:
    """
    Applies random perturbations to model weights.

    Based on the Byzantine threat model (Blanchard et al., 2017) with
    optional norm-clipping for defense evasion (Sun et al., 2019).

    Args:
        parameters: List of model parameter arrays.
        noise_scale: Noise magnitude as multiple of parameter std deviation.
        clip_norm: If set, clip the L2 norm of the total perturbation to this
            value. This keeps the poisoned update within a plausible distance
            of the original, making it harder for norm-based defenses (Krum,
            Bulyan) to detect.
        seed: Random seed.

    Returns:
        List of perturbed parameter arrays.
    """
    rng = np.random.default_rng(seed)
    perturbed_params = []

    for param in parameters:
        param_std = np.std(param) + 1e-8
        scaled_noise = rng.standard_normal(param.shape) * noise_scale * param_std
        perturbed = param + scaled_noise
        perturbed_params.append(perturbed.astype(param.dtype))

    if clip_norm is not None:
        # Compute total delta and clip its L2 norm
        all_deltas = np.concatenate(
            [(p - o).flatten() for p, o in zip(perturbed_params, parameters, strict=True)]
        )
        delta_norm = np.linalg.norm(all_deltas)
        if delta_norm > clip_norm:
            scale = clip_norm / (delta_norm + 1e-10)
            perturbed_params = [
                (o + (p - o) * scale).astype(o.dtype)
                for p, o in zip(perturbed_params, parameters, strict=True)
            ]
            logger.debug(f"Byzantine perturbation clipped: {delta_norm:.2f} -> {clip_norm:.2f}")

    logger.debug(f"Byzantine perturbation applied: noise_scale={noise_scale} std")
    return perturbed_params


# Research: FedAvg-aware scaling to circumvent Byzantine defenses (Baruch et al., 2019)
# https://proceedings.neurips.cc/paper/2019/hash/ec1c59141046cd1866bbbcdfb6ae31d4-Abstract.html
def apply_boosted_scaling(
    parameters: Sequence[NDArray],
    n_total: int,
    n_malicious: int = 1,
    boost_factor: float = 1.0,
    seed: int | None = None,
    **_kwargs: object,
) -> list[NDArray]:
    """
    Scale update by n_total / n_malicious to counteract FedAvg averaging.

    Based on "A Little Is Enough" (Baruch et al., 2019). After
    FedAvg aggregation (``update = sum(updates) / n``), a single malicious
    client's contribution is diluted by 1/n. This attack scales the update
    so that the malicious contribution dominates the aggregate.

    Args:
        parameters: Model update parameters (typically the trained weights or
            the delta from the global model).
        n_total: Total number of clients participating in the round.
        n_malicious: Number of colluding malicious clients. Defaults to 1.
        boost_factor: Additional scaling multiplier. 1.0 means exact
            cancellation of FedAvg dilution.
        seed: Random seed (unused, kept for interface consistency).

    Returns:
        List of scaled parameter arrays.
    """
    if n_malicious < 1:
        raise ValueError(f"n_malicious must be >= 1, got {n_malicious}")
    if n_total < n_malicious:
        raise ValueError(f"n_total ({n_total}) must be >= n_malicious ({n_malicious})")

    scale = (n_total / n_malicious) * boost_factor
    scaled_params = [param * scale for param in parameters]

    logger.debug(
        f"Boosted scaling applied: n_total={n_total}, n_malicious={n_malicious}, "
        f"boost_factor={boost_factor}, effective_scale={scale:.2f}"
    )
    return scaled_params


# Research: Optimized model poisoning against Byzantine-robust FL (Xie et al., 2020)
# https://arxiv.org/abs/1911.11962
def apply_inner_product_manipulation(
    parameters: Sequence[NDArray],
    perturbation_strength: float = 0.5,
    target_direction: str = "negative",
    seed: int | None = None,
    **_kwargs: object,
) -> list[NDArray]:
    """
    Aggregation-aware attack that stays within a plausible L2 ball.

    Based on "Fall of Empires: Breaking Byzantine-tolerant SGD by Inner Product
    Manipulation" (Xie et al., 2020). Unlike random Byzantine perturbation,
    this attack crafts a deliberate perturbation along a chosen direction
    while keeping the L2 distance to the original update within the range
    of natural inter-client variance. This makes it effective against
    Krum, Multi-Krum, and Bulyan defenses.

    Directions:
        - ``"negative"``: Negate the update direction (untargeted degradation).
          The result is ``param * (1 - 2 * strength)``, which reverses the
          learning direction when strength > 0.5.
        - ``"zero"``: Push toward zero weights (prevent learning).
          The result is ``param * (1 - strength)``.
        - ``"random"``: L2-norm-bounded random perturbation. The noise vector
          has the same L2 norm as ``strength * ||param||``.

    Args:
        parameters: Trained model parameters (the honest local update).
        perturbation_strength: Controls perturbation magnitude as a fraction
            of the update's L2 norm. Range [0, 1]. Higher values are more
            aggressive but more likely to be detected.
        target_direction: One of ``"negative"``, ``"zero"``, or ``"random"``.
        seed: Random seed (used for ``"random"`` direction).

    Returns:
        List of perturbed parameter arrays.
    """
    rng = np.random.default_rng(seed)

    if target_direction == "negative":
        result = [
            (param * (1 - 2 * perturbation_strength)).astype(param.dtype) for param in parameters
        ]
    elif target_direction == "zero":
        result = [(param * (1 - perturbation_strength)).astype(param.dtype) for param in parameters]
    elif target_direction == "random":
        result = []
        for param in parameters:
            noise = rng.standard_normal(param.shape).astype(param.dtype)
            param_norm = np.linalg.norm(param) + 1e-8
            noise_norm = np.linalg.norm(noise) + 1e-8
            scaled_noise = noise * (perturbation_strength * param_norm / noise_norm)
            result.append(param + scaled_noise)
    else:
        raise ValueError(
            f"Unknown target_direction: {target_direction!r}. "
            f"Expected 'negative', 'zero', or 'random'."
        )

    logger.debug(
        f"Inner product manipulation applied: strength={perturbation_strength}, "
        f"direction={target_direction}"
    )
    return result


# Research: Optimization-based model poisoning (Bhagoji et al., ICML 2019)
# https://proceedings.mlr.press/v97/bhagoji19a.html
# Research: Local model poisoning against Byzantine-robust aggregation (Fang et al., USENIX 2020)
# https://www.usenix.org/conference/usenixsecurity20/presentation/fang
# Research: Model replacement / constrain-and-scale (Bagdasaryan et al., AISTATS 2020)
# https://proceedings.mlr.press/v108/bagdasaryan20a.html
def apply_alternating_min_poisoning(
    parameters: Sequence[NDArray],
    global_parameters: Sequence[NDArray] | None = None,
    n_total: int = 10,
    n_malicious: int = 1,
    tau_factor: float = 1.0,
    pgd_steps: int = 20,
    pgd_step_size: float = 0.1,
    seed: int | None = None,
    **_kwargs: object,
) -> list[NDArray]:
    """Optimization-based attack via projected gradient descent in weight space.

    Implements the *min-max* model-poisoning strategy from Fang et al.
    (USENIX Security 2020) combined with the FedAvg-aware scaling budget from
    Bagdasaryan et al. (AISTATS 2020) and the alternating-minimization framing
    of Bhagoji et al. (ICML 2019).

    Unlike heuristic attacks (random Byzantine noise, constant scaling), this
    attack computes the perturbation direction that **maximally diverges** from
    the honest aggregate update while staying within an L2 trust region τ.
    The trust region is chosen to be FedAvg-aware:

    .. math::

        \\tau = \\text{tau\\_factor} \\cdot \\frac{n_{\\text{total}}}{n_{\\text{malicious}}}
                              \\cdot \\|\\delta_{\\text{honest}}\\|_2

    This makes the poisoned update the same scale as an honest update after
    FedAvg averaging, passing norm-based defenses (Krum, Bulyan, norm-clipping)
    while pointing in the direction maximally harmful to convergence.

    **Algorithm (PGD in weight space):**

    1. Compute the honest local update: ``δ = parameters − global_parameters``
       (if ``global_parameters`` is ``None``, ``parameters`` is treated as δ).
    2. Set τ = tau_factor × (n_total / n_malicious) × ‖δ‖₂.
    3. Initialise adversarial delta: ``adv = −δ`` (opposite direction), then
       project onto the L2 ball of radius τ.
    4. Run ``pgd_steps`` iterations:
       ``adv ← adv + pgd_step_size · τ · (−δ / ‖δ‖)`` then re-project onto ball.
    5. Return ``global_parameters + adv`` (or just ``adv`` when no global given).

    Args:
        parameters: Locally-trained model parameters from the malicious client.
        global_parameters: Global model parameters at the start of the round.
            When provided, the attack is computed as a delta from the global
            model. When ``None``, ``parameters`` is treated as the raw update
            vector (e.g., stochastic gradient).
        n_total: Total number of clients in the federation. Used to compute
            the FedAvg-aware scaling factor.
        n_malicious: Number of colluding malicious clients (≥ 1).
        tau_factor: Multiplier on the trust-region radius τ. Values > 1 make
            the attack more aggressive but easier to detect; < 1 is stealthier.
        pgd_steps: Number of projected gradient descent iterations. More steps
            converge closer to the optimal boundary point.
        pgd_step_size: Step size as a fraction of τ per PGD iteration.
            Typical range [0.05, 0.2].
        seed: Random seed (unused; kept for interface consistency).

    Returns:
        List of poisoned parameter arrays with the same shapes and dtypes as
        the input ``parameters``.

    Raises:
        ValueError: If ``n_malicious < 1``, ``n_total < n_malicious``, or
            ``pgd_step_size`` is outside (0, 1].
    """
    if n_malicious < 1:
        raise ValueError(f"n_malicious must be >= 1, got {n_malicious}")
    if n_total < n_malicious:
        raise ValueError(f"n_total ({n_total}) must be >= n_malicious ({n_malicious})")
    if not (0.0 < pgd_step_size <= 1.0):
        raise ValueError(f"pgd_step_size must be in (0, 1], got {pgd_step_size}")

    # Collect per-parameter metadata for shape reconstruction at the end
    shapes = [np.asarray(p).shape for p in parameters]
    dtypes = [np.asarray(p).dtype for p in parameters]

    # Work in float64 throughout; cast back to original dtype at the end
    params_flat = np.concatenate([np.asarray(p, dtype=np.float64).flatten() for p in parameters])

    if global_parameters is not None:
        global_flat = np.concatenate(
            [np.asarray(g, dtype=np.float64).flatten() for g in global_parameters]
        )
    else:
        global_flat = np.zeros_like(params_flat)

    # Honest local update (delta)
    delta_flat = params_flat - global_flat
    delta_norm = float(np.linalg.norm(delta_flat)) + 1e-10

    # FedAvg-aware trust-region radius (Bagdasaryan et al., eq. 1 / Fang et al., Sec. 3)
    tau = tau_factor * (n_total / n_malicious) * delta_norm

    # Initialise adversarial delta as the negated honest update.
    # This is the steepest-descent starting point on the L2 sphere.
    adv_flat = -delta_flat.copy()
    adv_norm = float(np.linalg.norm(adv_flat))
    if adv_norm > tau:
        adv_flat = adv_flat * (tau / adv_norm)

    # Constant PGD gradient direction: unit vector antiparallel to honest delta.
    # Maximising inner_product(-delta, adv) subject to ||adv||_2 <= tau is
    # equivalent to placing adv at the antipodal point on the trust-region sphere.
    grad_dir = -delta_flat / delta_norm  # unit vector, constant across all steps
    step = pgd_step_size * tau

    for _ in range(pgd_steps):
        adv_flat = adv_flat + step * grad_dir
        # Project back onto L2 ball of radius tau
        adv_norm = float(np.linalg.norm(adv_flat))
        if adv_norm > tau:
            adv_flat = adv_flat * (tau / adv_norm)

    # Reconstruct poisoned model weights: global + adversarial delta
    poisoned_flat = global_flat + adv_flat

    # Split flat result back into per-parameter arrays
    result: list[NDArray] = []
    offset = 0
    for shape, dtype in zip(shapes, dtypes, strict=True):
        size = int(np.prod(shape)) if shape else 1
        chunk = poisoned_flat[offset : offset + size]
        result.append(chunk.reshape(shape).astype(dtype))
        offset += size

    logger.debug(
        f"Alternating-min poisoning: n_total={n_total}, n_malicious={n_malicious}, "
        f"tau={tau:.4f}, pgd_steps={pgd_steps}, pgd_step_size={pgd_step_size}"
    )
    return result


# ---------------------------------------------------------------------------
# Registry mapping attack type names to functions
# ---------------------------------------------------------------------------

_WEIGHT_ATTACK_FUNCTIONS: dict[str, Callable] = {
    "model_poisoning": apply_model_poisoning,
    "gradient_scaling": apply_gradient_scaling,
    "byzantine_perturbation": apply_byzantine_perturbation,
    "boosted_scaling": apply_boosted_scaling,
    "inner_product_manipulation": apply_inner_product_manipulation,
    "alternating_min_poisoning": apply_alternating_min_poisoning,
}


def apply_weight_poisoning(
    parameters: Sequence[NDArray],
    attack_configs: list[dict],
) -> list[NDArray]:
    """
    Applies weight-level poisoning attacks based on configuration.

    Args:
        parameters: List of model parameter arrays.
        attack_configs: List of attack configuration dicts. Each dict must
            contain an ``attack_type`` key. All other keys (except scheduling
            metadata) are forwarded as kwargs to the attack function.

    Returns:
        List of poisoned parameter arrays.

    Raises:
        ValueError: If attack_type is not a valid weight attack.
    """
    result = list(parameters)

    for config in attack_configs:
        attack_type = config.get("attack_type")

        if attack_type not in WEIGHT_ATTACK_TYPES:
            continue

        attack_fn = _WEIGHT_ATTACK_FUNCTIONS.get(attack_type)
        if attack_fn is None:
            raise ValueError(f"Unknown weight attack type: {attack_type}")

        # Forward only attack-specific kwargs, strip scheduling metadata
        attack_kwargs = {k: v for k, v in config.items() if k not in _SCHEDULING_KEYS}
        result = attack_fn(result, **attack_kwargs)
        _check_and_warn_overflow(result, attack_type)

    return result


def is_weight_attack(attack_type: str) -> bool:
    """Checks if an attack type is a weight-level attack."""
    return attack_type in WEIGHT_ATTACK_TYPES
