from __future__ import annotations

import logging
from typing import Any, cast

from flwr_datasets.partitioner import DirichletPartitioner
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, DataCollatorForLanguageModeling, PreTrainedTokenizerBase

from datasets import Dataset as HFDataset  # type: ignore[attr-defined]
from datasets import DatasetDict, load_dataset  # type: ignore[attr-defined]


class HuggingFaceTextDatasetLoader:
    """
    Unified dataset loader for HuggingFace text datasets with MLM task support.

    Examples:
        Financial PhraseBank: hf_dataset_path="takala/financial_phrasebank",
                             hf_dataset_name="sentences_allagree",
                             tokenize_columns=["sentence"]
        LexGLUE LEDGAR: hf_dataset_path="coastalcph/lex_glue",
                       hf_dataset_name="ledgar",
                       tokenize_columns=["text"]
    """

    def __init__(
        self,
        hf_dataset_path: str,
        hf_dataset_name: str | None = None,
        tokenize_columns: list[Any] | None = None,
        remove_columns: list[Any] | None = None,
        dataset_dir: str | None = None,  # Not used, kept for compatibility
        num_of_clients: int = 5,
        training_subset_fraction: float = 0.8,
        model_name: str = "distilbert-base-uncased",
        batch_size: int = 16,
        chunk_size: int = 256,
        mlm_probability: float = 0.15,
        num_poisoned_clients: int = 0,
        attack_schedule: list[Any] | None = None,
        max_samples: int | None = None,  # Limit dataset size
    ):
        self.hf_dataset_path = hf_dataset_path
        self.hf_dataset_name = hf_dataset_name
        self.tokenize_columns = tokenize_columns or ["text"]
        self.remove_columns = remove_columns
        self.num_of_clients = num_of_clients
        self.training_subset_fraction = training_subset_fraction
        self.model_name = model_name
        self.batch_size = batch_size
        self.chunk_size = chunk_size
        self.mlm_probability = mlm_probability
        self.num_poisoned_clients = num_poisoned_clients
        self.attack_schedule = attack_schedule
        self.max_samples = max_samples
        self.tokenizer: PreTrainedTokenizerBase | None = None

    def _partition_iid(self, full_dataset: Any) -> list[Any]:
        """Partition dataset uniformly across clients (IID distribution)."""
        client_size = len(full_dataset) // self.num_of_clients
        client_partitions: list[Any] = []

        for client_id in range(self.num_of_clients):
            start_idx = client_id * client_size
            end_idx = (
                start_idx + client_size
                if client_id < self.num_of_clients - 1
                else len(full_dataset)
            )
            client_partitions.append(full_dataset.select(range(start_idx, end_idx)))

        return client_partitions

    def _partition_label_skew_dirichlet(self, full_dataset: Any, alpha: float = 0.5) -> list[Any]:
        """
        Partition dataset using Dirichlet distribution (Non-IID).

        Uses Flower's DirichletPartitioner based on the paper
        "Bayesian Nonparametric Federated Learning of Neural Networks"
        (https://arxiv.org/abs/1905.12022).

        Lower alpha = more heterogeneous (typical: 0.1-1.0).

        Args:
            full_dataset: HuggingFace Dataset with "label" column
            alpha: Dirichlet concentration parameter

        Returns:
            List of dataset partitions, one per client
        """
        partitioner = DirichletPartitioner(
            num_partitions=self.num_of_clients,
            partition_by="label",
            alpha=alpha,
            min_partition_size=1,
            self_balancing=True,
            seed=42,
        )

        # Assign dataset to partitioner
        partitioner.dataset = full_dataset

        # Load partitions for each client
        return [partitioner.load_partition(i) for i in range(self.num_of_clients)]

    def load_datasets(self):
        """Loads dataset from HuggingFace Hub and partitions into clients."""
        trainloaders = []
        valloaders = []

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        tokenizer = self.tokenizer
        assert tokenizer is not None, "Tokenizer failed to load"

        # Skip filesystem poisoning (dynamic poisoning handled in training)
        if self.attack_schedule:
            poisoned_client_ids = []
        else:
            poisoned_client_ids = list(range(self.num_poisoned_clients))

        if self.hf_dataset_name:
            dataset = cast(
                DatasetDict,
                load_dataset(self.hf_dataset_path, self.hf_dataset_name, trust_remote_code=True),
            )
        else:
            dataset = cast(DatasetDict, load_dataset(self.hf_dataset_path, trust_remote_code=True))

        full_dataset: HFDataset = dataset["train"]

        # Limit dataset size for memory optimization
        if self.max_samples is not None and len(full_dataset) > self.max_samples:
            original_size = len(full_dataset)
            full_dataset = full_dataset.shuffle(seed=42)
            full_dataset = full_dataset.select(range(self.max_samples))
            logging.info(
                f"Dataset optimization: Limited from {original_size:,} to {self.max_samples:,} samples "
                f"({(self.max_samples / original_size) * 100:.1f}%) for faster processing"
            )

        if self.remove_columns is None:
            self.remove_columns = [
                col
                for col in full_dataset.column_names
                if col not in ["input_ids", "attention_mask"]
            ]

        # Use Non-IID for labeled datasets, IID for unlabeled
        if "label" in full_dataset.column_names:
            client_partitions = self._partition_label_skew_dirichlet(full_dataset, alpha=0.5)
        else:
            # Only shuffle if not already shuffled above
            if self.max_samples is None or len(dataset["train"]) <= self.max_samples:
                full_dataset = full_dataset.shuffle(seed=42)
            client_partitions = self._partition_iid(full_dataset)

        for client_id in range(self.num_of_clients):
            client_dataset = client_partitions[client_id]

            def tokenize_function(examples):
                texts = [
                    " ".join(row)
                    for row in zip(*[examples[col] for col in self.tokenize_columns], strict=False)
                ]
                return tokenizer(texts, truncation=False)

            def chunk_function(examples: dict[str, Any]) -> dict[str, Any]:
                concatenated: dict[str, Any] = {k: sum(examples[k], []) for k in examples}
                total_len = len(concatenated["input_ids"])
                total_len = (total_len // self.chunk_size) * self.chunk_size

                result = {
                    k: [t[i : i + self.chunk_size] for i in range(0, total_len, self.chunk_size)]
                    for k, t in concatenated.items()
                }
                result["labels"] = result["input_ids"].copy()
                return result

            client_dataset = client_dataset.map(tokenize_function, batched=True)
            columns_to_remove = [
                col for col in self.remove_columns if col in client_dataset.column_names
            ]
            if columns_to_remove:
                client_dataset = client_dataset.remove_columns(columns_to_remove)
            client_dataset = client_dataset.map(chunk_function, batched=True)
            split_dataset = client_dataset.train_test_split(
                test_size=(1 - self.training_subset_fraction), seed=42
            )

            collate_fn = DataCollatorForLanguageModeling(
                tokenizer=tokenizer,
                mlm=True,
                mlm_probability=0.75 if client_id in poisoned_client_ids else self.mlm_probability,
                mask_replace_prob=0 if client_id in poisoned_client_ids else 0.8,
                random_replace_prob=1 if client_id in poisoned_client_ids else 0.1,
            )

            trainloader = DataLoader(
                split_dataset["train"],  # pyright: ignore[reportArgumentType]
                batch_size=self.batch_size,
                shuffle=True,
                collate_fn=collate_fn,
                num_workers=0,
                pin_memory=False,
            )
            valloader = DataLoader(
                split_dataset["test"],  # pyright: ignore[reportArgumentType]
                batch_size=self.batch_size,
                shuffle=False,
                collate_fn=collate_fn,
                num_workers=0,
                pin_memory=False,
            )

            trainloaders.append(trainloader)
            valloaders.append(valloader)

        return trainloaders, valloaders
