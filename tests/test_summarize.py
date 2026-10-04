"""The financial-poisoning summary reads its caption from the run manifests."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytest.importorskip("matplotlib")
EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments" / "financial_poisoning"


@pytest.fixture(scope="module")
def summarize() -> ModuleType:
    sys.path.insert(0, str(EXPERIMENT))
    try:
        return importlib.import_module("summarize")
    finally:
        sys.path.remove(str(EXPERIMENT))


def _manifest(model: str = "m", dataset: str = "d", size: int | None = 970) -> dict[str, Any]:
    scores: dict[str, Any] = {"loss": 1.0, "accuracy": 0.5}
    if size is not None:
        scores["num-examples"] = size
    return {
        "run_config": {"model-name": model, "dataset": dataset},
        "global_metrics": {"0": scores},
    }


def test_setting_reads_model_dataset_and_size(summarize: ModuleType) -> None:
    cells = {("clean", "fedavg"): [_manifest(), _manifest()]}
    assert summarize.setting(cells) == "m + LoRA, d test split (n=970)"


def test_setting_leaves_out_a_size_some_manifest_lacks(summarize: ModuleType) -> None:
    # The committed manifests predate num-examples and name their scores heldout_metrics.
    old = {"run_config": {"model-name": "m", "dataset": "d"}, "heldout_metrics": {"0": {}}}
    cells = {("clean", "fedavg"): [_manifest(), old]}
    assert summarize.setting(cells) == "m + LoRA, d test split"


@pytest.mark.parametrize(
    "other", [_manifest(model="x"), _manifest(dataset="x"), _manifest(size=500)]
)
def test_setting_refuses_manifests_that_disagree(summarize: ModuleType, other: Any) -> None:
    with pytest.raises(SystemExit):
        summarize.setting({("clean", "fedavg"): [_manifest(), other]})


def test_attacker_counts_come_from_the_scenarios(summarize: ModuleType) -> None:
    assert summarize._attackers("clean") == 0
    assert summarize._attackers("flip") == 1
