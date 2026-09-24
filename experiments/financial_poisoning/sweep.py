"""Run the financial-sentiment poisoning grid: scenario x aggregation rule x seed.

Twelve simulated banks fine-tune DistilBERT (LoRA) on Financial PhraseBank sentiment.
One bank relabels negative news as positive from ``ATTACK_START`` on. Each run's
provenance manifest is copied to ``results/runs/<scenario>__<strategy>__s<seed>.json``;
existing results are skipped, so an interrupted sweep resumes where it stopped.

    uv run --no-sync python experiments/financial_poisoning/sweep.py [--seeds 0 1 2]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parent / "results"
RUNS = RESULTS / "runs"

NUM_CLIENTS = 12
ROUNDS = 20
ATTACK_START = 6

BASE = {
    "num-server-rounds": ROUNDS,
    "model-name": '"distilbert-base-uncased"',
    "lora-target-modules": '"q_lin,v_lin"',
    "learning-rate": 0.0005,
    "local-epochs": 1,
    "dataset": '"atrost/financial_phrasebank"',
    "text-column": '"sentence"',
    "num-labels": 3,
    "partitioner": '"iid"',
    "fraction-train": 1.0,
    # The server scores the held-out split; client-side evaluation would only add time.
    "fraction-evaluate": 0.0,
    "flip-from": 0,  # negative
    "flip-to": 2,  # positive
    "heldout-split": '"test"',
    "attack-start-round": ATTACK_START,
}

# One bank in twelve, as on the slide. "boosted" also scales its update by the
# number of banks, the classic model-replacement move (Bagdasaryan et al., 2020).
SCENARIOS: dict[str, dict[str, object]] = {
    "clean": {},
    "flip": {"malicious-partitions": '"0"', "attack": '"label-flip"'},
    "flip-boosted": {
        "malicious-partitions": '"0"',
        "attack": '"label-flip"',
        "boost": float(NUM_CLIENTS),
    },
}

# f = 1 for the rules that take the attacker count; Multi-Krum keeps n - f updates.
STRATEGIES: dict[str, dict[str, object]] = {
    "fedavg": {},
    "multikrum": {"num-malicious": 1, "num-nodes-to-select": NUM_CLIENTS - 1},
    "krum": {"num-malicious": 1},
    "trimmed-mean": {"trim-beta": 1 / NUM_CLIENTS},
    "median": {},
    "bulyan": {"num-malicious": 1},
}

# A third of an 8 GB GPU per client: three DistilBERT clients plus the server's
# scoring model fit; a fifth oversubscribes VRAM and WSL spills it to system RAM.
FEDERATION = (
    f"num-supernodes={NUM_CLIENTS} client-resources-num-cpus=1 client-resources-num-gpus=0.34"
)


def _run_config(scenario: str, strategy: str, seed: int) -> str:
    cfg = {**BASE, **SCENARIOS[scenario], **STRATEGIES[strategy], "strategy": f'"{strategy}"'}
    cfg["seed"] = seed
    return " ".join(f"{k}={v}" for k, v in cfg.items())


def run_one(scenario: str, strategy: str, seed: int) -> Path:
    """Run one cell; return the copied manifest path."""
    out = RUNS / f"{scenario}__{strategy}__s{seed}.json"
    runs = ROOT / "runs"
    before = set(runs.glob("run-*.json")) if runs.exists() else set()
    cmd = [
        "flwr",
        "run",
        ".",
        "local",
        "--stream",
        "--federation-config",
        FEDERATION,
        "--run-config",
        _run_config(scenario, strategy, seed),
    ]
    log = RESULTS / "logs" / f"{out.stem}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as fh:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, check=False)
    new = sorted(set(runs.glob("run-*.json")) - before)
    if rc.returncode != 0 or len(new) != 1:
        raise RuntimeError(f"{out.stem}: rc={rc.returncode}, {len(new)} new manifest(s); see {log}")
    shutil.copy(new[0], out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--scenarios", nargs="+", default=list(SCENARIOS))
    parser.add_argument("--strategies", nargs="+", default=list(STRATEGIES))
    args = parser.parse_args()
    RUNS.mkdir(parents=True, exist_ok=True)
    cells = [(sc, st, sd) for sd in args.seeds for sc in args.scenarios for st in args.strategies]
    for i, (scenario, strategy, seed) in enumerate(cells, 1):
        out = RUNS / f"{scenario}__{strategy}__s{seed}.json"
        if out.exists():
            print(f"[{i}/{len(cells)}] skip {out.name}", flush=True)
            continue
        start = time.monotonic()
        run_one(scenario, strategy, seed)
        print(f"[{i}/{len(cells)}] {out.name} {time.monotonic() - start:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
