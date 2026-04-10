from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.ticker import MaxNLocator

from intellifl.data_models.simulation_strategy_config import StrategyConfig
from intellifl.federated_simulation import FederatedSimulation
from intellifl.output_handlers.directory_handler import DirectoryHandler

plot_size = (11, 7)
bar_width = 0.2

ATTACK_ABBREV = {
    "label_flipping": "lf",
    "targeted_label_flipping": "tlf",
    "gaussian_noise": "gn",
    "backdoor_trigger": "bd",
    "token_replacement": "tr",
    "model_poisoning": "mp",
    "gradient_scaling": "gs",
    "boosted_scaling": "bs",
    "byzantine_perturbation": "bp",
    "inner_product_manipulation": "ipm",
    "alternating_min_poisoning": "amp",
}

ATTACK_COLORS = {
    "label_flipping": "#ff9999",
    "targeted_label_flipping": "#c0392b",
    "gaussian_noise": "#9999ff",
    "backdoor_trigger": "#2980b9",
    "token_replacement": "#99ff99",
    "model_poisoning": "#9b59b6",
    "gradient_scaling": "#e67e22",
    "boosted_scaling": "#d35400",
    "byzantine_perturbation": "#1abc9c",
    "inner_product_manipulation": "#8e44ad",
    "alternating_min_poisoning": "#16a085",
}

ATTACK_HATCHES = {
    "label_flipping": "////",
    "targeted_label_flipping": "xxxx",
    "gaussian_noise": "\\\\\\\\",
    "backdoor_trigger": "....",
    "token_replacement": "xxxx",
    "model_poisoning": "++",
    "gradient_scaling": "**",
    "boosted_scaling": "//..",
    "byzantine_perturbation": "--",
    "inner_product_manipulation": "xx",
    "alternating_min_poisoning": "||",
}


def _get_client_attack_summary(client_id: int, attack_schedule: list) -> str:
    """
    Generate abbreviated attack summary for a specific client.

    Args:
        client_id: ID of the client to check
        attack_schedule: List of attack schedule entries

    Returns:
        Formatted string like " (lf r2-6, gn r4-8)" or empty string if no attacks
    """
    if not attack_schedule:
        return ""

    client_attacks = []

    for entry in attack_schedule:
        selection = entry.get("selection_strategy")
        is_targeted = False

        if selection == "specific":
            if client_id in entry.get("malicious_client_ids", []):
                is_targeted = True
        elif selection == "random" or selection == "percentage":
            if client_id in entry.get("_selected_clients", []):
                is_targeted = True

        if is_targeted:
            attack_type = entry["attack_type"]
            abbrev = ATTACK_ABBREV.get(attack_type, attack_type[:2])
            attack_str = f"{abbrev} r{entry['start_round']}-{entry['end_round']}"
            client_attacks.append(attack_str)

    if client_attacks:
        if len(client_attacks) > 3:
            display = ", ".join(client_attacks[:3]) + f" +{len(client_attacks) - 3} more"
        else:
            display = ", ".join(client_attacks)
        return f" ({display})"
    return ""


def _generate_single_string_strategy_label(strategy_config: StrategyConfig) -> str:
    """Generate single-string label for strategy (better to use as legend)"""

    return (
        f"strategy: {strategy_config.aggregation_strategy_keyword}, "
        f"dataset: {strategy_config.dataset_keyword}, "
        f"remove: {strategy_config.remove_clients}, "
        f"remove_from: {strategy_config.begin_removing_from_round if strategy_config.remove_clients else 'n/a'}, "
        f"total clients: {strategy_config.num_of_clients}, "
        f"bad_clients: {strategy_config.num_of_malicious_clients}, "
        f"client_epochs: {strategy_config.num_of_client_epochs}, "
        f"batch_size: {strategy_config.batch_size}"
    )


def _generate_multi_string_strategy_label(strategy_config: StrategyConfig) -> str:
    """Generate multi-string label for strategy (better to use as plot title)"""

    return _generate_single_string_strategy_label(strategy_config).replace(", ", "\n")


def _add_attack_background_shading(
    ax: Axes,
    attack_schedule: list,
    client_id: int | None = None,
) -> None:
    """
    Add background shading for attack-active rounds.

    Args:
        ax: Matplotlib axes object
        attack_schedule: List of attack schedule entries
        client_id: If None, show ALL attacks across all clients.
                  If specified, only show attacks affecting that client.
    """
    if not attack_schedule:
        return

    # Track which attack periods we've already added to avoid duplicate labels
    added_attacks = set()

    for entry in attack_schedule:
        if client_id is not None:
            selection = entry.get("selection_strategy")
            if selection == "specific":
                if client_id not in entry.get("malicious_client_ids", []):
                    continue
            elif selection == "random":
                # For random selection, show shading for all clients since any could be affected
                pass

        attack_key = (entry["attack_type"], entry["start_round"], entry["end_round"])

        if attack_key in added_attacks:
            continue

        added_attacks.add(attack_key)

        ax.axvspan(
            entry["start_round"] - 0.4,
            entry["end_round"] + 0.4,
            alpha=0.15,
            facecolor=ATTACK_COLORS.get(entry["attack_type"], "#dddddd"),
            hatch=ATTACK_HATCHES.get(entry["attack_type"], ""),
            edgecolor="black",
            linewidth=0.5,
            label=f"{entry['attack_type']} (r{entry['start_round']}-{entry['end_round']})",
        )


def _is_client_malicious(client_id: int, attack_schedule: list) -> bool:
    """Check if client is targeted by any attack in the schedule."""
    if not attack_schedule:
        return False
    for entry in attack_schedule:
        selection = entry.get("selection_strategy")
        if selection == "specific":
            if client_id in entry.get("malicious_client_ids", []):
                return True
        elif selection in ("random", "percentage"):
            if client_id in entry.get("_selected_clients", []):
                return True
    return False


def save_plot_data_json(
    simulation_strategy: FederatedSimulation, directory_handler: DirectoryHandler
) -> None:
    """Export plot data as JSON for interactive frontend visualization."""
    client_histories = simulation_strategy.strategy_history.get_all_clients()
    if not client_histories:
        return

    attack_schedule = simulation_strategy.strategy_config.attack_schedule or []
    rounds = client_histories[0].rounds
    plottable_metrics = client_histories[0].plottable_metrics

    per_client_metrics = []
    for client in client_histories:
        metrics_dict: dict[str, list[float | None]] = {}
        for metric_name in plottable_metrics:
            values = client.get_metric_by_name(metric_name)
            metrics_dict[metric_name] = [float(v) if v is not None else None for v in values]
        client_data = {
            "client_id": client.client_id,
            "is_malicious": _is_client_malicious(client.client_id, attack_schedule),
            "metrics": metrics_dict,
        }
        per_client_metrics.append(client_data)

    plot_data = {
        "per_client_metrics": per_client_metrics,
        "rounds": list(rounds),
        "removal_threshold_history": list(
            simulation_strategy.strategy_history.rounds_history.removal_threshold_history
        )
        if simulation_strategy.strategy_history.rounds_history.removal_threshold_history
        else None,
        "strategy_number": simulation_strategy.strategy_config.strategy_number,
    }

    output_path = (
        f"{directory_handler.dirname}/"
        f"plot_data_{simulation_strategy.strategy_config.strategy_number}.json"
    )
    with open(output_path, "w") as f:
        json.dump(plot_data, f, indent=2)


def show_plots_within_strategy(
    simulation_strategy: FederatedSimulation, directory_handler: DirectoryHandler
) -> None:
    """Show all per-client plots within the strategy"""

    if not (
        simulation_strategy.strategy_config.show_plots
        or simulation_strategy.strategy_config.save_plots
    ):
        return

    list_of_client_histories = simulation_strategy.strategy_history.get_all_clients()

    if not list_of_client_histories:
        return

    if simulation_strategy.strategy_config.save_plots:
        save_plot_data_json(simulation_strategy, directory_handler)

    plottable_metrics = list_of_client_histories[0].plottable_metrics

    for metric_name in plottable_metrics:
        plt.figure(figsize=plot_size, layout="constrained")
        ax = plt.gca()

        if simulation_strategy.strategy_config.attack_schedule:
            _add_attack_background_shading(
                ax,
                simulation_strategy.strategy_config.attack_schedule,
                client_id=None,
            )

        removal_threshold_history = (
            simulation_strategy.strategy_history.rounds_history.removal_threshold_history
        )

        if (
            metric_name == "removal_criterion_history" and removal_threshold_history
        ):  # Only plot if threshold was collected
            # Ensure rounds and removal_threshold_history have matching dimensions
            client_rounds = list_of_client_histories[0].rounds
            min_length = min(len(client_rounds), len(removal_threshold_history))
            plt.plot(
                client_rounds[:min_length],
                removal_threshold_history[:min_length],
                label="removal threshold",
                linestyle="--",
                color="red",
            )

        for client_info in list_of_client_histories:
            metric_values = client_info.get_metric_by_name(metric_name)

            # Ensure rounds and metric_values have matching dimensions
            min_length = min(len(client_info.rounds), len(metric_values))

            # Generate label with attack summary
            attack_summary = _get_client_attack_summary(
                client_info.client_id,
                simulation_strategy.strategy_config.attack_schedule or [],
            )
            client_label = f"client_{client_info.client_id}{attack_summary}"

            plt.plot(
                client_info.rounds[:min_length],
                metric_values[:min_length],
                label=client_label,
            )

            # to put X on values of clients that were excluded
            excluded_values = [
                metric if participated == 0 else None
                for metric, participated in zip(
                    metric_values[:min_length],
                    client_info.aggregation_participation_history[:min_length],
                    strict=False,
                )
            ]
            plt.plot(client_info.rounds[:min_length], excluded_values, "kx")  # type: ignore[arg-type]

        plt.xlabel("round #")
        plt.ylabel(metric_name)

        plot_strategy_title = _generate_single_string_strategy_label(
            simulation_strategy.strategy_config
        )
        plt.title(f"{metric_name}\n{plot_strategy_title}", fontsize=10)

        legend_title = "clients and attacks"
        num_clients = simulation_strategy.strategy_config.num_of_clients or 1

        plt.legend(
            title=legend_title,
            bbox_to_anchor=(1.05, 1),
            loc="upper left",
            ncol=math.ceil(num_clients / 20),
            fontsize=8,
        )
        ax = plt.gca()
        ax.xaxis.set_major_locator(MaxNLocator(integer=True, steps=[2, 5]))

        if simulation_strategy.strategy_config.save_plots:
            plt.savefig(
                f"{directory_handler.new_plots_dirname}/"
                f"{metric_name}_{simulation_strategy.strategy_config.strategy_number}.pdf"
            )

        if simulation_strategy.strategy_config.show_plots:
            plt.show()

        plt.close()


def show_inter_strategy_plots(
    executed_simulation_strategies: list, directory_handler: DirectoryHandler
) -> None:
    """Show comparing data from all strategies"""

    if not (
        executed_simulation_strategies[0].strategy_config.show_plots
        or executed_simulation_strategies[0].strategy_config.save_plots
    ):
        return

    rounds = executed_simulation_strategies[0].strategy_history.get_all_clients()[0].rounds

    # line plots
    plottable_metrics = executed_simulation_strategies[
        0
    ].strategy_history.rounds_history.plottable_metrics

    for metric_name in plottable_metrics:
        plt.figure(figsize=plot_size, layout="constrained")

        for simulation_strategy in executed_simulation_strategies:
            round_info = simulation_strategy.strategy_history.rounds_history

            metric_values = round_info.get_metric_by_name(metric_name)

            if metric_values:  # plot only if metrics were actually collected
                # Ensure rounds and metric_values have matching dimensions
                min_length = min(len(rounds), len(metric_values))
                plt.plot(
                    rounds[:min_length],
                    metric_values[:min_length],
                    label=_generate_single_string_strategy_label(
                        simulation_strategy.strategy_config
                    ),
                )
        plt.xlabel("round #")
        plt.ylabel(metric_name)
        plt.title(f"{metric_name} across strategies")
        ax = plt.gca()
        # Only show legend if there are labeled artists
        if any(ax.get_legend_handles_labels()):
            plt.legend(title="strategies", loc="upper center", bbox_to_anchor=(0.5, -0.1))
        ax.xaxis.set_major_locator(MaxNLocator(integer=True, steps=[2, 5]))

        if executed_simulation_strategies[0].strategy_config.save_plots:
            plt.savefig(f"{directory_handler.new_plots_dirname}/{metric_name}.pdf")

        if executed_simulation_strategies[0].strategy_config.show_plots:
            plt.show()

        plt.close()

    # bar plots
    barable_metrics = executed_simulation_strategies[
        0
    ].strategy_history.rounds_history.barable_metrics

    for metric_name in barable_metrics:
        plt.figure(figsize=plot_size, layout="constrained")

        rounds_array = np.arange(len(rounds))
        num_strategies = len(executed_simulation_strategies)

        for i, simulation_strategy in enumerate(executed_simulation_strategies):
            round_info = simulation_strategy.strategy_history.rounds_history
            metric_values = round_info.get_metric_by_name(metric_name)

            if metric_values:  # Plot only if metrics were collected
                plt.bar(
                    rounds_array + i * bar_width,  # Offset bars to avoid overlap
                    metric_values,
                    width=bar_width,
                    label=_generate_single_string_strategy_label(
                        simulation_strategy.strategy_config
                    ),
                    alpha=0.8,
                )

        plt.xlabel("round #")
        plt.ylabel(metric_name)
        plt.title(f"{metric_name} across strategies")
        ax = plt.gca()
        # Only show legend if there are labeled artists
        if any(ax.get_legend_handles_labels()):
            plt.legend(title="strategies", loc="upper center", bbox_to_anchor=(0.5, -0.1))
        ax.xaxis.set_major_locator(MaxNLocator(integer=True, steps=[2, 5]))
        ax.set_xticks(
            rounds_array + (num_strategies - 1) * bar_width / 2
        )  # Adjust x-ticks to align
        ax.set_xticklabels(rounds)

        if executed_simulation_strategies[0].strategy_config.save_plots:
            plt.savefig(f"{directory_handler.new_plots_dirname}/{metric_name}.pdf")

        if executed_simulation_strategies[0].strategy_config.show_plots:
            plt.show()

        plt.close()
