"""Animated GIF visualization for attack snapshots in federated learning.

Based on IEEE Transactions on Visualization research on data-driven animations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, MaxNLocator

from intellifl.attack_utils.snapshot_image_viz import TITLE_STYLE

DEFAULT_FPS = 2  # Slow enough to read, fast enough to engage
DEFAULT_DPI = 150  # Balance of quality and file size
DEFAULT_DURATION_PER_FRAME_MS = 500
LOOP_PAUSE_MS = 1500


def save_attack_timeline_gif(
    attack_timeline: dict[str, dict[str, list[str]]],
    filepath: Path,
    total_rounds: int,
    total_clients: int,
    attack_types: list[str] | None = None,
    figsize: tuple[int, int] = (10, 6),
) -> None:
    """Create animated GIF showing attack timeline progression round by round.

    Args:
        attack_timeline: Nested dict mapping client_id -> round -> [attack_types].
            Example: {"0": {"2": ["label_flipping"], "3": ["label_flipping"]}}
        filepath: Output path for the GIF file.
        total_rounds: Total number of federated learning rounds.
        total_clients: Total number of clients in the federation.
        attack_types: Attack types to include in legend. Auto-detected if None.
        figsize: Figure dimensions in inches.
    """
    if attack_types is None:
        detected_types: set[str] = set()
        for client_data in attack_timeline.values():
            for round_attacks in client_data.values():
                detected_types.update(round_attacks)
        attack_types = sorted(detected_types)

    attack_colors = {
        "label_flipping": "#e74c3c",
        "targeted_label_flipping": "#c0392b",
        "gaussian_noise": "#3498db",
        "backdoor_trigger": "#2980b9",
        "model_poisoning": "#9b59b6",
        "gradient_scaling": "#e67e22",
        "byzantine_perturbation": "#1abc9c",
        "boosted_scaling": "#d35400",
        "inner_product_manipulation": "#8e44ad",
        "alternating_min_poisoning": "#16a085",
        "token_replacement": "#f39c12",
    }

    matrix = np.zeros((total_clients, total_rounds))
    attack_matrix: list[list[str | None]] = [
        [None for _ in range(total_rounds)] for _ in range(total_clients)
    ]

    for client_id, client_data in attack_timeline.items():
        client_idx = int(client_id)
        for round_num, attacks in client_data.items():
            round_idx = int(round_num) - 1
            if 0 <= round_idx < total_rounds and 0 <= client_idx < total_clients:
                matrix[client_idx, round_idx] = 1
                attack_matrix[client_idx][round_idx] = attacks[0] if attacks else None

    fig, ax = plt.subplots(figsize=figsize, facecolor="white", layout="constrained")
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
        }
    )

    # Add consistent figure title
    fig.suptitle(
        "Attack Timeline: Federation Rounds",
        fontsize=TITLE_STYLE["fontsize"],
        fontweight=TITLE_STYLE["fontweight"],
        color=TITLE_STYLE["color"],
    )

    ax.imshow(
        np.zeros_like(matrix),
        cmap="Greys",
        aspect="auto",
        vmin=0,
        vmax=1,
        alpha=0.3,
    )

    patches = []
    for i in range(total_clients):
        row_patches = []
        for j in range(total_rounds):
            patch = Rectangle(
                (j - 0.4, i - 0.4),
                0.8,
                0.8,
                facecolor="none",
                edgecolor="none",
                linewidth=2,
            )
            ax.add_patch(patch)
            row_patches.append(patch)
        patches.append(row_patches)

    # Limit tick density for readability
    ax.xaxis.set_major_locator(MaxNLocator(nbins=15, integer=True))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: str(int(x + 1))))

    ax.yaxis.set_major_locator(MaxNLocator(nbins=20, integer=True))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"Client {int(y)}"))

    ax.set_xlabel("Round", fontweight="bold")
    ax.set_ylabel("Client", fontweight="bold")

    round_text = ax.text(
        0.5,
        1.08,
        "",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=16,
        fontweight="bold",
        color="#2c3e50",
    )

    legend_elements = []
    for attack_type in attack_types:
        color = attack_colors.get(attack_type, "#95a5a6")
        legend_elements.append(
            Rectangle(
                (0, 0),
                1,
                1,
                facecolor=color,
                label=attack_type.replace("_", " ").title(),
            )
        )
    if legend_elements:
        ax.legend(
            handles=legend_elements,
            loc="upper left",
            bbox_to_anchor=(1.02, 1),
            frameon=True,
            fancybox=True,
            shadow=True,
        )

    def init():
        round_text.set_text("Round 0 / Starting...")
        for i in range(total_clients):
            for j in range(total_rounds):
                patches[i][j].set_facecolor("none")
        return [round_text] + [p for row in patches for p in row]

    def update(frame):
        current_round = frame + 1
        round_text.set_text(f"Round {current_round} / {total_rounds}")

        for i in range(total_clients):
            for j in range(current_round):
                attack_type = attack_matrix[i][j]
                if attack_type:
                    color = attack_colors.get(attack_type, "#95a5a6")
                    patches[i][j].set_facecolor(color)
                    patches[i][j].set_edgecolor("#2c3e50")
                    patches[i][j].set_alpha(0.9)

        return [round_text] + [p for row in patches for p in row]

    anim = FuncAnimation(
        fig,
        update,
        frames=total_rounds,
        init_func=init,
        blit=True,
        interval=DEFAULT_DURATION_PER_FRAME_MS,
        repeat=True,
    )

    writer = PillowWriter(fps=DEFAULT_FPS)
    anim.save(str(filepath), writer=writer, dpi=DEFAULT_DPI)
    plt.close(fig)

    logging.info(f"Saved attack timeline animation: {filepath}")


def save_accuracy_progression_gif(
    round_metrics: list[dict[str, Any]],
    filepath: Path,
    attack_rounds: list[int] | None = None,
    figsize: tuple[int, int] = (10, 6),
) -> None:
    """Create animated GIF showing accuracy progression with attack shading.

    Args:
        round_metrics: List of dicts with 'round' and 'accuracy' keys.
        filepath: Output path for the GIF file.
        attack_rounds: Round numbers where attacks were active (shown as red shading).
        figsize: Figure dimensions in inches.
    """
    if not round_metrics:
        logging.warning("No round metrics provided for accuracy animation")
        return

    rounds = [m.get("round", i + 1) for i, m in enumerate(round_metrics)]
    accuracies = [m.get("accuracy", 0) * 100 for m in round_metrics]
    total_rounds = len(rounds)

    fig, ax = plt.subplots(figsize=figsize, facecolor="white", layout="constrained")
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
        }
    )

    ax.set_xlim(0.5, total_rounds + 0.5)
    ax.set_ylim(0, max(max(accuracies) * 1.15, 10))
    ax.set_xlabel("Round", fontweight="bold")
    ax.set_ylabel("Accuracy (%)", fontweight="bold")
    ax.set_title("Model Accuracy Progression", fontweight="bold", pad=20)
    ax.grid(True, alpha=0.3, linestyle="--")

    (line,) = ax.plot([], [], "b-", linewidth=2.5, label="Accuracy")
    (scatter,) = ax.plot([], [], "bo", markersize=8)

    if attack_rounds:
        for r in attack_rounds:
            ax.axvspan(r - 0.5, r + 0.5, alpha=0.15, color="red")

    value_text = ax.text(
        0,
        0,
        "",
        fontsize=12,
        fontweight="bold",
        color="#2c3e50",
        ha="left",
        va="bottom",
    )

    round_text = ax.text(
        0.98,
        0.02,
        "",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=12,
        fontweight="bold",
        color="#7f8c8d",
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#bdc3c7"},
    )

    ax.legend(loc="lower right")

    def init():
        line.set_data([], [])
        scatter.set_data([], [])
        value_text.set_text("")
        round_text.set_text("Starting...")
        return line, scatter, value_text, round_text

    def update(frame):
        n = frame + 1
        x_data = rounds[:n]
        y_data = accuracies[:n]

        line.set_data(x_data, y_data)
        scatter.set_data(x_data, y_data)

        current_acc = y_data[-1]
        value_text.set_position((x_data[-1] + 0.2, current_acc + 1))
        value_text.set_text(f"{current_acc:.1f}%")
        round_text.set_text(f"Round {n} / {total_rounds}")

        return line, scatter, value_text, round_text

    anim = FuncAnimation(
        fig,
        update,
        frames=total_rounds,
        init_func=init,
        blit=True,
        interval=DEFAULT_DURATION_PER_FRAME_MS,
        repeat=True,
    )

    writer = PillowWriter(fps=DEFAULT_FPS)
    anim.save(str(filepath), writer=writer, dpi=DEFAULT_DPI)
    plt.close(fig)

    logging.info(f"Saved accuracy progression animation: {filepath}")


def save_client_comparison_gif(
    per_client_metrics: dict[int, list[dict[str, Any]]],
    filepath: Path,
    malicious_clients: list[int] | None = None,
    figsize: tuple[int, int] = (12, 6),
) -> None:
    """Create animated GIF comparing per-client accuracy over rounds.

    Args:
        per_client_metrics: Dict mapping client_id -> list of round metrics.
        filepath: Output path for the GIF file.
        malicious_clients: Client IDs to highlight in red (honest clients are green).
        figsize: Figure dimensions in inches.
    """
    if not per_client_metrics:
        logging.warning("No per-client metrics provided for comparison animation")
        return

    malicious_clients = malicious_clients or []
    client_ids = sorted(per_client_metrics.keys())
    total_rounds = max(len(metrics) for metrics in per_client_metrics.values())

    fig, ax = plt.subplots(figsize=figsize, facecolor="white", layout="constrained")

    honest_color = "#2ecc71"
    malicious_color = "#e74c3c"
    colors = {
        cid: malicious_color if cid in malicious_clients else honest_color for cid in client_ids
    }

    ax.set_xlim(0.5, total_rounds + 0.5)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Round", fontweight="bold")
    ax.set_ylabel("Accuracy (%)", fontweight="bold")
    ax.set_title("Per-Client Accuracy Comparison", fontweight="bold", pad=20)
    ax.grid(True, alpha=0.3, linestyle="--")

    lines = {}
    for cid in client_ids:
        label = f"Client {cid}"
        if cid in malicious_clients:
            label += " (M)"
        (line,) = ax.plot(
            [],
            [],
            color=colors[cid],
            linewidth=2,
            label=label,
            alpha=0.8,
        )
        lines[cid] = line

    round_text = ax.text(
        0.02,
        0.98,
        "",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=14,
        fontweight="bold",
        color="#2c3e50",
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#bdc3c7"},
    )

    ax.legend(loc="lower right", ncol=2, fontsize=9)

    def init():
        for line in lines.values():
            line.set_data([], [])
        round_text.set_text("Starting...")
        return list(lines.values()) + [round_text]

    def update(frame):
        n = frame + 1

        for cid in client_ids:
            metrics = per_client_metrics[cid][:n]
            if metrics:
                x_data = [m.get("round", i + 1) for i, m in enumerate(metrics)]
                y_data = [m.get("accuracy", 0) * 100 for m in metrics]
                lines[cid].set_data(x_data, y_data)

        round_text.set_text(f"Round {n} / {total_rounds}")
        return list(lines.values()) + [round_text]

    anim = FuncAnimation(
        fig,
        update,
        frames=total_rounds,
        init_func=init,
        blit=True,
        interval=DEFAULT_DURATION_PER_FRAME_MS,
        repeat=True,
    )

    writer = PillowWriter(fps=DEFAULT_FPS)
    anim.save(str(filepath), writer=writer, dpi=DEFAULT_DPI)
    plt.close(fig)

    logging.info(f"Saved client comparison animation: {filepath}")


def generate_all_animations(
    output_dir: Path,
    attack_summary: dict[str, Any],
    round_metrics: list[dict[str, Any]] | None = None,
    per_client_metrics: dict[int, list[dict[str, Any]]] | None = None,
    strategy_number: int = 0,
) -> list[Path]:
    """Generate all available animations for a simulation.

    Args:
        output_dir: Base output directory for the simulation.
        attack_summary: Attack summary dict from summary.json.
        round_metrics: Per-round metrics for accuracy animation.
        per_client_metrics: Per-client metrics for comparison animation.
        strategy_number: Strategy index for multi-strategy runs.

    Returns:
        List of paths to generated animation files.
    """
    generated = []
    snapshots_dir = output_dir / f"attack_snapshots_{strategy_number}"

    if not snapshots_dir.exists():
        snapshots_dir.mkdir(parents=True, exist_ok=True)

    attack_timeline = attack_summary.get("attack_timeline", {})
    if attack_timeline:
        experiment = attack_summary.get("experiment", {})
        total_rounds = experiment.get("total_rounds", 10)
        total_clients = experiment.get("total_clients", 5)
        attack_types = attack_summary.get("attack_summary", {}).get("attack_types", [])

        timeline_path = snapshots_dir / "attack_timeline.gif"
        try:
            save_attack_timeline_gif(
                attack_timeline=attack_timeline,
                filepath=timeline_path,
                total_rounds=total_rounds,
                total_clients=total_clients,
                attack_types=attack_types,
            )
            generated.append(timeline_path)
        except Exception as e:
            logging.warning(f"Failed to generate attack timeline animation: {e}")

    if round_metrics:
        attack_rounds = attack_summary.get("attack_summary", {}).get("rounds_with_attacks", [])
        accuracy_path = snapshots_dir / "accuracy_progression.gif"
        try:
            save_accuracy_progression_gif(
                round_metrics=round_metrics,
                filepath=accuracy_path,
                attack_rounds=attack_rounds,
            )
            generated.append(accuracy_path)
        except Exception as e:
            logging.warning(f"Failed to generate accuracy animation: {e}")

    if per_client_metrics:
        malicious_clients = attack_summary.get("attack_summary", {}).get("clients_attacked", [])
        comparison_path = snapshots_dir / "client_comparison.gif"
        try:
            save_client_comparison_gif(
                per_client_metrics=per_client_metrics,
                filepath=comparison_path,
                malicious_clients=malicious_clients,
            )
            generated.append(comparison_path)
        except Exception as e:
            logging.warning(f"Failed to generate client comparison animation: {e}")

    logging.info(f"Generated {len(generated)} animations in {snapshots_dir}")
    return generated
