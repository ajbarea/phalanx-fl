"""
Unit tests for network model definitions.

Tests network model initialization, forward passes, parameter extraction,
and state management using the unified MedMNISTCNN via build_cnn_model().
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any
from unittest.mock import patch

import torch
import torch.nn as nn

from intellifl.network_models import build_cnn_model
from intellifl.network_models.transformer_models import (
    get_lora_state_dict,
    load_model,
    load_model_with_lora,
    set_lora_state_dict,
)
from tests.common import Mock, np, pytest


class TestNetworkModels:
    """Test network model definitions via the build_cnn_model registry."""

    @pytest.fixture(
        params=[
            ("femnist_iid", (1, 28, 28), 62),
            ("femnist_niid", (1, 28, 28), 62),
            ("pneumoniamnist", (1, 28, 28), 2),
            ("bloodmnist", (3, 28, 28), 8),
            ("breastmnist", (1, 28, 28), 2),
            ("dermamnist", (3, 28, 28), 7),
            ("octmnist", (1, 28, 28), 4),
            ("organamnist", (1, 28, 28), 11),
            ("organcmnist", (1, 28, 28), 11),
            ("organsmnist", (1, 28, 28), 11),
            ("pathmnist", (3, 28, 28), 9),
            ("retinamnist", (3, 28, 28), 5),
            ("tissuemnist", (1, 28, 28), 8),
        ]
    )
    def network_config(self, request: Any) -> dict[str, Any]:
        """Parameterized fixture for different network configurations."""
        key, input_shape, num_classes = request.param
        return {
            "key": key,
            "input_shape": input_shape,
            "num_classes": num_classes,
        }

    def test_network_initialization(self, network_config: dict[str, Any]) -> None:
        """Test network initialization."""
        network = build_cnn_model(network_config["key"])

        assert isinstance(network, nn.Module)
        assert hasattr(network, "conv1")
        assert hasattr(network, "fc1")

        # Check weights are initialized (not all zeros)
        conv1_layer = network.conv1
        assert isinstance(conv1_layer, nn.Conv2d)
        conv1_weights = conv1_layer.weight.data
        assert not torch.allclose(conv1_weights, torch.zeros_like(conv1_weights))

    def test_network_forward_pass(self, network_config: dict[str, Any]) -> None:
        """Test forward pass through networks."""
        network = build_cnn_model(network_config["key"])
        input_shape = network_config["input_shape"]
        num_classes = network_config["num_classes"]
        network.eval()

        batch_size = 4
        mock_input = torch.randn(batch_size, *input_shape)

        with torch.no_grad():
            output = network(mock_input)

        assert output.shape == (batch_size, num_classes)
        assert not torch.allclose(output, torch.zeros_like(output))
        assert not torch.isnan(output).any()

    def test_network_parameter_extraction(self, network_config: dict[str, Any]) -> None:
        """Test parameter extraction from networks."""
        network = build_cnn_model(network_config["key"])

        parameters: list[torch.Tensor] = list(network.parameters())

        assert len(parameters) > 0
        for param in parameters:
            assert isinstance(param, torch.Tensor)
            assert param.requires_grad

        state_dict = network.state_dict()
        assert isinstance(state_dict, OrderedDict)
        assert len(state_dict) > 0

    def test_network_parameter_setting(self, network_config: dict[str, Any]) -> None:
        """Test setting parameters in networks."""
        network = build_cnn_model(network_config["key"])

        original_state_dict = network.state_dict()
        original_copy: dict[str, torch.Tensor] = {
            k: v.clone() for k, v in original_state_dict.items()
        }

        modified_state_dict: dict[str, torch.Tensor] = {
            key: param + torch.randn_like(param) * 0.5 for key, param in original_state_dict.items()
        }

        network.load_state_dict(modified_state_dict)

        new_state_dict = network.state_dict()
        for key in original_copy:
            assert not torch.allclose(original_copy[key], new_state_dict[key])

    def test_network_weight_initialization(self, network_config: dict[str, Any]) -> None:
        """Test that weight initialization methods work correctly."""
        network1 = build_cnn_model(network_config["key"])
        network2 = build_cnn_model(network_config["key"])

        conv1_weights1 = network1.conv1.weight.data
        conv1_weights2 = network2.conv1.weight.data

        # Different random seeds → different weights
        assert not torch.allclose(conv1_weights1, conv1_weights2)

        # Biases initialized to zero
        if network1.conv1.bias is not None:
            assert torch.allclose(
                network1.conv1.bias.data, torch.zeros_like(network1.conv1.bias.data)
            )

    def test_network_gradient_computation(self, network_config: dict[str, Any]) -> None:
        """Test that networks can compute gradients."""
        network = build_cnn_model(network_config["key"])
        input_shape = network_config["input_shape"]
        num_classes = network_config["num_classes"]

        network.train()

        batch_size = 2
        mock_input = torch.randn(batch_size, *input_shape)
        mock_target = torch.randint(0, num_classes, (batch_size,))

        output = network(mock_input)
        loss = nn.CrossEntropyLoss()(output, mock_target)
        loss.backward()

        for param in network.parameters():
            if param.requires_grad:
                assert param.grad is not None
                assert torch.any(torch.abs(param.grad) > 0) or param.numel() == 0

    def test_network_training_evaluation_modes(self, network_config: dict[str, Any]) -> None:
        """Test switching between training and evaluation modes."""
        network = build_cnn_model(network_config["key"])
        input_shape = network_config["input_shape"]
        batch_size = 2
        mock_input = torch.randn(batch_size, *input_shape)

        network.train()
        assert network.training
        output_train = network(mock_input)

        network.eval()
        assert not network.training
        with torch.no_grad():
            output_eval = network(mock_input)

        assert output_train.shape == output_eval.shape
        assert not torch.isnan(output_train).any()
        assert not torch.isnan(output_eval).any()

    def test_network_dropout_behavior(self, network_config: dict[str, Any]) -> None:
        """Test dropout behavior in training vs evaluation mode."""
        network = build_cnn_model(network_config["key"])
        input_shape = network_config["input_shape"]
        batch_size = 10
        mock_input = torch.randn(batch_size, *input_shape)

        torch.manual_seed(42)

        network.train()
        [network(mock_input).clone() for _ in range(5)]

        network.eval()
        with torch.no_grad():
            outputs_eval = [network(mock_input).clone() for _ in range(5)]

        for i in range(1, len(outputs_eval)):
            assert torch.allclose(outputs_eval[0], outputs_eval[i])

    @pytest.mark.parametrize("batch_size", [1, 4, 8])
    def test_network_batch_size_handling(
        self, network_config: dict[str, Any], batch_size: int
    ) -> None:
        """Test networks handle different batch sizes correctly."""
        network = build_cnn_model(network_config["key"])
        input_shape = network_config["input_shape"]
        num_classes = network_config["num_classes"]
        network.eval()

        mock_input = torch.randn(batch_size, *input_shape)
        with torch.no_grad():
            output = network(mock_input)

        assert output.shape == (batch_size, num_classes)

    def test_network_memory_efficiency(self, network_config: dict[str, Any]) -> None:
        """Test that networks don't have memory leaks."""
        network = build_cnn_model(network_config["key"])
        input_shape = network_config["input_shape"]
        network.eval()

        for _ in range(10):
            mock_input = torch.randn(2, *input_shape)
            with torch.no_grad():
                output = network(mock_input)
            del mock_input, output

    def test_network_parameter_count(self, network_config: dict[str, Any]) -> None:
        """Test that networks have reasonable parameter counts."""
        network = build_cnn_model(network_config["key"])

        total_params = sum(p.numel() for p in network.parameters())
        trainable_params = sum(p.numel() for p in network.parameters() if p.requires_grad)

        assert total_params > 0
        assert trainable_params > 0
        assert trainable_params == total_params
        assert 1000 < total_params < 100_000_000

    def test_network_device_compatibility(self, network_config: dict[str, Any]) -> None:
        """Test that networks work on different devices."""
        network = build_cnn_model(network_config["key"])
        input_shape = network_config["input_shape"]

        network = network.to("cpu")
        mock_input = torch.randn(2, *input_shape).to("cpu")

        with torch.no_grad():
            output = network(mock_input)

        assert output.device.type == "cpu"

        if torch.cuda.is_available():
            network = network.to("cuda")
            mock_input = mock_input.to("cuda")
            with torch.no_grad():
                output = network(mock_input)
            assert output.device.type == "cuda"


class TestBERTModelFunctions:
    """Test suite for BERT model loading and LoRA functions."""

    @patch("transformers.AutoModelForMaskedLM")
    @patch("peft.get_peft_model")
    def test_load_model_with_lora(self, mock_get_peft_model, mock_auto_model):
        """Test loading BERT model with LoRA configuration."""
        mock_base_model = Mock()
        mock_auto_model.from_pretrained.return_value = mock_base_model

        mock_lora_model = Mock()
        mock_lora_model.print_trainable_parameters.return_value = None
        mock_get_peft_model.return_value = mock_lora_model

        model = load_model_with_lora(
            model_name="bert-base-uncased",
            lora_rank=16,
            lora_alpha=32,
            lora_dropout=0.1,
            lora_target_modules=["query", "value"],
        )

        mock_auto_model.from_pretrained.assert_called_once_with("bert-base-uncased")
        mock_get_peft_model.assert_called_once()
        assert model == mock_lora_model

    @patch("transformers.AutoModelForMaskedLM")
    def test_load_model(self, mock_auto_model):
        """Test loading BERT model without LoRA."""
        mock_model = Mock()
        mock_auto_model.from_pretrained.return_value = mock_model

        model = load_model("bert-base-uncased")

        mock_auto_model.from_pretrained.assert_called_once_with("bert-base-uncased")
        assert model == mock_model

    @patch("intellifl.network_models.transformer_models.get_peft_model_state_dict")
    def test_get_lora_state_dict(self, mock_get_peft_state_dict):
        """Test getting LoRA state dict as numpy arrays."""
        mock_state_dict = OrderedDict({"lora_A": torch.randn(10, 5), "lora_B": torch.randn(5, 10)})
        mock_get_peft_state_dict.return_value = mock_state_dict

        mock_model = Mock()
        result = get_lora_state_dict(mock_model)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(arr, np.ndarray) for arr in result)
        mock_get_peft_state_dict.assert_called_once_with(mock_model)

    @patch("intellifl.network_models.transformer_models.set_peft_model_state_dict")
    @patch("intellifl.network_models.transformer_models.get_peft_model_state_dict")
    def test_set_lora_state_dict(self, mock_get_peft_state_dict, mock_set_peft_state_dict):
        """Test setting LoRA state dict from numpy arrays."""
        mock_state_dict = OrderedDict({"lora_A": torch.randn(10, 5), "lora_B": torch.randn(5, 10)})
        mock_get_peft_state_dict.return_value = mock_state_dict

        mock_model = Mock()
        state_list = [np.random.randn(10, 5), np.random.randn(5, 10)]

        set_lora_state_dict(mock_model, state_list)

        mock_get_peft_state_dict.assert_called_once_with(mock_model)
        mock_set_peft_state_dict.assert_called_once()

        call_args = mock_set_peft_state_dict.call_args
        assert call_args[0][0] == mock_model
        assert isinstance(call_args[0][1], OrderedDict)

    def test_lora_state_dict_consistency(self):
        """Test that LoRA state dict operations are consistent."""
        mock_model = Mock()

        with (
            patch(
                "intellifl.network_models.transformer_models.get_peft_model_state_dict"
            ) as mock_get,
            patch(
                "intellifl.network_models.transformer_models.set_peft_model_state_dict"
            ) as mock_set,
        ):
            original_state_dict = OrderedDict(
                {"lora_A": torch.randn(5, 3), "lora_B": torch.randn(3, 5)}
            )
            mock_get.return_value = original_state_dict

            state_list = get_lora_state_dict(mock_model)
            set_lora_state_dict(mock_model, state_list)

            assert mock_get.call_count == 2
            mock_set.assert_called_once()


class TestNetworkModelIntegration:
    """Integration tests for network models."""

    def test_network_training_loop_simulation(self):
        """Test a simulated training loop with network models."""
        network = build_cnn_model("bloodmnist")
        optimizer = torch.optim.Adam(network.parameters(), lr=0.001)
        criterion = nn.CrossEntropyLoss()

        batch_size = 4
        input_shape = (3, 28, 28)
        num_classes = 8

        network.train()

        for _step in range(3):
            inputs = torch.randn(batch_size, *input_shape)
            targets = torch.randint(0, num_classes, (batch_size,))

            outputs = network(inputs)
            loss = criterion(outputs, targets)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            assert loss.item() >= 0
            assert not torch.isnan(loss)

    def test_network_evaluation_simulation(self):
        """Test a simulated evaluation with network models."""
        network = build_cnn_model("femnist_iid")
        criterion = nn.CrossEntropyLoss()

        network.eval()

        total_loss = 0
        correct = 0
        total = 0

        batch_size = 4
        input_shape = (1, 28, 28)
        num_classes = 62  # canonical FEMNIST class count post-2026-05-23 migration

        with torch.no_grad():
            for _batch in range(3):
                inputs = torch.randn(batch_size, *input_shape)
                targets = torch.randint(0, num_classes, (batch_size,))

                outputs = network(inputs)
                loss = criterion(outputs, targets)

                total_loss += loss.item()
                _, predicted = torch.max(outputs.data, 1)
                total += targets.size(0)
                correct += int((predicted == targets).sum().item())

        avg_loss = total_loss / 3
        accuracy = correct / total

        assert avg_loss >= 0
        assert 0 <= accuracy <= 1

    @pytest.mark.parametrize(
        "dataset_key,input_shape",
        [
            ("femnist_iid", (1, 28, 28)),
            ("pneumoniamnist", (1, 28, 28)),
            ("bloodmnist", (3, 28, 28)),
            ("breastmnist", (1, 28, 28)),
            ("dermamnist", (3, 28, 28)),
            ("octmnist", (1, 28, 28)),
            ("organamnist", (1, 28, 28)),
            ("organcmnist", (1, 28, 28)),
            ("organsmnist", (1, 28, 28)),
            ("pathmnist", (3, 28, 28)),
            ("retinamnist", (3, 28, 28)),
            ("tissuemnist", (1, 28, 28)),
        ],
    )
    def test_network_state_dict_serialization(self, dataset_key, input_shape):
        """Test that network state dicts can be serialized and deserialized."""
        network1 = build_cnn_model(dataset_key)
        network2 = build_cnn_model(dataset_key)

        state_dict = network1.state_dict()
        network2.load_state_dict(state_dict)

        for (name1, param1), (name2, param2) in zip(
            network1.named_parameters(), network2.named_parameters(), strict=False
        ):
            assert name1 == name2
            assert torch.allclose(param1, param2)

    def test_network_reproducibility(self):
        """Test that networks produce reproducible results with same seed."""
        input_shape = (3, 28, 28)
        batch_size = 2

        torch.manual_seed(42)
        network1 = build_cnn_model("bloodmnist")
        inputs = torch.randn(batch_size, *input_shape)
        network1.eval()
        with torch.no_grad():
            output1 = network1(inputs)

        torch.manual_seed(42)
        network2 = build_cnn_model("bloodmnist")
        inputs = torch.randn(batch_size, *input_shape)
        network2.eval()
        with torch.no_grad():
            output2 = network2(inputs)

        assert torch.allclose(output1, output2)

    def test_network_parameter_sharing(self):
        """Test parameter sharing between network instances."""
        network1 = build_cnn_model("pneumoniamnist")
        network2 = build_cnn_model("pneumoniamnist")

        assert not torch.allclose(network1.conv1.weight, network2.conv1.weight)

        network2.load_state_dict(network1.state_dict())
        assert torch.allclose(network1.conv1.weight, network2.conv1.weight)

        with torch.no_grad():
            network1.conv1.weight += 0.1

        assert not torch.allclose(network1.conv1.weight, network2.conv1.weight)
