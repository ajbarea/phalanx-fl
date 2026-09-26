"""The sample count a client reports as its FedAvg aggregation weight.

``len(DataLoader)`` is a batch count; FedAvg's ``weighted_by_key="num-examples"`` needs
a row count. These lock the distinction, which no federated run in CI would surface.
"""

from __future__ import annotations

from typing import Any

import torch
from torch.utils.data import DataLoader, TensorDataset

from phalanx.client_app import _sample_count


def _loader(rows: int, batch_size: int = 32) -> DataLoader[Any]:
    return DataLoader(TensorDataset(torch.zeros(rows)), batch_size=batch_size)


def test_sample_count_reports_rows_not_batches() -> None:
    # The pairs that collide under len(loader): both are 2 batches, and 500/501 both 16.
    assert _sample_count(_loader(33)) == 33
    assert _sample_count(_loader(64)) == 64
    assert _sample_count(_loader(500)) == 500
    assert _sample_count(_loader(501)) == 501


def test_sample_count_is_independent_of_batch_size() -> None:
    # The weight must describe the partition, not how it was chopped up.
    assert {_sample_count(_loader(501, bs)) for bs in (1, 7, 32, 512, 1024)} == {501}


def test_sample_count_handles_an_empty_partition() -> None:
    assert _sample_count(_loader(0)) == 0
