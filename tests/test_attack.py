"""Poisoning + robust-aggregation plumbing: label flip, attack success, boost, strategy pick."""

from __future__ import annotations

import math

import numpy as np
import pytest
import torch
from flwr.serverapp.strategy import Bulyan, FedAvg, FedTrimmedAvg, MultiKrum

from phalanx.client_app import attack_for, boost_update, is_malicious
from phalanx.server_app import ObservableFedAvg, ObservableMixin, build_strategy, outlier_rank
from phalanx.task import attack_success_rate, flip_labels

_CFG = {
    "malicious-partitions": "0, 3",
    "attack-start-round": 2,
    "attack": "label-flip",
    "flip-from": 0,
    "flip-to": 2,
    "boost": 5.0,
}


def test_flip_labels_rewrites_only_the_source_class() -> None:
    assert flip_labels([0, 1, 2, 0], (0, 2)) == [2, 1, 2, 2]


def test_attack_success_rate_counts_source_predicted_as_target() -> None:
    refs = torch.tensor([0, 0, 0, 0, 1, 2])
    preds = torch.tensor([2, 2, 0, 1, 2, 2])
    assert attack_success_rate(preds, refs, (0, 2)) == pytest.approx(0.5)


def test_attack_success_rate_is_nan_without_source_examples() -> None:
    assert math.isnan(attack_success_rate(torch.tensor([1]), torch.tensor([1]), (0, 2)))


@pytest.mark.parametrize(
    ("listed", "partition", "expected"),
    [("0, 3", 3, True), ("0,3", 1, False), ("", 0, False), ("10", 1, False)],
)
def test_is_malicious_matches_whole_ids(listed: str, partition: int, expected: bool) -> None:
    assert is_malicious({"malicious-partitions": listed}, partition) is expected


def test_attack_for_waits_for_start_round_and_spares_honest_clients() -> None:
    assert attack_for(_CFG, 0, 1) == (None, 1.0)
    assert attack_for(_CFG, 1, 5) == (None, 1.0)
    assert attack_for(_CFG, 0, 2) == ((0, 2), 5.0)


def test_attack_for_boost_only_attack_has_no_flip() -> None:
    assert attack_for({**_CFG, "attack": "none"}, 3, 2) == (None, 5.0)


def test_boost_update_scales_the_delta_from_global() -> None:
    g = {"w": torch.tensor([1.0, 1.0])}
    local = {"w": torch.tensor([2.0, 0.0])}
    assert torch.equal(boost_update(g, local, 3.0)["w"], torch.tensor([4.0, -2.0]))


def test_outlier_rank_puts_the_far_update_first() -> None:
    # Coordinate-wise median is 0.05, which update 4 sits on exactly.
    updates = [np.full(4, v) for v in (0.0, 0.2, 9.0, -0.1, 0.05)]
    assert outlier_rank(updates, 2) == 1
    assert outlier_rank(updates, 4) == 5


def _cfg(strategy: str) -> dict[str, object]:
    return {
        "strategy": strategy,
        "fraction-train": 1.0,
        "fraction-evaluate": 1.0,
        "num-malicious": 1,
        "num-nodes-to-select": 11,
        "trim-beta": 0.1,
    }


def test_build_strategy_keeps_fedavg_as_the_default_observable() -> None:
    assert type(build_strategy(_cfg("fedavg"))) is ObservableFedAvg


@pytest.mark.parametrize(
    ("name", "base"),
    [("multikrum", MultiKrum), ("trimmed-mean", FedTrimmedAvg), ("bulyan", Bulyan)],
)
def test_build_strategy_wraps_robust_rules_observably(name: str, base: type[FedAvg]) -> None:
    strategy = build_strategy(_cfg(name))
    assert isinstance(strategy, base)
    assert isinstance(strategy, ObservableMixin)


def test_build_strategy_passes_rule_parameters() -> None:
    multikrum = build_strategy(_cfg("multikrum"))
    trimmed = build_strategy(_cfg("trimmed-mean"))
    assert isinstance(multikrum, MultiKrum) and isinstance(trimmed, FedTrimmedAvg)
    assert multikrum.num_nodes_to_select == 11
    assert trimmed.beta == pytest.approx(0.1)


def test_build_strategy_rejects_unknown_names() -> None:
    with pytest.raises(ValueError, match="unknown strategy"):
        build_strategy(_cfg("fedsgd"))
