"""phalanx-fl: model (HF transformer + LoRA), data (flwr-datasets non-IID), train/eval.

Anchored on Flower's quickstart-huggingface example (flwr 1.31 app-model), adapted to:
  - LoRA adapters via PEFT (only the adapters are federated — tiny, privacy-preserving);
  - non-IID partitioning via flwr-datasets' DirichletPartitioner (IID available as a fallback).
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np
import torch
from datasets.utils.logging import disable_progress_bar
from evaluate import load as load_metric
from flwr_datasets import FederatedDataset
from flwr_datasets.partitioner import DirichletPartitioner, IidPartitioner, Partitioner
from peft import LoraConfig, TaskType, get_peft_model
from peft.utils import get_peft_model_state_dict, set_peft_model_state_dict
from torch.optim import AdamW
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
)

disable_progress_bar()

# Cache the FederatedDataset so each simulated client doesn't re-download/re-partition.
_fds: FederatedDataset | None = None


def set_seed(seed: int) -> None:
    """Seed Python / NumPy / torch RNGs so a client's local training is reproducible.

    Clients seed per-partition (see client_app) so each is deterministic yet distinct;
    combined with the partitioner/split seeds, a whole run replays. CPU-only here, so
    no CUDA-determinism caveats apply.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _make_partitioner(name: str, num_partitions: int, alpha: float) -> Partitioner:
    """IID baseline or a Dirichlet non-IID partitioner (lower alpha = more label skew)."""
    if name == "dirichlet":
        return DirichletPartitioner(
            num_partitions=num_partitions,
            partition_by="label",
            alpha=alpha,
            seed=42,
        )
    return IidPartitioner(num_partitions=num_partitions)


def load_data(
    partition_id: int,
    num_partitions: int,
    model_name: str,
    *,
    dataset: str = "stanfordnlp/imdb",
    partitioner: str = "dirichlet",
    alpha: float = 0.5,
) -> tuple[DataLoader[Any], DataLoader[Any]]:
    """Load and tokenize this client's partition; return (train, test) DataLoaders."""
    global _fds
    if _fds is None:
        _fds = FederatedDataset(
            dataset=dataset,
            partitioners={"train": _make_partitioner(partitioner, num_partitions, alpha)},
        )
    partition = _fds.load_partition(partition_id)
    split = partition.train_test_split(test_size=0.2, seed=42)

    tokenizer: Any = AutoTokenizer.from_pretrained(model_name, model_max_length=512)

    def tokenize(examples: dict[str, Any]) -> Any:
        return tokenizer(examples["text"], truncation=True, add_special_tokens=True)

    split = split.map(tokenize, batched=True)
    split = split.remove_columns("text").rename_column("label", "labels")

    collator = DataCollatorWithPadding(tokenizer=tokenizer)
    trainloader = DataLoader(split["train"], shuffle=True, batch_size=32, collate_fn=collator)
    testloader = DataLoader(split["test"], batch_size=32, collate_fn=collator)
    return trainloader, testloader


def get_model(model_name: str, num_labels: int = 2) -> Any:
    """A HF sequence-classification model wrapped with a LoRA adapter (PEFT)."""
    base = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=num_labels)
    lora = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=8,
        lora_alpha=16,
        lora_dropout=0.1,
        bias="none",
    )
    return get_peft_model(base, lora)


def get_adapter_state(model: Any) -> dict[str, torch.Tensor]:
    """Trainable tensors that get federated: LoRA adapters + the task head.

    PEFT adds the (randomly initialised) sequence-classification head to
    ``modules_to_save``, so it is trained and aggregated alongside the LoRA adapters
    while the BERT backbone stays frozen — a small payload, not the full model.
    """
    return get_peft_model_state_dict(model)


def set_adapter_state(model: Any, state: dict[str, torch.Tensor]) -> None:
    """Load aggregated adapter + head tensors back into the model (mutates ``state``)."""
    set_peft_model_state_dict(model, state)


def train_fn(model: Any, trainloader: DataLoader[Any], epochs: int, device: torch.device) -> float:
    """Local training; returns mean batch loss."""
    optimizer = AdamW(model.parameters(), lr=5e-5)
    model.train()
    total, steps = 0.0, 0
    for _ in range(epochs):
        for batch in trainloader:
            batch = {k: v.to(device) for k, v in batch.items()}
            outputs = model(**batch)
            outputs.loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            total += float(outputs.loss.item())
            steps += 1
    return total / max(steps, 1)


def test_fn(model: Any, testloader: DataLoader[Any], device: torch.device) -> tuple[float, float]:
    """Local evaluation; returns (mean loss, accuracy)."""
    metric: Any = load_metric("accuracy")
    model.eval()
    loss, steps = 0.0, 0
    for batch in testloader:
        batch = {k: v.to(device) for k, v in batch.items()}
        with torch.no_grad():
            outputs = model(**batch)
        loss += float(outputs.loss.item())
        steps += 1
        predictions = torch.argmax(outputs.logits, dim=-1)
        metric.add_batch(predictions=predictions, references=batch["labels"])
    accuracy = float(metric.compute()["accuracy"])
    return loss / max(steps, 1), accuracy
