from __future__ import annotations

import gc
import logging
from collections import OrderedDict
from pathlib import Path

import flwr as fl
import numpy as np
import torch
from flwr.common import NDArrays, Scalar

from intellifl.attack_utils.attack_snapshots import save_attack_snapshot, save_visual_snapshot
from intellifl.attack_utils.poisoning import apply_poisoning_attack, should_poison_this_round
from intellifl.attack_utils.snapshot_image_viz import save_weight_attack_prediction_grid
from intellifl.attack_utils.weight_poisoning import (
    WEIGHT_ATTACK_TYPES,
    apply_weight_poisoning,
    is_weight_attack,
)
from intellifl.attack_utils.weight_snapshots import (
    compute_weight_diff_statistics,
    save_weight_snapshot,
)


class FlowerClient(fl.client.NumPyClient):  # type: ignore[name-defined]
    """Flower client supporting CNN and transformer models with attack simulation."""

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
        snapshot_max_samples=6,
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

    @staticmethod
    def _compute_changed_sample_mask(
        data_sample: torch.Tensor | None,
        labels_sample: torch.Tensor,
        original_data_sample: torch.Tensor | None = None,
        original_labels_sample: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Compute per-sample change mask from labels and/or data deltas."""
        batch_size = int(labels_sample.shape[0])
        changed_mask = torch.zeros(batch_size, dtype=torch.bool)

        if (
            original_labels_sample is not None
            and labels_sample.shape == original_labels_sample.shape
            and int(original_labels_sample.shape[0]) == batch_size
        ):
            label_diff = labels_sample != original_labels_sample
            if label_diff.ndim > 1:
                label_diff = label_diff.reshape(batch_size, -1).any(dim=1)
            changed_mask |= label_diff.detach().cpu()

        if (
            data_sample is not None
            and original_data_sample is not None
            and data_sample.shape == original_data_sample.shape
            and int(data_sample.shape[0]) == batch_size
        ):
            if torch.is_floating_point(data_sample) or torch.is_floating_point(
                original_data_sample
            ):
                data_diff = (data_sample - original_data_sample).abs() > 1e-6
            else:
                data_diff = data_sample != original_data_sample

            if data_diff.ndim > 1:
                data_diff = data_diff.reshape(batch_size, -1).any(dim=1)
            changed_mask |= data_diff.detach().cpu()

        return changed_mask

    @staticmethod
    def _select_snapshot_indices(
        changed_mask: torch.Tensor,
        batch_size: int,
        max_samples: int,
    ) -> torch.Tensor:
        """Prioritize changed samples, then fill remaining slots with unchanged ones."""
        if batch_size <= 0:
            return torch.empty(0, dtype=torch.long)

        if max_samples <= 0 or batch_size <= max_samples:
            return torch.arange(batch_size, dtype=torch.long)

        mask = (
            changed_mask.detach().cpu()
            if changed_mask.numel()
            else torch.zeros(batch_size, dtype=torch.bool)
        )
        changed_indices = torch.nonzero(mask, as_tuple=False).flatten()
        unchanged_indices = torch.nonzero(~mask, as_tuple=False).flatten()
        ordered_indices = torch.cat((changed_indices, unchanged_indices), dim=0)

        if ordered_indices.numel() == 0:
            ordered_indices = torch.arange(batch_size, dtype=torch.long)

        return ordered_indices[:max_samples]

    def _save_attack_snapshots(
        self,
        current_round,
        attack_configs,
        data_sample,
        labels_sample,
        original_data_sample=None,
        original_labels_sample=None,
    ):
        """Save attack snapshots for CNN and transformer models."""
        if not (self.save_attack_snapshots and self.output_dir):
            return False

        # Weight attacks get separate visualization via save_weight_snapshot()
        data_attack_configs = [
            cfg
            for cfg in (attack_configs if isinstance(attack_configs, list) else [attack_configs])
            if cfg.get("attack_type") not in WEIGHT_ATTACK_TYPES
        ]

        if not data_attack_configs:
            return False

        changed_mask = self._compute_changed_sample_mask(
            data_sample=data_sample,
            labels_sample=labels_sample,
            original_data_sample=original_data_sample,
            original_labels_sample=original_labels_sample,
        )
        selected_indices = self._select_snapshot_indices(
            changed_mask=changed_mask,
            batch_size=int(labels_sample.shape[0]),
            max_samples=self.snapshot_max_samples,
        )
        if selected_indices.numel() == 0:
            return False

        data_sample = data_sample.index_select(0, selected_indices)
        labels_sample = labels_sample.index_select(0, selected_indices)
        if original_data_sample is not None:
            original_data_sample = original_data_sample.index_select(0, selected_indices)
        if original_labels_sample is not None:
            original_labels_sample = original_labels_sample.index_select(0, selected_indices)

        save_attack_snapshot(
            client_id=self.client_id,
            round_num=current_round,
            attack_config=data_attack_configs,
            data_sample=data_sample,
            labels_sample=labels_sample,
            original_labels_sample=original_labels_sample,
            output_dir=self.output_dir,
            max_samples=int(data_sample.shape[0]),
            save_format=self.attack_snapshot_format,
            experiment_info=self.experiment_info,
            strategy_number=self.strategy_number,
        )

        wants_visual = self.attack_snapshot_format in ["visual", "pickle_and_visual"]
        can_visualize = original_data_sample is not None and (
            self.model_type == "cnn"
            or (self.model_type == "transformer" and self.tokenizer is not None)
        )
        if wants_visual and can_visualize:
            assert original_data_sample is not None
            kwargs = {}
            if self.model_type == "transformer":
                kwargs["tokenizer"] = self.tokenizer
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
                **kwargs,
            )

        return bool(changed_mask.any().item())

    @staticmethod
    def _get_num_classes(net) -> int:
        """Infer the number of output classes from the network's final layer."""
        if hasattr(net, "fc3"):
            return net.fc3.out_features
        if hasattr(net, "fc"):
            return net.fc.out_features
        return 10

    def _to_device_only_tensors(self, batch: dict) -> dict:
        """Move only tensor values to device, leaving non-tensors as-is.

        This handles batches that may contain non-tensor metadata fields
        (strings, lists, etc.) that would cause errors with .to(device).
        """
        return {
            k: v.to(self.training_device) if torch.is_tensor(v) else v for k, v in batch.items()
        }

    def set_parameters(self, net, parameters: list[np.ndarray]) -> None:
        """Load parameters into the model, handling LoRA adapters if enabled."""
        if self.use_lora:
            from intellifl.network_models.transformer_models import (
                get_peft_model_state_dict,
                set_peft_model_state_dict,
            )

            params_dict = zip(get_peft_model_state_dict(net).keys(), parameters, strict=False)
            state_dict = OrderedDict({k: torch.Tensor(v) for k, v in params_dict})
            set_peft_model_state_dict(net, state_dict)
        else:
            params_dict = zip(net.state_dict().keys(), parameters, strict=False)
            state_dict = OrderedDict({k: torch.Tensor(v) for k, v in params_dict})
            net.load_state_dict(state_dict, strict=False)

    def get_parameters(self, config) -> list[np.ndarray]:
        """Extract model parameters as numpy arrays."""
        if self.use_lora:
            from intellifl.network_models.transformer_models import get_peft_model_state_dict

            state_dict = get_peft_model_state_dict(self.net)
            return [val.cpu().numpy() for val in state_dict.values()]
        else:
            return [val.cpu().numpy() for _, val in self.net.state_dict().items()]

    def _get_sample_batch_for_viz(self, max_samples: int = 8):
        """Get a sample batch from trainloader for visualization."""
        for batch in self.trainloader:
            if self.model_type == "cnn":
                images, labels = batch
            else:
                images, labels = batch["input_ids"], batch["labels"]
            return images[:max_samples], labels[:max_samples]
        return None, None

    def _get_predictions(self, images: torch.Tensor, top_k: int = 5) -> tuple:
        """Run inference and return top-K predictions plus full probabilities."""
        self.net.eval()
        with torch.inference_mode():
            outputs = self.net(images.to(self.training_device))
            probs = torch.softmax(outputs, dim=1)
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
        global_params=None,
        mu=0.01,
        config=None,
    ) -> tuple[float, float]:
        """Train the network with optional dynamic poisoning.

        Args:
            net: Neural network model to train.
            trainloader: DataLoader for training data.
            epochs: Number of training epochs.
            global_params: Global parameters for FedProx proximal term.
            mu: FedProx proximal term coefficient.
            config: Flower config dict containing server_round.

        Returns:
            Tuple of (final_loss, final_accuracy).
        """
        current_round = config.get("server_round", 1) if config else 1

        if self.model_type == "cnn":
            criterion = torch.nn.CrossEntropyLoss()
            optimizer: torch.optim.Optimizer = torch.optim.Adam(
                net.parameters(), lr=self.learning_rate or 1e-3
            )
            net.train()
            num_classes = self._get_num_classes(net)

            epoch_loss: float = 0.0
            epoch_acc: float = 0.0
            snapshot_saved = False
            cnn_snapshot_fallback: dict | None = None

            for epoch in range(epochs):
                correct, total, epoch_loss = 0, 0, 0.0

                for images, labels in trainloader:
                    should_poison, attack_configs = should_poison_this_round(
                        current_round, self.client_id, self.attacks_schedule
                    )

                    if should_poison and attack_configs:
                        original_images = images.detach().clone()
                        original_labels = labels.detach().clone()

                        for attack_config in attack_configs:
                            if is_weight_attack(attack_config.get("attack_type", "")):
                                continue
                            images, labels = apply_poisoning_attack(
                                images,
                                labels,
                                attack_config,
                                tokenizer=self.tokenizer,
                                num_classes=num_classes,
                                client_id=self.client_id,
                            )

                        if epoch == 0 and not snapshot_saved:
                            if cnn_snapshot_fallback is None:
                                cnn_snapshot_fallback = {
                                    "current_round": current_round,
                                    "attack_configs": attack_configs,
                                    "data_sample": images.detach(),
                                    "labels_sample": labels.detach(),
                                    "original_data_sample": original_images,
                                    "original_labels_sample": original_labels,
                                }

                            changed_mask = self._compute_changed_sample_mask(
                                data_sample=images,
                                labels_sample=labels,
                                original_data_sample=original_images,
                                original_labels_sample=original_labels,
                            )
                            if changed_mask.any().item():
                                self._save_attack_snapshots(
                                    current_round=current_round,
                                    attack_configs=attack_configs,
                                    data_sample=images,
                                    labels_sample=labels,
                                    original_data_sample=original_images,
                                    original_labels_sample=original_labels,
                                )
                                snapshot_saved = True

                    images, labels = (
                        images.to(self.training_device),
                        labels.to(self.training_device),
                    )
                    optimizer.zero_grad()
                    outputs = net(images)
                    loss = criterion(outputs, labels)
                    loss.backward()
                    optimizer.step()

                    epoch_loss += loss.item()
                    total += labels.size(0)
                    correct += (torch.max(outputs.data, 1)[1] == labels).sum().item()
                    del outputs, loss

                epoch_loss /= max(1, len(trainloader))
                epoch_acc = 0.0
                if total > 0:
                    epoch_acc = correct / total
                if epoch == 0 and not snapshot_saved and cnn_snapshot_fallback is not None:
                    self._save_attack_snapshots(**cnn_snapshot_fallback)
                    snapshot_saved = True
                # Free fallback dict and originals after epoch 0 — no longer needed
                if epoch == 0:
                    del cnn_snapshot_fallback
                    cnn_snapshot_fallback = None
                    gc.collect()

            return float(epoch_loss), float(epoch_acc)

        elif self.model_type == "transformer":
            optimizer = torch.optim.AdamW(net.parameters(), lr=self.learning_rate or 5e-5)
            net.train()

            epoch_loss = 0.0
            epoch_acc = 0.0
            snapshot_saved = False
            transformer_snapshot_fallback: dict | None = None

            for epoch in range(epochs):
                logging.debug(f"[Client {self.client_id}] Starting epoch {epoch + 1}/{epochs}")
                total_loss = 0
                correct, total = 0, 0

                for batch_idx, batch in enumerate(trainloader):
                    should_poison, attack_configs = should_poison_this_round(
                        current_round, self.client_id, self.attacks_schedule
                    )
                    if should_poison and attack_configs:
                        original_input_ids = batch["input_ids"].detach().clone()
                        original_labels = batch["labels"].detach().clone()

                        for attack_config in attack_configs:
                            if attack_config.get("attack_type") == "token_replacement":
                                batch["input_ids"], batch["labels"] = apply_poisoning_attack(
                                    batch["input_ids"],
                                    batch["labels"],
                                    attack_config,
                                    tokenizer=self.tokenizer,
                                    client_id=self.client_id,
                                )

                        if epoch == 0 and not snapshot_saved:
                            if transformer_snapshot_fallback is None:
                                transformer_snapshot_fallback = {
                                    "current_round": current_round,
                                    "attack_configs": attack_configs,
                                    "data_sample": batch["input_ids"].detach(),
                                    "labels_sample": batch["labels"].detach(),
                                    "original_data_sample": original_input_ids,
                                    "original_labels_sample": original_labels,
                                }

                            changed_mask = self._compute_changed_sample_mask(
                                data_sample=batch["input_ids"],
                                labels_sample=batch["labels"],
                                original_data_sample=original_input_ids,
                                original_labels_sample=original_labels,
                            )
                            if changed_mask.any().item():
                                self._save_attack_snapshots(
                                    current_round=current_round,
                                    attack_configs=attack_configs,
                                    data_sample=batch["input_ids"],
                                    labels_sample=batch["labels"],
                                    original_data_sample=original_input_ids,
                                    original_labels_sample=original_labels,
                                )
                                snapshot_saved = True

                    batch = self._to_device_only_tensors(batch)
                    labels = batch["labels"]

                    outputs = net(**batch)
                    loss = outputs.loss

                    # FedProx: add proximal term to prevent drift from global model
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
                if epoch == 0 and not snapshot_saved and transformer_snapshot_fallback is not None:
                    self._save_attack_snapshots(**transformer_snapshot_fallback)
                    snapshot_saved = True
                # Free fallback dict and originals after epoch 0 — no longer needed
                if epoch == 0:
                    del transformer_snapshot_fallback
                    transformer_snapshot_fallback = None
                    gc.collect()
                logging.debug(
                    f"[Client {self.client_id}] Epoch {epoch + 1} complete - Loss: {epoch_loss:.4f}, Accuracy: {epoch_acc:.4f}"
                )

            return float(epoch_loss), float(epoch_acc)

        else:
            raise ValueError(
                f"Unsupported model type: {self.model_type}. Supported types are 'cnn' and 'transformer'."
            )

    def test(self, net, testloader, config=None) -> tuple[float, float]:
        """Evaluate the network on the test set.

        Args:
            net: Neural network model to evaluate.
            testloader: DataLoader for test data.
            config: Optional config dict containing 'server_round' for dynamic poisoning.

        Returns:
            Tuple of (loss, accuracy).
        """
        current_round = config.get("server_round", 1) if config else 1

        if self.model_type == "cnn":
            criterion = torch.nn.CrossEntropyLoss()
            correct, total, loss = 0, 0, 0.0
            net.eval()
            num_classes = self._get_num_classes(net)

            with torch.inference_mode():
                for images, labels in testloader:
                    should_poison, attack_configs = should_poison_this_round(
                        current_round, self.client_id, self.attacks_schedule
                    )
                    if should_poison and attack_configs:
                        for attack_config in attack_configs:
                            if is_weight_attack(attack_config.get("attack_type", "")):
                                continue
                            images, labels = apply_poisoning_attack(
                                images,
                                labels,
                                attack_config,
                                tokenizer=self.tokenizer,
                                num_classes=num_classes,
                                client_id=self.client_id,
                            )

                    images, labels = (
                        images.to(self.training_device),
                        labels.to(self.training_device),
                    )
                    outputs = net(images)
                    loss += criterion(outputs, labels).item()
                    _, predicted = torch.max(outputs.data, 1)
                    total += labels.size(0)
                    correct += (predicted == labels).sum().item()
            loss /= max(1, len(testloader))
            accuracy = 0.0
            if total > 0:
                accuracy = correct / total
            return loss, accuracy

        elif self.model_type == "transformer":
            net.eval()
            total_loss: float = 0.0
            correct, total = 0, 0

            with torch.inference_mode():
                for batch in testloader:
                    should_poison, attack_configs = should_poison_this_round(
                        current_round, self.client_id, self.attacks_schedule
                    )
                    if should_poison and attack_configs:
                        for attack_config in attack_configs:
                            if attack_config.get("attack_type") == "token_replacement":
                                batch["input_ids"], batch["labels"] = apply_poisoning_attack(
                                    batch["input_ids"],
                                    batch["labels"],
                                    attack_config,
                                    tokenizer=self.tokenizer,
                                    client_id=self.client_id,
                                )

                    batch = self._to_device_only_tensors(batch)
                    labels = batch["labels"]

                    outputs = net(**batch)
                    loss = outputs.loss.item()
                    total_loss += loss

                    if hasattr(outputs, "logits"):
                        preds = torch.argmax(outputs.logits, dim=-1)
                        mask = labels != -100
                        correct += (preds[mask] == labels[mask]).sum().item()
                        total += mask.sum().item()

            loss = total_loss / max(1, len(testloader))
            accuracy = 0.0
            if total > 0:
                accuracy = correct / total
            return loss, accuracy

        else:
            raise ValueError(
                f"Unsupported model type: {self.model_type}. Supported types are 'cnn' and 'transformer'."
            )

    def fit(self, parameters, config):
        """Perform local training and return updated parameters.

        Args:
            parameters: Model parameters from the server.
            config: Flower config dict containing server_round.

        Returns:
            Tuple of (updated_parameters, num_samples, metrics_dict).
        """
        logging.debug(
            f"[Client {self.client_id}] Starting fit() - Setting parameters and beginning training"
        )
        self.set_parameters(self.net, parameters)

        # FedProx needs global params for proximal term on non-malicious transformer clients
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
            preds_after = None
            probs_after = None
            sample_labels = None

            if self.save_attack_snapshots and self.output_dir:
                params_before = [p.copy() for p in trained_parameters]

                # Capture pre-attack state for before/after visualization
                if self.model_type == "cnn":
                    sample_images, sample_labels = self._get_sample_batch_for_viz(max_samples=4)
                    if sample_images is not None:
                        preds_before, probs_before = self._get_predictions(sample_images)

            poisoned_parameters = apply_weight_poisoning(trained_parameters, weight_attack_configs)

            if self.save_attack_snapshots and self.output_dir and params_before:
                preds_after = None
                probs_after = None
                if sample_images is not None and preds_before is not None:
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

            # Clean up weight poisoning intermediate data after snapshots are saved
            # Keep poisoned_parameters since it's returned, but free other temporaries
            if params_before is not None:
                del params_before
            if sample_images is not None:
                del sample_images
            if preds_before is not None:
                del preds_before
            if probs_before is not None:
                del probs_before
            if preds_after is not None:
                del preds_after
            if probs_after is not None:
                del probs_after
            gc.collect()

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
        """Evaluate model on validation data.

        Args:
            parameters: Model parameters from the server.
            config: Flower config dict.

        Returns:
            Tuple of (loss, num_samples, metrics_dict).
        """
        self.set_parameters(self.net, parameters)
        loss, accuracy = self.test(self.net, self.valloader, config=config)

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        metrics: dict[str, Scalar] = {
            "accuracy": float(accuracy),
            "partition_id": self.client_id,
        }
        return float(loss), len(self.valloader.dataset), metrics
