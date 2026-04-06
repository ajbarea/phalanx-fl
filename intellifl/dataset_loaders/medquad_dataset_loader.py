from __future__ import annotations

import glob
import os
from typing import Any

from torch.utils.data import DataLoader
from transformers import AutoTokenizer, DataCollatorForLanguageModeling, PreTrainedTokenizerBase

from datasets import load_dataset  # type: ignore[attr-defined]


class MedQuADDatasetLoader:
    def __init__(
        self,
        dataset_dir: str,
        num_of_clients: int,
        training_subset_fraction: float,
        model_name: str,
        batch_size: int = 16,
        chunk_size: int = 256,
        mlm_probability: float = 0.15,
        num_poisoned_clients: int = 0,
        attack_schedule: list[Any] | None = None,
        tokenize_columns: list[str] | None = None,
        remove_columns: list[str] | None = None,
    ) -> None:
        self.dataset_dir = dataset_dir
        self.num_of_clients = num_of_clients
        self.training_subset_fraction = training_subset_fraction
        self.model_name = model_name
        self.batch_size = batch_size
        self.chunk_size = chunk_size
        self.mlm_probability = mlm_probability
        self.num_poisoned_clients = num_poisoned_clients
        self.attack_schedule = attack_schedule
        self.tokenize_columns = tokenize_columns or ["answer"]
        self.remove_columns = remove_columns or ["answer", "token_type_ids", "question"]
        self.tokenizer: PreTrainedTokenizerBase | None = None

    def load_datasets(self):
        """Load and tokenize dataset for masked language modeling."""
        trainloaders = []
        valloaders = []

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        tokenizer = self.tokenizer
        assert tokenizer is not None, "Tokenizer failed to load"

        # Skip filesystem poisoning if attack_schedule is configured
        # (dynamic poisoning will be applied in-memory during training)
        if self.attack_schedule:
            poisoned_client_ids = []
        else:
            poisoned_client_ids = list(range(self.num_poisoned_clients))

        client_folders = [d for d in os.listdir(self.dataset_dir) if d.startswith("client_")]
        for client_folder in sorted(client_folders, key=lambda string: int(string.split("_")[1])):
            json_files = glob.glob(os.path.join(self.dataset_dir, client_folder, "*.json"))

            client_dataset = load_dataset("json", data_files=json_files)

            # Large max_length avoids truncation warnings; chunking handles splitting
            def tokenize_function(examples):
                texts = [
                    " ".join(row)
                    for row in zip(*[examples[col] for col in self.tokenize_columns], strict=False)
                ]
                return tokenizer(texts, truncation=True, max_length=100000)

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
                col for col in self.remove_columns if col in client_dataset["train"].column_names
            ]
            if columns_to_remove:
                client_dataset = client_dataset.remove_columns(columns_to_remove)
            client_dataset = client_dataset.map(chunk_function, batched=True)
            dataset = client_dataset["train"].train_test_split(
                test_size=(1 - self.training_subset_fraction)
            )

            client_folder_num = int(client_folder.split("_")[1])

            # Poisoned clients get higher masking with random token replacement
            collate_fn = DataCollatorForLanguageModeling(
                tokenizer=tokenizer,
                mlm=True,
                mlm_probability=0.75
                if client_folder_num in poisoned_client_ids
                else self.mlm_probability,
                mask_replace_prob=0 if client_folder_num in poisoned_client_ids else 0.8,
                random_replace_prob=1 if client_folder_num in poisoned_client_ids else 0.1,
            )

            trainloader = DataLoader(
                dataset["train"],  # pyright: ignore[reportArgumentType]
                batch_size=self.batch_size,
                shuffle=True,
                collate_fn=collate_fn,
                num_workers=0,
                pin_memory=False,
            )
            valloader = DataLoader(
                dataset["test"],  # pyright: ignore[reportArgumentType]
                batch_size=self.batch_size,
                shuffle=False,
                collate_fn=collate_fn,
                num_workers=0,
                pin_memory=False,
            )

            trainloaders.append(trainloader)
            valloaders.append(valloader)

        return trainloaders, valloaders
