"""
Image visualization utilities for attack snapshots.

Visualizations for federated learning attacks:
- Side-by-side image grids (original vs poisoned)
- Confusion matrices for label flipping attacks
- Difference heatmaps for noise-based attacks
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Rectangle

from ._helpers import extract_attack_param, extract_attack_type


def _display_image(ax, image: np.ndarray) -> None:
    """Display an image on matplotlib axes with denormalization."""
    image = (image * 0.5) + 0.5

    if image.shape[0] == 1:
        ax.imshow(image[0], cmap="gray")
    else:
        ax.imshow(image.transpose(1, 2, 0))


# ============================================================================
# STANDARD TITLE STYLING (DRY principle - tweak once, apply everywhere)
# ============================================================================
TITLE_STYLE = {
    "fontsize": 14,
    "fontweight": "bold",
    "color": "#2c3e50",  # Dark blue-gray for professional look
}

SUBTITLE_STYLE = {
    "fontsize": 11,
    "fontweight": "normal",
    "color": "#7f8c8d",  # Lighter gray for subtitles
    "style": "italic",
}


def _add_figure_title(
    fig_or_ax,
    title: str,
    subtitle: str | None = None,
    use_suptitle: bool = True,
) -> None:
    """Add a standardized title to a figure or axes.

    Args:
        fig_or_ax: Figure or Axes object to add title to.
        title: Main title text.
        subtitle: Optional subtitle text (appears on second line).
        use_suptitle: If True, uses fig.suptitle(); if False, uses ax.set_title().
    """
    full_title = title
    if subtitle:
        full_title = f"{title}\n{subtitle}"

    if use_suptitle:
        fig_or_ax.suptitle(full_title, **TITLE_STYLE)
    else:
        fig_or_ax.set_title(full_title, pad=15, **TITLE_STYLE)


def _normalize_axes(axes, rows: int, cols: int):
    """Normalize axes array to 2D for consistent indexing."""
    if rows == 1 and cols == 1:
        return [[axes]]
    elif rows == 1:
        return [axes]
    elif cols == 1:
        return [[ax] for ax in axes]
    else:
        return axes


def _calculate_balanced_layout(num_samples: int, max_cols: int = 4) -> tuple[int, int]:
    """Calculate balanced grid layout (rows, cols) to avoid sparse final rows.

    Example: 6 samples with max_cols=4:
    - Standard: row 1 (4), row 2 (2) -> Unbalanced
    - Balanced: row 1 (3), row 2 (3) -> (2, 3)

    Example: 5 samples with max_cols=4:
    - Standard: row 1 (4), row 2 (1) -> Unbalanced
    - Balanced: row 1 (3), row 2 (2) -> (2, 3)

    Args:
        num_samples: Total number of items to display.
        max_cols: Maximum number of columns per row.

    Returns:
        Tuple of (num_rows, cols_per_row).
    """
    if num_samples == 0:
        return 0, 0

    num_rows = math.ceil(num_samples / max_cols)
    cols_per_row = math.ceil(num_samples / num_rows)

    return num_rows, cols_per_row


_extract_attack_param = extract_attack_param
_extract_attack_type = extract_attack_type


def _build_single_attack_title(
    attack_config: dict | list[dict],
    attack_type: str,
    labels: np.ndarray,
    original_labels: np.ndarray,
    index: int,
    style: str,
) -> str:
    """Build title string for a single attack sample visualization."""
    if attack_type == "label_flipping":
        if style == "side_by_side":
            return f"Poisoned\nLabel: {labels[index]}"
        return f"Label: {labels[index]}\n(was {original_labels[index]})"

    elif attack_type == "gaussian_noise":
        snr = _extract_attack_param(attack_config, "target_noise_snr")
        if style == "side_by_side":
            return f"Poisoned (Noise)\nSNR: {snr}dB\nLabel: {labels[index]}"
        return f"Noisy (SNR: {snr}dB)\nLabel: {labels[index]}"

    elif attack_type == "token_replacement":
        return f"Token poisoned\nLabel: {labels[index]}"

    elif attack_type == "targeted_label_flipping":
        src = _extract_attack_param(attack_config, "source_class", default="?")
        tgt = _extract_attack_param(attack_config, "target_class", default="?")
        if style == "side_by_side":
            return f"Targeted Flip ({src}->{tgt})\nLabel: {labels[index]}"
        return f"Label: {labels[index]}\n(target: {src}->{tgt})"

    elif attack_type == "backdoor_trigger":
        tgt = _extract_attack_param(attack_config, "target_class", default="?")
        pattern = _extract_attack_param(attack_config, "trigger_pattern", default="square")
        if style == "side_by_side":
            return f"Backdoor ({pattern})\nTarget: {tgt}\nLabel: {labels[index]}"
        return f"Backdoor -> {tgt}\nLabel: {labels[index]}"

    else:
        prefix = f"Poisoned ({attack_type})" if style == "side_by_side" else attack_type
        return f"{prefix}\nLabel: {labels[index]}"


def _build_attack_title(
    attack_config: dict | list[dict],
    attack_type: str,
    labels: np.ndarray,
    original_labels: np.ndarray,
    index: int,
    style: str = "side_by_side",
) -> str:
    """Build title for attack visualization, handling composite attacks."""
    if isinstance(attack_config, list) and len(attack_config) > 1:
        title_parts = ["Poisoned"] if style == "side_by_side" else []

        for cfg in attack_config:
            cfg_type = cfg.get("attack_type", "unknown")
            if cfg_type == "label_flipping":
                if style == "side_by_side":
                    title_parts.append(f"Label: {labels[index]}")
                else:
                    title_parts.append(
                        f"Label Flip: {labels[index]} (was {original_labels[index]})"
                    )
            elif cfg_type == "gaussian_noise":
                snr = cfg.get("target_noise_snr", "?")
                if style == "side_by_side":
                    title_parts.append(f"Noise: {snr}dB")
                else:
                    title_parts.append(f"Noise (SNR: {snr}dB)")
            elif cfg_type == "token_replacement" and style == "fallback":
                title_parts.append("Token poisoned")
            elif cfg_type == "targeted_label_flipping":
                src = cfg.get("source_class", "?")
                tgt = cfg.get("target_class", "?")
                if style == "side_by_side":
                    title_parts.append(f"Targeted Flip: {src}->{tgt}")
                else:
                    title_parts.append(f"Targeted Flip ({src}->{tgt})")
            elif cfg_type == "backdoor_trigger":
                tgt = cfg.get("target_class", "?")
                pattern = cfg.get("trigger_pattern", "square")
                if style == "side_by_side":
                    title_parts.append(f"Backdoor ({pattern})->cls {tgt}")
                else:
                    title_parts.append(f"Backdoor ({pattern})")

        return "\n".join(title_parts) if title_parts else f"{attack_type}\nLabel: {labels[index]}"
    else:
        return _build_single_attack_title(
            attack_config, attack_type, labels, original_labels, index, style
        )


def save_backdoor_trigger_grid(
    images: np.ndarray,
    labels: np.ndarray,
    original_labels: np.ndarray,
    filepath: Path,
    attack_config: dict | list[dict],
    original_images: np.ndarray | None = None,
    max_samples: int = 4,
) -> None:
    """Save publication-quality backdoor trigger visualization.

    4-column layout per sample row:
    [Original] | [Poisoned + red box] | [Magnified trigger region] | [Difference heatmap]

    Args:
        images: Poisoned images array (N, C, H, W).
        labels: Poisoned labels array.
        original_labels: Original labels array.
        filepath: Output file path (.png).
        attack_config: Attack configuration dict or list of dicts.
        original_images: Original clean images (N, C, H, W).
        max_samples: Maximum samples to display.
    """
    matplotlib.use("Agg")

    num_samples = min(len(images), max_samples)
    images = images[:num_samples]
    labels = labels[:num_samples]
    original_labels = original_labels[:num_samples]
    if original_images is not None:
        original_images = original_images[:num_samples]

    # Extract trigger config
    trigger_position = _extract_attack_param(
        attack_config, "trigger_position", default="bottom_right"
    )
    trigger_size = int(_extract_attack_param(attack_config, "trigger_size", default=4))
    trigger_pattern = _extract_attack_param(attack_config, "trigger_pattern", default="square")
    target_class = _extract_attack_param(attack_config, "target_class", default="?")

    _, c, h, w = images.shape if len(images.shape) == 4 else (num_samples, 1, *images.shape[1:])

    fig = plt.figure(figsize=(18, 4 * num_samples + 1.5), layout="constrained")
    subfigs = fig.subfigures(2, 1, height_ratios=[1, 0.05], hspace=0.02)

    main_fig = subfigs[0]
    axes = main_fig.subplots(
        num_samples,
        4,
        gridspec_kw={"wspace": 0.2, "hspace": 0.3},
    )
    if num_samples == 1:
        axes = axes.reshape(1, -1)

    for i in range(num_samples):
        clean_img = original_images[i] if original_images is not None else images[i]
        pois_img = images[i]

        # Denormalize for display
        clean_disp = (clean_img * 0.5) + 0.5
        pois_disp = (pois_img * 0.5) + 0.5

        # --- Detect trigger bounds ---
        if trigger_position == "random" or original_images is None:
            # Auto-detect trigger via absolute difference
            diff_abs = np.abs(pois_disp - clean_disp)
            diff_sum = diff_abs.sum(axis=0) if c > 1 else diff_abs[0]
            threshold = diff_sum.max() * 0.3 if diff_sum.max() > 0 else 0
            mask = diff_sum > threshold
            ys, xs = np.where(mask)
            if len(ys) > 0:
                y_start, y_end = int(ys.min()), int(ys.max()) + 1
                x_start, x_end = int(xs.min()), int(xs.max()) + 1
            else:
                y_start, x_start = h - trigger_size, w - trigger_size
                y_end, x_end = h, w
        else:
            if trigger_position == "bottom_right":
                y_start, x_start = h - trigger_size, w - trigger_size
            elif trigger_position == "top_left":
                y_start, x_start = 0, 0
            elif trigger_position == "center":
                y_start = (h - trigger_size) // 2
                x_start = (w - trigger_size) // 2
            else:
                y_start, x_start = h - trigger_size, w - trigger_size
            y_end = min(y_start + trigger_size, h)
            x_end = min(x_start + trigger_size, w)

        # --- Column 1: Original ---
        ax_orig = axes[i, 0]
        _display_image(ax_orig, clean_img)
        ax_orig.set_title(
            f"Original\nLabel: {original_labels[i]}",
            fontsize=10,
            fontweight="bold",
            color="#2c3e50",
        )
        ax_orig.axis("off")

        # --- Column 2: Poisoned + red box ---
        ax_pois = axes[i, 1]
        _display_image(ax_pois, pois_img)
        # Draw red rectangle around trigger region
        rect = Rectangle(
            (x_start - 0.5, y_start - 0.5),
            x_end - x_start,
            y_end - y_start,
            linewidth=2,
            edgecolor="red",
            facecolor="none",
        )
        ax_pois.add_patch(rect)
        ax_pois.set_title(
            f"Poisoned\nLabel: {labels[i]}", fontsize=10, fontweight="bold", color="#c0392b"
        )
        ax_pois.axis("off")

        # --- Column 3: Trigger-region delta heatmap (magnified) ---
        ax_mag = axes[i, 2]
        clean_crop = np.clip(clean_disp[:, y_start:y_end, x_start:x_end], 0, 1)
        pois_crop = np.clip(pois_disp[:, y_start:y_end, x_start:x_end], 0, 1)

        trigger_diff = np.abs(pois_crop - clean_crop)
        trigger_diff_disp = np.mean(trigger_diff, axis=0) if c > 1 else trigger_diff[0]

        scale = max(1, 32 // max(trigger_diff_disp.shape[0], trigger_diff_disp.shape[1], 1))
        kernel = np.ones((scale, scale))
        trigger_diff_zoom = np.kron(trigger_diff_disp, kernel)

        zoom_vmax = float(np.max(trigger_diff_zoom))
        if zoom_vmax <= 1e-8:
            zoom_vmax = 1e-8
        ax_mag.imshow(trigger_diff_zoom, cmap="magma", vmin=0, vmax=zoom_vmax)

        max_delta = float(np.max(trigger_diff))
        if max_delta < 0.01:
            ax_mag.text(
                0.5,
                0.5,
                "WARNING\nTrigger delta ≈ 0\nTrigger may match\nbackground intensity",
                transform=ax_mag.transAxes,
                ha="center",
                va="center",
                fontsize=8,
                fontweight="bold",
                color="white",
                bbox={"boxstyle": "round,pad=0.4", "facecolor": "#c0392b", "alpha": 0.85},
            )

        ax_mag.set_title(
            (
                "Trigger Delta (|Poisoned - Clean|)\n"
                f"Mean: {float(np.mean(trigger_diff)):.4f} | Max: {max_delta:.4f}"
            ),
            fontsize=9,
            fontweight="bold",
            color="#8e44ad",
        )
        ax_mag.axis("off")

        # --- Column 4: Difference heatmap ---
        ax_diff = axes[i, 3]
        diff = pois_disp - clean_disp
        diff_disp = np.mean(diff, axis=0) if c > 1 else diff[0]
        vmax = float(np.max(np.abs(diff_disp)))
        if vmax <= 1e-8:
            vmax = 1e-8
        ax_diff.imshow(diff_disp, cmap="RdBu_r", vmin=-vmax, vmax=vmax)
        ax_diff.add_patch(
            Rectangle(
                (x_start - 0.5, y_start - 0.5),
                x_end - x_start,
                y_end - y_start,
                linewidth=1.5,
                edgecolor="#8e44ad",
                facecolor="none",
            )
        )
        ax_diff.set_title(
            "Difference Heatmap\n(trigger outlined)",
            fontsize=10,
            fontweight="bold",
            color="#8e44ad",
        )
        ax_diff.axis("off")

    _add_figure_title(
        main_fig,
        f"Backdoor Trigger Attack: {trigger_pattern} ({trigger_size}x{trigger_size})",
        subtitle=f"Target class: {target_class} | Position: {trigger_position}",
    )

    # Footer
    num_poisoned = int(np.sum(labels != original_labels))
    footer_text = (
        f"Trigger: {trigger_pattern} ({trigger_size}x{trigger_size}) at {trigger_position} | "
        f"Target: {target_class} | Poisoned: {num_poisoned}/{len(labels)}"
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

    try:
        plt.savefig(filepath, dpi=150, bbox_inches="tight", pad_inches=0.2, facecolor="white")
    finally:
        plt.close(fig)


def save_targeted_label_flipping_grid(
    images: np.ndarray,
    labels: np.ndarray,
    original_labels: np.ndarray,
    filepath: Path,
    attack_config: dict | list[dict],
    max_samples: int = 8,
) -> None:
    """Save publication-quality targeted label flipping visualization.

    2-section layout:
    Section A: Source-to-target arrow diagram with stats
    Section B: Grid of affected samples (source_class only)

    Args:
        images: Image array (N, C, H, W).
        labels: Poisoned labels array.
        original_labels: Original labels array.
        filepath: Output file path (.png).
        attack_config: Attack configuration dict or list of dicts.
        max_samples: Maximum affected samples to show in grid.
    """
    matplotlib.use("Agg")

    source_class = _extract_attack_param(attack_config, "source_class", default=None)
    target_class = _extract_attack_param(attack_config, "target_class", default=None)
    flip_ratio = _extract_attack_param(attack_config, "flip_ratio", "poison_ratio", default="?")

    # Find affected samples (where original label == source_class)
    if source_class is not None:
        affected_mask = original_labels == int(source_class)
    else:
        affected_mask = labels != original_labels

    affected_indices = np.where(affected_mask)[0]
    num_affected = len(affected_indices)
    num_source = (
        int(np.sum(original_labels == int(source_class)))
        if source_class is not None
        else num_affected
    )
    num_flipped = int(np.sum(labels[affected_mask] != original_labels[affected_mask]))
    flip_pct = (num_flipped / num_source * 100) if num_source > 0 else 0

    # Limit displayed samples
    show_indices = affected_indices[:max_samples]
    num_show = len(show_indices)

    num_rows, samples_per_row = _calculate_balanced_layout(num_show, max_cols=4)
    if num_rows == 0:
        num_rows = 1

    fig = plt.figure(
        figsize=(6 * samples_per_row, 3 + 4 * num_rows + 1),
        layout="constrained",
    )

    # Section A (arrow diagram) + Section B (sample grid) + footer
    subfigs = fig.subfigures(3, 1, height_ratios=[0.25, 1, 0.05], hspace=0.05)

    # --- Section A: Source -> Target arrow diagram ---
    arrow_fig = subfigs[0]
    ax_arrow = arrow_fig.add_axes([0.1, 0.1, 0.8, 0.8])
    ax_arrow.set_xlim(0, 1)
    ax_arrow.set_ylim(0, 1)
    ax_arrow.axis("off")

    # Source badge (green)
    ax_arrow.add_patch(
        Rectangle(
            (0.1, 0.3),
            0.25,
            0.4,
            facecolor="#27ae60",
            edgecolor="#1e8449",
            linewidth=2,
            zorder=2,
        )
    )
    ax_arrow.text(
        0.225,
        0.5,
        f"Source: {source_class}",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
        color="white",
        zorder=3,
    )

    # Target badge (red)
    ax_arrow.add_patch(
        Rectangle(
            (0.65, 0.3),
            0.25,
            0.4,
            facecolor="#c0392b",
            edgecolor="#922b21",
            linewidth=2,
            zorder=2,
        )
    )
    ax_arrow.text(
        0.775,
        0.5,
        f"Target: {target_class}",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
        color="white",
        zorder=3,
    )

    # Arrow connecting badges
    arrow = FancyArrowPatch(
        (0.37, 0.5),
        (0.63, 0.5),
        arrowstyle="-|>",
        mutation_scale=25,
        lw=3,
        color="#c0392b",
        zorder=1,
    )
    ax_arrow.add_patch(arrow)

    # Stats text above arrow
    ax_arrow.text(
        0.5,
        0.85,
        f"{num_flipped} of {num_source} source-class samples flipped ({flip_pct:.1f}%)",
        ha="center",
        va="center",
        fontsize=11,
        fontweight="bold",
        color="#2c3e50",
    )

    # --- Section B: Affected samples grid ---
    grid_fig = subfigs[1]
    if num_show > 0:
        grid_axes = grid_fig.subplots(
            num_rows,
            samples_per_row * 2,
            gridspec_kw={"wspace": 0.3, "hspace": 0.4},
            width_ratios=[1, 1.2] * samples_per_row,
        )
        if num_rows == 1 and samples_per_row * 2 == 1:
            grid_axes = np.array([[grid_axes]])
        elif num_rows == 1:
            grid_axes = grid_axes.reshape(1, -1)

        for si, idx in enumerate(show_indices):
            row_idx = si // samples_per_row
            col_offset = (si % samples_per_row) * 2

            # Image
            ax_img = grid_axes[row_idx, col_offset]
            _display_image(ax_img, images[idx])
            ax_img.axis("off")
            ax_img.set_title(f"Sample {idx}", fontsize=9, fontweight="bold", pad=3)

            # Label badges
            ax_lbl = grid_axes[row_idx, col_offset + 1]
            ax_lbl.set_xlim(0, 1)
            ax_lbl.set_ylim(0, 1)
            ax_lbl.axis("off")

            label_changed = original_labels[idx] != labels[idx]

            # "Was" badge (green)
            ax_lbl.add_patch(
                Rectangle(
                    (0.02, 0.6),
                    0.96,
                    0.25,
                    facecolor="#27ae60",
                    edgecolor="#1e8449",
                    linewidth=2,
                    transform=ax_lbl.transAxes,
                )
            )
            ax_lbl.text(
                0.5,
                0.725,
                f"Was: {original_labels[idx]}",
                ha="center",
                va="center",
                fontsize=12,
                fontweight="bold",
                color="white",
                transform=ax_lbl.transAxes,
            )

            # Arrow if changed
            if label_changed:
                ax_lbl.annotate(
                    "",
                    xy=(0.5, 0.45),
                    xytext=(0.5, 0.55),
                    xycoords="axes fraction",
                    textcoords="axes fraction",
                    arrowprops={"arrowstyle": "->", "color": "#c0392b", "lw": 2.5},
                )

            # "Now" badge
            badge_color = "#c62828" if label_changed else "#95a5a6"
            edge_color = "#8b1c1c" if label_changed else "#7f8c8d"
            ax_lbl.add_patch(
                Rectangle(
                    (0.02, 0.15),
                    0.96,
                    0.25,
                    facecolor=badge_color,
                    edgecolor=edge_color,
                    linewidth=2,
                    transform=ax_lbl.transAxes,
                )
            )
            now_text = f"Now: {labels[idx]}" if label_changed else f"Unchanged: {labels[idx]}"
            ax_lbl.text(
                0.5,
                0.275,
                now_text,
                ha="center",
                va="center",
                fontsize=12,
                fontweight="bold",
                color="white",
                transform=ax_lbl.transAxes,
            )

        # Hide unused axes
        total_slots = num_rows * samples_per_row
        for si in range(num_show, total_slots):
            row_idx = si // samples_per_row
            col_offset = (si % samples_per_row) * 2
            grid_axes[row_idx, col_offset].axis("off")
            grid_axes[row_idx, col_offset + 1].axis("off")
    else:
        ax_empty = grid_fig.add_axes([0.1, 0.1, 0.8, 0.8])
        ax_empty.axis("off")
        ax_empty.text(
            0.5,
            0.5,
            "No affected samples found",
            ha="center",
            va="center",
            fontsize=12,
            style="italic",
        )

    _add_figure_title(
        fig,
        "Targeted Label Flipping Attack",
        subtitle=f"Source class {source_class} -> Target class {target_class}",
    )

    # Footer
    footer_text = f"Source: {source_class} | Target: {target_class} | Flip ratio: {flip_ratio}"
    footer_fig = subfigs[2]
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

    try:
        plt.savefig(filepath, dpi=150, bbox_inches="tight", pad_inches=0.2, facecolor="white")
    finally:
        plt.close(fig)


def save_composite_synopsis(
    images: np.ndarray,
    labels: np.ndarray,
    original_labels: np.ndarray,
    filepath: Path,
    attack_config: list[dict],
    original_images: np.ndarray | None = None,
    max_samples: int = 4,
) -> None:
    """Save a 3-column 'Synopsis Plate' for publication-quality attack visualization.

    Designed for academic papers to show the full lifecycle of an attack sample:
    [Original Image] | [Attack Vector/Impact] | [Poisoned Image]

    Args:
        images: Poisoned images array (N, C, H, W).
        labels: Poisoned labels array.
        original_labels: Original labels array.
        filepath: Output file path (.png).
        attack_config: List of attack configuration dicts.
        original_images: Original images (N, C, H, W).
        max_samples: Max samples to show (default: 4).
    """
    matplotlib.use("Agg")

    num_samples = min(len(images), max_samples)
    images = images[:num_samples]
    labels = labels[:num_samples]
    original_labels = original_labels[:num_samples]
    if original_images is not None:
        original_images = original_images[:num_samples]

    # Detect attack components
    has_noise = any(cfg.get("attack_type") == "gaussian_noise" for cfg in attack_config)
    has_backdoor = any(cfg.get("attack_type") == "backdoor_trigger" for cfg in attack_config)
    has_targeted_flip = any(
        cfg.get("attack_type") == "targeted_label_flipping" for cfg in attack_config
    )
    has_flip = any(cfg.get("attack_type") == "label_flipping" for cfg in attack_config)

    fig, axes = plt.subplots(
        num_samples,
        3,
        figsize=(15, 4 * num_samples),
        layout="constrained",
        gridspec_kw={"wspace": 0.2, "hspace": 0.3},
    )

    if num_samples == 1:
        axes = np.array([axes])

    for i in range(num_samples):
        # --- Column 1: Original ---
        ax_orig = axes[i, 0]
        if original_images is not None:
            _display_image(ax_orig, original_images[i])
        else:
            _display_image(ax_orig, images[i])  # Fallback
        ax_orig.set_title(
            f"Original\n(Label: {original_labels[i]})", fontsize=11, fontweight="bold"
        )
        ax_orig.axis("off")

        # --- Column 2: Attack Vector / Impact ---
        ax_impact = axes[i, 1]
        ax_impact.axis("off")

        # Priority: noise > backdoor > targeted_flip > flip > fallback
        if has_noise and original_images is not None:
            # Show difference heatmap
            diff = (images[i] * 0.5 + 0.5) - (original_images[i] * 0.5 + 0.5)
            if images[i].shape[0] > 1:
                diff_disp = np.mean(diff, axis=0)
            else:
                diff_disp = diff[0]

            vmax = max(0.1, np.max(np.abs(diff)))
            ax_impact.imshow(diff_disp, cmap="RdBu_r", vmin=-vmax, vmax=vmax)
            ax_impact.set_title("Perturbation\n(Delta Heatmap)", fontsize=10, color="#8e44ad")
        elif has_backdoor and original_images is not None:
            # Show trigger delta
            diff = (images[i] * 0.5 + 0.5) - (original_images[i] * 0.5 + 0.5)
            if images[i].shape[0] > 1:
                diff_disp = np.mean(diff, axis=0)
            else:
                diff_disp = diff[0]

            vmax = max(0.05, np.max(np.abs(diff)))
            ax_impact.imshow(diff_disp, cmap="RdBu_r", vmin=-vmax, vmax=vmax)
            ax_impact.set_title("Trigger Delta\n(Backdoor)", fontsize=10, color="#8e44ad")
        elif has_targeted_flip:
            # Show source -> target arrow
            src_cfg = next(
                (c for c in attack_config if c.get("attack_type") == "targeted_label_flipping"), {}
            )
            src = src_cfg.get("source_class", "?")
            tgt = src_cfg.get("target_class", "?")
            ax_impact.annotate(
                "",
                xy=(0.8, 0.5),
                xytext=(0.2, 0.5),
                arrowprops={"arrowstyle": "->", "lw": 3, "color": "#c0392b"},
            )
            ax_impact.text(
                0.5,
                0.6,
                f"cls {src} → cls {tgt}",
                ha="center",
                va="bottom",
                fontweight="bold",
                color="#c0392b",
                fontsize=14,
            )
            ax_impact.set_title("Attack Effect\n(Targeted Flip)", fontsize=10, color="#c0392b")
        elif has_flip:
            # Show label transformation arrow
            ax_impact.annotate(
                "",
                xy=(0.8, 0.5),
                xytext=(0.2, 0.5),
                arrowprops={"arrowstyle": "->", "lw": 3, "color": "#c0392b"},
            )
            ax_impact.text(
                0.5,
                0.6,
                f"{original_labels[i]} → {labels[i]}",
                ha="center",
                va="bottom",
                fontweight="bold",
                color="#c0392b",
                fontsize=14,
            )
            ax_impact.set_title("Attack Effect\n(Label Flip)", fontsize=10, color="#c0392b")
        else:
            ax_impact.text(0.5, 0.5, "Attack Applied", ha="center", va="center", style="italic")

        # --- Column 3: Poisoned ---
        ax_pois = axes[i, 2]
        _display_image(ax_pois, images[i])

        # Color coding for title based on success
        is_flipped = labels[i] != original_labels[i]
        title_color = "#c0392b" if is_flipped else "#2c3e50"
        status = "POISONED" if is_flipped else "CLEAN/NOISY"

        ax_pois.set_title(
            f"{status}\n(Label: {labels[i]})", fontsize=11, fontweight="bold", color=title_color
        )
        ax_pois.axis("off")

        # Add a subtle red frame if poisoned
        if is_flipped or has_noise or has_backdoor:
            rect = Rectangle(
                (0, 0),
                1,
                1,
                linewidth=3,
                edgecolor=title_color,
                facecolor="none",
                transform=ax_pois.transAxes,
            )
            ax_pois.add_patch(rect)

    # Master title
    names = [cfg.get("attack_type", "?") for cfg in attack_config]
    _add_figure_title(
        fig,
        f"Composite Attack Synopsis: {' + '.join(names)}",
        subtitle="Publication-ready multi-panel snapshot",
    )

    try:
        plt.savefig(filepath, dpi=150, bbox_inches="tight")
    finally:
        plt.close(fig)


def save_image_grid(
    images: np.ndarray,
    labels: np.ndarray,
    original_labels: np.ndarray,
    filepath: Path,
    attack_config: dict | list[dict],
    original_images: np.ndarray | None = None,
) -> None:
    """Save image grid visualization comparing original and poisoned samples.

    Args:
        images: Poisoned images array of shape (N, C, H, W).
        labels: Poisoned labels array.
        original_labels: Original labels array before attack.
        filepath: Output file path for the visualization.
        attack_config: Attack configuration dict or list of dicts.
        original_images: Original images for side-by-side comparison (optional).
    """
    matplotlib.use("Agg")

    num_samples = len(images)
    attack_type = _extract_attack_type(attack_config)

    if original_images is not None:
        rows, pairs_per_row = _calculate_balanced_layout(num_samples, max_cols=4)
        cols = pairs_per_row * 2
        figsize = (3 * cols, 3 * rows)

        fig, axes = plt.subplots(
            rows,
            cols,
            figsize=figsize,
            layout="constrained",
            gridspec_kw={"wspace": 0.3, "hspace": 0.5},
        )

        axes = _normalize_axes(axes, rows, cols)

        for i in range(num_samples):
            pair_idx = i % pairs_per_row
            row_idx = i // pairs_per_row
            col_original = pair_idx * 2
            col_poisoned = pair_idx * 2 + 1

            ax_original = axes[row_idx][col_original]
            _display_image(ax_original, original_images[i])

            ax_original.set_title(
                f"Original\nLabel: {original_labels[i]}",
                fontsize=10,
                fontweight="bold",
                color="#2c3e50",
            )
            ax_original.axis("off")

            ax_poisoned = axes[row_idx][col_poisoned]
            _display_image(ax_poisoned, images[i])

            title = _build_attack_title(
                attack_config, attack_type, labels, original_labels, i, "side_by_side"
            )

            ax_poisoned.set_title(title, fontsize=9, fontweight="bold", color="#c0392b")
            ax_poisoned.axis("off")

        total_pairs_needed = num_samples
        total_subplots = rows * pairs_per_row
        for i in range(total_pairs_needed, total_subplots):
            pair_idx = i % pairs_per_row
            row_idx = i // pairs_per_row
            col_original = pair_idx * 2
            col_poisoned = pair_idx * 2 + 1
            axes[row_idx][col_original].axis("off")
            axes[row_idx][col_poisoned].axis("off")

        fig.canvas.draw()

        for row_idx in range(rows):
            row_start = row_idx * pairs_per_row
            row_pairs_used = min(pairs_per_row, max(0, num_samples - row_start))
            for pair_idx in range(max(0, row_pairs_used - 1)):
                col_poisoned = pair_idx * 2 + 1
                ax_poisoned = axes[row_idx][col_poisoned]

                bbox = ax_poisoned.get_position()

                line = Line2D(
                    [bbox.x1 + 0.015, bbox.x1 + 0.015],
                    [bbox.y0, bbox.y1],
                    transform=fig.transFigure,
                    color="#95a5a6",
                    linewidth=2,
                    linestyle="-",
                    alpha=0.6,
                )
                fig.add_artist(line)

        # Add figure title
        attack_display = attack_type.replace("_", " ").title()
        _add_figure_title(fig, f"{attack_display}: Original vs Poisoned Comparison")

    else:
        rows, cols = _calculate_balanced_layout(num_samples, max_cols=8)

        figsize = (4 * cols, 4 * rows)
        fig, axes = plt.subplots(rows, cols, figsize=figsize, layout="constrained")

        if num_samples == 1:
            axes = [axes]
        else:
            axes = axes.flatten() if hasattr(axes, "flatten") else axes

        for i in range(num_samples):
            ax = axes[i]

            _display_image(ax, images[i])

            title = _build_attack_title(
                attack_config, attack_type, labels, original_labels, i, "fallback"
            )

            ax.set_title(title, fontsize=14, fontweight="bold")
            ax.axis("off")

        total_subplots = rows * cols
        for i in range(num_samples, total_subplots):
            axes[i].axis("off")

        # Add figure title
        attack_display = attack_type.replace("_", " ").title()
        _add_figure_title(fig, f"{attack_display}: Poisoned Samples")

    try:
        plt.savefig(filepath, dpi=150, bbox_inches="tight", pad_inches=0.3)
    finally:
        plt.close(fig)


def save_label_confusion_matrix(
    original_labels: np.ndarray,
    poisoned_labels: np.ndarray,
    filepath: Path,
    attack_config: dict | list[dict] | None = None,
    class_names: list[str] | None = None,
) -> None:
    """Saves a publication-quality confusion matrix showing label flipping mappings.

    Creates an annotated heatmap visualization showing how original labels were
    remapped to poisoned labels. Designed for academic publications with:
    - Clear axis labels and title
    - Annotated cells with counts and percentages
    - Publication-friendly colormap (Blues)
    - High DPI output (300) for print quality

    Args:
        original_labels: Original label array before poisoning.
        poisoned_labels: Poisoned label array after attack.
        filepath: Output file path for the visualization.
        attack_config: Attack configuration for metadata (optional).
        class_names: Human-readable class names for axis labels (optional).

    Note:
        If class_names is not provided, uses numeric class indices (0, 1, 2, ...).
        The confusion matrix shows original labels on y-axis (rows) and
        poisoned labels on x-axis (columns), following sklearn convention.
    """
    matplotlib.use("Agg")

    all_labels = np.concatenate([original_labels, poisoned_labels])
    unique_classes = sorted(np.unique(all_labels).tolist())
    num_classes = len(unique_classes)

    confusion = np.zeros((num_classes, num_classes), dtype=int)
    for orig, pois in zip(original_labels, poisoned_labels, strict=False):
        orig_idx = unique_classes.index(int(orig))
        pois_idx = unique_classes.index(int(pois))
        confusion[orig_idx, pois_idx] += 1

    row_sums = confusion.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    percentages = confusion / row_sums * 100

    fig_size = max(6, num_classes * 0.8)
    fig, ax = plt.subplots(figsize=(fig_size, fig_size), dpi=150, layout="constrained")

    im = ax.imshow(confusion, cmap="Blues", aspect="equal")

    cbar = ax.figure.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.set_ylabel("Count", rotation=-90, va="bottom", fontsize=11)

    if class_names and len(class_names) >= num_classes:
        tick_labels = [class_names[c] for c in unique_classes]
    else:
        tick_labels = [str(c) for c in unique_classes]

    ax.set_xticks(np.arange(num_classes))
    ax.set_yticks(np.arange(num_classes))
    ax.set_xticklabels(tick_labels, fontsize=10)
    ax.set_yticklabels(tick_labels, fontsize=10)

    if num_classes > 6:
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    thresh = confusion.max() / 2.0
    for i in range(num_classes):
        for j in range(num_classes):
            count = confusion[i, j]
            pct = percentages[i, j]
            if count > 0:
                text = f"{count}\n({pct:.0f}%)"
                color = "white" if count > thresh else "black"
                weight = "bold" if i != j and count > 0 else "normal"
                ax.text(
                    j,
                    i,
                    text,
                    ha="center",
                    va="center",
                    color=color,
                    fontsize=9,
                    fontweight=weight,
                )

    ax.set_xlabel("Poisoned Label", fontsize=12, fontweight="bold")
    ax.set_ylabel("Original Label", fontsize=12, fontweight="bold")
    normalized_attack_config: dict | list[dict] = attack_config if attack_config is not None else {}
    attack_type = (
        _extract_attack_type(normalized_attack_config)
        if attack_config is not None
        else "label_flipping"
    )
    if attack_type == "targeted_label_flipping":
        source_class = _extract_attack_param(normalized_attack_config, "source_class", default="?")
        target_class = _extract_attack_param(normalized_attack_config, "target_class", default="?")
        matrix_title = (
            f"Targeted Label Flipping Attack: {source_class} -> {target_class} Mapping Matrix"
        )
    else:
        matrix_title = "Label Flipping Attack: Class Mapping Matrix"

    _add_figure_title(
        ax,
        matrix_title,
        use_suptitle=False,
    )

    total_samples = len(original_labels)
    flipped_count = int(np.sum(original_labels != poisoned_labels))
    flip_rate = flipped_count / total_samples * 100 if total_samples > 0 else 0

    if attack_type == "targeted_label_flipping":
        source_class = _extract_attack_param(normalized_attack_config, "source_class", default="?")
        target_class = _extract_attack_param(normalized_attack_config, "target_class", default="?")
        stats_text = (
            f"Source {source_class} → Target {target_class}: "
            f"{flipped_count}/{total_samples} ({flip_rate:.1f}%)"
        )
    else:
        stats_text = (
            f"Total Samples: {total_samples} | Labels Flipped: {flipped_count} ({flip_rate:.1f}%)"
        )
    fig.text(
        0.5,
        0.01,
        stats_text,
        ha="center",
        fontsize=10,
        style="italic",
        color="#555555",
    )

    try:
        plt.savefig(filepath, dpi=150, bbox_inches="tight", pad_inches=0.3, facecolor="white")
    finally:
        plt.close(fig)


def save_noise_difference_heatmap(
    original_images: np.ndarray,
    noisy_images: np.ndarray,
    filepath: Path,
    attack_config: dict | list[dict] | None = None,
    max_samples: int = 4,
) -> None:
    """Saves a publication-quality difference heatmap for noise attack visualization.

    Creates a side-by-side visualization showing original images, noisy images,
    and the pixel-wise difference using a diverging colormap. Designed for
    academic publications with:
    - Three-column layout (Original | Noisy | Difference)
    - Diverging colormap (RdBu_r) centered at zero for difference
    - Per-sample and aggregate statistics
    - High DPI output (300) for print quality

    Args:
        original_images: Original image array of shape (N, C, H, W).
        noisy_images: Noisy image array of shape (N, C, H, W).
        filepath: Output file path for the visualization.
        attack_config: Attack configuration for metadata (optional).
        max_samples: Maximum number of samples to display (default: 4).

    Note:
        The difference heatmap uses RdBu_r colormap where:
        - Blue indicates negative differences (noise reduced intensity)
        - White indicates no change
        - Red indicates positive differences (noise increased intensity)
    """
    matplotlib.use("Agg")

    num_samples = min(len(original_images), max_samples)
    original_images = original_images[:num_samples]
    noisy_images = noisy_images[:num_samples]

    # Normalize images from [-1, 1] or [0, 1] to [0, 1] for display
    def normalize_for_display(img):
        img = np.array(img)
        if img.min() < 0:
            img = (img * 0.5) + 0.5
        return np.clip(img, 0, 1)

    orig_norm = normalize_for_display(original_images)
    noisy_norm = normalize_for_display(noisy_images)
    differences = noisy_norm - orig_norm

    # Use subfigures: main content area + dedicated footer row
    fig = plt.figure(figsize=(11, 3 * num_samples + 1.5), layout="constrained")
    subfigs = fig.subfigures(2, 1, height_ratios=[1, 0.06], hspace=0.02)

    # Main content subfigure
    main_fig = subfigs[0]
    axes = main_fig.subplots(
        num_samples,
        3,
        gridspec_kw={"wspace": 0.15, "hspace": 0.25, "right": 0.72},
    )

    if num_samples == 1:
        axes = axes.reshape(1, -1)

    snr = None
    if attack_config:
        snr = _extract_attack_param(attack_config, "target_noise_snr", default=None)

    # Consistent colormap scaling across all samples for visual comparison
    global_max_diff = np.max(np.abs(differences))
    if global_max_diff == 0:
        global_max_diff = 0.1

    norm = TwoSlopeNorm(vmin=-global_max_diff, vcenter=0, vmax=global_max_diff)

    im = None  # Initialize before loop to avoid possibly unbound error

    for i in range(num_samples):
        orig_img = orig_norm[i]
        noisy_img = noisy_norm[i]
        diff_img = differences[i]

        if orig_img.shape[0] == 1:
            orig_disp = orig_img[0]
            noisy_disp = noisy_img[0]
            diff_disp = diff_img[0]
            cmap_img = "gray"
        else:
            orig_disp = orig_img.transpose(1, 2, 0)
            noisy_disp = noisy_img.transpose(1, 2, 0)
            diff_disp = np.mean(diff_img, axis=0)
            cmap_img = None

        ax_orig = axes[i, 0]
        if cmap_img:
            ax_orig.imshow(orig_disp, cmap=cmap_img, vmin=0, vmax=1)
        else:
            ax_orig.imshow(orig_disp)
        ax_orig.set_title("Original", fontsize=11, fontweight="bold", color="#2c3e50")
        ax_orig.axis("off")

        ax_noisy = axes[i, 1]
        if cmap_img:
            ax_noisy.imshow(noisy_disp, cmap=cmap_img, vmin=0, vmax=1)
        else:
            ax_noisy.imshow(noisy_disp)

        noisy_title = "Noisy"
        if snr is not None:
            noisy_title += f" (SNR: {snr}dB)"
        ax_noisy.set_title(noisy_title, fontsize=11, fontweight="bold", color="#c0392b")
        ax_noisy.axis("off")

        ax_diff = axes[i, 2]
        im = ax_diff.imshow(diff_disp, cmap="RdBu_r", norm=norm)
        ax_diff.axis("off")

        mean_diff = np.mean(np.abs(diff_img))
        max_diff = np.max(np.abs(diff_img))
        stats_title = f"Difference\nMean: {mean_diff:.4f} | Max: {max_diff:.4f}"
        ax_diff.set_title(stats_title, fontsize=10, fontweight="bold", color="#8e44ad")

        if i == 0:
            ax_orig.text(
                -0.15,
                0.5,
                f"Sample {i + 1}",
                transform=ax_orig.transAxes,
                fontsize=10,
                fontweight="bold",
                va="center",
                ha="right",
                rotation=90,
            )
        else:
            ax_orig.text(
                -0.15,
                0.5,
                f"Sample {i + 1}",
                transform=ax_orig.transAxes,
                fontsize=10,
                va="center",
                ha="right",
                rotation=90,
            )

    assert im is not None, "No samples to display"
    cbar = main_fig.colorbar(im, ax=axes[:, 2], shrink=0.8, pad=0.15)
    cbar.set_label(
        "Pixel Difference (Noisy - Original)",
        rotation=270,
        labelpad=15,
        fontsize=10,
    )

    title = "Gaussian Noise Attack: Pixel-Level Difference Analysis"
    subtitle = f"Target SNR: {snr} dB" if snr is not None else None
    _add_figure_title(main_fig, title, subtitle=subtitle)

    total_mean_diff = np.mean(np.abs(differences))
    total_max_diff = np.max(np.abs(differences))
    total_std_diff = np.std(differences)

    stats_text = (
        f"Aggregate Statistics | "
        f"Mean Absolute Diff: {total_mean_diff:.4f} | "
        f"Max Absolute Diff: {total_max_diff:.4f} | "
        f"Std Dev: {total_std_diff:.4f}"
    )

    # Footer subfigure with dedicated stats area
    footer_fig = subfigs[1]
    footer_ax = footer_fig.add_axes([0, 0, 1, 1])
    footer_ax.axis("off")
    footer_ax.text(
        0.5,
        0.5,
        stats_text,
        ha="center",
        va="center",
        fontsize=10,
        style="italic",
        color="#555555",
        transform=footer_ax.transAxes,
    )

    try:
        plt.savefig(filepath, dpi=150, bbox_inches="tight", pad_inches=0.2, facecolor="white")
    finally:
        plt.close(fig)


def save_label_flipping_grid(
    images: np.ndarray,
    labels: np.ndarray,
    original_labels: np.ndarray,
    filepath: Path,
    attack_config: dict | list[dict],
) -> None:
    """Save label flipping visualization with prominent label badges.

    Args:
        images: Image array of shape (N, C, H, W).
        labels: Poisoned labels array.
        original_labels: Original labels array before attack.
        filepath: Output file path for the visualization.
        attack_config: Attack configuration dict or list of dicts.
    """
    matplotlib.use("Agg")

    num_samples = len(images)

    num_rows, samples_per_row = _calculate_balanced_layout(num_samples, max_cols=4)

    fig_width = 6 * samples_per_row
    fig_height = 4 * num_rows + 1.8

    # Use subfigures: main content area + dedicated footer row
    fig = plt.figure(figsize=(fig_width, fig_height), layout="constrained")
    subfigs = fig.subfigures(2, 1, height_ratios=[1, 0.05], hspace=0.02)

    # Add consistent figure title
    _add_figure_title(
        fig,
        "Label Flipping: Original vs Corrupted Labels",
        subtitle="⚠️ Training labels have been corrupted - images remain unchanged",
    )

    # Main content subfigure
    main_fig = subfigs[0]
    gs = main_fig.add_gridspec(
        num_rows,
        samples_per_row * 2,  # 2 columns per sample (image + labels)
        height_ratios=[1] * num_rows,
        width_ratios=[1, 1.2] * samples_per_row,
        hspace=0.4,
        wspace=0.3,
    )

    num_flipped = np.sum(original_labels != labels)
    flip_rate = num_flipped / len(labels) * 100 if len(labels) > 0 else 0

    axes_to_line = []
    for i in range(num_samples):
        row_idx = i // samples_per_row
        col_offset = (i % samples_per_row) * 2

        ax_img = main_fig.add_subplot(gs[row_idx, col_offset])
        _display_image(ax_img, images[i])
        ax_img.axis("off")
        ax_img.set_title(f"Sample {i + 1}", fontsize=10, fontweight="bold", pad=5)

        ax_labels = main_fig.add_subplot(gs[row_idx, col_offset + 1])
        ax_labels.set_xlim(0, 1)
        ax_labels.set_ylim(0, 1)
        ax_labels.axis("off")

        orig_label = original_labels[i]
        pois_label = labels[i]
        label_changed = orig_label != pois_label

        ax_labels.add_patch(
            Rectangle(
                (0.02, 0.6),
                0.96,
                0.25,
                facecolor="#27ae60",
                edgecolor="#1e8449",
                linewidth=2,
                transform=ax_labels.transAxes,
            )
        )
        ax_labels.text(
            0.5,
            0.725,
            f"Original: {orig_label}",
            ha="center",
            va="center",
            fontsize=14,
            fontweight="bold",
            color="white",
            transform=ax_labels.transAxes,
        )

        if label_changed:
            ax_labels.annotate(
                "",
                xy=(0.5, 0.45),
                xytext=(0.5, 0.55),
                xycoords="axes fraction",
                textcoords="axes fraction",
                arrowprops={"arrowstyle": "->", "color": "#c0392b", "lw": 3},
            )

        badge_color = "#c62828" if label_changed else "#95a5a6"
        edge_color = "#8b1c1c" if label_changed else "#7f8c8d"
        ax_labels.add_patch(
            Rectangle(
                (0.02, 0.15),
                0.96,
                0.25,
                facecolor=badge_color,
                edgecolor=edge_color,
                linewidth=2,
                transform=ax_labels.transAxes,
            )
        )

        label_text = f"Poisoned: {pois_label}" if label_changed else f"Unchanged: {pois_label}"
        ax_labels.text(
            0.5,
            0.275,
            label_text,
            ha="center",
            va="center",
            fontsize=14,
            fontweight="bold",
            color="white",
            transform=ax_labels.transAxes,
        )

        # Draw vertical separator if not the last item in a row
        if (i + 1) % samples_per_row != 0 and (i + 1) < num_samples:
            axes_to_line.append(ax_labels)

    main_fig.canvas.draw()

    for ax in axes_to_line:
        bbox = ax.get_position()
        line = Line2D(
            [bbox.x1 + 0.015, bbox.x1 + 0.015],
            [bbox.y0, bbox.y1],
            transform=main_fig.transFigure,
            color="#95a5a6",
            linewidth=2,
            linestyle="-",
            alpha=0.6,
        )
        main_fig.add_artist(line)

    # Footer subfigure with dedicated stats area
    footer_fig = subfigs[1]
    footer_ax = footer_fig.add_axes([0, 0, 1, 1])
    footer_ax.axis("off")
    footer_ax.text(
        0.5,
        0.5,
        f"Labels Flipped: {num_flipped}/{len(labels)} ({flip_rate:.1f}%)",
        ha="center",
        va="center",
        fontsize=11,
        style="italic",
        color="#555555",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#f8f9fa", "edgecolor": "#dee2e6"},
        transform=footer_ax.transAxes,
    )

    try:
        plt.savefig(filepath, dpi=150, bbox_inches="tight", pad_inches=0.2, facecolor="white")
    finally:
        plt.close(fig)


def save_label_flipping_summary(
    original_labels: np.ndarray,
    poisoned_labels: np.ndarray,
    filepath: Path,
    attack_config: dict | list[dict] | None = None,
) -> dict:
    """Save summary statistics for label flipping attack as JSON.

    Args:
        original_labels: Original label array before poisoning.
        poisoned_labels: Poisoned label array after attack.
        filepath: Output file path for the JSON summary.
        attack_config: Attack configuration for metadata (optional).

    Returns:
        Dictionary with summary statistics.
    """
    import json

    total_samples = len(original_labels)
    flipped_mask = original_labels != poisoned_labels
    flipped_count = np.sum(flipped_mask)
    flip_rate = flipped_count / total_samples * 100 if total_samples > 0 else 0

    flip_patterns: dict[str, int] = {}
    for orig, pois in zip(
        original_labels[flipped_mask], poisoned_labels[flipped_mask], strict=False
    ):
        key = f"{int(orig)}->{int(pois)}"
        flip_patterns[key] = flip_patterns.get(key, 0) + 1

    sorted_patterns = sorted(flip_patterns.items(), key=lambda x: -x[1])

    top_patterns = []
    for pattern, count in sorted_patterns[:5]:
        from_label, to_label = pattern.split("->")
        top_patterns.append(
            {
                "from": int(from_label),
                "to": int(to_label),
                "count": count,
                "percentage": round(count / flipped_count * 100, 1) if flipped_count > 0 else 0,
            }
        )

    classes_affected = sorted(set(original_labels[flipped_mask].tolist()))
    classes_targeted = sorted(set(poisoned_labels[flipped_mask].tolist()))

    if isinstance(attack_config, dict):
        normalized_config = attack_config
    elif (
        isinstance(attack_config, list)
        and len(attack_config) == 1
        and isinstance(attack_config[0], dict)
    ):
        normalized_config = attack_config[0]
    else:
        normalized_config = None

    summary = {
        "total_samples": int(total_samples),
        "flipped_samples": int(flipped_count),
        "flip_rate": round(flip_rate, 2),
        "top_flip_patterns": top_patterns,
        "classes_affected": classes_affected,
        "classes_targeted": classes_targeted,
        "attack_config": normalized_config,
    }

    with open(filepath, "w") as f:
        json.dump(summary, f, indent=2)

    return summary


def save_weight_attack_prediction_grid(
    images: np.ndarray,
    labels: np.ndarray,
    predictions_before: list[list[tuple]],
    predictions_after: list[list[tuple]],
    weight_stats: dict,
    filepath: Path,
    attack_config: dict | list[dict],
    class_names: list[str] | None = None,
    full_probs_before: np.ndarray | None = None,
    full_probs_after: np.ndarray | None = None,
) -> None:
    """Save visualization showing prediction changes from weight poisoning attacks.

    Creates a grid visualization with bar charts showing top-K predictions
    BEFORE and AFTER weight poisoning, always including the true class.

    Args:
        images: Sample images array of shape (N, C, H, W).
        labels: Ground truth labels array.
        predictions_before: List of lists of (class_idx, confidence) tuples before poisoning.
        predictions_after: List of lists of (class_idx, confidence) tuples after poisoning.
        weight_stats: Dictionary with weight change statistics.
        filepath: Output file path for the visualization.
        attack_config: Attack configuration dict or list of dicts.
        class_names: Optional human-readable class names for labels.
        full_probs_before: Full probability arrays (N, num_classes) before poisoning.
        full_probs_after: Full probability arrays (N, num_classes) after poisoning.
    """
    matplotlib.use("Agg")

    num_samples = min(len(images), 4)  # Limit to 4 samples for cleaner layout
    attack_type = _extract_attack_type(attack_config)

    def get_class_name(idx):
        if class_names and idx < len(class_names):
            return class_names[idx]
        return str(idx)

    def get_display_classes(preds_list, true_label, full_probs=None, top_k=4):
        """Get top-K classes to display, always including true label."""
        display_classes = {}
        for cls_idx, conf in preds_list[:top_k]:
            display_classes[cls_idx] = conf

        if true_label not in display_classes:
            if full_probs is not None:
                display_classes[true_label] = float(full_probs[true_label])
            else:
                true_conf = 0.0
                for cls_idx, conf in preds_list:
                    if cls_idx == true_label:
                        true_conf = conf
                        break
                display_classes[true_label] = true_conf

        sorted_classes = sorted(display_classes.items(), key=lambda x: -x[1])
        return sorted_classes[:top_k]

    # Use subfigures: main content area + dedicated footer row
    fig = plt.figure(figsize=(16, 3.5 * num_samples + 1.8), layout="constrained")
    subfigs = fig.subfigures(2, 1, height_ratios=[1, 0.08], hspace=0.02)

    # Main content subfigure
    main_fig = subfigs[0]
    gs = main_fig.add_gridspec(
        num_samples,
        3,
        width_ratios=[1, 1.5, 1.5],
        hspace=0.20,
        wspace=0.3,
    )

    for i in range(num_samples):
        preds_before = predictions_before[i]
        preds_after = predictions_after[i]
        true_label = int(labels[i])

        probs_before = full_probs_before[i] if full_probs_before is not None else None
        probs_after = full_probs_after[i] if full_probs_after is not None else None

        before_confs = {}
        after_confs = {}

        for cls_idx, conf in preds_before:
            before_confs[cls_idx] = conf
        for cls_idx, conf in preds_after:
            after_confs[cls_idx] = conf

        if probs_before is not None:
            for cls in range(len(probs_before)):
                if cls not in before_confs:
                    before_confs[cls] = float(probs_before[cls])
        if probs_after is not None:
            for cls in range(len(probs_after)):
                if cls not in after_confs:
                    after_confs[cls] = float(probs_after[cls])

        all_classes = sorted(
            before_confs.keys(),
            key=lambda c: before_confs.get(c, 0),
            reverse=True,
        )[:5]

        if true_label not in all_classes:
            all_classes = all_classes[:4] + [true_label]

        all_classes = sorted(
            all_classes,
            key=lambda c: before_confs.get(c, 0),
            reverse=True,
        )

        ax_img = main_fig.add_subplot(gs[i, 0])
        _display_image(ax_img, images[i])
        ax_img.axis("off")
        ax_img.set_title(f"Sample {i + 1}", fontsize=11, fontweight="bold")

        ax_before = main_fig.add_subplot(gs[i, 1])
        bar_labels = [
            f"✓ {get_class_name(c)}" if c == true_label else f"   {get_class_name(c)}"
            for c in all_classes
        ]
        bar_values = [before_confs.get(c, 0) * 100 for c in all_classes]
        bar_colors = ["#27ae60" if c == true_label else "#3498db" for c in all_classes]
        bar_edges = ["#1a7a3e" if c == true_label else "none" for c in all_classes]
        bar_linewidths = [2.5 if c == true_label else 0 for c in all_classes]

        bars = ax_before.barh(
            bar_labels,
            bar_values,
            color=bar_colors,
            height=0.6,
            edgecolor=bar_edges,
            linewidth=bar_linewidths,
        )
        ax_before.invert_yaxis()  # Flip so highest confidence is at top
        ax_before.set_xlim(0, 105)
        ax_before.set_xlabel("Confidence %", fontsize=9)
        ax_before.set_title("BEFORE Attack", fontsize=11, fontweight="bold", color="#27ae60")
        ax_before.tick_params(axis="y", labelsize=10)
        for j, label in enumerate(ax_before.get_yticklabels()):
            if all_classes[j] == true_label:
                label.set_fontweight("bold")
                label.set_color("#1a5c2e")

        for bar, val in zip(bars, bar_values, strict=False):
            ax_before.text(
                val + 1,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}%",
                va="center",
                fontsize=9,
            )

        ax_after = main_fig.add_subplot(gs[i, 2])
        bar_values_after = [after_confs.get(c, 0) * 100 for c in all_classes]
        bar_colors_after = ["#27ae60" if c == true_label else "#e74c3c" for c in all_classes]
        bar_edges_after = ["#1a7a3e" if c == true_label else "none" for c in all_classes]

        bars_after = ax_after.barh(
            bar_labels,
            bar_values_after,
            color=bar_colors_after,
            height=0.6,
            edgecolor=bar_edges_after,
            linewidth=bar_linewidths,
        )
        ax_after.invert_yaxis()  # Match BEFORE chart orientation
        ax_after.set_xlim(0, 105)
        ax_after.set_xlabel("Confidence %", fontsize=9)
        ax_after.set_title("AFTER Attack", fontsize=11, fontweight="bold", color="#c0392b")
        ax_after.tick_params(axis="y", labelsize=10)
        for j, label in enumerate(ax_after.get_yticklabels()):
            if all_classes[j] == true_label:
                label.set_fontweight("bold")
                label.set_color("#1a5c2e")

        for bar, val in zip(bars_after, bar_values_after, strict=False):
            ax_after.text(
                val + 1,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}%",
                va="center",
                fontsize=9,
            )

    attack_display = attack_type.replace("_", " ").title()
    _add_figure_title(
        main_fig,
        f"Weight Attack Prediction Impact: {attack_display}",
        subtitle="(✓ = Ground Truth Label)",
    )

    pct_changed = weight_stats.get("pct_changed", 0)
    diff_mean = weight_stats.get("diff_mean", 0)
    diff_max = weight_stats.get("diff_max", 0)
    diff_l2 = weight_stats.get("diff_l2_norm", 0)

    pred_changes = sum(
        1
        for pb, pa in zip(predictions_before, predictions_after, strict=False)
        if pb and pa and pb[0][0] != pa[0][0]
    )
    pred_change_pct = (pred_changes / len(predictions_before) * 100) if predictions_before else 0

    stats_text = (
        f"Weight Stats: {pct_changed:.1f}% changed | "
        f"Mean diff: {diff_mean:.4f} | "
        f"Max diff: {diff_max:.4f} | "
        f"L2 norm: {diff_l2:.2f} | "
        f"Predictions changed: {pred_changes}/{len(predictions_before)} ({pred_change_pct:.0f}%)"
    )

    # Footer subfigure with dedicated stats area
    footer_fig = subfigs[1]
    footer_ax = footer_fig.add_axes([0, 0, 1, 1])
    footer_ax.axis("off")
    footer_ax.text(
        0.5,
        0.5,
        stats_text,
        ha="center",
        va="center",
        fontsize=10,
        style="italic",
        color="#555555",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#f8f9fa", "edgecolor": "#dee2e6"},
        transform=footer_ax.transAxes,
    )

    try:
        plt.savefig(filepath, dpi=150, bbox_inches="tight", pad_inches=0.2, facecolor="white")
    finally:
        plt.close(fig)
