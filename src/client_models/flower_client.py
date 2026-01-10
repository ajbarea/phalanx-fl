from __future__ import annotations

import logging
from collections import OrderedDict
from pathlib import Path

import flwr as fl
import numpy as np
import torch
from flwr.common import NDArrays, Scalar

from src.attack_utils.attack_snapshots import save_attack_snapshot, save_visual_snapshot
from src.attack_utils.poisoning import apply_poisoning_attack, should_poison_this_round
from src.attack_utils.snapshot_image_viz import save_weight_attack_prediction_grid
from src.attack_utils.weight_poisoning import (
    WEIGHT_ATTACK_TYPES,
    apply_weight_poisoning,
)
from src.attack_utils.weight_snapshots import (
    compute_weight_diff_statistics,
    save_weight_snapshot,
)


class FlowerClient(fl.client.NumPyClient):  # type: ignore[name-defined]
    def __init__(
        self,
        client_id,
        net,
        trainloader,
        valloader,
        training_device,
        num_of_client_epochs,
        model_type="cnn",
        use_lora=False,
        num_malicious_clients=0,
        attacks_schedule=None,
        save_attack_snapshots=False,
        attack_snapshot_format="pickle_and_visual",
        snapshot_max_samples=5,
        output_dir=None,
        experiment_info=None,
        strategy_number=0,
        tokenizer=None,
        learning_rate=None,
    ):
        self.client_id = client_id
        self.net = net
        self.trainloader = trainloader
        self.valloader = valloader
        self.training_device = training_device
        self.model_type = model_type
        self.num_of_client_epochs = num_of_client_epochs
        self.use_lora = use_lora
        self.num_malicious_clients = num_malicious_clients
        self.attacks_schedule = attacks_schedule
        self.save_attack_snapshots = save_attack_snapshots
        self.attack_snapshot_format = attack_snapshot_format
        self.snapshot_max_samples = snapshot_max_samples
        self.output_dir = output_dir
        self.experiment_info = experiment_info
        self.strategy_number = strategy_number
        self.tokenizer = tokenizer
        self.learning_rate = learning_rate

    def _save_attack_snapshots(
        self,
        current_round,
        attack_configs,
        data_sample,
        labels_sample,
        original_data_sample=None,
        original_labels_sample=None,
    ):
        """Save attack snapshots for both CNN and transformer models.

        Note: Weight attacks (model_poisoning, gradient_scaling, byzantine_perturbation)
        are filtered out here - they get separate visualization via save_weight_snapshot()
        since they don't modify input data, only model weights.
        """
        if not (self.save_attack_snapshots and self.output_dir):
            return

        # Filter out weight attacks - they get separate visualization
        # since they don't change input data (only model weights)
        data_attack_configs = [
            cfg
            for cfg in (attack_configs if isinstance(attack_configs, list) else [attack_configs])
            if cfg.get("attack_type") not in WEIGHT_ATTACK_TYPES
        ]

        if not data_attack_configs:
            return  # No data attacks to visualize

        save_attack_snapshot(
            client_id=self.client_id,
            round_num=current_round,
            attack_config=data_attack_configs,
            data_sample=data_sample,
            labels_sample=labels_sample,
            original_labels_sample=original_labels_sample,
            output_dir=self.output_dir,
            max_samples=self.snapshot_max_samples,
            save_format=self.attack_snapshot_format,
            experiment_info=self.experiment_info,
            strategy_number=self.strategy_number,
        )

        if self.attack_snapshot_format in ["visual", "pickle_and_visual"]:
            if self.model_type == "cnn" and original_data_sample is not None:
                save_visual_snapshot(
                    client_id=self.client_id,
                    round_num=current_round,
                    attack_config=data_attack_configs,
                    data_sample=data_sample.cpu().numpy(),
                    labels_sample=labels_sample.cpu().numpy(),
                    original_labels_sample=original_labels_sample.cpu().numpy()
                    if original_labels_sample is not None
                    else labels_sample.cpu().numpy(),
                    output_dir=self.output_dir,
                    experiment_info=self.experiment_info,
                    strategy_number=self.strategy_number,
                    original_data_sample=original_data_sample.cpu().numpy(),
                )
            elif (
                self.model_type == "transformer"
                and original_data_sample is not None
                and self.tokenizer is not None
            ):
                save_visual_snapshot(
                    client_id=self.client_id,
                    round_num=current_round,
                    attack_config=data_attack_configs,
                    data_sample=data_sample.cpu().numpy(),
                    labels_sample=labels_sample.cpu().numpy(),
                    original_labels_sample=original_labels_sample.cpu().numpy()
                    if original_labels_sample is not None
                    else labels_sample.cpu().numpy(),
                    output_dir=self.output_dir,
                    experiment_info=self.experiment_info,
                    strategy_number=self.strategy_number,
                    tokenizer=self.tokenizer,
                    original_data_sample=original_data_sample.cpu().numpy(),
                )

    def set_parameters(self, net, parameters: list[np.ndarray]):
        if self.use_lora:
            from src.network_models.bert_model_definition import (
                get_peft_model_state_dict,
                set_peft_model_state_dict,
            )

            params_dict = zip(get_peft_model_state_dict(net).keys(), parameters, strict=False)
            state_dict = OrderedDict({k: torch.Tensor(v) for k, v in params_dict})
            set_peft_model_state_dict(net, state_dict)
        else:
            params_dict = zip(net.state_dict().keys(), parameters, strict=False)
            state_dict = OrderedDict({k: torch.Tensor(v) for k, v in params_dict})
            self.net.load_state_dict(state_dict, strict=False)

    def get_parameters(self, config):
        if self.use_lora:
            from src.network_models.bert_model_definition import get_peft_model_state_dict

            state_dict = get_peft_model_state_dict(self.net)
            return [val.cpu().numpy() for val in state_dict.values()]
        else:
            return [val.cpu().numpy() for _, val in self.net.state_dict().items()]

    def _get_sample_batch_for_viz(self, max_samples: int = 8):
        """Get a sample batch from trainloader for visualization.

        Args:
            max_samples: Maximum number of samples to return.

        Returns:
            Tuple of (images, labels) tensors.
        """
        for batch in self.trainloader:
            if self.model_type == "cnn":
                images, labels = batch
            else:
                images, labels = batch["input_ids"], batch["labels"]
            return images[:max_samples], labels[:max_samples]
        return None, None

    def _get_predictions(self, images: torch.Tensor, top_k: int = 5) -> tuple:
        """Run inference and return top-K predictions plus full probabilities.

        Args:
            images: Input images tensor.
            top_k: Number of top predictions to return per image.

        Returns:
            Tuple of (top_k_preds, full_probs) where:
            - top_k_preds: List of lists of (class_idx, confidence) tuples
            - full_probs: numpy array of shape (N, num_classes) with all probabilities
        """
        self.net.eval()
        with torch.no_grad():
            outputs = self.net(images.to(self.training_device))
            probs = torch.softmax(outputs, dim=1)
            # Get top-K predictions for each sample
            top_confs, top_preds = probs.topk(top_k, dim=1)
        self.net.train()

        results = []
        for i in range(len(images)):
            sample_preds = [(top_preds[i, k].item(), top_confs[i, k].item()) for k in range(top_k)]
            results.append(sample_preds)

        return results, probs.cpu().numpy()

    def train(
        self,
        net,
        trainloader,
        epochs: int,
        verbose=False,
        global_params=None,
        mu=0.01,
        config=None,
    ):
        """Train the network on the training set with optional dynamic poisoning."""
        current_round = config.get("server_round", 1) if config else 1

        if self.model_type == "cnn":
            criterion = torch.nn.CrossEntropyLoss()
            optimizer: torch.optim.Optimizer = torch.optim.Adam(
                net.parameters(), lr=self.learning_rate or 1e-3
            )
            net.train()

            if hasattr(net, "fc3"):
                num_classes = net.fc3.out_features
            elif hasattr(net, "fc"):
                num_classes = net.fc.out_features
            else:
                # Default fallback
                num_classes = 10

            # Initialize before loop to avoid possibly unbound errors
            epoch_loss: float = 0.0
            epoch_acc: float = 0.0

            for epoch in range(epochs):
                correct, total, epoch_loss = 0, 0, 0.0

                for batch_idx, (images, labels) in enumerate(trainloader):
                    should_poison, attack_configs = should_poison_this_round(
                        current_round, self.client_id, self.attacks_schedule
                    )

                    if should_poison and attack_configs:
                        original_images = images.clone()
                        original_labels = labels.clone()

                        for attack_config in attack_configs:
                            images, labels = apply_poisoning_attack(
                                images,
                                labels,
                                attack_config,
                                tokenizer=self.tokenizer,
                                num_classes=num_classes,
                            )

                        if epoch == 0 and batch_idx == 0:
                            self._save_attack_snapshots(
                                current_round=current_round,
                                attack_configs=attack_configs,
                                data_sample=images,
                                labels_sample=labels,
                                original_data_sample=original_images,
                                original_labels_sample=original_labels,
                            )

                    images, labels = (
                        images.to(self.training_device),
                        labels.to(self.training_device),
                    )
                    optimizer.zero_grad()
                    outputs = net(images)
                    loss = criterion(outputs, labels)
                    loss.backward()
                    optimizer.step()

                    epoch_loss += loss
                    total += labels.size(0)
                    correct += (torch.max(outputs.data, 1)[1] == labels).sum().item()
                    del outputs, loss

                epoch_loss /= len(trainloader.dataset) or 1
                epoch_acc = correct / total if total > 0 else 0.0
                if verbose:
                    logging.info(
                        f"Epoch {epoch + 1}: train loss {epoch_loss}, accuracy {epoch_acc}"
                    )

            return float(epoch_loss), float(epoch_acc)

        elif self.model_type == "transformer":
            optimizer = torch.optim.AdamW(net.parameters(), lr=self.learning_rate or 5e-5)
            net.train()

            # Initialize before loop to avoid possibly unbound errors
            epoch_loss = 0.0
            epoch_acc = 0.0

            for epoch in range(epochs):
                logging.debug(f"[Client {self.client_id}] Starting epoch {epoch + 1}/{epochs}")
                total_loss = 0
                correct, total = 0, 0

                for batch_idx, batch in enumerate(trainloader):
                    should_poison, attack_configs = should_poison_this_round(
                        current_round, self.client_id, self.attacks_schedule
                    )
                    if should_poison and attack_configs:
                        original_input_ids = batch["input_ids"].clone()
                        original_labels = batch["labels"].clone()

                        for attack_config in attack_configs:
                            if attack_config.get("attack_type") == "token_replacement":
                                batch["input_ids"], batch["labels"] = apply_poisoning_attack(
                                    batch["input_ids"],
                                    batch["labels"],
                                    attack_config,
                                    tokenizer=self.tokenizer,
                                )

                        if epoch == 0 and batch_idx == 0:
                            self._save_attack_snapshots(
                                current_round=current_round,
                                attack_configs=attack_configs,
                                data_sample=batch["input_ids"],
                                labels_sample=batch["labels"],
                                original_data_sample=original_input_ids,
                                original_labels_sample=original_labels,
                            )

                    batch = {k: v.to(self.training_device) for k, v in batch.items()}
                    labels = batch["labels"]

                    outputs = net(**batch)
                    loss = outputs.loss

                    if global_params is not None and self.client_id >= self.num_malicious_clients:
                        local_params = [
                            torch.tensor(p, device=self.training_device)
                            for p in self.get_parameters(config={})
                        ]
                        prox_term = sum(
                            torch.norm(lp - gp) ** 2
                            for lp, gp in zip(local_params, global_params, strict=False)
                        )
                        loss = loss + (mu / 2) * prox_term

                    loss.backward()

                    optimizer.step()
                    optimizer.zero_grad()
                    total_loss += loss.item()

                    if hasattr(outputs, "logits"):
                        preds = torch.argmax(outputs.logits, dim=-1)
                        mask = labels != -100
                        correct += (preds[mask] == labels[mask]).sum().item()
                        total += mask.sum().item()

                    if (batch_idx + 1) % 10 == 0:
                        logging.debug(
                            f"[Client {self.client_id}] Batch {batch_idx + 1}/{len(trainloader)} - Loss: {loss.item():.4f}"
                        )

                    del outputs, loss, batch

                epoch_loss = total_loss / len(trainloader)
                epoch_acc = correct / total if total > 0 else 0
                logging.debug(
                    f"[Client {self.client_id}] Epoch {epoch + 1} complete - Loss: {epoch_loss:.4f}, Accuracy: {epoch_acc:.4f}"
                )

                if verbose:
                    logging.info(
                        f"Epoch {epoch + 1}: train loss {epoch_loss}, accuracy {epoch_acc}"
                    )

            return float(epoch_loss), float(epoch_acc)

        else:
            raise ValueError(
                f"Unsupported model type: {self.model_type}. Supported types are 'cnn' and 'mlm'."
            )

    def test(self, net, testloader):
        """Evaluate the network on the entire test set."""

        if self.model_type == "cnn":
            criterion = torch.nn.CrossEntropyLoss()
            correct, total, loss = 0, 0, 0.0
            net.eval()

            with torch.no_grad():
                for images, labels in testloader:
                    images, labels = (
                        images.to(self.training_device),
                        labels.to(self.training_device),
                    )
                    outputs = net(images)
                    loss += criterion(outputs, labels).item()
                    _, predicted = torch.max(outputs.data, 1)
                    total += labels.size(0)
                    correct += (predicted == labels).sum().item()
            loss /= len(testloader.dataset) if len(testloader.dataset) > 0 else 1
            accuracy = correct / total if total > 0 else 0.0
            return loss, accuracy

        elif self.model_type == "transformer":
            net.eval()
            total_loss: float = 0.0
            correct, total = 0, 0

            with torch.no_grad():
                for batch in testloader:
                    batch = {k: v.to(self.training_device) for k, v in batch.items()}
                    labels = batch["labels"]

                    outputs = net(**batch)
                    loss = outputs.loss.item()
                    total_loss += loss

                    if hasattr(outputs, "logits"):
                        preds = torch.argmax(outputs.logits, dim=-1)
                        mask = labels != -100
                        correct += (preds[mask] == labels[mask]).sum().item()
                        total += mask.sum().item()

            loss = total_loss / len(testloader)
            accuracy = correct / total if total > 0 else 0
            return loss, accuracy

        else:
            raise ValueError(
                f"Unsupported model type: {self.model_type}. Supported types are 'cnn' and 'mlm'."
            )

    def fit(self, parameters, config):
        logging.debug(
            f"[Client {self.client_id}] Starting fit() - Setting parameters and beginning training"
        )
        self.set_parameters(self.net, parameters)

        global_params = None
        if (
            self.model_type == "transformer"
            and self.use_lora
            and self.client_id >= self.num_malicious_clients
        ):
            global_params = [
                torch.tensor(p, device=self.training_device) for p in self.get_parameters(config={})
            ]

        logging.debug(
            f"[Client {self.client_id}] Training for {self.num_of_client_epochs} epoch(s) with {len(self.trainloader)} batches"
        )
        epoch_loss, epoch_acc = self.train(
            self.net,
            self.trainloader,
            epochs=self.num_of_client_epochs,
            global_params=global_params,
            config=config,
        )
        logging.debug(
            f"[Client {self.client_id}] Training complete - Loss: {epoch_loss:.4f}, Accuracy: {epoch_acc:.4f}"
        )

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        trained_parameters = self.get_parameters(self.net)

        current_round = int(config.get("server_round", 1)) if config else 1
        should_poison, attack_configs = should_poison_this_round(
            current_round, self.client_id, self.attacks_schedule
        )

        weight_attack_configs = [
            cfg for cfg in attack_configs if cfg.get("attack_type") in WEIGHT_ATTACK_TYPES
        ]

        if should_poison and weight_attack_configs:
            logging.info(
                f"[Client {self.client_id}] WEIGHT POISONING at round {current_round}: "
                f"{[cfg.get('attack_type') for cfg in weight_attack_configs]}"
            )

            params_before = None
            sample_images = None
            preds_before = None
            probs_before = None

            sample_labels = None  # Initialize to avoid possibly unbound error
            if self.save_attack_snapshots and self.output_dir:
                params_before = [p.copy() for p in trained_parameters]

                # Get sample batch and predictions BEFORE poisoning (for visualization)
                if self.model_type == "cnn":
                    sample_images, sample_labels = self._get_sample_batch_for_viz(max_samples=4)
                    if sample_images is not None:
                        preds_before, probs_before = self._get_predictions(sample_images)

            poisoned_parameters = apply_weight_poisoning(trained_parameters, weight_attack_configs)

            if self.save_attack_snapshots and self.output_dir and params_before:
                preds_after = None
                probs_after = None
                if sample_images is not None and preds_before is not None:
                    # Temporarily load poisoned weights to get post-attack predictions
                    self.set_parameters(self.net, poisoned_parameters)
                    preds_after, probs_after = self._get_predictions(sample_images)

                for attack_cfg in weight_attack_configs:
                    attack_type = attack_cfg.get("attack_type")

                    save_weight_snapshot(
                        parameters_before=params_before,
                        parameters_after=poisoned_parameters,
                        attack_type=attack_type,
                        attack_config=attack_cfg,
                        client_id=self.client_id,
                        round_num=current_round,
                        output_dir=self.output_dir,
                        strategy_number=self.strategy_number,
                        experiment_info=self.experiment_info,
                    )

                    if (
                        sample_images is not None
                        and sample_labels is not None
                        and preds_before is not None
                        and preds_after is not None
                    ):
                        try:
                            weight_stats = compute_weight_diff_statistics(
                                params_before, poisoned_parameters
                            )
                            snapshot_dir = (
                                Path(self.output_dir)
                                / f"attack_snapshots_{self.strategy_number}"
                                / f"client_{self.client_id}"
                                / f"round_{current_round}"
                            )
                            snapshot_dir.mkdir(parents=True, exist_ok=True)

                            save_weight_attack_prediction_grid(
                                images=sample_images.cpu().numpy(),
                                labels=sample_labels.cpu().numpy(),
                                predictions_before=preds_before,
                                predictions_after=preds_after,
                                weight_stats=weight_stats,
                                filepath=snapshot_dir / f"{attack_type}_prediction_comparison.png",
                                attack_config=attack_cfg,
                                full_probs_before=probs_before,
                                full_probs_after=probs_after,
                            )
                            logging.debug(
                                f"Saved weight attack prediction comparison: "
                                f"client {self.client_id}, round {current_round}"
                            )
                        except Exception as e:
                            logging.warning(f"Failed to save weight attack prediction grid: {e}")

            return (
                poisoned_parameters,
                len(self.trainloader.dataset),
                {
                    "loss": epoch_loss,
                    "accuracy": epoch_acc,
                    "partition_id": self.client_id,
                },
            )

        return (
            trained_parameters,
            len(self.trainloader.dataset),
            {
                "loss": epoch_loss,
                "accuracy": epoch_acc,
                "partition_id": self.client_id,
            },
        )

    def evaluate(
        self, parameters: NDArrays, config: dict[str, Scalar]
    ) -> tuple[float, int, dict[str, Scalar]]:
        self.set_parameters(self.net, parameters)
        loss, accuracy = self.test(self.net, self.valloader)

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        metrics: dict[str, Scalar] = {
            "accuracy": float(accuracy),
            "partition_id": self.client_id,
        }
        return float(loss), len(self.valloader.dataset), metrics
