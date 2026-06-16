"""Model + adapter helpers in phalanx.task.

These download Google's tiny BERT (~18 MB) from the Hugging Face Hub.
"""

from __future__ import annotations

import pytest
import torch
from flwr.app import ArrayRecord

from phalanx.task import get_adapter_state, get_model, set_adapter_state

MODEL = "google/bert_uncased_L-2_H-128_A-2"


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
