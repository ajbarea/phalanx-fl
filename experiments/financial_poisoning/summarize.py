"""Build the results folder from the sweep's run manifests.

Writes, under ``results/``:

- ``rounds.csv``: one row per (scenario, rule, seed, round), the raw series;
- ``summary.csv`` / ``summary.md`` / ``summary.tex``: per (scenario, rule), median
  [min, max] over seeds;
- ``figures/attack_success_by_round.{png,pdf}`` and ``figures/final_by_rule.{png,pdf}``.

Every figure is read from the held-out (clean test split) metrics the server recorded
in each manifest; nothing is retyped.

    uv run --no-sync python experiments/financial_poisoning/summarize.py
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sweep import (
    ATTACK_START,
    NUM_CLIENTS,
    RESULTS,
    ROUNDS,
    RUNS,
    SCENARIOS,
    STRATEGIES,
)

FIGURES = RESULTS / "figures"

# Categorical slots 1-3 of the dataviz reference palette (validated all-pairs, light).
SERIES = {"clean": "#2a78d6", "flip": "#eb6834", "flip-boosted": "#1baf7a"}
LABELS = {
    "clean": "No attacker",
    "flip": "1 of 12 flips labels",
    "flip-boosted": "1 of 12 flips labels, boosted",
}
RULE_LABELS = {
    "fedavg": "FedAvg (no defense)",
    "krum": "Krum",
    "multikrum": "Multi-Krum",
    "trimmed-mean": "Trimmed-Mean",
    "median": "Median",
    "bulyan": "Bulyan",
}
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

Cells = dict[tuple[str, str], list[dict[str, Any]]]


def load() -> Cells:
    cells: Cells = defaultdict(list)
    for path in sorted(RUNS.glob("*__*__s*.json")):
        scenario, strategy, seed = path.stem.split("__")
        manifest = json.loads(path.read_text())
        manifest["_seed"] = int(seed.removeprefix("s"))
        cells[(scenario, strategy)].append(manifest)
    return cells


def series(manifest: dict[str, Any], key: str) -> list[float]:
    heldout = manifest["heldout_metrics"]
    return [float(heldout[str(r)][key]) for r in range(ROUNDS + 1)]


def _ranks(manifest: dict[str, Any]) -> list[int]:
    return [r for rs in manifest["attacker_outlier_rank"].values() for r in rs]


def _fmt(values: list[float], scale: float = 100) -> str:
    med = statistics.median(values) * scale
    return f"{med:.1f} [{min(values) * scale:.1f}, {max(values) * scale:.1f}]"


def _ordered(cells: Cells) -> list[tuple[str, str]]:
    return [(sc, st) for sc in SCENARIOS for st in STRATEGIES if (sc, st) in cells]


def write_rounds(cells: Cells) -> None:
    with (RESULTS / "rounds.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "scenario",
                "rule",
                "seed",
                "round",
                "attacker_active",
                "accuracy",
                "loss",
                "attack_success_rate",
                "attacker_outlier_rank",
            ]
        )
        for scenario, strategy in _ordered(cells):
            for m in sorted(cells[(scenario, strategy)], key=lambda m: m["_seed"]):
                acc, loss = series(m, "accuracy"), series(m, "loss")
                asr = series(m, "attack_success_rate")
                ranks = m["attacker_outlier_rank"]
                for r in range(ROUNDS + 1):
                    active = scenario != "clean" and r >= ATTACK_START
                    writer.writerow(
                        [
                            scenario,
                            strategy,
                            m["_seed"],
                            r,
                            int(active),
                            f"{acc[r]:.4f}",
                            f"{loss[r]:.4f}",
                            f"{asr[r]:.4f}",
                            ranks.get(str(r), [""])[0],
                        ]
                    )


def summarize(cells: Cells) -> list[dict[str, Any]]:
    rows = []
    window = range(ATTACK_START, ROUNDS + 1)
    for scenario, strategy in _ordered(cells):
        runs = cells[(scenario, strategy)]
        ranks = [r for m in runs for r in _ranks(m)]
        rows.append(
            {
                "scenario": scenario,
                "rule": strategy,
                "seeds": len(runs),
                "final_accuracy_pct": _fmt([series(m, "accuracy")[ROUNDS] for m in runs]),
                "final_attack_success_pct": _fmt(
                    [series(m, "attack_success_rate")[ROUNDS] for m in runs]
                ),
                "mean_attack_success_attack_rounds_pct": _fmt(
                    [
                        statistics.mean(series(m, "attack_success_rate")[r] for r in window)
                        for m in runs
                    ]
                ),
                "attacker_outlier_rank_median": (
                    f"{statistics.median(ranks):g}" if ranks else "n/a"
                ),
            }
        )
    return rows


def write_tables(rows: list[dict[str, Any]]) -> None:
    with (RESULTS / "summary.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    head = [
        "| scenario | rule | seeds | final accuracy (%) | final attack success (%) |"
        f" mean attack success, rounds {ATTACK_START}-{ROUNDS} (%) |"
        f" attacker outlier rank (of {NUM_CLIENTS}) |",
        "|---|---|---|---|---|---|---|",
    ]
    body = [
        f"| {LABELS[r['scenario']]} | {RULE_LABELS[r['rule']]} | {r['seeds']} |"
        f" {r['final_accuracy_pct']} | {r['final_attack_success_pct']} |"
        f" {r['mean_attack_success_attack_rounds_pct']} | {r['attacker_outlier_rank_median']} |"
        for r in rows
    ]
    (RESULTS / "summary.md").write_text("\n".join(head + body) + "\n")

    tex = [
        "% Generated by experiments/financial_poisoning/summarize.py; do not edit.",
        "% Median [min, max] over seeds, percent. Requires \\usepackage{booktabs}.",
        "\\begin{tabular}{llrlll}",
        "\\toprule",
        f"Scenario & Rule & Seeds & Final acc. & Final ASR & Mean ASR, rounds "
        f"{ATTACK_START}--{ROUNDS} \\\\",
        "\\midrule",
    ]
    tex += [
        f"{LABELS[r['scenario']]} & {RULE_LABELS[r['rule']]} & {r['seeds']} &"
        f" {r['final_accuracy_pct']} & {r['final_attack_success_pct']} &"
        f" {r['mean_attack_success_attack_rounds_pct']} \\\\"
        for r in rows
    ]
    tex += ["\\bottomrule", "\\end{tabular}"]
    (RESULTS / "summary.tex").write_text("\n".join(tex) + "\n")


def _style(ax: Any) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _save(fig: Any, stem: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(FIGURES / f"{stem}.{ext}", dpi=200, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def figure_by_round(cells: Cells) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    ax.axvspan(ATTACK_START - 0.5, ROUNDS + 0.5, color=GRID, alpha=0.45, linewidth=0)
    ax.text(ATTACK_START - 0.3, 101, "attacker active", color=INK_2, fontsize=9, va="bottom")
    rounds = list(range(ROUNDS + 1))
    for scenario in SCENARIOS:
        runs = cells.get((scenario, "fedavg"), [])
        if not runs:
            continue
        per_round = list(zip(*(series(m, "attack_success_rate") for m in runs), strict=True))
        med = [statistics.median(v) * 100 for v in per_round]
        ax.fill_between(
            rounds,
            [min(v) * 100 for v in per_round],
            [max(v) * 100 for v in per_round],
            color=SERIES[scenario],
            alpha=0.15,
            linewidth=0,
        )
        ax.plot(rounds, med, color=SERIES[scenario], linewidth=2, label=LABELS[scenario])
        ax.annotate(
            f"{med[-1]:.0f}%",
            (ROUNDS, med[-1]),
            xytext=(6, 0),
            textcoords="offset points",
            color=INK,
            fontsize=9,
            va="center",
        )
    ax.set_xlim(0, ROUNDS + 1.5)
    ax.set_ylim(0, 100)
    ax.set_xticks(range(0, ROUNDS + 1, 2))
    ax.set_xlabel("Training round", color=INK_2, fontsize=10)
    ax.set_ylabel("Negative news labelled positive (%)", color=INK_2, fontsize=10)
    ax.set_title(
        "Attack success by round, FedAvg (no defense)", color=INK, fontsize=12, loc="left", pad=18
    )
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper left")
    fig.text(
        0.01,
        -0.04,
        f"Median over seeds; band = min to max. {NUM_CLIENTS} banks, DistilBERT + LoRA, "
        "Financial PhraseBank test split (n=970).",
        color=INK_2,
        fontsize=8,
    )
    _save(fig, "attack_success_by_round")


def figure_by_rule(cells: Cells) -> None:
    rules = [st for st in STRATEGIES if any((sc, st) in cells for sc in SCENARIOS)]
    fig, axes = plt.subplots(1, 2, figsize=(9, 0.55 * len(rules) + 1.6), sharey=True)
    fig.patch.set_facecolor(SURFACE)
    offsets = {sc: (i - 1) * 0.22 for i, sc in enumerate(SCENARIOS)}
    panels = [
        ("attack_success_rate", "Attack success, final round (%)"),
        ("accuracy", "Accuracy, final round (%)"),
    ]
    for ax, (key, title) in zip(axes, panels, strict=True):
        _style(ax)
        for scenario in SCENARIOS:
            for y, rule in enumerate(rules):
                runs = cells.get((scenario, rule), [])
                if not runs:
                    continue
                vals = [series(m, key)[ROUNDS] * 100 for m in runs]
                yy = y + offsets[scenario]
                ax.hlines(yy, min(vals), max(vals), color=SERIES[scenario], linewidth=2)
                ax.plot(
                    statistics.median(vals),
                    yy,
                    "o",
                    markersize=8,
                    color=SERIES[scenario],
                    markeredgecolor=SURFACE,
                    markeredgewidth=2,
                    label=LABELS[scenario] if y == 0 else None,
                )
        ax.set_xlim(0, 100)
        ax.set_title(title, color=INK, fontsize=11, loc="left")
    axes[0].set_yticks(range(len(rules)), [RULE_LABELS[r] for r in rules], color=INK)
    axes[0].set_ylim(len(rules) - 0.5, -0.5)  # first rule on top; sharey applies it to both
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        frameon=False,
        fontsize=9,
        labelcolor=INK,
        loc="lower center",
        ncol=3,
        bbox_to_anchor=(0.5, -0.06),
    )
    fig.text(0.01, -0.12, "Dot = median over seeds; line = min to max.", color=INK_2, fontsize=8)
    _save(fig, "final_by_rule")


def main() -> None:
    cells = load()
    if not cells:
        raise SystemExit(f"no manifests under {RUNS}")
    write_rounds(cells)
    write_tables(summarize(cells))
    figure_by_round(cells)
    figure_by_rule(cells)
    print((RESULTS / "summary.md").read_text())


if __name__ == "__main__":
    main()
