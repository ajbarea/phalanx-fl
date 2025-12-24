"""
Image visualization utilities for attack snapshots.

Provides publication-quality visualizations for federated learning attack research:
- Side-by-side image grids (original vs poisoned)
- Confusion matrices for label flipping attacks
- Difference heatmaps for noise-based attacks
"""

import math
from pathlib import Path
from typing import List, Optional, Union

import matplotlib
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.colors import TwoSlopeNorm


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
    attack_config: Union[dict, List[dict]], *attack_parameters: str, default: any = "?"
) -> any:
    """Extract first matching parameter from attack config."""
    config = (
        attack_config[0]
        if isinstance(attack_config, list) and attack_config
        else attack_config
    )

    if isinstance(config, dict):
        for attack_parameter in attack_parameters:
            if attack_parameter in config:
                return config[attack_parameter]

    return default


def _extract_attack_type(attack_config: Union[dict, List[dict]]) -> str:
    """Extract attack type string from config, joining multiple with underscore."""
    if isinstance(attack_config, list):
        if attack_config:
            attack_types = [
                cfg.get("attack_type") or cfg.get("type", "unknown")
                for cfg in attack_config
            ]
            return "_".join(attack_types)
        else:
            return "unknown"
    else:
        return attack_config.get("attack_type") or attack_config.get("type", "unknown")


def _build_single_attack_title(
    attack_config: Union[dict, List[dict]],
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
    attack_config: Union[dict, List[dict]],
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

        return (
            "\n".join(title_parts)
            if title_parts
            else f"{attack_type}\nLabel: {labels[index]}"
        )
    else:
        return _build_single_attack_title(
            attack_config, attack_type, labels, original_labels, index, style
        )


def save_image_grid(
    images: np.ndarray,
    labels: np.ndarray,
    original_labels: np.ndarray,
    filepath: Path,
    attack_config: Union[dict, List[dict]],
    original_images: Optional[np.ndarray] = None,
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
            rows, cols, figsize=figsize, gridspec_kw={"wspace": 0.3, "hspace": 0.5}
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

            ax_poisoned.set_title(
                title, fontsize=10, fontweight="bold", color="#c0392b"
            )
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

                line = plt.Line2D(
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
    attack_config: Optional[Union[dict, List[dict]]] = None,
    class_names: Optional[List[str]] = None,
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

    # Determine unique classes from both arrays
    all_labels = np.concatenate([original_labels, poisoned_labels])
    unique_classes = sorted(np.unique(all_labels).tolist())
    num_classes = len(unique_classes)

    # Build confusion matrix
    confusion = np.zeros((num_classes, num_classes), dtype=int)
    for orig, pois in zip(original_labels, poisoned_labels):
        orig_idx = unique_classes.index(int(orig))
        pois_idx = unique_classes.index(int(pois))
        confusion[orig_idx, pois_idx] += 1

    # Calculate percentages for annotation
    row_sums = confusion.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1  # Avoid division by zero
    percentages = confusion / row_sums * 100

    # Create figure with appropriate size
    fig_size = max(6, num_classes * 0.8)
    fig, ax = plt.subplots(figsize=(fig_size, fig_size), dpi=100)

    # Create heatmap using imshow (publication-quality approach)
    im = ax.imshow(confusion, cmap="Blues", aspect="equal")

    # Add colorbar with label
    cbar = ax.figure.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.set_ylabel("Count", rotation=-90, va="bottom", fontsize=11)

    # Set axis labels
    if class_names and len(class_names) >= num_classes:
        tick_labels = [class_names[c] for c in unique_classes]
    else:
        tick_labels = [str(c) for c in unique_classes]

    ax.set_xticks(np.arange(num_classes))
    ax.set_yticks(np.arange(num_classes))
    ax.set_xticklabels(tick_labels, fontsize=10)
    ax.set_yticklabels(tick_labels, fontsize=10)

    # Rotate x-axis labels for readability if many classes
    if num_classes > 6:
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    # Add annotations with count and percentage
    thresh = confusion.max() / 2.0
    for i in range(num_classes):
        for j in range(num_classes):
            count = confusion[i, j]
            pct = percentages[i, j]
            # Show count and percentage, highlight diagonal (unchanged labels)
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

    # Set labels and title
    ax.set_xlabel("Poisoned Label", fontsize=12, fontweight="bold")
    ax.set_ylabel("Original Label", fontsize=12, fontweight="bold")
    ax.set_title(
        "Label Flipping Attack: Class Mapping Matrix",
        fontsize=14,
        fontweight="bold",
        pad=15,
    )

    # Add summary statistics as text below the plot
    total_samples = len(original_labels)
    flipped_count = np.sum(original_labels != poisoned_labels)
    flip_rate = flipped_count / total_samples * 100 if total_samples > 0 else 0

    stats_text = f"Total Samples: {total_samples} | Labels Flipped: {flipped_count} ({flip_rate:.1f}%)"
    fig.text(
        0.5,
        0.02,
        stats_text,
        ha="center",
        fontsize=10,
        style="italic",
        color="#555555",
    )

    plt.tight_layout(rect=[0, 0.05, 1, 1])
    plt.savefig(filepath, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()


def save_noise_difference_heatmap(
    original_images: np.ndarray,
    noisy_images: np.ndarray,
    filepath: Path,
    attack_config: Optional[Union[dict, List[dict]]] = None,
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

    # Calculate differences
    orig_norm = normalize_for_display(original_images)
    noisy_norm = normalize_for_display(noisy_images)
    differences = noisy_norm - orig_norm

    # Create figure: 3 columns (original, noisy, difference) x num_samples rows
    fig, axes = plt.subplots(
        num_samples,
        3,
        figsize=(12, 3.5 * num_samples),
        gridspec_kw={"wspace": 0.3, "hspace": 0.4},
    )

    # Handle single sample case
    if num_samples == 1:
        axes = axes.reshape(1, -1)

    # Extract SNR if available
    snr = None
    if attack_config:
        snr = _extract_attack_param(attack_config, "target_noise_snr", default=None)

    # Find global min/max for consistent colormap scaling across all samples
    global_max_diff = np.max(np.abs(differences))
    if global_max_diff == 0:
        global_max_diff = 0.1  # Fallback if no difference

    # Create normalization centered at zero
    norm = TwoSlopeNorm(vmin=-global_max_diff, vcenter=0, vmax=global_max_diff)

    for i in range(num_samples):
        orig_img = orig_norm[i]
        noisy_img = noisy_norm[i]
        diff_img = differences[i]

        # Prepare images for display (C, H, W) -> (H, W) or (H, W, C)
        if orig_img.shape[0] == 1:
            orig_disp = orig_img[0]
            noisy_disp = noisy_img[0]
            diff_disp = diff_img[0]
            cmap_img = "gray"
        else:
            orig_disp = orig_img.transpose(1, 2, 0)
            noisy_disp = noisy_img.transpose(1, 2, 0)
            diff_disp = np.mean(diff_img, axis=0)  # Average across channels for diff
            cmap_img = None  # RGB

        # Original image
        ax_orig = axes[i, 0]
        if cmap_img:
            ax_orig.imshow(orig_disp, cmap=cmap_img, vmin=0, vmax=1)
        else:
            ax_orig.imshow(orig_disp)
        ax_orig.set_title("Original", fontsize=11, fontweight="bold", color="#2c3e50")
        ax_orig.axis("off")

        # Noisy image
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

        # Difference heatmap
        ax_diff = axes[i, 2]
        im = ax_diff.imshow(diff_disp, cmap="RdBu_r", norm=norm)
        ax_diff.axis("off")

        # Per-sample statistics
        mean_diff = np.mean(np.abs(diff_img))
        max_diff = np.max(np.abs(diff_img))
        stats_title = f"Difference\nMean: {mean_diff:.4f} | Max: {max_diff:.4f}"
        ax_diff.set_title(stats_title, fontsize=10, fontweight="bold", color="#8e44ad")

        # Add row label on left side
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

    # Add colorbar for difference
    cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
    cbar = fig.colorbar(im, cax=cbar_ax)
    cbar.set_label(
        "Pixel Difference (Noisy - Original)",
        rotation=270,
        labelpad=20,
        fontsize=11,
    )

    # Main title
    title = "Gaussian Noise Attack: Pixel-Level Difference Analysis"
    if snr is not None:
        title += f"\nTarget SNR: {snr} dB"
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.98)

    # Aggregate statistics at bottom
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
