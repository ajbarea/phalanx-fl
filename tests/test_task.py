"""Model + adapter helpers in phalanx.task.

These download Google's tiny BERT (~18 MB) from the Hugging Face Hub.
"""

from __future__ import annotations

import pytest
import torch
from datasets import Dataset
from flwr.app import ArrayRecord

from phalanx import task
from phalanx.task import get_adapter_state, get_model, set_adapter_state, set_seed

MODEL = "google/bert_uncased_L-2_H-128_A-2"


def test_set_seed_makes_training_rng_deterministic() -> None:
    set_seed(123)
    a = torch.randn(8)
    set_seed(123)
    b = torch.randn(8)
    assert torch.equal(a, b)


def test_set_seed_separates_ids_a_scaled_sum_would_merge() -> None:
    # 1000 * round + partition + 100_000 * seed gave seed 0 / round 101 and seed 1 / round 1
    # the same stream; SeedSequence hashes the ids, so they no longer collide.
    def draw(entropy: list[int]) -> tuple[float, float, float]:
        set_seed(entropy)
        return task.random.random(), float(task.np.random.rand()), float(torch.rand(1))

    assert draw([101, 0, 0]) != draw([1, 0, 1])
    assert draw([3, 2, 1]) == draw([3, 2, 1])


def test_server_and_client_entropy_never_share_a_stream() -> None:
    # SeedSequence pads entropy with zeros, so untagged [5] and [5, 0, 0] are one stream:
    # a run's initial adapters at seed 5 would replay client round 5, partition 0, seed 0.
    def state(entropy: list[int]) -> list[int]:
        return task.np.random.SeedSequence(entropy).generate_state(4).tolist()

    assert state([5]) == state([5, 0, 0])
    assert state(task.server_entropy(5)) != state(task.client_entropy(5, 0, 0))


@pytest.mark.skipif(not torch.cuda.is_available(), reason="needs CUDA")
def test_set_seed_makes_cuda_accumulation_deterministic() -> None:
    # index_add_ on CUDA accumulates with atomics, so a float32 sum over many duplicate
    # indices varies between runs unless set_seed has switched on deterministic kernels.
    def accumulate() -> torch.Tensor:
        set_seed(123)
        src = torch.randn(1_000_000, 64, device="cuda")
        idx = torch.randint(0, 16, (1_000_000,), device="cuda")
        return torch.zeros(16, 64, device="cuda").index_add_(0, idx, src)

    try:
        first, second = accumulate(), accumulate()
        assert torch.are_deterministic_algorithms_enabled()
        assert torch.equal(first, second)
    finally:
        torch.use_deterministic_algorithms(False)


def test_set_seed_fixes_the_cublas_workspace_on_cuda(monkeypatch) -> None:
    # Deterministic mode makes cuBLAS raise on the first matmul without a fixed workspace.
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch, "use_deterministic_algorithms", lambda mode: None)
    monkeypatch.delenv("CUBLAS_WORKSPACE_CONFIG", raising=False)
    set_seed(0)
    assert task.os.environ["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":16:8")
    set_seed(0)
    assert task.os.environ["CUBLAS_WORKSPACE_CONFIG"] == ":16:8"


def test_partition_shuffle_follows_the_seed(monkeypatch) -> None:
    # IidPartitioner takes no seed, so without this every seed holds the same partitions.
    seen: list[int] = []

    class _StopError(Exception):
        pass

    class _FakeFDS:
        def __init__(self, *, seed: int, **kwargs: object) -> None:
            seen.append(seed)

        def load_partition(self, partition_id: int) -> None:
            raise _StopError

    monkeypatch.setattr(task, "FederatedDataset", _FakeFDS)
    monkeypatch.setattr(task, "_fds", {})
    for seed in (0, 3):
        with pytest.raises(_StopError):
            task.load_data(0, 4, MODEL, partitioner="iid", seed=seed)
    assert seen == [42, 45]


@pytest.fixture(scope="module")
def model():
    return get_model(MODEL, num_labels=2)


def test_model_exposes_lora_adapters(model) -> None:
    lora_params = [n for n, _ in model.named_parameters() if "lora" in n.lower()]
    assert lora_params, "expected PEFT LoRA adapter parameters on the model"


def test_adapter_state_excludes_frozen_backbone(model) -> None:
    state = get_adapter_state(model)
    assert state, "adapter state dict should be non-empty"
    # Adapter-only payload = LoRA tensors + the (newly initialised) classification
    # head; never the frozen BERT backbone (embeddings / encoder base weights).
    assert all(("lora" in k.lower() or "classifier" in k.lower()) for k in state), sorted(state)[:5]


def test_adapter_state_roundtrips(model) -> None:
    # The federation invariant: the keys a client returns (get after set) must match
    # the keys the server broadcast (a fresh get). set_peft_model_state_dict mutates
    # its argument in place, so pass it a fresh dict, not the one we compare against.
    sent = set(get_adapter_state(model))
    set_adapter_state(model, get_adapter_state(model))  # must not raise
    assert set(get_adapter_state(model)) == sent


def test_adapter_state_survives_arrayrecord_roundtrip(model) -> None:
    """The adapter-only federation path: ArrayRecord must preserve LoRA keys + values."""
    before = get_adapter_state(model)
    after = ArrayRecord(before).to_torch_state_dict()
    assert set(after) == set(before)
    for key in before:
        assert torch.equal(after[key], before[key]), key


def _rows(n: int) -> Dataset:
    return Dataset.from_dict(
        {"text": [f"review {i}" for i in range(n)], "label": [i % 2 for i in range(n)]}
    )


def _row_tokens(loader) -> list[int]:
    return [int(t) for batch in loader for t in batch["input_ids"][:, 2]]


def test_global_test_is_the_unpartitioned_test_split(monkeypatch) -> None:
    requested = []

    def fake_load_dataset(name, split):
        requested.append((name, split))
        return _rows(10)

    monkeypatch.setattr(task, "load_dataset", fake_load_dataset)
    loader = task.load_global_test(MODEL, dataset="some/dataset")
    assert requested == [("some/dataset", "test")]
    assert task.sample_count(loader) == 10


def test_global_test_sample_is_seeded_and_sized(monkeypatch) -> None:
    monkeypatch.setattr(task, "load_dataset", lambda name, split: _rows(50))
    a = task.load_global_test(MODEL, size=8)
    b = task.load_global_test(MODEL, size=8)
    assert task.sample_count(a) == 8
    # The same rows every round, in the same order: the number compares across rounds.
    assert _row_tokens(a) == _row_tokens(b)
    assert task.sample_count(task.load_global_test(MODEL, size=0)) == 50
    assert task.sample_count(task.load_global_test(MODEL, size=500)) == 50


def test_global_test_refuses_a_negative_size(monkeypatch) -> None:
    monkeypatch.setattr(task, "load_dataset", lambda name, split: _rows(5))
    with pytest.raises(ValueError, match=">= 0"):
        task.load_global_test(MODEL, size=-1)


def test_seeded_initial_adapters_are_the_same_every_run() -> None:
    # The server seeds before building the initial adapters, so round 0 replays.
    set_seed(0)
    first = get_adapter_state(get_model(MODEL))
    set_seed(0)
    second = get_adapter_state(get_model(MODEL))
    assert all(torch.equal(first[k], second[k]) for k in first)
