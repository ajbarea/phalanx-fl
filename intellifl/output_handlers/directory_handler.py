from __future__ import annotations

import csv
import datetime
import json
import logging
from pathlib import Path

import numpy as np

from intellifl.data_models.simulation_strategy_history import SimulationStrategyHistory
from intellifl.utils.reproducibility import save_reproducibility_manifest


class DirectoryHandler:
    dirname: str | None = None

    def __init__(self, output_dir: str | None = None):
        """Initialize directory handler.

        Args:
            output_dir: Output directory path. Defaults to timestamped dir in out/.
        """
        base = (
            Path(output_dir)
            if output_dir
            else Path(f"out/{datetime.datetime.now().strftime('%m-%d-%Y_%H-%M-%S_%f')}")
        )
        self.dirname = str(base)
        self.new_plots_dirname = self.dirname
        self.new_csv_dirname = str(base / "csv")
        self.simulation_strategy_history: SimulationStrategyHistory | None = None
        self.dataset_dir: str | None = None

        DirectoryHandler.dirname = self.dirname

        base.mkdir(parents=True, exist_ok=True)
        (base / "csv").mkdir(exist_ok=True)

    def assign_dataset_dir(self, strategy_number):
        """Create and set dataset directory for the strategy."""
        assert self.dirname is not None
        dataset_path = Path(self.dirname) / f"dataset_{strategy_number}"
        dataset_path.mkdir(exist_ok=True)
        self.dataset_dir = str(dataset_path)

    def save_csv_and_config(self, simulation_strategy_history: SimulationStrategyHistory) -> None:
        """
        Save per-client, per-round and per-execution metrics to CSV files, as well as simulation strategy config.
        """

        self.simulation_strategy_history = simulation_strategy_history

        self._save_simulation_config()
        self._save_per_client_to_csv()
        self._save_per_round_to_csv()
        self._save_per_execution_to_csv()
        self._save_latex_tables()
        self._save_citation_bib()
        self._save_reproducibility_manifest()

    def _save_simulation_config(self):
        """Save simulation config to current directory"""
        assert self.simulation_strategy_history is not None

        config_dict = self.simulation_strategy_history.strategy_config.__dict__.copy()

        # Convert PyTorch device to string for JSON serialization
        if "training_device" in config_dict and hasattr(config_dict["training_device"], "type"):
            config_dict["training_device"] = str(config_dict["training_device"])

        with open(
            f"{self.dirname}/"
            f"strategy_config_{self.simulation_strategy_history.strategy_config.strategy_number}.json",
            "w",
        ) as file:
            json.dump(config_dict, file, indent=4)

    def _save_per_client_to_csv(self):
        """Save per-client metrics to csv"""
        assert self.simulation_strategy_history is not None
        assert self.simulation_strategy_history.strategy_config.num_of_rounds is not None

        csv_filepath = (
            f"{self.new_csv_dirname}/"
            f"per_client_metrics_{self.simulation_strategy_history.strategy_config.strategy_number}.csv"
        )
        with open(csv_filepath, mode="w", newline="", encoding="utf-8") as client_csv:
            writer = csv.writer(client_csv)

            csv_headers: list[str] = ["round"]
            savable_metrics = self.simulation_strategy_history.get_all_clients()[0].savable_metrics

            for metric_name in savable_metrics:
                for client_info in self.simulation_strategy_history.get_all_clients():
                    csv_headers.append(f"client_{client_info.client_id}_{metric_name}")

            writer.writerow(csv_headers)

            for round_num in range(
                1, self.simulation_strategy_history.strategy_config.num_of_rounds + 1
            ):
                row: list[str | int | float] = [round_num]

                for metric_name in savable_metrics:
                    for client_info in self.simulation_strategy_history.get_all_clients():
                        try:
                            value = client_info.get_metric_by_name(metric_name)[round_num - 1]
                            row.append(value if value is not None else "not collected")
                        except IndexError:
                            row.append("not collected")

                writer.writerow(row)

    def _save_per_round_to_csv(self):
        """Save per-round metrics to csv"""
        assert self.simulation_strategy_history is not None
        assert self.simulation_strategy_history.strategy_config.num_of_rounds is not None

        csv_filepath = (
            f"{self.new_csv_dirname}/"
            f"round_metrics_{self.simulation_strategy_history.strategy_config.strategy_number}.csv"
        )
        with open(csv_filepath, mode="w", newline="", encoding="utf-8") as round_csv:
            writer = csv.writer(round_csv)

            savable_metrics = self.simulation_strategy_history.rounds_history.savable_metrics

            csv_headers = ["round"] + list(savable_metrics)
            writer.writerow(csv_headers)

            for round_num in range(
                1, self.simulation_strategy_history.strategy_config.num_of_rounds + 1
            ):
                row: list[str | int | float] = [round_num]

                for metric_name in savable_metrics:
                    collected_history = (
                        self.simulation_strategy_history.rounds_history.get_metric_by_name(
                            metric_name
                        )
                    )
                    try:
                        value = collected_history[round_num - 1]
                        row.append(value if value is not None else "not collected")
                    except IndexError:
                        row.append("not collected")

                writer.writerow(row)

    def _save_per_execution_to_csv(self):
        """
        Save MAD stats per execution:
            mean for (TP, TN, FP, FN, accuracy, precision, recall, f1)
                    ± std
        """
        assert self.simulation_strategy_history is not None

        if not self.simulation_strategy_history.strategy_config.remove_clients:
            return

        csv_filepath = (
            f"{self.new_csv_dirname}/"
            f"exec_stats_{self.simulation_strategy_history.strategy_config.strategy_number}.csv"
        )
        with open(csv_filepath, mode="w", newline="", encoding="utf-8") as exec_stats:
            writer = csv.writer(exec_stats)

            statsable_metrics = self.simulation_strategy_history.rounds_history.statsable_metrics

            csv_headers = [f"mean_{metric_name}" for metric_name in statsable_metrics]
            writer.writerow(csv_headers)

            metric_cells = []
            started_removing_from = (
                self.simulation_strategy_history.strategy_config.begin_removing_from_round or 1
            )

            for metric_name in statsable_metrics:
                collected_history = (
                    self.simulation_strategy_history.rounds_history.get_metric_by_name(metric_name)[
                        started_removing_from - 1 :
                    ]
                )

                metric_mean = np.mean(collected_history) if collected_history else 0.0
                metric_std = np.std(collected_history) if collected_history else 0.0

                if metric_name in (
                    "average_accuracy_history",
                    "removal_accuracy_history",
                    "removal_precision_history",
                    "removal_recall_history",
                    "removal_f1_history",
                ):
                    metric_mean *= 100
                    metric_std *= 100

                if metric_name in (
                    "tp_history",
                    "tn_history",
                    "fp_history",
                    "fn_history",
                ):
                    total_cases = self.simulation_strategy_history.strategy_config.num_of_clients
                    assert total_cases is not None
                    metric_mean = metric_mean / total_cases * 100
                    metric_std = metric_std / total_cases * 100

                metric_cells.append(f"{metric_mean:.2f} ± {metric_std:.2f}")

            writer.writerow(metric_cells)

    def _save_latex_tables(self):
        """Save metrics as publication-quality LaTeX tables."""
        assert self.simulation_strategy_history is not None
        assert self.dirname is not None
        strategy_num = self.simulation_strategy_history.strategy_config.strategy_number
        latex_dir = Path(self.dirname) / "latex"
        latex_dir.mkdir(exist_ok=True)

        # Round Metrics Table (Summary of every 5 rounds)
        round_metrics_path = latex_dir / f"round_metrics_{strategy_num}.tex"
        savable_metrics = list(self.simulation_strategy_history.rounds_history.savable_metrics)

        # Filter for key metrics only if too many
        key_metrics = ["aggregated_loss_history", "average_accuracy_history"]
        if "removal_accuracy_history" in savable_metrics:
            key_metrics.append("removal_accuracy_history")

        with open(round_metrics_path, "w") as f:
            f.write("\\begin{table}[h]\n\\centering\n")
            f.write("\\caption{Simulation Round Metrics (Strategy " + str(strategy_num) + ")}\n")

            # Escape underscores for LaTeX
            cols = ["Round"] + [m.replace("_", "\\_") for m in key_metrics]
            f.write("\\begin{tabular}{l" + "c" * len(key_metrics) + "}\n\\hline\n")
            f.write(" & ".join(cols) + " \\\\ \\hline\n")

            num_rounds = self.simulation_strategy_history.strategy_config.num_of_rounds
            assert num_rounds is not None
            for r in range(1, num_rounds + 1):
                if r == 1 or r == num_rounds or r % 5 == 0:
                    row = [str(r)]
                    for m in key_metrics:
                        val = self.simulation_strategy_history.rounds_history.get_metric_by_name(m)[
                            r - 1
                        ]
                        row.append(f"{val:.4f}" if val is not None else "N/A")
                    f.write(" & ".join(row) + " \\\\\n")

            f.write("\\hline\n\\end{tabular}\n\\end{table}\n")

        # Execution Stats Table (The "Publication result")
        if self.simulation_strategy_history.strategy_config.remove_clients:
            exec_stats_path = latex_dir / f"execution_stats_{strategy_num}.tex"
            statsable_metrics = self.simulation_strategy_history.rounds_history.statsable_metrics

            with open(exec_stats_path, "w") as f:
                f.write("\\begin{table}[h]\n\\centering\n")
                f.write(
                    "\\caption{Detection and Accuracy Performance (Strategy "
                    + str(strategy_num)
                    + ")}\n"
                )
                f.write("\\begin{tabular}{lc}\n\\hline\n")
                f.write("Metric & Value ($\\pm$ std) \\\\ \\hline\n")

                started_removing_from = (
                    self.simulation_strategy_history.strategy_config.begin_removing_from_round or 1
                )

                for metric_name in statsable_metrics:
                    collected_history = (
                        self.simulation_strategy_history.rounds_history.get_metric_by_name(
                            metric_name
                        )[started_removing_from - 1 :]
                    )

                    metric_mean = np.mean(collected_history) if collected_history else 0.0
                    metric_std = np.std(collected_history) if collected_history else 0.0

                    # Standardize percentages
                    if (
                        "accuracy" in metric_name
                        or "precision" in metric_name
                        or "recall" in metric_name
                        or "f1" in metric_name
                    ):
                        metric_mean *= 100
                        metric_std *= 100

                    label = metric_name.replace("_history", "").replace("_", " ").title()
                    f.write(f"{label} & {metric_mean:.2f}\\% $\\pm$ {metric_std:.2f}\\% \\\\\n")

                f.write("\\hline\n\\end{tabular}\n\\end{table}\n")

    def _save_citation_bib(self):
        """Generate a BibTeX citation file for this specific simulation run."""
        assert self.simulation_strategy_history is not None
        assert self.dirname is not None
        run_id = Path(self.dirname).name
        strategy_num = self.simulation_strategy_history.strategy_config.strategy_number
        assert strategy_num is not None
        dataset = self.simulation_strategy_history.strategy_config.dataset_keyword
        strategy = self.simulation_strategy_history.strategy_config.aggregation_strategy_keyword

        bib_content = f"""@misc{{intellifl_{run_id}_s{strategy_num},
  title = {{Federated Learning Experiment Result: {run_id}}},
  author = {{IntelliFL Execution Framework}},
  year = {{2026}},
  howpublished = {{\\url{{https://github.com/dmitrykoro/fl-execution-framework}}}},
  note = {{Dataset: {dataset}, Strategy: {strategy}, Run ID: {run_id}}}
}}
"""
        bib_path = Path(self.dirname) / "CITATION.bib"
        with open(bib_path, "a" if strategy_num > 0 else "w") as f:
            f.write(bib_content)

    def _save_reproducibility_manifest(self):
        """Save the reproducibility MANIFEST.json."""
        assert self.dirname is not None
        assert self.simulation_strategy_history is not None
        try:
            config_path = (
                Path(self.dirname)
                / f"strategy_config_{self.simulation_strategy_history.strategy_config.strategy_number}.json"
            )
            save_reproducibility_manifest(self.dirname, config_path)
        except Exception as e:
            logging.error(f"Failed to save reproducibility manifest in DirectoryHandler: {e}")
