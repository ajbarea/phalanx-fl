"""Build the results folder from the sweep's run manifests.

Writes, under ``results/``:

- ``rounds.csv``: one row per (scenario, rule, seed, round), the raw series;
- ``summary.csv`` / ``summary.md`` / ``summary.tex``: per (scenario, rule), median
  [min, max] over seeds;
- ``figures/attack_success_by_round.{png,pdf}`` and ``figures/by_rule.{png,pdf}``.

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


def _ranks(manifest: dict[str, Any], rounds: range) -> list[int]:
    """The attacker's outlier ranks over ``rounds`` (its flag rides every round it trains)."""
    ranks = manifest["attacker_outlier_rank"]
    return [r for rnd in rounds for r in ranks.get(str(rnd), [])]


def _window() -> range:
    """The attack rounds; the boosted attack swings round to round, so figures average them."""
    return range(ATTACK_START, ROUNDS + 1)


def _stats(values: list[float]) -> tuple[float, float, float]:
    """(median, min, max) in percent."""
    return statistics.median(values) * 100, min(values) * 100, max(values) * 100


def _fmt(stats: tuple[float, float, float]) -> str:
    return f"{stats[0]:.1f} [{stats[1]:.1f}, {stats[2]:.1f}]"


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
        attacking = [r for m in runs for r in _ranks(m, window)]
        honest = [r for m in runs for r in _ranks(m, range(1, ATTACK_START))]
        rows.append(
            {
                "scenario": scenario,
                "rule": strategy,
                "seeds": len(runs),
                "final_accuracy": _stats([series(m, "accuracy")[ROUNDS] for m in runs]),
                "final_attack_success": _stats(
                    [series(m, "attack_success_rate")[ROUNDS] for m in runs]
                ),
                "mean_attack_success_attack_rounds": _stats(
                    [
                        statistics.mean(series(m, "attack_success_rate")[r] for r in window)
                        for m in runs
                    ]
                ),
                # The boosted attack swings round to round, so the final round alone can land
                # on a peak or a trough; the attack-round mean is the stable figure.
                "mean_accuracy_attack_rounds": _stats(
                    [statistics.mean(series(m, "accuracy")[r] for r in window) for m in runs]
                ),
                # Share of attack rounds where the attacker's update was the farthest of all.
                "attacker_farthest_share_pct": (
                    100 * sum(r == 1 for r in attacking) / len(attacking) if attacking else None
                ),
                # Control: its median rank while still honest (rounds before ATTACK_START).
                "attacker_honest_rank_median": statistics.median(honest) if honest else None,
            }
        )
    return rows


def _tex(stats: tuple[float, float, float]) -> str:
    return f"{stats[0]:.1f}\\,{{\\scriptsize[{stats[1]:.1f}, {stats[2]:.1f}]}}"


def _rank(row: dict[str, Any]) -> str:
    share = row["attacker_farthest_share_pct"]
    return "n/a" if share is None else f"{share:.0f}"


def _honest(row: dict[str, Any]) -> str:
    rank = row["attacker_honest_rank_median"]
    return "n/a" if rank is None else f"{rank:g}"


def write_tables(rows: list[dict[str, Any]]) -> None:
    metrics = (
        "final_accuracy",
        "final_attack_success",
        "mean_attack_success_attack_rounds",
        "mean_accuracy_attack_rounds",
    )
    with (RESULTS / "summary.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["scenario", "rule", "seeds"]
            + [f"{m}_pct_{s}" for m in metrics for s in ("median", "min", "max")]
            + ["attacker_farthest_share_pct", "attacker_honest_rank_median"]
        )
        for r in rows:
            share, honest = r["attacker_farthest_share_pct"], r["attacker_honest_rank_median"]
            writer.writerow(
                [r["scenario"], r["rule"], r["seeds"]]
                + [f"{v:.2f}" for m in metrics for v in r[m]]
                + ["" if share is None else f"{share:.1f}", "" if honest is None else f"{honest:g}"]
            )

    head = [
        "| scenario | rule | seeds | final accuracy (%) | final attack success (%) |"
        f" mean attack success, rounds {ATTACK_START}-{ROUNDS} (%) |"
        f" mean accuracy, rounds {ATTACK_START}-{ROUNDS} (%) |"
        f" attack rounds attacker was farthest of {NUM_CLIENTS} (%) |"
        f" attacker's median rank, honest rounds 1-{ATTACK_START - 1} |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    body = [
        f"| {LABELS[r['scenario']]} | {RULE_LABELS[r['rule']]} | {r['seeds']} |"
        f" {_fmt(r['final_accuracy'])} | {_fmt(r['final_attack_success'])} |"
        f" {_fmt(r['mean_attack_success_attack_rounds'])} |"
        f" {_fmt(r['mean_accuracy_attack_rounds'])} | {_rank(r)} |"
        f" {_honest(r)} |"
        for r in rows
    ]
    (RESULTS / "summary.md").write_text("\n".join(head + body) + "\n")

    seeds = sorted({r["seeds"] for r in rows})
    tex = [
        "% Generated by experiments/financial_poisoning/summarize.py; do not edit.",
        f"% Median over {'/'.join(map(str, seeds))} seed(s), [min, max] in small type; percent.",
        "% Requires \\usepackage{booktabs}.",
        "\\begingroup\\setlength{\\tabcolsep}{4pt}  % fits one text column",
        "\\begin{tabular}{lccc}",
        "\\toprule",
        f"& \\multicolumn{{2}}{{c}}{{Final round}} & Rounds {ATTACK_START}--{ROUNDS} \\\\",
        "\\cmidrule(lr){2-3}\\cmidrule(lr){4-4}",
        "Rule & Accuracy & Attack success & Mean attack success \\\\",
    ]
    for scenario in SCENARIOS:
        group = [r for r in rows if r["scenario"] == scenario]
        if not group:
            continue
        tex += ["\\midrule", f"\\multicolumn{{4}}{{l}}{{\\emph{{{LABELS[scenario]}}}}} \\\\"]
        tex += [
            f"{RULE_LABELS[r['rule']]} & {_tex(r['final_accuracy'])} &"
            f" {_tex(r['final_attack_success'])} &"
            f" {_tex(r['mean_attack_success_attack_rounds'])} \\\\"
            for r in group
        ]
    tex += ["\\bottomrule", "\\end{tabular}", "\\endgroup"]
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
    ax.text(1, 101, "all banks honest", color=INK_2, fontsize=9, va="bottom")
    # Round 0 is the untrained model (random head), not a training outcome.
    rounds = list(range(1, ROUNDS + 1))
    for scenario in SCENARIOS:
        runs = cells.get((scenario, "fedavg"), [])
        if not runs:
            continue
        per_round = list(zip(*(series(m, "attack_success_rate")[1:] for m in runs), strict=True))
        med = [statistics.median(v) * 100 for v in per_round]
        ax.fill_between(
            rounds,
            [min(v) * 100 for v in per_round],
            [max(v) * 100 for v in per_round],
            color=SERIES[scenario],
            alpha=0.15,
            linewidth=0,
        )
        window_mean = statistics.median(
            statistics.mean(series(m, "attack_success_rate")[r] for r in _window()) for m in runs
        )
        ax.plot(
            rounds,
            med,
            color=SERIES[scenario],
            linewidth=2,
            label=f"{LABELS[scenario]} (avg {window_mean * 100:.0f}%)",
        )
    ax.set_xlim(0.5, ROUNDS + 0.5)
    ax.set_ylim(0, 100)
    ax.set_xticks([1, *range(5, ROUNDS + 1, 5)])
    ax.set_xlabel("Training round", color=INK_2, fontsize=10)
    ax.set_ylabel("Negative sentences labelled positive (%)", color=INK_2, fontsize=10)
    ax.set_title(
        "Attack success by round, FedAvg (no defense)", color=INK, fontsize=12, loc="left", pad=18
    )
    # Below the plot: inside it, the legend would sit on the attacker's late peaks.
    fig.subplots_adjust(bottom=0.24)
    fig.legend(
        frameon=False,
        fontsize=9,
        labelcolor=INK,
        loc="upper center",
        ncol=3,
        bbox_to_anchor=(0.5, 0.08),
    )
    fig.text(
        0.01,
        -0.02,
        f"Median over seeds; band = min to max; avg = mean of rounds {ATTACK_START}-{ROUNDS}. "
        f"{NUM_CLIENTS} banks, DistilBERT + LoRA, Financial PhraseBank test split (n=970).",
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
        ("attack_success_rate", f"Attack success, mean of rounds {ATTACK_START}-{ROUNDS} (%)"),
        ("accuracy", f"Accuracy, mean of rounds {ATTACK_START}-{ROUNDS} (%)"),
    ]
    for ax, (key, title) in zip(axes, panels, strict=True):
        _style(ax)
        ax.grid(axis="y", visible=False)  # dots sit off the row line by scenario
        for scenario in SCENARIOS:
            for y, rule in enumerate(rules):
                runs = cells.get((scenario, rule), [])
                if not runs:
                    continue
                vals = [statistics.mean(series(m, key)[r] for r in _window()) * 100 for m in runs]
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
        if key == "accuracy":
            # Dots encode position, not length: zoom to the data so rules separate.
            low = min(
                statistics.mean(series(m, key)[r] for r in _window()) * 100
                for runs in cells.values()
                for m in runs
            )
            ax.set_xlim(max(0, (low // 10) * 10 - 10), 100)
        else:
            ax.set_xlim(0, 100)
        ax.set_title(title, color=INK, fontsize=11, loc="left")
    axes[0].set_yticks(range(len(rules)), [RULE_LABELS[r] for r in rules], color=INK)
    axes[0].set_ylim(len(rules) - 0.5, -0.5)  # first rule on top; sharey applies it to both
    handles, labels = axes[0].get_legend_handles_labels()
    fig.subplots_adjust(top=0.84)
    fig.legend(
        handles,
        labels,
        frameon=False,
        fontsize=9,
        labelcolor=INK,
        loc="lower center",
        ncol=3,
        bbox_to_anchor=(0.5, 0.92),
    )
    note = "Dot = median over seeds; line = min to max. Accuracy axis starts above zero."
    seeds = {r: max(len(cells.get((sc, r), [])) for sc in SCENARIOS) for r in rules}
    most = max(seeds.values())
    fewer = [f"{RULE_LABELS[r]} ({n})" for r, n in seeds.items() if n < most]
    if fewer:
        note += f" Seeds per rule: {most}, except " + ", ".join(fewer) + "."
    fig.text(0.01, 0.0, note, color=INK_2, fontsize=8)
    _save(fig, "by_rule")


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
