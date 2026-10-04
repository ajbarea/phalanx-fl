"""phalanx-fl: model (HF transformer + LoRA), data (flwr-datasets non-IID), train/eval.

Anchored on Flower's quickstart-huggingface example (flwr 1.36 app-model), adapted to:
  - LoRA adapters via PEFT (only the adapters are federated — tiny, privacy-preserving);
  - non-IID partitioning via flwr-datasets' DirichletPartitioner (IID available as a fallback);
  - an optional label-flip data-poisoning attack;
  - a global test set, the dataset's own ``test`` split, which the partitioner never sees,
    scored for accuracy and the flip's attack success rate.
"""

from __future__ import annotations

import os
import random
from collections.abc import Sequence
from typing import Any

import numpy as np
import torch
from datasets import Dataset, load_dataset
from datasets.utils.logging import disable_progress_bar
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


def set_seed(entropy: int | Sequence[int]) -> None:
    """Seed Python / NumPy / torch RNGs from ``entropy`` so training is reproducible.

    ``entropy`` goes through numpy's ``SeedSequence``, which hashes it into a 128-bit pool.
    Clients pass ``[round, partition, seed]``, the varying ids first as numpy recommends,
    so every (round, partition, seed) gets its own stream; a sum of scaled ids repeats
    once an id outgrows its scale.

    On CUDA, nondeterministic kernels are disabled too, strictly: an op with no
    deterministic kernel raises, failing that client, rather than warning and letting the
    replay drift unnoticed. The mode is process-wide and also slows some kernels.
    """
    sequence = np.random.SeedSequence(entropy)
    words = sequence.generate_state(4)  # 128 bits as uint32
    random.seed(int.from_bytes(words.tobytes(), "little"))
    np.random.seed(words)
    torch.manual_seed(int(sequence.generate_state(1, dtype=np.uint64)[0]))
    if torch.cuda.is_available():
        # cuBLAS has deterministic kernels only with a fixed workspace, read when its first
        # handle is created; without it the first matmul raises. A value already set wins.
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        torch.use_deterministic_algorithms(True)


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
            seed=42 + seed,  # the pre-partition shuffle: IID partitions vary by seed too
        )
    partition = _fds[key].load_partition(partition_id)
    split = partition.train_test_split(test_size=0.2, seed=42 + seed)
    train = split["train"]
    if flip is not None:
        train = train.map(lambda b: {"label": flip_labels(b["label"], flip)}, batched=True)
    return (
        _loader(train, model_name, text_column=text_column, shuffle=True),
        _loader(split["test"], model_name, text_column=text_column, shuffle=False),
    )


def load_global_test(
    model_name: str,
    *,
    dataset: str = "stanfordnlp/imdb",
    text_column: str = "text",
    size: int = 0,
    seed: int = 42,
) -> DataLoader[Any]:
    """The dataset's ``test`` split, shared by every round and untouched by the partitioner.

    Client holdouts inherit their partition's label skew; this split does not, so its
    accuracy compares across partitioners and alphas. ``size`` > 0 takes a seeded sample
    of that many rows, the same rows every round; 0 keeps the whole split.
    """
    if size < 0:
        raise ValueError(f"global-eval-size must be >= 0, got {size}")
    split: Any = load_dataset(dataset, split="test")
    if 0 < size < len(split):
        split = split.shuffle(seed=seed).select(range(size))
    return _loader(split, model_name, text_column=text_column, shuffle=False)


def _loader(
    split: Dataset, model_name: str, *, text_column: str = "text", shuffle: bool
) -> DataLoader[Any]:
    """Tokenize ``text_column`` of a text/label split into a padded DataLoader."""
    tokenizer: Any = AutoTokenizer.from_pretrained(model_name, model_max_length=512)

    def tokenize(examples: dict[str, Any]) -> Any:
        return tokenizer(examples[text_column], truncation=True, add_special_tokens=True)

    keep = {text_column, "label"}
    split = split.remove_columns([c for c in split.column_names if c not in keep])
    tokenized = split.map(tokenize, batched=True)
    tokenized = tokenized.remove_columns(text_column).rename_column("label", "labels")
    collator = DataCollatorWithPadding(tokenizer=tokenizer)
    return DataLoader(tokenized, shuffle=shuffle, batch_size=32, collate_fn=collator)


def sample_count(loader: Any) -> int:
    """Rows behind a loader, which is what FedAvg must weight by.

    ``len(loader)`` counts batches, not rows: 33 rows and 64 rows both report 2 at
    ``batch_size=32``. FedAvg takes ``weighted_by_key="num-examples"``, so a batch count
    here quantises the adapter aggregate toward the smallest partitions.
    """
    return len(loader.dataset)


def default_device() -> torch.device:
    return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


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


def _accuracy(predictions: torch.Tensor, references: torch.Tensor) -> float:
    return float((predictions == references).float().mean())


def test_fn(model: Any, testloader: DataLoader[Any], device: torch.device) -> tuple[float, float]:
    """Local evaluation; returns (mean loss, accuracy)."""
    loss, predictions, references = _predict(model, testloader, device)
    return loss, _accuracy(predictions, references)


def global_eval_fn(
    model: Any, loader: DataLoader[Any], device: torch.device, flip: Flip
) -> dict[str, float]:
    """Global-test loss, accuracy and the attack success rate of ``flip``."""
    loss, predictions, references = _predict(model, loader, device)
    return {
        "loss": loss,
        "accuracy": _accuracy(predictions, references),
        "attack_success_rate": attack_success_rate(predictions, references, flip),
    }
