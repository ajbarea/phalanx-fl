"""phalanx-fl: model (HF transformer + LoRA), data (flwr-datasets non-IID), train/eval.

Anchored on Flower's quickstart-huggingface example (flwr 1.36 app-model), adapted to:
  - LoRA adapters via PEFT (only the adapters are federated — tiny, privacy-preserving);
  - non-IID partitioning via flwr-datasets' DirichletPartitioner (IID available as a fallback);
  - an optional label-flip data-poisoning attack and a clean held-out test split scored
    for accuracy plus attack success rate.
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np
import torch
from datasets import load_dataset
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

# Cache the FederatedDataset per partitioning so each simulated client doesn't
# re-download/re-partition.
_fds: dict[tuple[str, str, int, float, int], FederatedDataset] = {}

# A label flip: every training example labelled ``source`` is relabelled ``target``.
Flip = tuple[int, int]


def set_seed(seed: int) -> None:
    """Seed Python / NumPy / torch RNGs so a client's local training is reproducible.

    Clients seed per-partition (see client_app) so each is deterministic yet distinct;
    combined with the partitioner/split seeds, a whole run replays. CPU-only here, so
    no CUDA-determinism caveats apply.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _make_partitioner(name: str, num_partitions: int, alpha: float, seed: int) -> Partitioner:
    """IID baseline or a Dirichlet non-IID partitioner (lower alpha = more label skew)."""
    if name == "dirichlet":
        return DirichletPartitioner(
            num_partitions=num_partitions,
            partition_by="label",
            alpha=alpha,
            seed=42 + seed,
        )
    return IidPartitioner(num_partitions=num_partitions)


def flip_labels(labels: list[int], flip: Flip) -> list[int]:
    """Relabel every ``source`` label as ``target``; other labels pass through."""
    source, target = flip
    return [target if label == source else label for label in labels]


def _tokenized_loader(
    split: Any, model_name: str, text_column: str, *, shuffle: bool
) -> DataLoader[Any]:
    """Tokenize ``text_column`` and batch with dynamic padding."""
    tokenizer: Any = AutoTokenizer.from_pretrained(model_name, model_max_length=512)

    def tokenize(examples: dict[str, Any]) -> Any:
        return tokenizer(examples[text_column], truncation=True, add_special_tokens=True)

    keep = {text_column, "label"}
    split = split.remove_columns([c for c in split.column_names if c not in keep])
    split = split.map(tokenize, batched=True)
    split = split.remove_columns(text_column).rename_column("label", "labels")
    collator = DataCollatorWithPadding(tokenizer=tokenizer)
    return DataLoader(split, shuffle=shuffle, batch_size=32, collate_fn=collator)


def load_data(
    partition_id: int,
    num_partitions: int,
    model_name: str,
    *,
    dataset: str = "stanfordnlp/imdb",
    text_column: str = "text",
    partitioner: str = "dirichlet",
    alpha: float = 0.5,
    seed: int = 0,
    flip: Flip | None = None,
) -> tuple[DataLoader[Any], DataLoader[Any]]:
    """Load and tokenize this client's partition; return (train, test) DataLoaders.

    ``flip`` poisons this client's training labels only; its local test split stays
    clean so the reported local accuracy is still meaningful.
    """
    key = (dataset, partitioner, num_partitions, alpha, seed)
    if key not in _fds:
        _fds[key] = FederatedDataset(
            dataset=dataset,
            partitioners={"train": _make_partitioner(partitioner, num_partitions, alpha, seed)},
        )
    partition = _fds[key].load_partition(partition_id)
    split = partition.train_test_split(test_size=0.2, seed=42 + seed)
    train = split["train"]
    if flip is not None:
        train = train.map(lambda b: {"label": flip_labels(b["label"], flip)}, batched=True)
    return (
        _tokenized_loader(train, model_name, text_column, shuffle=True),
        _tokenized_loader(split["test"], model_name, text_column, shuffle=False),
    )


def load_heldout(
    model_name: str, *, dataset: str, split: str, text_column: str = "text"
) -> DataLoader[Any]:
    """A clean split no client trains on, for server-side (centralized) evaluation."""
    heldout = load_dataset(dataset, split=split)
    return _tokenized_loader(heldout, model_name, text_column, shuffle=False)


def get_model(model_name: str, num_labels: int = 2, target_modules: str = "") -> Any:
    """A HF sequence-classification model wrapped with a LoRA adapter (PEFT).

    ``target_modules`` is a comma-separated list of layer names to adapt (e.g.
    ``"q_lin,v_lin"`` for DistilBERT); empty uses PEFT's per-architecture default.
    """
    base = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=num_labels)
    lora = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=8,
        lora_alpha=16,
        lora_dropout=0.1,
        bias="none",
        target_modules=target_modules.replace(" ", "").split(",") if target_modules else None,
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


def train_fn(
    model: Any, trainloader: DataLoader[Any], epochs: int, device: torch.device, lr: float = 5e-5
) -> float:
    """Local training; returns mean batch loss."""
    optimizer = AdamW(model.parameters(), lr=lr)
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


def _predict(
    model: Any, loader: DataLoader[Any], device: torch.device
) -> tuple[float, torch.Tensor, torch.Tensor]:
    """Mean batch loss plus all (predictions, references) over ``loader``."""
    model.eval()
    loss, steps = 0.0, 0
    predictions, references = [], []
    for batch in loader:
        batch = {k: v.to(device) for k, v in batch.items()}
        with torch.no_grad():
            outputs = model(**batch)
        loss += float(outputs.loss.item())
        steps += 1
        predictions.append(torch.argmax(outputs.logits, dim=-1).cpu())
        references.append(batch["labels"].cpu())
    return loss / max(steps, 1), torch.cat(predictions), torch.cat(references)


def attack_success_rate(predictions: torch.Tensor, references: torch.Tensor, flip: Flip) -> float:
    """Share of true-``source`` examples predicted as ``target``; NaN if none exist."""
    source, target = flip
    mask = references == source
    if not bool(mask.any()):
        return float("nan")
    return float((predictions[mask] == target).float().mean())


def test_fn(model: Any, testloader: DataLoader[Any], device: torch.device) -> tuple[float, float]:
    """Local evaluation; returns (mean loss, accuracy)."""
    metric: Any = load_metric("accuracy")
    loss, predictions, references = _predict(model, testloader, device)
    metric.add_batch(predictions=predictions, references=references)
    return loss, float(metric.compute()["accuracy"])


def heldout_fn(
    model: Any, loader: DataLoader[Any], device: torch.device, flip: Flip
) -> dict[str, float]:
    """Held-out loss, accuracy and attack success rate for ``flip``."""
    loss, predictions, references = _predict(model, loader, device)
    return {
        "loss": loss,
        "accuracy": float((predictions == references).float().mean()),
        "attack_success_rate": attack_success_rate(predictions, references, flip),
    }
