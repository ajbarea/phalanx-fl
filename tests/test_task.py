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


@pytest.mark.skipif(not torch.cuda.is_available(), reason="needs CUDA")
def test_set_seed_makes_cuda_training_deterministic() -> None:
    def grads() -> list[torch.Tensor]:
        set_seed(123)
        emb = torch.nn.Embedding(1000, 128).cuda()
        head = torch.nn.Linear(128, 2).cuda()
        idx = torch.randint(0, 1000, (64, 32), device="cuda")
        head(emb(idx)).mean().backward()
        assert emb.weight.grad is not None and head.weight.grad is not None
        return [emb.weight.grad, head.weight.grad]

    first, second = grads(), grads()
    assert torch.are_deterministic_algorithms_enabled()
    assert all(torch.equal(a, b) for a, b in zip(first, second, strict=True))


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
