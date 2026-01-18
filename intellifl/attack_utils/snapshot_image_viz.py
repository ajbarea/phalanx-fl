"""
Image visualization utilities for attack snapshots.

Provides publication-quality visualizations for federated learning attack research:
- Side-by-side image grids (original vs poisoned)
- Confusion matrices for label flipping attacks
- Difference heatmaps for noise-based attacks
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle


def _display_image(ax, image: np.ndarray) -> None:
    """Display an image on matplotlib axes with denormalization."""
    image = (image * 0.5) + 0.5

    if image.shape[0] == 1:
        ax.imshow(image[0], cmap="gray")
    else:
        ax.imshow(image.transpose(1, 2, 0))


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


def _extract_attack_param(
    attack_config: dict | list[dict], *attack_parameters: str, default: Any = "?"
) -> Any:
    """Extract first matching parameter from attack config."""
    config = (
        attack_config[0] if isinstance(attack_config, list) and attack_config else attack_config
    )

    if isinstance(config, dict):
        for attack_parameter in attack_parameters:
            if attack_parameter in config:
                return config[attack_parameter]

    return default


def _extract_attack_type(attack_config: dict | list[dict]) -> str:
    """Extract attack type string from config, joining multiple with underscore."""
    if isinstance(attack_config, list):
        if attack_config:
            attack_types = [
                cfg.get("attack_type") or cfg.get("type", "unknown") for cfg in attack_config
            ]
            return "_".join(attack_types)
        else:
            return "unknown"
    else:
        return attack_config.get("attack_type") or attack_config.get("type", "unknown")


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

        return "\n".join(title_parts) if title_parts else f"{attack_type}\nLabel: {labels[index]}"
    else:
        return _build_single_attack_title(
            attack_config, attack_type, labels, original_labels, index, style
        )


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

        if has_noise and original_images is not None:
            # Show difference heatmap
            diff = (images[i] * 0.5 + 0.5) - (original_images[i] * 0.5 + 0.5)
            if images[i].shape[0] > 1:
                diff_disp = np.mean(diff, axis=0)
            else:
                diff_disp = diff[0]

            # Normalize diff for RdBu_r
            vmax = max(0.1, np.max(np.abs(diff)))
            ax_impact.imshow(diff_disp, cmap="RdBu_r", vmin=-vmax, vmax=vmax)
            ax_impact.set_title("Perturbation\n(Delta Heatmap)", fontsize=10, color="#8e44ad")
        elif has_flip:
            # Show transformation arrow
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
        if is_flipped or has_noise:
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
    fig.suptitle(
        f"Composite Attack Synopsis: {' + '.join(names)}\nPublication-ready multi-panel snapshot",
        fontsize=16,
        fontweight="bold",
    )

    plt.savefig(filepath, dpi=300, bbox_inches="tight")
    plt.close()


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
        pairs_per_row = 4
        cols = pairs_per_row * 2
        rows = math.ceil(num_samples / pairs_per_row)
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

            ax_poisoned.set_title(title, fontsize=10, fontweight="bold", color="#c0392b")
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

        for row_idx in range(rows):
            for pair_idx in range(pairs_per_row - 1):
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

    else:
        max_cols = 8
        if num_samples <= max_cols:
            rows, cols = 1, num_samples
        else:
            cols = max_cols
            rows = math.ceil(num_samples / cols)

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

    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()


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
    fig, ax = plt.subplots(figsize=(fig_size, fig_size), dpi=100, layout="constrained")

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
    ax.set_title(
        "Label Flipping Attack: Class Mapping Matrix",
        fontsize=14,
        fontweight="bold",
        pad=15,
    )

    total_samples = len(original_labels)
    flipped_count = np.sum(original_labels != poisoned_labels)
    flip_rate = flipped_count / total_samples * 100 if total_samples > 0 else 0

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

    plt.savefig(filepath, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()


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

    fig, axes = plt.subplots(
        num_samples,
        3,
        figsize=(12, 3.5 * num_samples),
        layout="constrained",
        gridspec_kw={"wspace": 0.3, "hspace": 0.4},
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

    cbar_ax = fig.add_axes((0.92, 0.15, 0.02, 0.7))
    assert im is not None, "No samples to display"
    cbar = fig.colorbar(im, cax=cbar_ax)
    cbar.set_label(
        "Pixel Difference (Noisy - Original)",
        rotation=270,
        labelpad=20,
        fontsize=11,
    )

    title = "Gaussian Noise Attack: Pixel-Level Difference Analysis"
    if snr is not None:
        title += f"\nTarget SNR: {snr} dB"
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.98)

    total_mean_diff = np.mean(np.abs(differences))
    total_max_diff = np.max(np.abs(differences))
    total_std_diff = np.std(differences)

    stats_text = (
        f"Aggregate Statistics | "
        f"Mean Absolute Diff: {total_mean_diff:.4f} | "
        f"Max Absolute Diff: {total_max_diff:.4f} | "
        f"Std Dev: {total_std_diff:.4f}"
    )
    fig.text(
        0.45,
        0.02,
        stats_text,
        ha="center",
        fontsize=10,
        style="italic",
        color="#555555",
    )

    plt.savefig(filepath, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()


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

    samples_per_row = 4
    num_rows = math.ceil(num_samples / samples_per_row)

    fig_width = 24
    fig_height = 4 * num_rows + 1.5

    fig = plt.figure(figsize=(fig_width, fig_height), layout="constrained")

    gs = fig.add_gridspec(
        num_rows + 1,
        samples_per_row * 2,  # 2 columns per sample (image + labels)
        height_ratios=[0.4] + [1] * num_rows,
        width_ratios=[1, 1.2] * samples_per_row,
        hspace=0.4,
        wspace=0.3,
    )

    ax_header = fig.add_subplot(gs[0, :])
    ax_header.set_facecolor("#fff3cd")
    ax_header.text(
        0.5,
        0.5,
        "⚠️  LABEL FLIPPING ATTACK  ⚠️\n"
        "Training labels have been corrupted - images remain unchanged",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
        color="#856404",
        transform=ax_header.transAxes,
    )
    ax_header.set_xlim(0, 1)
    ax_header.set_ylim(0, 1)
    ax_header.axis("off")

    num_flipped = np.sum(original_labels != labels)
    flip_rate = num_flipped / len(labels) * 100 if len(labels) > 0 else 0

    axes_to_line = []
    for i in range(num_samples):
        row_idx = i // samples_per_row + 1
        col_offset = (i % samples_per_row) * 2

        ax_img = fig.add_subplot(gs[row_idx, col_offset])
        _display_image(ax_img, images[i])
        ax_img.axis("off")
        ax_img.set_title(f"Sample {i + 1}", fontsize=10, fontweight="bold", pad=5)

        ax_labels = fig.add_subplot(gs[row_idx, col_offset + 1])
        ax_labels.set_xlim(0, 1)
        ax_labels.set_ylim(0, 1)
        ax_labels.axis("off")

        orig_label = original_labels[i]
        pois_label = labels[i]
        label_changed = orig_label != pois_label

        ax_labels.add_patch(
            Rectangle(
                (0.1, 0.6),
                0.8,
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
                (0.1, 0.15),
                0.8,
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

    for ax in axes_to_line:
        bbox = ax.get_position()
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

    fig.text(
        0.5,
        0.01,
        f"Labels Flipped: {num_flipped}/{len(labels)} ({flip_rate:.1f}%)",
        ha="center",
        fontsize=11,
        style="italic",
        color="#555555",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#f8f9fa", "edgecolor": "#dee2e6"},
    )

    plt.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()


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

    summary = {
        "total_samples": int(total_samples),
        "flipped_samples": int(flipped_count),
        "flip_rate": round(flip_rate, 2),
        "top_flip_patterns": top_patterns,
        "classes_affected": classes_affected,
        "classes_targeted": classes_targeted,
        "attack_config": attack_config if isinstance(attack_config, dict) else None,
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

    fig = plt.figure(figsize=(16, 5 * num_samples + 1), layout="constrained")

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

        gs = fig.add_gridspec(
            num_samples,
            3,
            width_ratios=[1, 1.5, 1.5],
            hspace=0.4,
            wspace=0.3,
        )

        ax_img = fig.add_subplot(gs[i, 0])
        _display_image(ax_img, images[i])
        ax_img.axis("off")
        ax_img.set_title(f"Sample {i + 1}", fontsize=11, fontweight="bold")

        ax_before = fig.add_subplot(gs[i, 1])
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

        ax_after = fig.add_subplot(gs[i, 2])
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
    fig.suptitle(
        f"Weight Attack Prediction Impact: {attack_display}\n(✓ = Ground Truth Label)",
        fontsize=14,
        fontweight="bold",
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

    fig.text(
        0.5,
        0.02,
        stats_text,
        ha="center",
        fontsize=10,
        style="italic",
        color="#555555",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#f8f9fa", "edgecolor": "#dee2e6"},
    )

    plt.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
