"""
Utility functions for saving and visualizing weight poisoning snapshots.

Creates histograms and statistics showing weight distributions before
and after poisoning attacks for debugging and analysis.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from intellifl.attack_utils.snapshot_image_viz import TITLE_STYLE

logger = logging.getLogger(__name__)


def _get_weight_snapshot_dir(
    output_dir: str,
    client_id: int,
    round_num: int,
    strategy_number: int = 0,
) -> Path:
    """Get or create directory for weight snapshots.

    Args:
        output_dir: Base output directory path.
        client_id: Client ID for the snapshot.
        round_num: Round number for the snapshot.
        strategy_number: Strategy index for multi-strategy runs.

    Returns:
        Path object for the weight snapshot directory.
    """
    snapshots_base = Path(output_dir) / f"attack_snapshots_{strategy_number}"
    snapshot_dir = snapshots_base / f"client_{client_id}" / f"round_{round_num}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    return snapshot_dir


def _compute_weight_statistics(parameters: list[NDArray]) -> dict[str, float]:
    """Compute summary statistics for model parameters.

    Args:
        parameters: List of parameter arrays.

    Returns:
        Dictionary with statistics (mean, std, min, max, l2_norm, sparsity).
    """
    # Compute statistics incrementally without full concatenation
    total_elements = sum(p.size for p in parameters)
    running_sum = sum(float(np.sum(p)) for p in parameters)
    running_sum_sq = sum(float(np.sum(p**2)) for p in parameters)
    min_val = float(min(np.min(p) for p in parameters))
    max_val = float(max(np.max(p) for p in parameters))
    num_small = sum(int(np.sum(np.abs(p) < 1e-6)) for p in parameters)
    l2_norm = float(np.sqrt(running_sum_sq))

    mean = running_sum / total_elements
    variance = (running_sum_sq / total_elements) - (mean**2)
    std = float(np.sqrt(max(0, variance)))  # max() to avoid sqrt of negative due to numerical error

    return {
        "mean": mean,
        "std": std,
        "min": min_val,
        "max": max_val,
        "l2_norm": l2_norm,
        "sparsity": float(num_small / total_elements),
        "num_parameters": int(total_elements),
        "num_layers": len(parameters),
    }


def compute_weight_diff_statistics(
    params_before: list[NDArray],
    params_after: list[NDArray],
) -> dict[str, float]:
    """Compute statistics on the difference between weight sets.

    Args:
        params_before: Parameters before poisoning.
        params_after: Parameters after poisoning.

    Returns:
        Dictionary with difference statistics including:
        - diff_mean: Mean of weight differences
        - diff_std: Standard deviation of weight differences
        - diff_min: Minimum weight difference
        - diff_max: Maximum absolute weight difference
        - diff_l2_norm: L2 norm of the difference vector
        - num_changed: Number of weights that changed
        - pct_changed: Percentage of weights that changed
    """
    diffs = [after - before for before, after in zip(params_before, params_after, strict=False)]

    # Compute incrementally without full concatenation
    total_elements = sum(d.size for d in diffs)
    running_sum = sum(float(np.sum(d)) for d in diffs)
    running_sum_sq = sum(float(np.sum(d**2)) for d in diffs)
    min_val = float(min(np.min(d) for d in diffs))
    max_val = float(max(np.max(d) for d in diffs))
    num_changed = sum(int(np.sum(np.abs(d) > 1e-10)) for d in diffs)
    l2_norm = float(np.sqrt(running_sum_sq))

    mean = running_sum / total_elements
    variance = (running_sum_sq / total_elements) - (mean**2)
    std = float(np.sqrt(max(0, variance)))

    return {
        "diff_mean": mean,
        "diff_std": std,
        "diff_min": min_val,
        "diff_max": max_val,
        "diff_l2_norm": l2_norm,
        "num_changed": num_changed,
        "pct_changed": float(num_changed / total_elements * 100),
    }


def save_weight_snapshot(
    parameters_before: list[NDArray],
    parameters_after: list[NDArray],
    attack_type: str,
    attack_config: dict,
    client_id: int,
    round_num: int,
    output_dir: str,
    strategy_number: int = 0,
    experiment_info: dict[str, Any] | None = None,
    save_histogram: bool = True,
) -> None:
    """Save weight distribution snapshot before/after poisoning.

    Creates JSON metadata file with statistics and optionally a
    histogram visualization of weight distributions.

    Args:
        parameters_before: Model parameters before poisoning.
        parameters_after: Model parameters after poisoning.
        attack_type: Type of weight attack applied.
        attack_config: Attack configuration dictionary.
        client_id: Client ID.
        round_num: Round number.
        output_dir: Base output directory.
        strategy_number: Strategy index for multi-strategy runs.
        experiment_info: Additional experiment metadata.
        save_histogram: Whether to save histogram plot (requires matplotlib).
    """
    snapshot_dir = _get_weight_snapshot_dir(output_dir, client_id, round_num, strategy_number)

    stats_before = _compute_weight_statistics(parameters_before)
    stats_after = _compute_weight_statistics(parameters_after)
    diff_stats = compute_weight_diff_statistics(parameters_before, parameters_after)

    metadata = {
        "client_id": client_id,
        "round_num": round_num,
        "attack_type": attack_type,
        "attack_config": attack_config,
        "timestamp": datetime.now().isoformat(),
        "statistics": {
            "before": stats_before,
            "after": stats_after,
            "difference": diff_stats,
        },
    }

    if experiment_info:
        metadata["experiment_info"] = experiment_info

    json_path = snapshot_dir / f"{attack_type}_weight_metadata.json"
    with open(json_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.debug(
        f"Saved {attack_type} weight snapshot: client {client_id}, round {round_num} -> {json_path}"
    )

    if save_histogram:
        try:
            _save_weight_histogram(
                parameters_before,
                parameters_after,
                attack_type,
                snapshot_dir,
                client_id,
                round_num,
            )
        except ImportError:
            logger.warning("matplotlib not available, skipping histogram visualization")
        except Exception as e:
            logger.warning(f"Failed to save weight histogram: {e}")

        try:
            save_weight_layer_delta(
                parameters_before,
                parameters_after,
                attack_type,
                snapshot_dir,
                client_id,
                round_num,
            )
        except ImportError:
            logger.warning("matplotlib not available, skipping layer delta visualization")
        except Exception as e:
            logger.warning(f"Failed to save weight layer delta: {e}")


def _save_weight_histogram(
    params_before: list[NDArray],
    params_after: list[NDArray],
    attack_type: str,
    snapshot_dir: Path,
    client_id: int,
    round_num: int,
) -> None:
    """Save histogram comparing weight distributions.

    Args:
        params_before: Parameters before poisoning.
        params_after: Parameters after poisoning.
        attack_type: Attack type for filename.
        snapshot_dir: Directory to save histogram.
        client_id: Client ID for title.
        round_num: Round number for title.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Compute limits without full concatenation to save memory
    x_min = min(p.min() for p in params_before + params_after)
    x_max = max(p.max() for p in params_before + params_after)
    # Add small margin for visual padding
    x_margin = (x_max - x_min) * 0.02
    x_limits = (x_min - x_margin, x_max + x_margin)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4), layout="constrained")

    # Use incremental histogram binning to avoid full concatenation
    bin_edges = np.linspace(x_min, x_max, 101)  # 100 bins

    # Panel 0: Before poisoning (incremental histogram)
    counts_before = np.zeros(100)
    for p in params_before:
        layer_counts, _ = np.histogram(p.flatten(), bins=bin_edges)
        counts_before += layer_counts

    # Normalize for density
    bin_width = bin_edges[1] - bin_edges[0]
    total_elements = sum(p.size for p in params_before)
    density_before = counts_before / (total_elements * bin_width)
    axes[0].bar(
        bin_edges[:-1],
        density_before,
        width=bin_width,
        alpha=0.7,
        color="#3498db",
        edgecolor="none",
    )
    axes[0].set_title("Before Poisoning")
    axes[0].set_xlabel("Weight Value")
    axes[0].set_ylabel("Density")
    axes[0].set_yscale("log")
    axes[0].set_xlim(x_limits)

    # Panel 1: After poisoning (incremental histogram)
    counts_after = np.zeros(100)
    for p in params_after:
        layer_counts, _ = np.histogram(p.flatten(), bins=bin_edges)
        counts_after += layer_counts

    total_elements = sum(p.size for p in params_after)
    density_after = counts_after / (total_elements * bin_width)
    axes[1].bar(
        bin_edges[:-1], density_after, width=bin_width, alpha=0.7, color="#e74c3c", edgecolor="none"
    )
    axes[1].set_title("After Poisoning")
    axes[1].set_xlabel("Weight Value")
    axes[1].set_ylabel("Density")
    axes[1].set_yscale("log")
    axes[1].set_xlim(x_limits)

    # Panel 2: Comparison (reuse computed histograms)
    axes[2].bar(
        bin_edges[:-1],
        density_before,
        width=bin_width,
        alpha=0.5,
        color="#3498db",
        edgecolor="none",
        label="Before",
    )
    axes[2].bar(
        bin_edges[:-1],
        density_after,
        width=bin_width,
        alpha=0.5,
        color="#e74c3c",
        edgecolor="none",
        label="After",
    )
    axes[2].set_title("Comparison")
    axes[2].set_xlabel("Weight Value")
    axes[2].set_ylabel("Density")
    axes[2].set_yscale("log")
    axes[2].set_xlim(x_limits)
    axes[2].legend()

    attack_display = attack_type.replace("_", " ").title()
    fig.suptitle(
        f"Weight Distribution - Client {client_id}, Round {round_num} ({attack_display})",
        fontsize=TITLE_STYLE["fontsize"],
        fontweight=TITLE_STYLE["fontweight"],
        color=TITLE_STYLE["color"],
    )

    histogram_path = snapshot_dir / f"{attack_type}_weight_histogram.png"
    try:
        plt.savefig(histogram_path, dpi=100, bbox_inches="tight")
    finally:
        plt.close(fig)

    logger.debug(f"Saved weight histogram: {histogram_path}")


def save_weight_layer_delta(
    params_before: list[NDArray],
    params_after: list[NDArray],
    attack_type: str,
    snapshot_dir: Path,
    client_id: int,
    round_num: int,
) -> None:
    """Save per-layer weight delta visualization.

    2-panel side-by-side:
    [Per-layer L2 norm bar chart] | [Layer delta heatmap (binned)]

    Args:
        params_before: Parameters before poisoning.
        params_after: Parameters after poisoning.
        attack_type: Attack type for filename and title.
        snapshot_dir: Directory to save visualization.
        client_id: Client ID for title.
        round_num: Round number for title.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    num_layers = len(params_before)
    layer_names = [f"Layer {i}" for i in range(num_layers)]
    layer_l2 = []
    layer_diffs = []

    for before, after in zip(params_before, params_after, strict=False):
        diff = (after - before).flatten()
        layer_l2.append(float(np.linalg.norm(diff)))
        layer_diffs.append(diff)

    # Compute total L2 norm incrementally without concatenation
    total_l2 = float(np.sqrt(sum(np.sum(d**2) for d in layer_diffs)))
    most_affected_idx = int(np.argmax(layer_l2))
    least_affected_idx = int(np.argmin(layer_l2))

    # Use subfigures: main content + footer
    fig = plt.figure(figsize=(16, max(4, 0.5 * num_layers) + 1.5), layout="constrained")
    subfigs = fig.subfigures(2, 1, height_ratios=[1, 0.06], hspace=0.02)

    main_fig = subfigs[0]
    axes = main_fig.subplots(1, 2, gridspec_kw={"wspace": 0.3})

    # --- Panel 1: Per-layer L2 norm bar chart ---
    ax_bars = axes[0]
    l2_array = np.array(layer_l2)
    # Normalize for colormap
    l2_max = l2_array.max() if l2_array.max() > 0 else 1.0
    cmap = matplotlib.colormaps["RdYlGn_r"]
    colors = cmap(l2_array / l2_max)

    y_pos = np.arange(num_layers)
    ax_bars.barh(y_pos, l2_array, color=colors, height=0.7, edgecolor="none")
    ax_bars.set_yticks(y_pos)
    ax_bars.set_yticklabels(layer_names, fontsize=8)
    ax_bars.invert_yaxis()
    ax_bars.set_xlabel("L2 Norm of Delta", fontsize=10)
    ax_bars.set_title("Per-Layer L2 Norm", fontsize=12, fontweight="bold", color="#2c3e50")

    # Annotate values on bars
    for i, v in enumerate(layer_l2):
        ax_bars.text(v + l2_max * 0.01, i, f"{v:.3f}", va="center", fontsize=7)

    # --- Panel 2: Layer delta heatmap ---
    ax_heatmap = axes[1]
    num_bins = 100

    # Bin each layer's deltas independently into num_bins columns
    heatmap_data = np.zeros((num_layers, num_bins))
    for i, diff in enumerate(layer_diffs):
        if len(diff) <= num_bins:
            heatmap_data[i, : len(diff)] = diff
        else:
            # Bin by splitting into num_bins equal chunks and taking mean
            bins = np.array_split(diff, num_bins)
            heatmap_data[i] = [np.mean(b) for b in bins]

    vmax = np.max(np.abs(heatmap_data))
    if vmax == 0:
        vmax = 1e-6
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

    im = ax_heatmap.imshow(
        heatmap_data, aspect="auto", cmap="RdBu_r", norm=norm, interpolation="nearest"
    )
    ax_heatmap.set_yticks(y_pos)
    ax_heatmap.set_yticklabels(layer_names, fontsize=8)
    ax_heatmap.set_xlabel("Parameter Bin", fontsize=10)
    ax_heatmap.set_title("Layer Delta Heatmap", fontsize=12, fontweight="bold", color="#2c3e50")

    cbar = main_fig.colorbar(im, ax=ax_heatmap, shrink=0.8, pad=0.02)
    cbar.set_label("Weight Delta", fontsize=9)

    attack_display = attack_type.replace("_", " ").title()
    main_fig.suptitle(
        f"Weight Layer Delta - Client {client_id}, Round {round_num} ({attack_display})",
        fontsize=TITLE_STYLE["fontsize"],
        fontweight=TITLE_STYLE["fontweight"],
        color=TITLE_STYLE["color"],
    )

    # Footer
    footer_text = (
        f"Total L2: {total_l2:.4f} | "
        f"Most affected: {layer_names[most_affected_idx]} ({layer_l2[most_affected_idx]:.4f}) | "
        f"Least affected: {layer_names[least_affected_idx]} ({layer_l2[least_affected_idx]:.4f})"
    )
    footer_fig = subfigs[1]
    footer_ax = footer_fig.add_axes([0, 0, 1, 1])
    footer_ax.axis("off")
    footer_ax.text(
        0.5,
        0.5,
        footer_text,
        ha="center",
        va="center",
        fontsize=10,
        style="italic",
        color="#555555",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#f8f9fa", "edgecolor": "#dee2e6"},
        transform=footer_ax.transAxes,
    )

    path = snapshot_dir / f"{attack_type}_weight_layer_delta.png"
    try:
        plt.savefig(path, dpi=100, bbox_inches="tight", pad_inches=0.2, facecolor="white")
    finally:
        plt.close(fig)
    logger.debug(f"Saved weight layer delta: {path}")


def load_weight_snapshot(filepath: str | Path) -> dict | None:
    """Load a weight snapshot metadata file.

    Args:
        filepath: Path to the JSON metadata file.

    Returns:
        Dictionary containing snapshot metadata, or None if load fails.
    """
    path = Path(filepath)

    if not path.exists():
        logger.error(f"Weight snapshot file not found: {path}")
        return None

    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load weight snapshot {path}: {e}")
        return None


def list_weight_snapshots(output_dir: str, strategy_number: int = 0) -> list[Path]:
    """List all weight snapshots in an output directory.

    Args:
        output_dir: Base output directory.
        strategy_number: Strategy index to search.

    Returns:
        List of paths to weight snapshot metadata files.
    """
    snapshots_dir = Path(output_dir) / f"attack_snapshots_{strategy_number}"
    if not snapshots_dir.exists():
        return []

    return sorted(snapshots_dir.glob("client_*/round_*/*_weight_metadata.json"))
