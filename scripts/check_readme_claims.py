#!/usr/bin/env python3
"""Assert that README + docs claims trace to their source of truth.

These numbers (strategy / attack counts) and version badges live in prose but
derive from code (`STRATEGY_REGISTRY`, the attack registries) and `pyproject.toml`.
Prose drifts silently when the code moves and nothing rechecks it — a stale
Flower badge and an undercounted strategy roster both shipped before this gate
existed. Run in CI (Security Audit job) so any mismatch fails the PR.

Add a new claim by appending to `build_checks()`. Keep the regexes anchored to
the exact rendered text so a reworded sentence fails loud rather than silently
matching the wrong number.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

from intellifl.attack_utils.poisoning import DATA_ATTACK_TYPE_NAMES
from intellifl.attack_utils.weight_poisoning import WEIGHT_ATTACK_TYPE_NAMES
from intellifl.simulation_strategies import STRATEGY_REGISTRY

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _first(pattern: str, text: str, label: str) -> str:
    """Return the first capture group, or raise if the pattern is gone."""
    m = re.search(pattern, text)
    if m is None:
        raise SystemExit(
            f"FAIL: {label} — pattern not found (did the wording change?): {pattern!r}"
        )
    return m.group(1)


def build_checks() -> list[tuple[str, str, str, str]]:
    """Return (label, expected, actual, where) tuples — expected is source-of-truth."""
    # Source of truth from code.
    n_strategies = str(len(set(STRATEGY_REGISTRY.values())))
    n_attacks = str(len(DATA_ATTACK_TYPE_NAMES) + len(WEIGHT_ATTACK_TYPE_NAMES))

    # Source of truth from packaging.
    pyproject = tomllib.loads(_read("pyproject.toml"))
    requires_python = pyproject["project"]["requires-python"]
    py_floor = _first(r">=(\d+\.\d+)", requires_python, "requires-python floor")
    flwr_dep = next(d for d in pyproject["project"]["dependencies"] if d.startswith("flwr"))
    flwr_floor = _first(r"flwr>=(\d+\.\d+)", flwr_dep, "flwr floor")

    readme = _read("README.md")
    index = _read("docs/index.md")

    return [
        (
            "README strategy count",
            n_strategies,
            _first(r"\*\*(\d+) Aggregation Strategies\*\*", readme, "README strategy count"),
            "README.md",
        ),
        (
            "README attack count",
            n_attacks,
            _first(r"\*\*(\d+) Attack Types\*\*", readme, "README attack count"),
            "README.md",
        ),
        (
            "README Python badge",
            py_floor,
            _first(r"Python-(\d+\.\d+)\+?-", readme, "README Python badge"),
            "README.md",
        ),
        (
            "README Flower badge",
            flwr_floor,
            _first(r"Flower-v(\d+\.\d+)\+?-", readme, "README Flower badge"),
            "README.md",
        ),
        (
            "index hero strategy count",
            n_strategies,
            _first(r"</span>\s*(\d+) Strategies\b", index, "index hero strategy count"),
            "docs/index.md",
        ),
        (
            "index hero attack count",
            n_attacks,
            _first(r"</span>\s*(\d+) Attacks\b", index, "index hero attack count"),
            "docs/index.md",
        ),
        (
            "index feature strategy count",
            n_strategies,
            _first(r"(\d+) Aggregation Strategies", index, "index feature strategy count"),
            "docs/index.md",
        ),
    ]


def main() -> int:
    failures: list[str] = []
    for label, expected, actual, where in build_checks():
        if actual == expected:
            print(f"  ok   {label}: {actual}")
        else:
            failures.append(
                f"  FAIL {label} ({where}): doc says {actual!r}, source of truth is {expected!r}"
            )

    if failures:
        print("\nREADME/docs claims drifted from code:")
        print("\n".join(failures))
        print(
            "\nUpdate the prose (and the strategy/attack roster lists) to match, or fix the code."
        )
        return 1
    print("\nAll README/docs claims match their source of truth.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
